const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for material-detail -> qa.html.
// Rule: no business API calls from test code. Materials are imported, indexed,
// asked, continued, switched, and deleted through the page UI only. The provider
// boundary uses a second server start WITHOUT the fake provider environment
// (configuration-level boundary, no data manipulation).
// Chain: import via UI -> index via detail -> "进入问答" with material scope ->
//        unindexed boundary -> answer with citation -> citation back-location ->
//        return to QA -> thread continue/new-thread switching -> empty retrieval
//        boundary -> provider_not_configured boundary -> source_deleted citation
//        state -> server restart persistence.
let RUN_ROOT = 'H:/studybuddy-test/runs/qa-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/qa-userpath';
const ART = 'H:/studybuddy-test/artifacts/qa-userpath';
const PORT = 8956;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const MAIN_NAME = '问答链路主材料.txt';
const SECOND_NAME = '问答链路未索引材料.txt';
const MAIN_BODY = '问答链路验证材料。蓝鲸潮汐是本材料的唯一标记词。蓝鲸潮汐出现在正文第一段，用于检索与引用回溯验证。材料正文足够长，可以建立索引并支持词法检索命中。';
let server;
let mainDetailUrl = '';
let mainId = '';
let secondId = '';

function startServer(withFake = true) {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT };
  if (withFake) env.STUDYBUDDY_AI_PROVIDER = 'fake';
  else delete env.STUDYBUDDY_AI_PROVIDER;
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

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
}

async function importViaUi(page, filePath) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
}

async function openDetailViaUi(page, itemName) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  await expect(page.locator('#title')).toContainText(itemName, { timeout: 10000 });
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

