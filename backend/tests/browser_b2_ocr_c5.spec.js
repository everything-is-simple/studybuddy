const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/b2-ocr-c5-browser';
const PORT = 8832;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  delete env.STUDYBUDDY_OCR_ENABLED;
  delete env.STUDYBUDDY_OCR_PROVIDER;
  delete env.STUDYBUDDY_OCR_MODEL_ROOT;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/health`)).ok; } catch (_) { return false; }
  }, {timeout: 20000}).toBe(true);
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

function pngBuffer() {
  return Buffer.from('89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c6360000000020001e221bc330000000049454e44ae426082', 'hex');
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer();
  await ready();
});
test.afterEach(stop);

test('B2 C5 image capture exposes OCR gate and preserves review boundary', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${BASE}/app/capture.html`);
  await expect(page.locator('#ocr-notice')).toContainText(/本机 OCR 已配置|OCR Provider 未配置/);
  await page.locator('#new-session-btn').click();
  await page.locator('#asset-kind').selectOption('image');
  await expect(page.locator('#media-type')).toHaveValue('image/png');
  await page.locator('#original-name').fill('c5-slide.png');
  await page.locator('#new-session-form button[type="submit"]').click();
  await expect(page.locator('#sessions')).toContainText('c5-slide.png');
  await page.getByRole('button', {name: '查看详情'}).click();
  await expect(page.locator('input[type="file"]')).toHaveAttribute('accept', 'image/png,image/jpeg,image/webp');
  await page.locator('input[type="file"]').setInputFiles({name: 'c5-slide.png', mimeType: 'image/png', buffer: pngBuffer()});
  await expect(page.locator('[id^="upload-status-"]')).toContainText('上传成功');
  await expect(page.locator('#session-detail-dialog')).not.toBeVisible({timeout: 5000});
  await page.getByRole('button', {name: '查看详情'}).click();
  await expect(page.getByRole('button', {name: /转写/})).toBeVisible();
  await page.locator('#close-detail-btn').click();
  await page.reload();
  await expect(page.locator('#sessions')).toContainText('c5-slide.png');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  await expect(page.locator('body')).not.toContainText(/stored_path|traceback|raw provider|H:\\|sqlite/i);
  expect(errors).toEqual([]);
});

test('B2 C5 image failure and source lifecycle labels remain safe', async ({page}) => {
  await page.route('**/api/ai/capabilities', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({capture: {status: 'demo', provider_id: 'fake'}, ocr: {status: 'configured', provider_id: 'paddleocr', model_id: 'PP-OCRv5_server_det+PP-OCRv5_server_rec'}})}));
  await page.goto(`${BASE}/app/capture.html`);
  await expect(page.locator('#asr-notice')).not.toContainText('H:');
  await page.route('**/api/study/capture-sessions?*', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({items: [{id: 'c5-deleted', original_name: '已删除图片', status: 'confirmed', source_status: 'source_deleted', asset_kind: 'image', created_at: '2026-01-01T00:00:00Z'}]})}));
  await page.reload();
  await expect(page.locator('#sessions')).toContainText('已删除图片');
  await expect(page.locator('#sessions')).toContainText('已确认');
  await page.locator('#sessions').getByRole('button', {name: '查看详情'}).click();
  await page.route('**/api/study/capture-sessions/c5-deleted', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({id: 'c5-deleted', original_name: '已删除图片', status: 'confirmed', source_status: 'source_deleted', asset_kind: 'image', media_type: 'image/png'})}));
  await page.reload();
  await expect(page.locator('body')).not.toContainText(/stored_path|traceback|raw provider|private_backend_error/i);
});
