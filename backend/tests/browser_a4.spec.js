const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/a4-browser';
const PORT = 8820;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {
    ...process.env,
    PYTHONPATH: 'H:/studybuddy/backend',
    STUDYBUDDY_DATA_ROOT: RUN_ROOT,
    STUDYBUDDY_AI_PROVIDER: 'fake',
  };
  for (const key of ['STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL', 'STUDYBUDDY_AI_API_KEY']) delete env[key];
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 15000 }).toBe(true);
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

async function openPage(page, path) {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto(`${BASE}${path}`);
  return { consoleErrors, pageErrors };
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, { recursive: true, force: true });
  server = startServer();
  await ready();
});

test.afterEach(stop);

test('A4 provider page loads capabilities and safely recovers from API failure', async ({ page }) => {
  const errors = await openPage(page, '/app/settings-provider.html');
  await expect(page.locator('#state')).toHaveText('已加载');
  await expect(page.locator('#capabilities')).toBeVisible();
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  await expect(page.locator('body')).toContainText('测试通过 ≠ 已保存');
  await expect(page.locator('#provider-test')).toBeVisible();
  await expect(page.locator('#email-test')).toBeVisible();
  await expect(page.locator('body')).not.toContainText(/H:\\|sqlite|SELECT|Traceback|api[_-]?key|secret|token/i);
  await page.route('**/api/ai/capabilities', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_provider_error', path: 'H:/secret' }),
  }));
  await page.reload();
  await expect(page.locator('#state')).toHaveText('加载失败');
  await expect(page.locator('#error')).toBeVisible();
  await expect(page.locator('#error')).not.toContainText('private_provider_error');
  await expect(page.locator('#error')).not.toContainText('H:/secret');
  await page.unroute('**/api/ai/capabilities');
  await page.reload();
  await expect(page.locator('#state')).toHaveText('已加载');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  expect(errors.consoleErrors.filter(value => !value.includes('Failed to load resource'))).toEqual([]);
  expect(errors.pageErrors).toEqual([]);
});

test('P1-5-1 provider form tests connection and clears secret input', async ({ page }) => {
  await page.route('**/api/system/provider-connection-test', route => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }),
  }));
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-model').fill('synthetic-model');
  await page.locator('#provider-url').fill('https://loopback.invalid/v1');
  await page.locator('#provider-key').fill('TEST_SECRET_DO_NOT_LEAK_7d0f');
  await page.locator('#provider-form').evaluate(form => form.requestSubmit());
  await expect(page.locator('#provider-result')).toContainText('测试通过');
  await expect(page.locator('#provider-key')).toHaveValue('');
  await expect(page.locator('body')).not.toContainText('TEST_SECRET_DO_NOT_LEAK_7d0f');
});

test('P1-5-1 email form sends selected channel and keeps no save control', async ({ page }) => {
  let requestBody;
  await page.route('**/api/system/email-connection-test', async route => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
  });
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#email-channel').selectOption('feishu');
  await page.locator('#feishu-webhook').fill('TEST_WEBHOOK_DO_NOT_LEAK_5a21');
  await page.locator('#email-form').evaluate(form => form.requestSubmit());
  await expect(page.locator('#email-result')).toContainText('测试通过');
  await expect.poll(() => requestBody).toMatchObject({ channel: 'feishu', feishu_webhook: 'TEST_WEBHOOK_DO_NOT_LEAK_5a21' });
  await expect(page.locator('#feishu-webhook')).toHaveValue('');
  await expect(page.locator('body')).not.toContainText('TEST_WEBHOOK_DO_NOT_LEAK_5a21');
  await expect(page.locator('button', { hasText: '保存' })).toHaveCount(0);
});

test('A4 capture page creates a session and keeps failure state safe', async ({ page }) => {
  const errors = await openPage(page, '/app/capture.html');
  await expect(page.locator('#state')).toHaveText('暂无会话');
  await page.locator('#new-session-btn').click();
  await expect(page.locator('#new-session-dialog')).toBeVisible();
  await page.locator('#original-name').fill('A4 synthetic lecture');
  await page.locator('#new-session-form button[type="submit"]').click();
  await expect(page.locator('#state')).toContainText('共 1 个会话');
  await expect(page.locator('#sessions')).toContainText('A4 synthetic lecture');
  await page.getByRole('button', { name: '查看详情' }).click();
  await expect(page.locator('#session-detail-dialog')).toBeVisible();
  await expect(page.locator('#session-detail-content')).toContainText('A4 synthetic lecture');
  await page.locator('#close-detail-btn').click();
  await page.route('**/api/study/capture-sessions?*', route => route.fulfill({
    status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'private_capture_error', path: 'C:/secret' }),
  }));
  await page.locator('#refresh-btn').click();
  await expect(page.locator('#state')).toHaveText('加载失败');
  await expect(page.locator('#error')).toBeVisible();
  await expect(page.locator('#error')).not.toContainText('private_capture_error');
  await expect(page.locator('#error')).not.toContainText('C:/secret');
  await page.unroute('**/api/study/capture-sessions?*');
  await page.locator('#refresh-btn').click();
  await expect(page.locator('#state')).toContainText('共 1 个会话');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  expect(errors.consoleErrors.filter(value => !value.includes('Failed to load resource'))).toEqual([]);
  expect(errors.pageErrors).toEqual([]);
});

test('A4 task page exposes safe empty and invalid-task states', async ({ page }) => {
  const errors = await openPage(page, '/app/tasks.html');
  await expect(page.locator('#state')).toHaveText('当前无全局任务列表');
  await expect(page.locator('#info')).toContainText('embedding_index');
  await page.goto(`${BASE}/app/tasks.html?task_id=invalid-a4-task`);
  await expect(page.locator('#detail-state')).toHaveText('加载失败');
  await expect(page.locator('#detail-error')).toBeVisible();
  await expect(page.locator('#detail-error')).not.toContainText('invalid-a4-task');
  await expect(page.locator('body')).not.toContainText(/H:\\|sqlite|SELECT|Traceback|api[_-]?key|secret|token/i);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  expect(errors.consoleErrors.filter(value => !value.includes('Failed to load resource'))).toEqual([]);
  expect(errors.pageErrors).toEqual([]);
});
