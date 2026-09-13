// A-class pure user-path E2E for review.html (错题复盘).
//
// Rule (2026-09-01 revision): every mistake, session and exercise below is
// created by driving the real pages (materials -> material-detail -> exercises
// -> practice -> practice-session). The test code never calls a business API to
// create or read business state; it only reads what the browser already rendered.
//
// Chain: import material -> index -> AI draft exercise + user exercise -> confirm
//        -> practice session -> wrong answers -> mistakes -> review list
//        -> detail + feedback -> redo hand-off -> mark mastered -> archive
//        -> weak points -> failure injection -> race guard -> responsive/keyboard
//        -> real restart persistence -> cross-page state restore.

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

let RUN_ROOT = 'H:/studybuddy-test/runs/review-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/review-userpath';
const ART = 'H:/studybuddy-test/artifacts/review-userpath';
const PORT = 8971;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '复盘审查材料.txt';
const AI_HINT = 'Which statement is supported';
const EX_A = '复盘审查题目A';
const EX_B = '复盘审查题目B';
const SET_TITLE = '复盘审查练习集';
const FEEDBACK = '复盘反馈：公式推导有遗漏';

const VIEWPORTS = [
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '1280x800', width: 1280, height: 800 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '540x800', width: 540, height: 800 },
  { name: '390x844', width: 390, height: 844 },
];

let server;
let materialId = '';

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

function buildFixture() {
  fs.mkdirSync(FIXTURES, { recursive: true });
  fs.writeFileSync(path.join(FIXTURES, TXT_NAME),
    '复盘审查材料：本材料介绍欧姆定律。欧姆定律指出，通过导体的电流与导体两端的电压成正比，' +
    '与导体的电阻成反比。欧姆定律是电路分析的基础公式，复盘与错题必须能追溯到本材料。\n', 'utf8');
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|private_backend_error|H:\/secret/i);
}

async function importViaUi(page, filePath) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 15000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 40000 });
}

async function openDetailViaUi(page, itemName) {
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  materialId = decodeURIComponent(page.url().split('material=')[1]);
  await expect(page.locator('#title')).toContainText(itemName, { timeout: 15000 });
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

async function indexMaterialViaUi(page) {
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#index')).toBeEnabled({ timeout: 15000 });
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 40000 });
}

async function createAndSelectSetViaUi(page, title) {
  await page.goto(`${BASE}/app/exercises.html`);
  // #set-status is VISIBLE with a loading message before the list renders, so a
  // plain visibility wait can win the race and then create a duplicate set.
  // Settle on the real load outcome instead: rows exist, or loading text is gone.
  await expect.poll(async () => {
    if (await page.locator('#sets .set-item').count() > 0) return true;
    const text = (await page.locator('#set-status').innerText()).trim();
    return text !== '' && !text.includes('正在加载');
  }, { timeout: 15000 }).toBe(true);
  const existing = page.locator('#sets .set-item', { hasText: title });
  if (await existing.count() === 0) {
    await page.fill('#new-set-title', title);
    await page.click('#set-create-form button');
    await expect(page.locator('#exercise-status')).toHaveText('练习集已创建', { timeout: 15000 });
  }
  await existing.first().click();
  await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
}

async function confirmExerciseViaUi(page, promptText) {
  await expect(page.locator('#exercises .exercise-item', { hasText: promptText })).toBeVisible({ timeout: 15000 });
  await page.locator('#exercises .exercise-item', { hasText: promptText }).click();
  await expect(page.locator('#exercise-detail')).toContainText('状态：', { timeout: 10000 });
  await page.getByRole('button', { name: '确认题目' }).last().click();
  await expect(page.locator('#exercise-status')).toHaveText('题目已确认', { timeout: 15000 });
  await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
}

async function createUserExerciseViaUi(page, prompt) {
  await createAndSelectSetViaUi(page, SET_TITLE);
  await page.locator('#new-exercise-type').selectOption('multiple_choice');
  await page.fill('#new-exercise-prompt', prompt);
  await page.fill('#new-exercise-answer', '0');
  await page.click('#exercise-create-form button');
  await expect(page.locator('#exercise-status')).toHaveText('题目已创建', { timeout: 15000 });
  await confirmExerciseViaUi(page, prompt);
}

