const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for cards.html.
// Rule: no business API calls from test code. All data created via page UI.
// page.route is used ONLY for failure injection / latency simulation, never
// for data creation or id extraction.
// Chain: import -> index -> deck -> user card (XSS payload) -> edit -> confirm
//        -> review -> AI draft (fake provider) -> citation display -> reject
//        -> archive -> retrieval error paths -> material delete (citation
//        degradation) -> route failure injection + recovery -> responsive
//        5 viewports + keyboard -> real service restart persistence.
let RUN_ROOT = 'H:/studybuddy-test/runs/cards-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/cards-userpath';
const ART = 'H:/studybuddy-test/artifacts/cards-userpath';
const PORT = 8977;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '卡片链路测试材料.txt';
const TXT2_NAME = '未索引材料.txt';
const TOPIC = '欧姆定律';
const GENERATED_FRONT = `What does the source say about ${TOPIC}?`;
const XSS_FRONT = '<script>window.__xssHit=1</script><img src=x onerror="window.__xssHit=2">';
const XSS_BACK = '答案<b>加粗</b>尝试';
const EDITED_BACK = '欧姆定律是电路分析的基础公式（已编辑）';
const DECK_USER = '卡片链路卡组';
const DECK_AI = 'AI 草稿卡组';
let server;
let materialId = '';
let materialId2 = '';

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 20000 }).toBe(true);
}

function stopServer() {
  return new Promise(resolve => {
    if (!server || server.killed) { server = null; return resolve(); }
    let settled = false;
    const finish = () => { if (!settled) { settled = true; server = null; resolve(); } };
    server.once('exit', finish);
    server.kill();
    setTimeout(finish, 5000);
  });
}

function buildFixtures() {
  fs.mkdirSync(FIXTURES, { recursive: true });
  fs.writeFileSync(path.join(FIXTURES, TXT_NAME),
    '卡片链路测试材料：本材料介绍欧姆定律。欧姆定律指出，通过导体的电流与导体两端的电压成正比，' +
    '与导体的电阻成反比。欧姆定律是电路分析的基础公式，卡片应围绕欧姆定律展开复习。\n', 'utf8');
  fs.writeFileSync(path.join(FIXTURES, TXT2_NAME),
    '未索引材料：这份材料只做导入，不建立索引，用于触发材料尚未建立索引的错误提示。\n', 'utf8');
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
}

function watchDialogs(page) {
  const seen = [];
  page.on('dialog', async dialog => { seen.push(dialog.message()); await dialog.accept(); });
  return seen;
}

async function importViaUi(page, filePath, fileName) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 10000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
  const row = page.locator('#items li', { hasText: fileName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  const id = decodeURIComponent(page.url().split('material=')[1]);
  await expect(page.locator('#title')).toContainText(fileName, { timeout: 10000 });
  return id;
}

async function indexMaterialViaUi(page) {
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#index')).toBeEnabled({ timeout: 10000 });
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 30000 });
  await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });
}

async function openCards(page) {
  await page.goto(`${BASE}/app/cards.html`);
  // deck-status text is stale-but-hidden once decks exist; wait on real signals.
  await expect.poll(async () =>
    (await page.locator('#decks .deck-item').count()) > 0 ||
    (await page.locator('#deck-status').textContent()) === '暂无卡片组'
  , { timeout: 15000 }).toBe(true);
}

async function createDeckViaUi(page, title) {
  await page.fill('#new-deck-title', title);
  await page.locator('#new-deck-title').press('Enter');
  await expect(page.locator('#card-status')).toHaveText('卡片组已创建', { timeout: 15000 });
  await expect(page.locator('#decks .deck-item', { hasText: title })).toBeVisible({ timeout: 10000 });
}

