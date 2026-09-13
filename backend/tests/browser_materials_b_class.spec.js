const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// B-class independent review for materials.html. Pagination and stale-response
// boundaries use route mocks over the real server; business data creation uses
// page UI only. These tests re-read the page contract independently of the
// A-class userpath spec.
let ROOT = 'H:/studybuddy-test/runs/materials-b-class';
const PORT = 8969;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT };
  env.STUDYBUDDY_AI_PROVIDER = 'fake';
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

function material(id, name, status) {
  return { id, original_name: name, status: status || 'success', media_type: 'text/plain', text_length: 10, span_count: 0, created_at: '2026-01-01T00:00:00Z' };
}

test.describe.serial('materials.html B-class independent review', () => {
  test.beforeAll(async () => {
    ROOT = `H:/studybuddy-test/runs/materials-b-class-${Date.now()}`;
    fs.mkdirSync(ROOT, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('B-MAT-1 分页请求遵循 limit/offset 契约且 has_more 驱动翻页', async ({ page }) => {
    const requests = [];
    await page.route('**/api/materials?*', async route => {
      const url = new URL(route.request().url());
      requests.push(url.searchParams.get('limit') + '/' + url.searchParams.get('offset'));
      const offset = Number(url.searchParams.get('offset'));
      // 25 items total, page size 20: page 1 has 20 + has_more, page 2 has 5.
      const items = Array.from({ length: Math.min(5, Math.max(0, 25 - offset)) + (offset === 0 ? 15 : 0) }, (_, index) => material(`m-${offset + index}`, `材料 ${offset + index}`));
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items, total: 25, limit: 20, offset, has_more: offset + items.length < 25 }) });
    });
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#items li')).toHaveCount(20);
    await expect(page.locator('#state')).toContainText('显示 1-20，共 25 份');
    await expect(page.locator('#pagination')).toBeVisible();
    await page.locator('#pagination').getByRole('button', { name: '下一页' }).click();
    await expect(page.locator('#items li')).toHaveCount(5);
    await expect(page.locator('#state')).toContainText('显示 21-25，共 25 份');
    expect(requests).toEqual(['20/0', '20/20']);
  });

  test('B-MAT-2 迟到列表失败不得覆盖已加载的新视图', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).toContainText('暂无材料');
    // First request (deleted view) is slow and fails; the user toggles back to
    // the active view which loads successfully. The late failure must be
    // discarded instead of flipping the loaded view into an error state.
    await page.route('**/api/materials/deleted*', async route => {
      await new Promise(resolve => setTimeout(resolve, 800));
      return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'synthetic' }) });
    });
    await page.getByRole('button', { name: '查看回收站' }).click();
    await page.getByRole('button', { name: '返回材料列表' }).click();
    await expect(page.locator('#state')).toContainText('暂无材料', { timeout: 5000 });
    await expect(page.locator('#error')).toBeHidden();
    await expect(page.locator('#retry-materials')).toBeHidden();
    await page.waitForTimeout(1100);
    // The late deleted-view failure must not corrupt the active view.
    await expect(page.locator('#state')).toContainText('暂无材料');
    await expect(page.locator('#error')).toBeHidden();
    await expect(page.locator('#retry-materials')).toBeHidden();
    await page.unroute('**/api/materials/deleted*');
  });

  test('B-MAT-3 恶意重命名输入按纯文本渲染，不创建 HTML 节点', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).toContainText('暂无材料');
    await page.locator('#file-input').setInputFiles({ name: 'b-xss-carrier.txt', mimeType: 'text/plain', buffer: Buffer.from('xss carrier body') });
    await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 15000 });
    // Windows forbids < > " in real file names, so the malicious string enters
    // through the rename prompt (arbitrary UI text) instead of the upload path.
    // Opening tags only: _valid_filename rejects any name containing "/".
    const payload = '<img src=x onerror="window.__matXss=1"><svg onload=window.__matXss=2>';
    page.once('dialog', dialog => dialog.accept(payload));
    await page.getByRole('button', { name: '重命名' }).click();
    await expect(page.locator('#mutation-status')).toContainText('材料已重命名', { timeout: 5000 });
    await expect(page.locator('#items li a').first()).toContainText('<img src=x');
    expect(await page.locator('#items img').count()).toBe(0);
    expect(await page.locator('#items script').count()).toBe(0);
    expect(await page.evaluate(() => window.__matXss)).toBeUndefined();
  });

  test('B-MAT-4 重命名失败走安全文案、busy 防重复且恢复可重试', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).not.toContainText('加载中…', { timeout: 5000 });
    await page.locator('#file-input').setInputFiles({ name: 'b-rename.txt', mimeType: 'text/plain', buffer: Buffer.from('rename target body') });
    await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 15000 });
    const row = page.locator('#items li').filter({ hasText: 'b-rename.txt' }).first();
    await expect(row).toBeVisible();
    let failFirst = true;
    await page.route('**/api/materials/*', async route => {
      if (route.request().method() === 'PATCH' && failFirst) {
        failFirst = false;
        await new Promise(resolve => setTimeout(resolve, 700));
        // Real contract: FastAPI HTTPException sends {"detail": "<code>"}.
        return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'material_update_failed' }) });
      }
      return route.fallback();
    });
    page.once('dialog', dialog => dialog.accept('重命名后的材料'));
    await row.getByRole('button', { name: '重命名' }).click();
    await expect(row.getByRole('button', { name: '重命名' })).toBeDisabled();
    await expect(page.locator('#mutation-status')).toContainText('正在重命名材料…');
    await expect(page.locator('#mutation-status')).toContainText('材料更新失败，请重试', { timeout: 5000 });
    await expect(page.locator('#mutation-status')).not.toContainText('material_update_failed');
    await expect(row.getByRole('button', { name: '重命名' })).toBeEnabled();
    await page.unroute('**/api/materials/*');
    page.once('dialog', dialog => dialog.accept('重命名后的材料'));
    await row.getByRole('button', { name: '重命名' }).click();
    await expect(page.locator('#mutation-status')).toContainText('材料已重命名', { timeout: 5000 });
    await expect(page.locator('#items li a').first()).toContainText('重命名后的材料');
  });
});
