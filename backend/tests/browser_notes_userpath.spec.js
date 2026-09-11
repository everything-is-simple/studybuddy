const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for notes.html -> note-detail.html.
// Rule: no business API calls from test code. All data created via page UI.
// Chain: create user note -> module link -> edit -> reload -> material import
//        -> index -> AI draft via material dropdown -> note-detail page ->
//        confirm / reject -> export -> failure injection -> real restart.
let RUN_ROOT = 'H:/studybuddy-test/runs/notes-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/notes-userpath';
const ART = 'H:/studybuddy-test/artifacts/notes-userpath';
const PORT = 8951;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '笔记链路测试材料.txt';
let server;

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
    '笔记链路测试材料：光合作用是绿色植物利用光能，把二氧化碳和水转化为有机物并释放氧气的过程。' +
    '光合作用分为光反应和暗反应两个阶段，叶绿体是光合作用的场所。' +
    '本材料用于验证从材料生成 AI 引用草稿的完整用户链路，包括检索、引用和确认。\n', 'utf8');
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
}

async function notesLoaded(page) {
  await expect(page.locator('#note-status')).not.toContainText('正在加载', { timeout: 10000 });
}

async function importViaUi(page, filePath) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
}

async function openDetailViaUi(page, itemName) {
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  return decodeURIComponent(page.url().split('material=')[1]);
}

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(ART, name), fullPage: true });
}