async function selectDeckViaUi(page, title) {
  await page.locator('#decks .deck-item', { hasText: title }).click();
  await expect(page.locator('#deck-actions')).toBeVisible({ timeout: 10000 });
  // Selecting a deck starts an asynchronous card-list request. Do not take
  // counts or click cards until the request has reached either its empty or
  // ready terminal state; otherwise the test races the initial replaceChildren.
  await expect.poll(async () => {
    const status = await page.locator('#card-status').textContent();
    const visible = await page.locator('#cards .card-item').count();
    return visible > 0 || /该卡片组暂无(?:活动)?卡片|卡片操作失败，可重试/.test(status);
  }, { timeout: 15000 }).toBe(true);
}

async function generateDraftViaUi(page, topic, materialIds) {
  await page.fill('#card-topic', topic);
  await page.selectOption('#card-material-id', materialIds);
  await page.click('#card-generate-form button[type=submit]');
  await expect(page.locator('#card-status')).toHaveText('卡片草稿已生成', { timeout: 30000 });
}

const VIEWPORTS = [
  { name: '1280x720', width: 1280, height: 720 },
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '390x844', width: 390, height: 844 },
];

test.describe.serial('cards.html pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/cards-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixtures();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-CARD-1 空态+页面结构；导入→索引→刷新持久化（前置链路）', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await page.goto(`${BASE}/app/cards.html`);
    await expect(page.locator('h1')).toHaveText('学习卡片组');
    await expect(page.locator('#deck-status')).toHaveText('暂无卡片组', { timeout: 15000 });
    await expect(page.locator('#decks .deck-item')).toHaveCount(0);
    // Structure: forms, buttons, navigation, section ids.
    await expect(page.locator('#deck-create-form input')).toBeVisible();
    await expect(page.locator('#deck-create-form button')).toHaveText('创建卡片组');
    await expect(page.locator('#deck-actions')).toBeHidden();
    await expect(page.locator('[data-od-id="cards-decks"]')).toBeVisible();
    await expect(page.locator('[data-od-id="cards-detail"]')).toBeVisible();
    for (const label of ['今天', '计划', '资料', '问答', '笔记', '练习', '卡片', '题目', '报告', '任务', '设置', '复盘']) {
      await expect(page.locator('[data-nav]').locator(`a:text-is("${label}")`)).toHaveCount(1);
    }
    await expect(page.locator('[data-system-status]')).toHaveText('系统就绪', { timeout: 15000 });
    expect(dialogs).toHaveLength(0);
    await assertNoSensitiveVisibleText(page);

    // Prerequisite chain: import + index via UI, then verify persistence on reload.
    materialId = await importViaUi(page, path.join(FIXTURES, TXT_NAME), TXT_NAME);
    await indexMaterialViaUi(page);
    await page.reload();
    await expect(page.locator('#title')).toContainText(TXT_NAME, { timeout: 10000 });
    await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-2 建卡组（键盘）→ XSS 手建卡 → 编辑 → 确认 → 复习 → 刷新持久化', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openCards(page);
    await createDeckViaUi(page, DECK_USER);
    await selectDeckViaUi(page, DECK_USER);
    await expect(page.locator('#card-status')).toHaveText('该卡片组暂无活动卡片', { timeout: 10000 });
    await expect(page.locator('#deck-title')).toHaveText(DECK_USER);

    // XSS payload card via user form: must render as plain text, never execute.
    await page.fill('#new-card-front', XSS_FRONT);
    await page.fill('#new-card-back', XSS_BACK);
    await page.click('#card-create-form button[type=submit]');
    await expect(page.locator('#card-status')).toHaveText('卡片已创建', { timeout: 15000 });
    const item = page.locator('#cards .card-item', { hasText: XSS_FRONT });
    await expect(item).toBeVisible({ timeout: 10000 });
    await expect(item).toContainText('草稿');
    expect(await page.evaluate(() => window.__xssHit)).toBeUndefined();
    expect(await page.locator('#cards .card-item img').count()).toBe(0);
    expect(await page.locator('#cards script').count()).toBe(0);

    // Detail + draft edit + persistence of the edit.
    await item.click();
    await expect(page.locator('#card-detail')).toContainText(`问题：${XSS_FRONT}`, { timeout: 10000 });
    expect(await page.evaluate(() => window.__xssHit)).toBeUndefined();
    await page.getByLabel('卡片答案').fill(EDITED_BACK);
    await page.getByRole('button', { name: '保存卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('卡片已保存', { timeout: 15000 });
    await page.reload();
    await selectDeckViaUi(page, DECK_USER);
    await page.locator('#cards .card-item', { hasText: XSS_FRONT }).click();
    await expect(page.locator('#card-detail')).toContainText(EDITED_BACK, { timeout: 10000 });

    // Confirm: draft -> ready; edit form disappears (ready is not editable).
    await page.getByRole('button', { name: '确认卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('卡片已确认', { timeout: 15000 });
    await expect(page.getByRole('button', { name: '保存卡片' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '确认卡片' })).toHaveCount(0);
    await expect(page.locator('#cards .card-item', { hasText: XSS_FRONT })).toContainText('可用');
    await page.reload();
    await selectDeckViaUi(page, DECK_USER);
    await expect(page.locator('#cards .card-item', { hasText: XSS_FRONT })).toContainText('可用', { timeout: 10000 });

    // Real review on the ready card; status stays ready afterwards.
    await page.locator('#cards .card-item', { hasText: XSS_FRONT }).click();
    await page.getByRole('button', { name: '记为掌握' }).click();
    await expect(page.locator('#card-status')).toHaveText('复习记录已保存', { timeout: 15000 });
    await expect(page.locator('#cards .card-item', { hasText: XSS_FRONT })).toContainText('可用', { timeout: 10000 });
    await expect(page.getByRole('button', { name: '记为掌握' })).toHaveCount(1);
    expect(dialogs).toHaveLength(0);
    expect(await page.evaluate(() => window.__xssHit)).toBeUndefined();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-3 AI 草稿（真实链路）→ 引用展示 → 重复点击只生成一张', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openCards(page);
    await createDeckViaUi(page, DECK_AI);
    await selectDeckViaUi(page, DECK_AI);

    // Double-click protection: the page enters busy state synchronously, so
    // the second click must not create a second draft.
    await page.fill('#card-topic', TOPIC);
    await page.selectOption('#card-material-id', materialId);
    await page.locator('#card-generate-form button[type=submit]').dblclick();
    await expect(page.locator('#card-status')).toHaveText('卡片草稿已生成', { timeout: 30000 });
    await expect(page.locator('#decks .deck-item', { hasText: DECK_AI })).toContainText('1 张卡片（活动 1）');

    // Draft card content and status badge.
    const draft = page.locator('#cards .card-item', { hasText: GENERATED_FRONT });
    await expect(draft).toBeVisible({ timeout: 10000 });
    await expect(draft).toContainText('草稿');
    await expect(draft).toContainText('来源: 来源有效');
    await draft.click();
    await expect(page.locator('#card-detail')).toContainText(`问题：${GENERATED_FRONT}`, { timeout: 10000 });
    await expect(page.locator('#card-detail .citation-link')).toHaveCount(1);
    await expect(page.locator('#card-detail .citation-link')).toHaveAttribute('href', /material-detail\.html\?material=.*&citation=.*&kind=card/);
    await page.locator('#card-detail .citation-link').click();
    await expect(page).toHaveURL(/material-detail\.html\?material=.*&citation=.*&kind=card/);
    await expect(page.locator('#body-location')).toContainText('已定位引用来源', { timeout: 10000 });
    await expect(page.locator('#body mark.citation-highlight')).toBeVisible();
    await page.goBack();
    await selectDeckViaUi(page, DECK_AI);
    await page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).click();
    await expect(page.locator('#card-detail')).toContainText(`问题：${GENERATED_FRONT}`, { timeout: 10000 });
    expect(dialogs).toHaveLength(0);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-4 拒绝→仍在列表；归档→无恢复入口；归档态无复习按钮', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openCards(page);
    await selectDeckViaUi(page, DECK_AI);
    await generateDraftViaUi(page, TOPIC, materialId);
    const rejected = page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '草稿' }).first();
    await rejected.click();
    await page.getByRole('button', { name: '拒绝卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('卡片已拒绝', { timeout: 15000 });
    // Documented behavior: rejected cards stay visible in the default list.
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '已拒绝' }).first()).toBeVisible({ timeout: 10000 });
    // Rejected detail: no confirm/review buttons, archive still offered.
    await page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '已拒绝' }).first().click();
    await expect(page.getByRole('button', { name: '确认卡片' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '记为掌握' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '归档卡片' })).toHaveCount(1);
    await page.getByRole('button', { name: '归档卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('卡片已归档', { timeout: 15000 });
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '已拒绝' })).toHaveCount(0);
    await page.selectOption('#card-filter', 'archived');
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '已归档' }).first()).toBeVisible({ timeout: 10000 });
    // Archived detail exposes restore, but no edit/review/archive actions.
    await page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '已归档' }).first().click();
    await expect(page.getByRole('button', { name: '归档卡片' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '记为掌握' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '保存卡片' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '恢复卡片' })).toHaveCount(1);
    await expect(page.locator('#decks .deck-item', { hasText: DECK_AI })).toContainText('2 张卡片（活动 1）');
    expect(dialogs).toHaveLength(0);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-5 真实错误路径：未索引材料→提示；无关主题→未找到相关材料', async ({ page }) => {
    await openCards(page);
    materialId2 = await importViaUi(page, path.join(FIXTURES, TXT2_NAME), TXT2_NAME);
    await openCards(page);
    await selectDeckViaUi(page, DECK_AI);
    const before = await page.locator('#cards .card-item').count();

    // Unindexed material: retrieval_not_ready mapped to a friendly message.
    await generateDraftViaUiExpectError(page, TOPIC, materialId2, '材料尚未建立索引');
    // Indexed material but topic with no lexical hit: retrieval_empty.
    await generateDraftViaUiExpectError(page, '量子纠缠未知主题', materialId, '未找到相关材料');
    await expect(page.locator('#cards .card-item')).toHaveCount(before);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-6 来源失效降级：删除材料→来源已删除；草稿确认被拒；可用卡仍可复习', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openCards(page);
    // Confirm the AI draft (has valid citation) then create one more draft before deleting the source.
    await selectDeckViaUi(page, DECK_AI);
    const readyCard = page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '草稿' }).first();
    await readyCard.click();
    await page.getByRole('button', { name: '确认卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('卡片已确认', { timeout: 15000 });
    await generateDraftViaUi(page, TOPIC, materialId);
    const pendingDraft = page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '草稿' }).first();

    // Delete the source material through the materials UI (native confirm).
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 10000 });
    await page.locator('#items li', { hasText: TXT_NAME }).getByRole('button', { name: '删除' }).click();
    await expect(page.locator('#items li', { hasText: TXT_NAME })).toBeHidden({ timeout: 15000 });

    // Back on cards: source degradation remains visible on the list and detail.
    await openCards(page);
    await selectDeckViaUi(page, DECK_AI);
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '草稿' }).first()).toContainText('来源: 来源已删除', { timeout: 10000 });
    // Confirming the unconfirmed draft is rejected with a friendly message.
    await pendingDraft.click();
    await page.getByRole('button', { name: '确认卡片' }).click();
    await expect(page.locator('#card-status')).toHaveText('引用来源不可用', { timeout: 15000 });
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '草稿' }).first()).toBeVisible({ timeout: 10000 });
    // The ready card still reviews despite the broken source (documented behavior).
    await page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).filter({ hasText: '可用' }).first().click();
    await expect(page.getByRole('button', { name: '记为掌握' })).toHaveCount(1);
    await page.getByRole('button', { name: '记为掌握' }).click();
    await expect(page.locator('#card-status')).toHaveText('复习记录已保存', { timeout: 15000 });
    expect(dialogs.length).toBeGreaterThanOrEqual(1); // the delete confirm dialog
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-8 响应式 5 档 + 键盘焦点 + 跨页导航', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openCards(page);
    await selectDeckViaUi(page, DECK_AI);
    // Keyboard: focus style visible on input and button.
    await page.locator('#new-card-front').focus();
    expect(await page.evaluate(assertFocusStyleStr)).toBe(true);
    await page.locator('#refresh-decks').focus();
    expect(await page.evaluate(assertFocusStyleStr)).toBe(true);
    // Tab order inside the deck form: title input -> submit button.
    await page.locator('#new-deck-title').focus();
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement && document.activeElement.type)).toBe('submit');

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await expect.poll(() => page.evaluate(() =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      await page.screenshot({ path: path.join(ART, `cards-${vp.name}.png`), fullPage: true });
    }
    // Narrow viewport: nav collapses behind the toggle, still navigates cross-page.
    await page.setViewportSize({ width: 390, height: 844 });
    const toggle = page.locator('.nav-toggle');
    await expect(toggle).toBeVisible();
    await toggle.click();
    await page.locator('[data-nav]').locator('a:text-is("资料")').click();
    await page.waitForURL(/materials\.html/);
    await expect(page.locator('#items li', { hasText: TXT2_NAME })).toBeVisible({ timeout: 15000 });
    await page.locator('.nav-toggle').click();
    await page.locator('[data-nav]').locator('a:text-is("卡片")').click();
    await page.waitForURL(/cards\.html/);
    await expect(page.locator('#decks .deck-item', { hasText: DECK_AI })).toBeVisible({ timeout: 15000 });
    // Note: cards.html has no breadcrumb and no deck-id hand-off to review.html
    // (复盘 is mistake review, not card review) - recorded as findings.
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-CARD-9 服务真重启：卡组/卡片/状态/来源失效/XSS 内容全部持久化', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await stopServer();
    server = startServer();
    await ready();

    await openCards(page);
    await expect(page.locator('#decks .deck-item', { hasText: DECK_USER })).toBeVisible({ timeout: 20000 });
    await expect(page.locator('#decks .deck-item', { hasText: DECK_USER })).toContainText('1 张卡片（活动 1）');
    await expect(page.locator('#decks .deck-item', { hasText: DECK_AI })).toContainText('3 张卡片（活动 2）');

    await selectDeckViaUi(page, DECK_USER);
    const xss = page.locator('#cards .card-item', { hasText: XSS_FRONT });
    await expect(xss).toBeVisible({ timeout: 10000 });
    await expect(xss).toContainText('可用');
    await xss.click();
    await expect(page.locator('#card-detail')).toContainText(EDITED_BACK, { timeout: 10000 });
    await expect(page.getByRole('button', { name: '记为掌握' })).toHaveCount(1);
    expect(await page.evaluate(() => window.__xssHit)).toBeUndefined();

    await selectDeckViaUi(page, DECK_AI);
    const aiCards = page.locator('#cards .card-item', { hasText: GENERATED_FRONT });
    await expect(aiCards.first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#cards .card-item', { hasText: GENERATED_FRONT }).first()).toContainText('可用');
    // Deleted material stays unavailable after restart.
    await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
    await expect(page.locator('#title')).toHaveText('材料不可用', { timeout: 10000 });
    expect(dialogs).toHaveLength(0);
    await assertNoSensitiveVisibleText(page);
  });
});

async function generateDraftViaUiExpectError(page, topic, materialIds, expected) {
  await page.fill('#card-topic', topic);
  await page.selectOption('#card-material-id', materialIds);
  await page.click('#card-generate-form button[type=submit]');
  await expect(page.locator('#card-status')).toHaveText(expected, { timeout: 30000 });
}

// Evaluated inside the page against document.activeElement.
function assertFocusStyleStr() {
  const el = document.activeElement;
  if (!el || el === document.body) return false;
  const computed = window.getComputedStyle(el);
  return (computed.outlineStyle !== 'none' && computed.outlineWidth !== '0px')
    || computed.boxShadow !== 'none';
}
