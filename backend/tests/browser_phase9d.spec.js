const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase9d-ui';
const PORT = 8814;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer(deliveryMode = 'off') {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  env.STUDYBUDDY_REPORT_DELIVERY_MODE = deliveryMode;
  env.STUDYBUDDY_REPORT_DELIVERY_TARGETS = deliveryMode === 'dry_run' ? 'guardian-primary' : '';
  delete env.STUDYBUDDY_AI_PROVIDER;
  delete env.STUDYBUDDY_AI_MODEL;
  delete env.STUDYBUDDY_AI_BASE_URL;
  delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  for (let i = 0; i < 120; i += 1) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

function wavBuffer() {
  return Buffer.concat([Buffer.from('RIFF'), Buffer.from([20, 0, 0, 0]), Buffer.from('WAVE'), Buffer.from('StudyBuddy capture')]);
}

async function bootstrapProject(page) {
  const response = await page.request.post(`${BASE}/api/materials`, {
    multipart: {file: {name: 'workspace-seed.txt', mimeType: 'text/plain', buffer: Buffer.from('Workspace seed for project scope.')}},
  });
  expect(response.ok()).toBe(true);
}

async function createReport(page) {
  const response = await page.request.post(`${BASE}/api/study/reports`, {
    data: {
      report_kind: 'daily', timezone: 'UTC',
      period_start: '2026-01-15', period_end: '2026-01-16',
    },
  });
  expect(response.ok()).toBe(true);
  return response.json();
}

async function createCaptureViaUi(page) {
  await page.locator('#phase9d-asset-file').setInputFiles({
    name: 'lesson.wav', mimeType: 'audio/wav', buffer: wavBuffer(),
  });
  await page.locator('#phase9d-session-create').click();
  await expect(page.locator('#phase9d-status')).toContainText('原件已上传');
  return page.locator('#phase9d-capture-list button').first();
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer();
  await ready();
});
test.afterEach(stop);