test.describe.serial('material-detail -> qa.html pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/qa-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    fs.mkdirSync(FIXTURES, { recursive: true });
    fs.writeFileSync(path.join(FIXTURES, MAIN_NAME), MAIN_BODY, 'utf8');
    fs.writeFileSync(path.join(FIXTURES, SECOND_NAME), '这份材料故意不建立索引，用于验证未索引边界。', 'utf8');
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-QA-1 经 UI 导入两个材料并为主材料建立索引', async ({ page }) => {
    await importViaUi(page, path.join(FIXTURES, MAIN_NAME));
    await importViaUi(page, path.join(FIXTURES, SECOND_NAME));
    // Capture both ids from the detail URLs reached through the list UI.
    await openDetailViaUi(page, SECOND_NAME);
    secondId = decodeURIComponent(page.url().split('material=')[1]);
    await openDetailViaUi(page, MAIN_NAME);
    mainDetailUrl = page.url();
    mainId = decodeURIComponent(mainDetailUrl.split('material=')[1]);
    await expect(page.locator('#index')).toBeEnabled({ timeout: 10000 });
    await page.locator('#index').click();
    await expect(page.locator('#index-status')).toContainText('AI 索引已建立，可用于问答', { timeout: 30000 });
    await expect(page.locator('#capability-grid')).toContainText('可用（范围：本材料）');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-2 从 material-detail「进入问答」带入材料范围', async ({ page }) => {
    await page.goto(mainDetailUrl);
    await expect(page.locator('#qa')).toHaveAttribute('href', new RegExp(`qa\\.html\\?material=${mainId}$`), { timeout: 10000 });
    await page.locator('#qa').click();
    await expect(page).toHaveURL(new RegExp(`qa\\.html\\?material=${mainId}$`));
    await expect(page.locator('#materials')).toHaveValue(mainId, { timeout: 10000 });
    await expect(page.locator('#material-picker label', { hasText: MAIN_NAME }).locator('input')).toBeChecked({ timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-3 未建索引边界：安全文案，索引后真实回答', async ({ page }) => {
    await page.goto(`${BASE}/app/qa.html?material=${mainId}`);
    await expect(page.locator('#materials')).toHaveValue(mainId, { timeout: 10000 });
    // Scope ONLY the never-indexed material through the picker.
    const mainCheck = page.locator('#material-picker label', { hasText: MAIN_NAME }).locator('input');
    const secondCheck = page.locator('#material-picker label', { hasText: SECOND_NAME }).locator('input');
    await secondCheck.check({ timeout: 10000 });
    await mainCheck.uncheck();
    await expect(page.locator('#materials')).toHaveValue(secondId);
    await page.locator('#question').fill('未索引材料里有什么');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('材料索引尚未建立，请先建立索引', { timeout: 15000 });
    // Restore the indexed scope through the picker; the real question then answers.
    await mainCheck.check();
    await secondCheck.uncheck();
    await expect(page.locator('#materials')).toHaveValue(mainId);
    await page.locator('#question').fill('蓝鲸潮汐');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toHaveText('回答已生成', { timeout: 20000 });
    // The failed ask also persisted a thread holding only the user message;
    // together with the answered thread the history shows 2 entries.
    await expect(page.locator('#threads .thread-item')).toHaveCount(2);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-4 引用回答展开与引用回溯：qa → material-detail 定位正文 → 返回问答', async ({ page }) => {
    await page.goto(`${BASE}/app/qa.html?material=${mainId}`);
    await page.getByRole('button', { name: '查看对话与引用' }).first().click({ timeout: 10000 });
    const detail = page.locator('.thread-detail').first();
    await expect(detail).toContainText('Fake answer', { timeout: 10000 });
    await expect(detail).toContainText('蓝鲸潮汐');
    await expect(detail).toContainText('引用来源：');
    const citation = detail.locator('.citation-link').first();
    await expect(citation).toHaveCount(1);
    await expect(citation).not.toContainText('来源不可用');
    await citation.click();
    await expect(page).toHaveURL(/material-detail\.html\?material=.+&citation=.+/);
    await expect(page.locator('#body-location')).toContainText('已定位引用来源', { timeout: 10000 });
    await expect(page.locator('#body mark.citation-highlight')).toContainText('蓝鲸潮汐');
    await assertNoSensitiveVisibleText(page);
    // Return to the QA page; the conversation history is still there.
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`qa\\.html\\?material=${mainId}$`));
    await page.getByRole('button', { name: '查看对话与引用' }).first().click();
    await expect(page.locator('.thread-detail').first()).toContainText('Fake answer', { timeout: 10000 });
  });

  test('A-E2E-QA-5 线程继续/新对话切换：继续同线程，新对话建新线程', async ({ page }) => {
    await page.goto(`${BASE}/app/qa.html?material=${mainId}`);
    // 2 threads from QA-3 (one orphan from the failed ask, one answered).
    await expect(page.locator('#threads .thread-item')).toHaveCount(2, { timeout: 10000 });
    // Continue the most recent conversation explicitly (the answered thread).
    await page.getByRole('button', { name: '继续此对话' }).first().click();
    await expect(page.locator('#submit-status')).toContainText('已切换到该对话');
    await page.locator('#question').fill('蓝鲸潮汐');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toHaveText('回答已生成，已继续当前对话', { timeout: 20000 });
    await expect(page.locator('#threads .thread-item')).toHaveCount(2);
    await page.getByRole('button', { name: '查看对话与引用' }).first().click();
    await expect(page.locator('.thread-detail .thread-question')).toHaveCount(2, { timeout: 10000 });
    await expect(page.locator('.thread-detail .thread-answer')).toHaveCount(2);

    // Start a new conversation: the next question creates a second thread.
    await page.getByRole('button', { name: '新对话' }).click();
    await expect(page.locator('#submit-status')).toContainText('已开始新对话');
    await page.locator('#question').fill('蓝鲸潮汐');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toHaveText('回答已生成', { timeout: 20000 });
    await expect(page.locator('#threads .thread-item')).toHaveCount(3);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-6 空检索边界：安全文案且后续提问可恢复', async ({ page }) => {
    await page.goto(`${BASE}/app/qa.html?material=${mainId}`);
    await page.locator('#question').fill('zzzqqk 绝不存在的词');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('没有找到可引用的材料内容', { timeout: 15000 });
    await assertNoSensitiveVisibleText(page);
    // Recovery: a real question still answers.
    await page.locator('#question').fill('蓝鲸潮汐');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toHaveText('回答已生成', { timeout: 20000 });
  });

  test('A-E2E-QA-7 Provider 未配置边界：状态提示与提问安全文案', async ({ page }) => {
    await stopServer();
    server = startServer(false);
    await ready();
    await page.goto(`${BASE}/app/qa.html?material=${mainId}`);
    await expect(page.locator('#provider-status')).toHaveText('AI Provider 未配置，问答功能不可用', { timeout: 10000 });
    await page.locator('#question').fill('蓝鲸潮汐');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('尚未配置 AI Provider', { timeout: 15000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-8 删除来源材料后：引用真实展示「来源不可用」', async ({ page }) => {
    page.on('dialog', dialog => dialog.accept());
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
    const row = page.locator('#items li', { hasText: MAIN_NAME });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.getByRole('button', { name: '删除' }).click();
    await expect(row).toBeHidden({ timeout: 10000 });
    // The historical citations must now honestly report the unavailable source.
    await page.goto(`${BASE}/app/qa.html`);
    const openButtons = page.getByRole('button', { name: '查看对话与引用' });
    await expect(openButtons.first()).toBeVisible({ timeout: 10000 });
    const openCount = await openButtons.count();
    for (let i = 0; i < openCount; i++) await openButtons.nth(i).click();
    const unavailable = page.locator('.thread-detail .citation-link', { hasText: '来源不可用' });
    expect(await unavailable.count()).toBeGreaterThanOrEqual(1);
    await expect(unavailable.first()).not.toHaveAttribute('href', /.+/);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-QA-9 服务真重启后：线程历史与引用状态持久化', async ({ page }) => {
    await stopServer();
    server = startServer(true);
    await ready();
    await page.goto(`${BASE}/app/qa.html`);
    // 6 threads: 3 answered + 3 user-message-only threads from the failed asks.
    await expect(page.locator('#threads .thread-item')).toHaveCount(6, { timeout: 15000 });
    const openButtons = page.getByRole('button', { name: '查看对话与引用' });
    const openCount = await openButtons.count();
    for (let i = 0; i < openCount; i++) await openButtons.nth(i).click();
    await expect(page.locator('.thread-detail').filter({ hasText: 'Fake answer' }).first()).toBeVisible({ timeout: 10000 });
    const unavailable = page.locator('.thread-detail .citation-link', { hasText: '来源不可用' });
    expect(await unavailable.count()).toBeGreaterThanOrEqual(1);
    await expect(unavailable.first()).not.toHaveAttribute('href', /.+/);
    await assertNoSensitiveVisibleText(page);
  });
});
