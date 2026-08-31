const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ENABLED = process.env.STUDYBUDDY_RUN_REAL_ASR_SMOKE === '1';
const RUNTIME = process.env.STUDYBUDDY_ASR_RUNTIME || 'H:/Whisper/cli/main.exe';
const MODEL = process.env.STUDYBUDDY_ASR_MODEL_PATH || 'H:/Whisper/Models/ggml-large-v3-turbo.bin';
const FIXTURE = process.env.STUDYBUDDY_ASR_FIXTURE || 'H:/Whisper/Whisper-1.12.0/SampleClips/jfk.wav';
const RUN_ROOT = 'H:/studybuddy-test/runs/formal-asr-browser';
const PORT = 8831;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {
    ...process.env,
    PYTHONPATH: 'H:/studybuddy/backend',
    STUDYBUDDY_DATA_ROOT: RUN_ROOT,
    STUDYBUDDY_ASR_PROVIDER: 'whisper-cpp',
    STUDYBUDDY_ASR_MODEL: 'ggml-large-v3-turbo',
    STUDYBUDDY_ASR_RUNTIME: RUNTIME,
    STUDYBUDDY_ASR_MODEL_PATH: MODEL,
  };
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/health`)).ok; } catch (_) { return false; }
  }, { timeout: 20000 }).toBe(true);
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

test.skip(!ENABLED, 'opt-in real ASR browser smoke');
test.beforeEach(async () => {
  expect(fs.existsSync(RUNTIME)).toBe(true);
  expect(fs.existsSync(MODEL)).toBe(true);
  expect(fs.existsSync(FIXTURE)).toBe(true);
  fs.rmSync(RUN_ROOT, { recursive: true, force: true });
  server = startServer();
  await ready();
});
test.afterEach(stop);

test('configured local ASR creates a draft before an explicit confirmation', async ({ page }) => {
  const consoleErrors = [];
  const pageErrors = [];
  const dialogs = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('dialog', async dialog => { dialogs.push(dialog.message()); await dialog.accept(); });
  await page.goto(`${BASE}/app/capture.html`);
  await expect(page.locator('#asr-notice')).toContainText('本机 ASR 已配置');
  await expect(page.locator('#asr-notice')).toContainText('whisper-cpp');
  await expect(page.locator('#asr-notice')).not.toContainText(/H:|main\.exe|\.bin/i);

  await page.getByRole('button', { name: '新建采集会话' }).click();
  await page.locator('#original-name').fill('public-fixture.wav');
  await page.locator('#media-type').fill('audio/wav');
  await page.locator('#new-session-form button[type="submit"]').click();
  await page.getByRole('button', { name: '查看详情' }).click();
  await page.locator('input[type="file"]').setInputFiles(FIXTURE);
  await expect(page.locator('[id^="upload-status-"]')).toContainText('上传成功');
  await expect(page.locator('#session-detail-dialog')).not.toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('button', { name: '转写' })).toBeVisible();
  await page.getByRole('button', { name: '转写' }).click();
  await expect.poll(async () => {
    const response = await page.request.get(`${BASE}/api/study/capture-sessions?limit=10`);
    return (await response.json()).items[0]?.status;
  }, { timeout: 30000 }).toBe('review_required');
  await page.getByRole('button', { name: '查看详情' }).click();
  await expect(page.locator('#session-detail-content')).toContainText('转写草稿');
  await expect(page.getByRole('button', { name: '确认' })).toBeVisible();
  await page.getByRole('button', { name: '确认' }).click();
  await expect(page.locator('#session-detail-dialog')).not.toBeVisible({ timeout: 5000 });
  await expect(page.locator('#sessions')).toContainText('已确认');
  expect(dialogs).toContain('确定使用当前配置的本机转写 Provider 吗？');
  expect(dialogs).toContain('确认此转写草稿？确认后将转为正式材料。');
  await expect(page.locator('body')).not.toContainText(/stored_path|traceback|H:|main\.exe|\.bin/i);
  expect(consoleErrors.filter(value => !value.includes('Failed to load resource'))).toEqual([]);
  expect(pageErrors).toEqual([]);
});
