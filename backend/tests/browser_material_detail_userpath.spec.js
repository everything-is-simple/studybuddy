const { test, expect } = require('@playwright/test');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for materials.html -> material-detail.html.
// Rule: no business API calls from test code. All data created via page UI.
// Chain: import -> detail -> parse -> index -> source candidates ->
//        plan item link (+ duplicate guard) -> reload -> restart persistence.
let RUN_ROOT = 'H:/studybuddy-test/runs/material-detail-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/material-detail-userpath';
const ART = 'H:/studybuddy-test/artifacts/material-detail-userpath';
const PORT = 8942;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '材料详情链路测试.txt';
const PDF_NAME = 'blank-scan.pdf';
let server;
let detailUrl = '';
let txtDetailUrl = '';
let txtId = '';

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
    '材料详情链路测试：导入之后进入详情页，先解析出可用文本，再建立索引，' +
    '然后刷新来源候选并把片段关联到计划学习项。重复关联不应创建重复数据。\n', 'utf8');
  // Blank (image-only) PDF: parses to status=empty so the page must surface a
  // real OCR capability state instead of a fabricated success.
  const script = 'from pypdf import PdfWriter\n'
    + `w = PdfWriter(); w.add_blank_page(width=200, height=200); w.write(r'${path.join(FIXTURES, PDF_NAME)}')\n`;
  const scriptPath = path.join(FIXTURES, 'build_blank_pdf.py');
  fs.writeFileSync(scriptPath, script, 'utf8');
  execFileSync(PYTHON, [scriptPath], { timeout: 60000 });
  fs.rmSync(scriptPath, { force: true });
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
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  detailUrl = page.url();
  txtId = decodeURIComponent(detailUrl.split('material=')[1]);
  await expect(page.locator('#title')).toContainText(itemName, { timeout: 10000 });
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

async function clickWithRetry(page, action, assertion) {
  for (let i = 0; i < 3; i++) {
    try {
      await action();
      await assertion();
      return;
    } catch (_) { /* retry */ }
  }
  await assertion();
}