async function generateAiExerciseViaUi(page) {
  await createAndSelectSetViaUi(page, SET_TITLE);
  await page.fill('#exercise-topic', '欧姆定律');
  await page.fill('#exercise-material-ids', materialId);
  await page.click('#exercise-generate-form button[type=submit]');
  await expect(page.locator('#exercise-status')).toHaveText('题目草稿已生成', { timeout: 40000 });
  await confirmExerciseViaUi(page, AI_HINT);
}

// Creates a session through practice.html, answers every question with the wrong
// option (both exercise kinds use answer_key 0, so index 1 is always wrong) and
// finishes it, which is what materialises the mistake cases.
async function runWrongSessionViaUi(page, prompts) {
  await page.goto(`${BASE}/app/practice.html`);
  for (const prompt of prompts) {
    const item = page.locator('#recommendations .recommendation-item', { hasText: prompt });
    await expect(item).toBeVisible({ timeout: 20000 });
    await item.locator('input').check();
  }
  await page.getByRole('button', { name: '创建练习会话' }).click();
  await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 20000 });
  const sessionId = new URL(page.url()).searchParams.get('session_id');
  await page.getByRole('button', { name: '开始练习' }).click();
  await expect(page.locator('.practice-question')).toBeVisible({ timeout: 20000 });
  for (let i = 0; i < prompts.length; i++) {
    await expect(page.locator('.practice-question h3')).toHaveText(new RegExp(`第 ${i + 1} 题 / ${prompts.length}`), { timeout: 20000 });
    await page.locator('#answer').selectOption('1');
    await page.getByRole('button', { name: '提交答案' }).click();
    if (i < prompts.length - 1) {
      await expect(page.locator('.practice-question h3')).toHaveText(`第 ${i + 2} 题 / ${prompts.length}`, { timeout: 20000 });
    } else {
      await expect(page.locator('#session-status')).toContainText('答案已提交', { timeout: 20000 });
    }
  }
  await page.getByRole('button', { name: '完成会话' }).click();
  await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 20000 });
  return sessionId;
}

async function mistakeRowByTitle(page, title) {
  const row = page.locator('#review-list article', { hasText: title });
  await expect(row).toBeVisible({ timeout: 20000 });
  return row;
}

function assertFocusStyleStr() {
  const el = document.activeElement;
  if (!el || el === document.body) return false;
  const computed = window.getComputedStyle(el);
  return (computed.outlineStyle !== 'none' && computed.outlineWidth !== '0px') || computed.boxShadow !== 'none';
}