test('Phase 9D S7 capture workspace uploads, transcribes, confirms and recovers safely', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${BASE}/legacy`);
  await bootstrapProject(page);
  await page.getByRole('link', {name: '课堂与报告'}).click();
  await expect(page.locator('#phase9d')).toBeVisible();
  await expect(page.locator('#phase9d-status')).toContainText('已加载');

  const createButton = page.locator('#phase9d-session-create');
  await page.locator('#phase9d-asset-file').setInputFiles({
    name: 'lesson.wav', mimeType: 'audio/wav', buffer: wavBuffer(),
  });
  await createButton.click();
  await expect(createButton).toBeDisabled();
  await expect(page.locator('#phase9d-capture-list button')).toHaveCount(1);
  await expect(page.locator('#phase9d-status')).toContainText('原件已上传');

  await page.locator('#phase9d-capture-list button').first().click();
  await page.getByRole('button', {name: '触发 deterministic 转写'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('转写完成');
  await expect(page.locator('#phase9d-workspace')).toContainText('低置信，建议人工确认');
  await expect(page.locator('#phase9d-workspace')).toContainText('置信度 94%');
  await expect(page.locator('body')).not.toContainText('stored_path');
  await expect(page.locator('body')).not.toContainText('StudyBuddy capture');

  await page.getByRole('button', {name: '接入 S2 并确认'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('接入 S2 并确认');
  await expect(page.locator('#phase9d-detail')).toContainText('状态：confirmed');
  await expect(page.locator('#phase9d-detail')).toContainText('来源状态：valid');

  await page.reload();
  await page.getByRole('link', {name: '课堂与报告'}).click();
  await expect(page.locator('#phase9d-capture-list')).toContainText('confirmed');
  await page.locator('#phase9d-capture-list button').first().click();
  await expect(page.locator('#phase9d-detail')).toContainText('状态：confirmed');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole('link', {name: '课堂与报告'}).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#phase9d')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('traceback');
  await expect(page.locator('body')).not.toContainText('private_backend_error');
  await expect(page.locator('body')).not.toContainText('raw provider');
  expect(errors).toEqual([]);
});

test('Phase 9D S7 failure, retry boundary and archive gate stay safe', async ({page}) => {
  await page.goto(`${BASE}/legacy`);
  await bootstrapProject(page);
  await page.getByRole('link', {name: '课堂与报告'}).click();
  await createCaptureViaUi(page);
  await page.locator('#phase9d-capture-list button').first().click();
  const transcribeRoute = '**/api/study/capture-sessions/*/transcribe';
  await page.route(transcribeRoute, route => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({detail: 'transcription_provider_not_configured'}),
  }));
  await page.getByRole('button', {name: '触发 deterministic 转写'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('转写 Provider 尚未配置');
  await expect(page.locator('body')).not.toContainText('transcription_provider_not_configured');
  await page.unroute(transcribeRoute);

  await page.route(transcribeRoute, route => route.fulfill({
    status: 200, contentType: 'application/json', body: '{bad',
  }));
  await page.getByRole('button', {name: '触发 deterministic 转写'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('转写失败，请重试');
  await page.unroute(transcribeRoute);
  await page.route(transcribeRoute, route => route.abort());
  await page.getByRole('button', {name: '触发 deterministic 转写'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('转写失败，请重试');
  await page.unroute(transcribeRoute);

  await page.getByRole('button', {name: '归档采集'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('当前采集状态不允许此操作');
  await expect(page.locator('body')).not.toContainText('private_backend_error');
});

test('Phase 9D S6 report preview, default-off delivery and safe audit', async ({page}) => {
  await page.goto(`${BASE}/legacy`);
  await bootstrapProject(page);
  await page.getByRole('link', {name: '课堂与报告'}).click();
  await page.locator('#phase9d-period-start').fill('2026-01-15');
  await page.locator('#phase9d-period-end').fill('2026-01-16');
  await page.locator('#phase9d-report-create').click();
  await expect(page.locator('#phase9d-status')).toContainText('报告已生成');
  await expect(page.locator('#phase9d-workspace')).toContainText('报告仅展示脱敏学习统计');
  await expect(page.locator('#phase9d-detail-title')).toContainText('报告 · daily');
  await page.getByRole('button', {name: '导出 JSON'}).click();
  await page.getByRole('button', {name: '导出 Markdown'}).click();
  await page.getByRole('button', {name: '执行交付检查'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('交付检查：已关闭');
  await expect(page.locator('#phase9d-workspace')).toContainText('交付状态：blocked');
  await expect(page.locator('#phase9d-workspace')).toContainText('结果：未发送');
  await page.getByRole('button', {name: '查看交付审计'}).click();
  await expect(page.locator('#phase9d-workspace')).toContainText('交付审计 · 1 次尝试');
  await expect(page.locator('body')).not.toContainText('stored_path');
  await expect(page.locator('body')).not.toContainText('answer_key');
  await expect(page.locator('body')).not.toContainText('secret');
  await expect(page.locator('body')).not.toContainText('private_backend_error');

  const report = await createReport(page);
  expect(report.id).toMatch(/^report_/);
});

test('Phase 9D S6 explicit dry-run is visible and never reports sent', async ({page}) => {
  stop();
  server = startServer('dry_run');
  await ready();
  await page.goto(`${BASE}/legacy`);
  await bootstrapProject(page);
  await page.getByRole('link', {name: '课堂与报告'}).click();
  await page.locator('#phase9d-period-start').fill('2026-01-15');
  await page.locator('#phase9d-period-end').fill('2026-01-16');
  await page.locator('#phase9d-report-create').click();
  await expect(page.locator('#phase9d-status')).toContainText('报告已生成');
  await page.getByRole('button', {name: '执行交付检查'}).click();
  await expect(page.locator('#phase9d-status')).toContainText('dry-run（未真实外发）');
  await expect(page.locator('#phase9d-workspace')).toContainText('本地 dry-run 已完成，未发送网络请求');
  await expect(page.locator('#phase9d-workspace')).toContainText('结果：未发送');
  await expect(page.locator('body')).not.toContainText('delivery_live_not_approved');
  await expect(page.locator('body')).not.toContainText('stored_path');
});
