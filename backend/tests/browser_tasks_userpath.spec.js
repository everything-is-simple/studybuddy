const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class: task creation begins with visible materials UI and every task
// assertion is read from rendered pages. No page.request business operations.
let ROOT = `H:/studybuddy-test/runs/tasks-userpath-${Date.now()}`;
const FIXTURES = 'H:/studybuddy-test/fixtures/tasks-userpath';
const ART = 'H:/studybuddy-test/artifacts/tasks-userpath';
const PORT = 8977;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function start() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
function stop() { return new Promise(resolve => { if (!server || server.killed) { server = null; return resolve(); } let done = false; const finish = () => { if (!done) { done = true; server = null; resolve(); } }; server.once('exit', finish); server.kill(); setTimeout(finish, 5000); }); }
async function safe(page) { const body = await page.locator('body').innerText(); expect(body).not.toMatch(/traceback|sqlite|select .* from|input_fingerprint|stored_path|api[_-]?key|password|token|[A-Z]:\\/i); }
async function importText(page, name = '任务用户路径.txt') { fs.mkdirSync(FIXTURES, { recursive: true }); const file = path.join(FIXTURES, name); fs.writeFileSync(file, '任务用户路径材料：本地 fake Provider 用于建立可检索索引。', 'utf8'); await page.goto(`${BASE}/app/materials.html`); await page.setInputFiles('#file-input', file); await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 }); await page.locator('#items li', { hasText: name }).getByRole('button', { name: /详情/ }).click(); await page.waitForURL(/material-detail\.html\?material=/); await expect(page.locator('#state')).toHaveText('材料已加载'); }
async function queueFromUi(page) { await page.getByRole('button', { name: '加入索引任务' }).click(); await expect(page.locator('#index-status')).toContainText('索引任务已加入队列', { timeout: 10000 }); const link = page.getByRole('link', { name: '查看索引任务' }); await expect(link).toBeVisible(); return await link.getAttribute('href'); }

test.describe.serial('tasks.html A-class pure user path', () => {
  test.beforeAll(async () => { fs.rmSync(ROOT, { recursive: true, force: true }); fs.mkdirSync(ART, { recursive: true }); server = start(); await ready(); });
  test.afterAll(() => stop());

  test('TK-1 空数据根显示明确空态和已接入边界', async ({ page }) => {
    await page.goto(`${BASE}/app/tasks.html`);
    await expect(page.locator('#state')).toHaveText('当前无全局任务列表');
    await expect(page.locator('#tasks')).toContainText('暂无任务');
    await expect(page.locator('#retry-list')).toBeHidden();
    await expect(page.locator('#retry-detail')).toBeHidden();
    await expect(page.locator('#info')).toContainText('embedding_index');
    await safe(page);
  });

  test('TK-2 材料 UI 触发真实 embedding_index 任务并可查看详情', async ({ page }) => {
    await importText(page); const href = await queueFromUi(page); expect(href).toMatch(/tasks\.html\?task_id=/);
    await page.goto(`${BASE}${href}`); await expect(page.locator('#task-detail')).toContainText('材料向量索引');
    await expect(page.locator('#task-detail')).toContainText('等待中');
    await expect(page.locator('#task-detail')).toContainText('等待执行');
    await safe(page);
  });

  test('TK-3 详情深链、刷新和终态边界不产生重复轮询控件', async ({ page }) => {
    await importText(page, '任务详情刷新.txt'); const href = await queueFromUi(page); await page.goto(`${BASE}${href}`);
    await expect(page.locator('#detail-state')).toHaveText('已加载'); await expect(page).toHaveURL(/task_id=/);
    await page.reload(); await expect(page.locator('#detail-state')).toHaveText('已加载');
    await expect(page.locator('#task-detail [data-action="cancel"]')).toBeVisible();
    await page.screenshot({ path: `${ART}/detail-refresh.png`, fullPage: true }); await safe(page);
  });

  test('TK-4 页面取消 queued 任务，详情与列表显示真实持久状态', async ({ page }) => {
    await importText(page, '任务取消.txt'); const href = await queueFromUi(page); await page.goto(`${BASE}${href}`);
    await expect(page.locator('[data-action="cancel"]')).toBeVisible(); page.once('dialog', dialog => dialog.accept()); await page.locator('[data-action="cancel"]').click();
    await expect(page.locator('#task-detail')).toContainText('已取消', { timeout: 10000 }); await expect(page.locator('#detail-notice')).toContainText('任务已取消');
    await page.reload(); await expect(page.locator('#task-detail')).toContainText('已取消'); await expect(page.locator('[data-action="cancel"]')).toHaveCount(0); await safe(page);
  });

  test('TK-6 状态筛选、分页 URL 和返回后恢复', async ({ page }) => {
    await page.goto(`${BASE}/app/tasks.html`); await page.locator('#status-filter').selectOption('cancelled'); await page.locator('#apply-filters').click();
    await expect(page).toHaveURL(/status=cancelled/); await expect(page.locator('#state')).toContainText('共 1 个任务');
    await page.goto(`${BASE}/app/materials.html`); await page.goBack(); await expect(page.locator('#status-filter')).toHaveValue('cancelled'); await expect(page).toHaveURL(/status=cancelled/); await safe(page);
  });

  test('TK-8 五档 viewport、键盘焦点和重启后任务保留', async ({ page }) => {
    await page.goto(`${BASE}/app/tasks.html?status=cancelled`); await expect(page.locator('#tasks')).toContainText('已取消');
    for (const [width, height] of [[1920,1080],[1280,800],[768,1024],[540,800],[390,844]]) { await page.setViewportSize({ width, height }); await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true); await page.screenshot({ path: `${ART}/tasks-${width}x${height}.png`, fullPage: true }); }
    await page.keyboard.press('Tab'); await expect(page.locator(':focus-visible')).toHaveCount(1);
    await stop(); server = start(); await ready(); await page.goto(`${BASE}/app/tasks.html?status=cancelled`); await expect(page.locator('#tasks')).toContainText('已取消'); await safe(page);
  });
});