test.describe.serial('review.html pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/review-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixture();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('RV-1 空数据根：明确空态、无残留重试按钮、归档筛选可见', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-status')).toContainText('暂无错题记录', { timeout: 20000 });
    await expect(page.locator('#review-list article')).toHaveCount(0);
    await expect(page.locator('#retry-review')).toBeHidden();
    await expect(page.locator('#weak-point-status')).toContainText('暂无薄弱点记录', { timeout: 20000 });
    await expect(page.locator('#retry-weak-points')).toBeHidden();
    await expect(page.locator('#show-archived')).toHaveCount(1);
    await assertNoSensitiveVisibleText(page);
  });

  test('RV-2 纯 UI 建链造错题：列表显示真实题面与状态标签', async ({ page }) => {
    await importViaUi(page, path.join(FIXTURES, TXT_NAME));
    await openDetailViaUi(page, TXT_NAME);
    await indexMaterialViaUi(page);
    await generateAiExerciseViaUi(page);
    await createUserExerciseViaUi(page, EX_A);
    await runWrongSessionViaUi(page, [AI_HINT, EX_A]);

    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list article')).toHaveCount(2, { timeout: 20000 });
    await expect(page.locator('#review-list')).toContainText(AI_HINT);
    await expect(page.locator('#review-list')).toContainText(EX_A);
    await expect(page.locator('#review-list')).toContainText('状态：待处理');
    await assertNoSensitiveVisibleText(page);
  });

  test('RV-3 错题详情：题面/状态/反馈记录/来源链接 + 新增反馈立即可见', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const row = await mistakeRowByTitle(page, AI_HINT);
    await row.getByRole('button', { name: '查看详情' }).click();
    const detail = row.locator('.mistake-detail');
    await expect(detail).toContainText('题面：', { timeout: 20000 });
    await expect(detail).toContainText(AI_HINT);
    await expect(detail).toContainText('状态：待处理');
    await expect(detail).toContainText('反馈记录');
    const link = detail.getByRole('link', { name: '查看来源材料' });
    await expect(link).toBeVisible();
    expect(await link.getAttribute('href')).toContain('/app/material-detail.html?material=');

    await detail.getByLabel('复盘反馈').fill(FEEDBACK);
    await detail.getByRole('button', { name: '保存反馈' }).click();
    await expect(page.locator('#review-status')).toContainText('复盘反馈已保存', { timeout: 20000 });
    await expect(row.locator('.mistake-detail')).toContainText(FEEDBACK, { timeout: 20000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('RV-4 再次练习：创建新会话并跳转 practice-session 带入正确题目', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const row = await mistakeRowByTitle(page, EX_A);
    await row.getByRole('button', { name: '再次练习' }).click();
    await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 20000 });
    await expect(page.locator('#session-detail')).toBeVisible({ timeout: 20000 });
    await page.getByRole('button', { name: '开始练习' }).click();
    await expect(page.locator('.practice-question')).toContainText(EX_A, { timeout: 20000 });
  });

  test('RV-5 标记已掌握：状态更新且刷新后持久化', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const row = await mistakeRowByTitle(page, EX_A);
    await row.getByRole('button', { name: '查看详情' }).click();
    await row.locator('.mistake-detail').getByRole('button', { name: '标记已掌握' }).click();
    await expect(page.locator('#review-status')).toContainText('已标记为已掌握', { timeout: 20000 });
    await expect(page.locator('#review-list article', { hasText: EX_A })).toContainText('状态：已修正', { timeout: 20000 });

    await page.reload();
    await expect(page.locator('#review-list article', { hasText: EX_A })).toContainText('状态：已修正', { timeout: 20000 });
  });

  test('RV-6 归档错题：默认从列表移除，刷新后仍隐藏，显式筛选才可见', async ({ page }) => {
    await createUserExerciseViaUi(page, EX_B);
    await runWrongSessionViaUi(page, [EX_B]);

    await page.goto(`${BASE}/app/review.html`);
    const row = await mistakeRowByTitle(page, EX_B);
    await row.getByRole('button', { name: '归档' }).click();
    await expect(page.locator('#review-status')).toContainText('错题已归档', { timeout: 20000 });
    await expect(page.locator('#review-list article', { hasText: EX_B })).toHaveCount(0, { timeout: 15000 });
    await expect(page.locator('#review-list [data-review-hint]')).toContainText('已归档 1 条', { timeout: 15000 });

    await page.reload();
    await expect(page.locator('#review-list article', { hasText: EX_B })).toHaveCount(0, { timeout: 20000 });

    await page.locator('#show-archived').check();
    await expect(page.locator('#review-list article', { hasText: EX_B })).toHaveCount(1, { timeout: 15000 });
    await expect(page.locator('#review-list article', { hasText: EX_B })).toContainText('状态：已归档');
  });

  test('RV-7 薄弱点汇总：真实聚合已解决与未解决错题，归档错题不计入', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#weak-points .item-card')).toHaveCount(2, { timeout: 20000 });
    await expect(page.locator('#weak-points')).toContainText('出现 1 次');
    await expect(page.locator('#weak-points')).toContainText('未解决 1');
    await expect(page.locator('#weak-points')).toContainText('已修复 1');
    await assertNoSensitiveVisibleText(page);
  });

  test('RV-8 列表失败注入：安全文案 + #retry-review 真实恢复', async ({ page }) => {
    await page.route(`${BASE}/api/study/mistakes?*`, route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback', path: 'H:/secret' }),
    }));
    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-status')).toContainText('请求失败，请重试', { timeout: 20000 });
    await expect(page.locator('#retry-review')).toBeVisible();
    await assertNoSensitiveVisibleText(page);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-review').click();
    await expect(page.locator('#review-list article')).toHaveCount(2, { timeout: 20000 });
    await expect(page.locator('#retry-review')).toBeHidden();
  });

  test('RV-9 详情失败：独立重试控件真实恢复', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const probe = await mistakeRowByTitle(page, EX_A);
    const mistakeId = await probe.getAttribute('data-mistake-id');
    await page.route(`${BASE}/api/study/mistakes/${mistakeId}`, route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback', path: 'H:/secret' }),
    }));
    await page.goto(`${BASE}/app/review.html`);

    const row = await mistakeRowByTitle(page, EX_A);
    await row.getByRole('button', { name: '查看详情' }).click();
    await expect(row.locator('.mistake-detail')).toContainText('请求失败，请重试', { timeout: 20000 });
    await expect(row.locator('.retry-detail')).toBeVisible();
    await assertNoSensitiveVisibleText(page);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await row.locator('.retry-detail').click();
    await expect(row.locator('.mistake-detail')).toContainText('题面：', { timeout: 20000 });
    await expect(row.locator('.mistake-detail')).toContainText(EX_A, { timeout: 20000 });
  });

  test('RV-10 快速切换错题竞态：迟到旧详情不得覆盖新选择', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const probeAi = await mistakeRowByTitle(page, AI_HINT);
    const slowId = await probeAi.getAttribute('data-mistake-id');
    await page.route(`${BASE}/api/study/mistakes/${slowId}`, async route => {
      await new Promise(resolve => setTimeout(resolve, 900));
      return route.continue();
    });
    await page.goto(`${BASE}/app/review.html`);

    const rowAi = await mistakeRowByTitle(page, AI_HINT);
    const rowA = await mistakeRowByTitle(page, EX_A);
    await rowAi.getByRole('button', { name: '查看详情' }).click();
    await rowA.getByRole('button', { name: '查看详情' }).click();

    await expect(rowA.locator('.mistake-detail')).toContainText(EX_A, { timeout: 20000 });
    await page.waitForTimeout(1400);
    await expect(page.locator('#review-list .mistake-detail')).toHaveCount(1);
    await expect(rowA.locator('.mistake-detail')).toContainText(EX_A);
    await expect(rowAi.locator('.mistake-detail')).toHaveCount(0);
  });

  test('RV-11 五档响应式 + 键盘 Enter + 真服务重启持久化', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list article').first()).toBeVisible({ timeout: 20000 });

    // Keyboard: Enter activates the focused detail button; focus style is visible.
    const detailButton = page.locator('#review-list button', { hasText: '查看详情' }).first();
    await detailButton.focus();
    expect(await page.evaluate(assertFocusStyleStr)).toBe(true);
    await page.keyboard.press('Enter');
    await expect(page.locator('#review-list .mistake-detail').first()).toContainText('题面：', { timeout: 20000 });

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      await page.screenshot({ path: path.join(ART, `review-${vp.name}.png`), fullPage: true });
    }

    // Real restart: the archived/fixed/weak-point state must survive.
    await stopServer();
    server = startServer();
    await ready();

    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list article', { hasText: EX_A })).toContainText('状态：已修正', { timeout: 25000 });
    await expect(page.locator('#review-list article', { hasText: AI_HINT })).toBeVisible({ timeout: 25000 });
    await expect(page.locator('#review-list article', { hasText: EX_B })).toHaveCount(0);
    await expect(page.locator('#weak-points .item-card')).toHaveCount(2, { timeout: 25000 });

    const aiRow = await mistakeRowByTitle(page, AI_HINT);
    await aiRow.getByRole('button', { name: '查看详情' }).click();
    await expect(aiRow.locator('.mistake-detail')).toContainText(FEEDBACK, { timeout: 20000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('RV-12 跨页导航返回：筛选与选中错题状态保持', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const rowA = await mistakeRowByTitle(page, EX_A);
    const mistakeId = await rowA.getAttribute('data-mistake-id');

    // Direct URL load must open the requested mistake.
    await page.goto(`${BASE}/app/review.html?mistake_id=${encodeURIComponent(mistakeId)}`);
    await expect(rowA.locator('.mistake-detail')).toContainText(EX_A, { timeout: 20000 });

    await page.locator('#show-archived').check();
    await expect(page.locator('#review-list article')).toHaveCount(3, { timeout: 15000 });

    await page.locator('[data-nav] a', { hasText: '资料' }).click();
    await page.waitForURL(/materials\.html/);
    await page.locator('[data-nav] a', { hasText: '复盘' }).click();
    await page.waitForURL(/review\.html/);

    await expect(page.locator('#show-archived')).toBeChecked({ timeout: 20000 });
    await expect(page.locator('#review-list article')).toHaveCount(3, { timeout: 20000 });
    await expect(rowA.locator('.mistake-detail')).toContainText(EX_A, { timeout: 20000 });
    await assertNoSensitiveVisibleText(page);
  });
});