test.describe.serial('materials -> material-detail pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/material-detail-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixtures();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-MD-1 导入后从列表进入详情并展示解析状态', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).toHaveText('暂无材料', { timeout: 10000 });
    await importViaUi(page, path.join(FIXTURES, TXT_NAME));
    const link = page.locator('#items li a');
    await expect(link).toHaveAttribute('href', /material-detail\.html\?material=/);
    await openDetailViaUi(page, TXT_NAME);
    txtDetailUrl = detailUrl;
    await expect(page.locator('#stage-import')).toContainText('已导入');
    await expect(page.locator('#stage-parse')).toContainText('文本可用');
    await expect(page.locator('#stage-index')).toContainText('尚未建立索引', { timeout: 10000 });
    await expect(page.locator('#capability-grid')).toContainText('本材料类型不需要 OCR');
    await expect(page.locator('#capability-grid')).toContainText('ASR');
    await expect(page.locator('#capability-grid')).toContainText('不适用');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-MD-2 建立索引后展示索引数量与来源候选', async ({ page }) => {
    await page.goto(detailUrl);
    await expect(page.locator('#index')).toBeEnabled({ timeout: 10000 });
    await page.locator('#index').click();
    await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 30000 });
    await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/);
    // Candidates require the explicit refresh after indexing (observable state, not assumed).
    await clickWithRetry(page,
      () => page.locator('#refresh-candidates').click(),
      () => expect(page.locator('#candidate-status')).toContainText('已加载来源候选'));
    await expect(page.locator('#candidates')).toContainText('片段 1');
    await expect(page.locator('#capability-grid')).toContainText('可用（范围：本材料）');
    // Repeated refresh stays stable and idempotent.
    await clickWithRetry(page,
      () => page.locator('#refresh-candidates').click(),
      () => expect(page.locator('#candidate-status')).toContainText('已加载来源候选'));
    await expect(page.locator('#candidates')).toContainText('片段 1');
  });

  test('A-E2E-MD-3 关联计划学习项且重复关联不创建重复数据', async ({ page }) => {
    const goalTitle = '材料详情目标';
    const planTitle = '材料详情计划';
    const itemTitle = '材料详情学习项';
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#goal-status')).not.toContainText('正在加载', { timeout: 10000 });
    await page.fill('#goal-title', goalTitle);
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item', { hasText: goalTitle })).toBeVisible();
    await page.fill('#plan-title', planTitle);
    await page.locator('#plan-goal').selectOption({ label: goalTitle });
    await page.click('#plan-form button[type=submit]');
    await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', itemTitle);
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(page.locator('#plan-status')).toHaveText('学习项已添加');

    await page.goto(detailUrl);
    await expect(page.locator('#link-form')).toBeVisible({ timeout: 10000 });
    await page.locator('#link-plan').selectOption({ label: planTitle });
    await page.locator('#link-item').selectOption({ label: itemTitle });
    await expect(page.locator('#link-candidate')).toContainText('片段 1');
    await page.locator('#link-add').click();
    await expect(page.locator('#link-status')).toHaveText('已关联到学习项。', { timeout: 10000 });
    await expect(page.locator('#plan-links')).toContainText(`学习项：${itemTitle}`);
    await expect(page.locator('#plan-links')).toContainText(`计划：${planTitle}`);

    // Duplicate attempt must be refused without creating a second link.
    await clickWithRetry(page,
      () => page.locator('#link-add').click(),
      () => expect(page.locator('#link-status')).toHaveText('该学习项已关联此片段，无需重复添加。'));
    await expect(page.locator('#plan-links').getByRole('button', { name: '取消关联' })).toHaveCount(1);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-MD-4 页面刷新后状态恢复', async ({ page }) => {
    await page.goto(detailUrl);
    await expect(page.locator('#title')).toContainText(TXT_NAME, { timeout: 10000 });
    await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });
    await expect(page.locator('#plan-links')).toContainText('学习项：', { timeout: 10000 });
    await expect(page.locator('#link-form')).toBeVisible();
    await expect(page.locator('#candidates')).toContainText('片段 1');
  });

  test('A-E2E-MD-5 应用重启后解析、索引与关联全部持久化', async ({ page }) => {
    await stopServer();
    server = startServer();
    await ready();
    await page.goto(detailUrl);
    await expect(page.locator('#title')).toContainText(TXT_NAME, { timeout: 10000 });
    await expect(page.locator('#state')).toHaveText('材料已加载');
    await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });
    await expect(page.locator('#plan-links')).toContainText('学习项：', { timeout: 10000 });
    await expect(page.locator('#plan-links')).toContainText('来源：', { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-MD-6 无效 ID 与缺少 ID 显示明确错误且不泄露内部信息', async ({ page }) => {
    await page.goto(`${BASE}/app/material-detail.html?material=nonexistent-id-xyz`);
    await expect(page.locator('#title')).toHaveText('材料不可用', { timeout: 10000 });
    await expect(page.locator('#state')).toContainText('材料不存在或已删除');
    await expect(page.locator('#candidate-status')).toContainText('材料不可用');
    await expect(page.locator('#link-status')).toContainText('材料不可用');
    await expect(page.locator('#export-original')).toBeDisabled();
    await assertNoSensitiveVisibleText(page);

    await page.goto(`${BASE}/app/material-detail.html`);
    await expect(page.locator('#state')).toContainText('请从资料库进入', { timeout: 10000 });
    await expect(page.locator('#export-original')).toBeDisabled();
    await expect(page.locator('#export-text')).toBeDisabled();
    await expect(page.locator('#candidate-status')).toContainText('需要先选择材料');
  });

  test('A-E2E-MD-7 无文字层 PDF 显示真实 OCR 能力状态且不伪造成功', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
    await page.setInputFiles('#file-input', path.join(FIXTURES, PDF_NAME));
    // A text-less PDF imports with status "empty": the banner must not fake a success count.
    await expect(page.locator('#upload-status')).toContainText('已导入 0/1', { timeout: 30000 });
    const row = page.locator('#items li', { hasText: PDF_NAME });
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.getByRole('button', { name: /详情/ }).click();
    await page.waitForURL(/material-detail\.html\?material=/);
    detailUrl = page.url();
    await expect(page.locator('#title')).toContainText(PDF_NAME, { timeout: 10000 });
    await expect(page.locator('#state')).toHaveText('材料已加载');
    await expect(page.locator('#content')).toContainText('没有可提取的正文', { timeout: 10000 });
    await expect(page.locator('#capability-grid')).toContainText('OCR 组件：');
    const ocrText = await page.locator('#capability-grid').innerText();
    expect(ocrText).toMatch(/OCR 组件：(可用|未配置|已关闭|未安装|状态未知)/);
    await expect(page.locator('#capability-grid')).toContainText('不可用：尚未建立索引');
    await expect(page.locator('#index-status')).toContainText('尚未建立索引');
    // TXT material must not be blocked by the PDF/OCR path.
    await page.goto(txtDetailUrl);
    await expect(page.locator('#stage-parse')).toContainText('文本可用', { timeout: 10000 });
  });
});