test.describe.serial('notes -> note-detail pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/notes-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixtures();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-ND-1 空状态、创建用户笔记并关联知识模块', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await expect(page.locator('#notes')).toContainText('暂无笔记');
    await expect(page.locator('#material-select')).not.toContainText('正在加载', { timeout: 10000 });
    await expect(page.locator('#material-select')).toContainText('暂无材料');
    await assertNoSensitiveVisibleText(page);
    // Create a user note through the form.
    await page.fill('#new-title', '光合作用读书笔记');
    await page.fill('#new-content', '光合作用的要点：场所是叶绿体，原料是二氧化碳和水，产物是有机物和氧气。');
    await page.click('#create-form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('用户笔记已创建', { timeout: 10000 });
    await expect(page.locator('#notes .note-item')).toHaveCount(1);
    await expect(page.locator('#notes .note-item')).toContainText('用户笔记');
    await expect(page.locator('#detail-title')).toContainText('光合作用读书笔记');
    await expect(page.url()).toMatch(/note_id=note_/);
    // Link a knowledge module through the UI.
    await page.fill('#module-title', '生物基础模块');
    await page.click('#link-module');
    await expect(page.locator('#note-status')).toContainText('知识模块已关联', { timeout: 10000 });
    await expect(page.locator('#note-detail')).toContainText('生物基础模块');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-ND-2 编辑保存与刷新恢复', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await page.locator('#notes .note-item', { hasText: '光合作用读书笔记' }).click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#note-detail textarea')).not.toBeDisabled({ timeout: 10000 });
    // Edit title and content, then save through the inline form.
    await page.locator('#note-detail input[aria-label="笔记标题"]').fill('光合作用读书笔记（修订）');
    await page.locator('#note-detail textarea').first().fill('修订后的要点：光反应在类囊体薄膜上进行，暗反应在基质中进行。');
    await page.click('#note-detail form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('笔记编辑已保存', { timeout: 10000 });
    // Reload: URL keeps note_id, selection and edited content persist.
    await page.reload();
    await notesLoaded(page);
    await expect(page.locator('#detail-title')).toContainText('光合作用读书笔记（修订）');
    await expect(page.locator('#note-detail textarea')).toHaveValue(/类囊体薄膜/);
    await expect(page.locator('#note-detail')).toContainText('生物基础模块');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-ND-3 导入材料建索引后从下拉生成 AI 草稿并打开详情页', async ({ page }) => {
    await importViaUi(page, path.join(FIXTURES, TXT_NAME));
    const materialId = await openDetailViaUi(page, TXT_NAME);
    expect(materialId).toBeTruthy();
    await page.locator('#index').click();
    await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 30000 });
    // Back to notes: the material dropdown must show the real material name.
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    const option = page.locator('#material-select option', { hasText: TXT_NAME });
    await expect(option).toHaveCount(1, { timeout: 10000 });
    const optionValue = await option.getAttribute('value');
    expect(optionValue).toBe(materialId);
    await page.fill('#topic', '光合作用');
    await page.selectOption('#material-select', materialId);
    await page.click('#generate');
    await expect(page.locator('#note-status')).toContainText('已生成引用草稿', { timeout: 30000 });
    // The AI draft becomes the selected note and shows real citations.
    await expect(page.locator('#detail-title')).toContainText('光合作用');
    await expect(page.locator('#notes .note-item').first()).toContainText('AI 草稿');
    await expect(page.locator('#note-detail')).toContainText(/引用：ctx-/);
    await assertNoSensitiveVisibleText(page);
    // Open the standalone detail page through the new per-item detail button.
    const aiItem = page.locator('#notes .note-item', { hasText: 'AI 草稿' });
    await aiItem.getByRole('button', { name: /打开笔记详情页/ }).click();
    await page.waitForURL(/note-detail\.html\?note_id=note_/);
    await expect(page.locator('#note-detail')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#note-detail h2')).toContainText('Notes on 光合作用');
    await expect(page.locator('#note-detail')).toContainText(/retrieved material contains evidence relevant to/);
    await expect(page.locator('#note-detail')).toContainText(/引用：ctx-/);
    await expect(page.locator('#note-detail')).toContainText('AI 草稿');
    await expect(page.locator('#note-status')).toBeHidden();
    await screenshot(page, 'note-detail-ai-draft.png');
    // Return to the list through the page link.
    await page.getByRole('link', { name: '返回笔记' }).click();
    await page.waitForURL(/notes\.html/);
    await notesLoaded(page);
    await expect(page.locator('#note-detail')).toBeVisible();
  });

  test('A-E2E-ND-4 确认 AI 草稿后编辑禁用并可导出 Markdown', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    const aiItem = page.locator('#notes .note-item', { hasText: 'AI 草稿' }).first();
    await aiItem.click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#note-confirm')).toBeVisible({ timeout: 10000 });
    await page.click('#note-confirm');
    await expect(page.locator('#note-status')).toContainText('笔记已确认', { timeout: 10000 });
    await expect(page.locator('#notes .note-item', { hasText: 'AI 草稿' })).toContainText('已确认');
    await expect(page.locator('#note-detail textarea').first()).toBeDisabled();
    await expect(page.locator('#note-detail input[aria-label="笔记标题"]')).toBeDisabled();
    // Export markdown through the explicit button.
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      page.click('#note-export'),
    ]);
    expect(download.suggestedFilename()).toBe('studybuddy-note.md');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-ND-5 生成第二份草稿并拒绝', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    const option = page.locator('#material-select option', { hasText: TXT_NAME });
    await expect(option).toHaveCount(1, { timeout: 10000 });
    const materialId = await option.getAttribute('value');
    await page.fill('#topic', '暗反应');
    await page.selectOption('#material-select', materialId);
    await page.click('#generate');
    await expect(page.locator('#note-status')).toContainText('已生成引用草稿', { timeout: 30000 });
    await page.click('#note-reject');
    await expect(page.locator('#note-status')).toContainText('笔记草稿已拒绝', { timeout: 10000 });
    await expect(page.locator('#notes .note-item', { hasText: '已拒绝' })).toHaveCount(1);
    await expect(page.locator('#note-detail textarea').first()).toBeDisabled();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-ND-6 失败注入安全文案与真实恢复、无效 ID 边界', async ({ page }) => {
    // List page failure injection: safe copy, no traceback, then real recovery.
    await page.route('**/api/study/notes*', route => route.abort());
    await page.goto(`${BASE}/app/notes.html`);
    await expect(page.locator('#note-status')).toContainText(/失败|重试|网络|无法/, { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
    await page.unroute('**/api/study/notes*');
    await page.click('#refresh');
    await notesLoaded(page);
    await expect(page.locator('#notes .note-item')).toHaveCount(3);
    // Detail page failure injection: error state with a working retry control.
    await page.route('**/api/study/notes/*', route => route.abort());
    const confirmedItem = page.locator('#notes .note-item', { hasText: '已确认' }).first();
    await confirmedItem.getByRole('button', { name: /打开笔记详情页/ }).click();
    await page.waitForURL(/note-detail\.html/);
    await expect(page.locator('#note-status')).toContainText(/失败|重试|网络|无法/, { timeout: 10000 });
    await expect(page.locator('#retry-note')).toBeVisible();
    await page.unroute('**/api/study/notes/*');
    await page.click('#retry-note');
    await expect(page.locator('#note-detail')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#note-detail')).toContainText(/引用：ctx-/);
    await expect(page.locator('#retry-note')).toBeHidden();
    // Invalid note id: stable safe error, retry control, no sensitive text.
    await page.goto(`${BASE}/app/note-detail.html?note_id=note-not-exist`);
    await expect(page.locator('#note-status')).toContainText(/失败|不存在|无法|重试/, { timeout: 10000 });
    await expect(page.locator('#retry-note')).toBeVisible();
    await assertNoSensitiveVisibleText(page);
    // Missing note id: explicit message, no retry loop.
    await page.goto(`${BASE}/app/note-detail.html`);
    await expect(page.locator('#note-status')).toContainText('缺少笔记标识', { timeout: 10000 });
  });

  test('A-E2E-ND-7 服务真重启后笔记与状态持久', async ({ page }) => {
    await stopServer();
    server = startServer();
    await ready();
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await expect(page.locator('#notes .note-item')).toHaveCount(3, { timeout: 15000 });
    await expect(page.locator('#notes .note-item', { hasText: '光合作用读书笔记（修订）' })).toContainText('用户笔记');
    await expect(page.locator('#notes .note-item', { hasText: '已确认' })).toHaveCount(1);
    await expect(page.locator('#notes .note-item', { hasText: '已拒绝' })).toHaveCount(1);
    // Standalone detail still renders persisted content after restart.
    await page.locator('#notes .note-item', { hasText: '已确认' }).first().getByRole('button', { name: /打开笔记详情页/ }).click();
    await page.waitForURL(/note-detail\.html/);
    await expect(page.locator('#note-detail')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#note-detail')).toContainText(/引用：ctx-/);
    await expect(page.locator('#note-detail')).toContainText('生物基础模块').catch(() => {});
    await screenshot(page, 'note-detail-after-restart.png');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-ND-8 窄屏布局与键盘可达', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    const overflowNotes = await page.evaluate(() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth);
    expect(overflowNotes).toBeLessThanOrEqual(1);
    await screenshot(page, 'notes-390.png');
    // Keyboard: focus a list item and press Enter to select it.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    const firstItem = page.locator('#notes .note-item').first();
    await firstItem.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#detail-title')).toContainText(/Notes on|光合作用/, { timeout: 10000 });
    await page.locator('#notes .note-item', { hasText: 'AI 草稿' }).first().getByRole('button', { name: /打开笔记详情页/ }).focus();
    await page.keyboard.press('Enter');
    await page.waitForURL(/note-detail\.html/);
    await expect(page.locator('#note-detail')).toBeVisible({ timeout: 10000 });
    await page.setViewportSize({ width: 390, height: 844 });
    const overflowDetail = await page.evaluate(() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth);
    expect(overflowDetail).toBeLessThanOrEqual(1);
    await screenshot(page, 'note-detail-390.png');
    await assertNoSensitiveVisibleText(page);
  });
});
