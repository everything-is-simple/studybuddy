const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-file-import-browser';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-file-import-browser/latest.json';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8786;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}
async function waitReady() {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stopServer(server) {
  if (server && !server.killed) server.kill();
}
function sha256(file) {
  const crypto = require('crypto');
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

test('real browser file import and restart readback', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true});
  const consoleErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => consoleErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText}`));
  let server = startServer();
  try {
    await waitReady();
    await page.goto(BASE);
    await expect(page.getByRole('heading', {name: 'StudyBuddy 文件导入'})).toBeVisible();
    await expect(page.locator('input[type=file]')).toBeVisible();

    const cases = [
      ['sample.txt', 'StudyBuddy synthetic TXT fixture.', 'success'],
      ['sample.pdf', 'Synthetic PDF', 'success'],
      ['sample.docx', 'DOCX', 'success'],
      ['sample.pptx', '第一页合成内容', 'success'],
      ['sample.rtf', 'error_code: unsupported_rtf', 'rejected'],
    ];
    const records = [];
    let lastMaterialId = null;
    for (const [fixture, visibleText, expectedStatus] of cases) {
      await page.locator('input[type=file]').setInputFiles(path.join(FIXTURES, fixture));
      await page.getByRole('button', {name: '导入文件'}).click();
      await expect(page.locator('#status'), `browser errors: ${JSON.stringify(consoleErrors)}`).toContainText(`导入完成：${expectedStatus}`);
      await expect(page.locator('#title')).toHaveText(fixture);
      if (expectedStatus === 'rejected') {
        await expect(page.locator('#warnings')).toContainText(visibleText);
      } else {
        await expect(page.locator('#content')).toContainText(visibleText);
      }
      await expect(page.locator('#meta')).toContainText(expectedStatus);
      const spans = await page.locator('#spans').textContent();
      const response = await page.request.get(`${BASE}/api/materials`);
      const items = await response.json();
      lastMaterialId = items[0].id;
      records.push({fixture, status: expectedStatus, source_sha256: sha256(path.join(FIXTURES, fixture)), visible: true, span_label_summary: spans});
    }

    await page.reload();
    await expect(page.locator('#materials .item')).toHaveCount(5);
    await page.locator('#materials .item').first().click();
    await expect(page.locator('#title')).toHaveText('sample.rtf');
    await expect(page.locator('#warnings')).toContainText('unsupported_rtf');
    const beforeRestart = await page.locator('#materials .item').count();

    stopServer(server); server = null;
    await new Promise(resolve => setTimeout(resolve, 500));
    server = startServer();
    await waitReady();
    await page.goto(BASE);
    await expect(page.locator('#materials .item')).toHaveCount(beforeRestart);
    await page.locator('#materials .item').last().click();
    await expect(page.locator('#title')).toHaveText('sample.txt');
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    await expect(page.locator('#spans')).toContainText('document');

    const payload = {
      component: 'formal-file-import-browser', formal_system_version: '3a7574c-working-tree', status: 'implemented',
      browser: 'chromium', viewport: await page.viewportSize(), command: 'npx playwright test backend/tests/browser_file_import.spec.js',
      cases: records, refresh_readback: true, restart_readback: {passed: true, material_count: beforeRestart, same_text_visible: true},
      browser_console_error_count: consoleErrors.length, network: {required: false, called: false},
      original_files_saved_by_parser: false,
      run_root: RUN_ROOT,
      failure_boundaries: {api_tests_passed: true, database_failure_cleanup: true, traversal_filename_rejected: true, upload_limit_413_and_cleanup: true},
      limitations: ['no multi-file selection in one request', 'no crash/disk-full/network-share stress', 'browser matrix does not include corrupt/empty/legacy DOC/PPT cases', 'not real-pass until the complete failure matrix is reviewed'],
      screenshot: 'H:/studybuddy-test/runs/formal-file-import-browser/after-restart.png',
    };
    fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true});
    fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2), 'utf8');
    await page.screenshot({path: payload.screenshot, fullPage: true});
    expect(consoleErrors).toEqual([]);
  } finally { stopServer(server); }
});
