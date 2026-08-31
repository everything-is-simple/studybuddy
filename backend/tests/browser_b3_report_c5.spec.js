const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/b3-report-c5';
const PORT = 8854;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT};
  delete env.STUDYBUDDY_AI_PROVIDER;
  delete env.STUDYBUDDY_AI_MODEL;
  delete env.STUDYBUDDY_AI_BASE_URL;
  delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}

async function ready() {
  await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, {timeout: 15000}).toBe(true);
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

async function createReport(page) {
  const seeded = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'report-scope.txt', mimeType: 'text/plain', buffer: Buffer.from('B3 C5 report scope seed')}}});
  expect(seeded.ok()).toBe(true);
  const response = await page.request.post(`${BASE}/api/study/reports`, {data: {report_kind: 'daily', timezone: 'UTC', period_start: '2026-01-15', period_end: '2026-01-16'}});
  expect(response.ok()).toBe(true);
  return response.json();
}

test.beforeEach(async () => { fs.rmSync(ROOT, {recursive: true, force: true}); server = startServer(); await ready(); });
test.afterEach(stop);

test('B3 C5 reports page renders safe projection, exports, reloads, and never presents delivery as sent', async ({page}) => {
  const errors = [];
  const external = [];
  page.on('console', message => { if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (!request.url().startsWith(BASE)) external.push(request.url()); });
  const report = await createReport(page);
  await page.goto(`${BASE}/app/reports.html?report_id=${encodeURIComponent(report.id)}`);
  await expect(page.locator('#report-detail-title')).toContainText('报告 · daily');
  await expect(page.locator('#report-detail')).toContainText('交付：未发送');
  await expect(page.locator('#report-detail')).toContainText('有效来源：0');
  await expect(page.locator('body')).not.toContainText(/stored_path|answer_key|safe_payload_json|secret|traceback|已发送/i);
  const jsonDownload = page.waitForEvent('download');
  await page.locator('#export-json').click();
  expect((await jsonDownload).suggestedFilename()).toBe('studybuddy-report.json');
  const markdownDownload = page.waitForEvent('download');
  await page.locator('#export-markdown').click();
  expect((await markdownDownload).suggestedFilename()).toBe('studybuddy-report.md');
  await page.reload();
  await expect(page.locator('#report-detail-title')).toContainText('报告 · daily');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test('B3 C5 reports page masks detail failures and permits list retry', async ({page}) => {
  await page.route('**/api/study/reports', route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'private_report_failure', path: 'H:/secret', traceback: 'hidden'})}));
  await page.goto(`${BASE}/app/reports.html`);
  await expect(page.locator('#report-status')).toContainText('请求失败，请重试');
  await expect(page.locator('#report-status')).not.toContainText(/private_report_failure|H:\/secret|traceback/i);
  await expect(page.locator('#retry-reports')).toBeVisible();
  await page.unroute('**/api/study/reports');
  await page.locator('#retry-reports').click();
  await expect(page.locator('#report-status')).toContainText('暂无报告');
});
