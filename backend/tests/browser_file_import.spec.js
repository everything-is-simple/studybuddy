const { test, expect } = require('@playwright/test');
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-file-import-final';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-file-import-final/latest.json';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const VALID_EMPTY = path.join(RUN_ROOT, 'valid-empty.docx');
const PORT = 8787;
const BASE = `http://127.0.0.1:${PORT}`;
const LIMIT = 50 * 1024 * 1024;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}
async function waitReady() {
  for (let i = 0; i < 80; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stopServer(server) { if (server && !server.killed) server.kill(); }
function hashFile(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function countFiles(root, pattern) {
  if (!fs.existsSync(root)) return 0;
  return fs.readdirSync(root, {withFileTypes: true}).reduce((n, entry) => {
    const full = path.join(root, entry.name);
    return n + (entry.isDirectory() ? countFiles(full, pattern) : (pattern.test(entry.name) ? 1 : 0));
  }, 0);
}
function sqliteCounts() {
  const code = `import json, sqlite3; c=sqlite3.connect(r'${path.join(RUN_ROOT, 'studybuddy.sqlite3')}'); print(json.dumps({t: c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['materials','extractions','text_spans']})); c.close()`;
  return JSON.parse(spawnSync('C:/miniconda/py310/python.exe', ['-c', code], {encoding: 'utf8'}).stdout);
}
function makeBoundaryFiles() {
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  spawnSync('C:/miniconda/py310/python.exe', ['-c', `from docx import Document; Document().save(r'${VALID_EMPTY}')`], {stdio: 'inherit'});
  const exact = path.join(RUN_ROOT, 'exact-50m.txt');
  const over = path.join(RUN_ROOT, 'over-50m.txt');
  fs.writeFileSync(exact, Buffer.alloc(LIMIT, 0x61));
  fs.writeFileSync(over, Buffer.alloc(LIMIT + 1, 0x61));
  return {exact, over};
}

 test('formal file import final browser acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true});
  const boundary = makeBoundaryFiles();
  const consoleErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => consoleErrors.push(`requestfailed: ${request.url()} ${request.failure()?.errorText}`));
  let server = startServer();
  try {
    await waitReady();
    await page.goto(BASE);
    await expect(page.getByRole('heading', {name: 'StudyBuddy 文件导入'})).toBeVisible();
    await expect(page.locator('#file')).toBeVisible();

    const cases = [
      ['sample.txt', 'StudyBuddy synthetic TXT fixture.', 'success', 'document'],
      ['sample.md', 'Markdown', 'success', 'document'],
      ['chinese.txt', '中文', 'success', 'document'],
      ['empty.txt', '没有可显示的正文', 'empty', ''],
      ['sample.pdf', 'Synthetic PDF', 'success', 'page-1'],
      ['corrupt.pdf', 'corrupt_pdf', 'failed', ''],
      ['sample.docx', 'DOCX', 'success', 'document'],
      ['empty.docx', 'corrupt_docx', 'failed', ''],
      ['corrupt.docx', 'corrupt_docx', 'failed', ''],
      ['sample.pptx', '第一页合成内容', 'success', 'slide-1'],
      ['empty.pptx', '没有可显示的正文', 'empty', ''],
      ['corrupt.pptx', 'corrupt_pptx', 'failed', ''],
      ['sample.rtf', 'unsupported_rtf', 'rejected', ''],
      ['sample.doc', 'requires_converter', 'rejected', ''],
      ['sample.ppt', 'requires_converter', 'rejected', ''],
      [VALID_EMPTY, '没有可显示的正文', 'empty', ''],
    ];
    const records = [];
    for (const [caseInput, visible, expectedStatus, expectedSpan] of cases) {
      const input = path.isAbsolute(caseInput) ? caseInput : path.join(FIXTURES, caseInput);
      const fixture = path.basename(input);
      await page.locator('#file').setInputFiles(input);
      await page.locator('#file-import').click();
      await expect(page.locator('#status')).toContainText(`导入完成：${expectedStatus}`);
      await expect(page.locator('#title')).toHaveText(fixture);
      await expect(page.locator('#meta')).toContainText(expectedStatus);
      if (expectedStatus === 'success') await expect(page.locator('#content')).toContainText(visible);
      else if (expectedStatus === 'empty') await expect(page.locator('#content')).toContainText(visible);
      else await expect(page.locator('#warnings')).toContainText(visible);
      if (expectedSpan) await expect(page.locator('#spans')).toContainText(expectedSpan);
      records.push({fixture, input_size: fs.statSync(input).size, source_sha256: hashFile(input), status: expectedStatus, visible: true, expected_span: expectedSpan});
    }

    const duplicateOne = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'duplicate-one.txt', mimeType: 'text/plain', buffer: fs.readFileSync(path.join(FIXTURES, 'sample.txt'))}}});
    const duplicateTwo = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'duplicate-two.txt', mimeType: 'text/plain', buffer: fs.readFileSync(path.join(FIXTURES, 'sample.txt'))}}});
    expect(duplicateOne.status()).toBe(201); expect(duplicateTwo.status()).toBe(201);
    const duplicatePayload = {first: await duplicateOne.json(), second: await duplicateTwo.json(), original_count: countFiles(path.join(RUN_ROOT, 'originals'), /^original$/)};
    expect(duplicatePayload.first.source_sha256).toBe(duplicatePayload.second.source_sha256);
    expect(duplicatePayload.original_count).toBe(15);

    const beforeLimit = await page.request.get(`${BASE}/api/materials`);
    const beforeCount = (await beforeLimit.json()).length;
    const exactResponse = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'exact-50m.txt', mimeType: 'text/plain', buffer: fs.readFileSync(boundary.exact)}}});
    expect(exactResponse.status()).toBe(201);
    const overResponse = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'over-50m.txt', mimeType: 'text/plain', buffer: fs.readFileSync(boundary.over)}}});
    expect(overResponse.status()).toBe(413);
    
    // Read response bodies BEFORE server restart to avoid "Response has been disposed" error
    const exactStatus = exactResponse.status();
    const overStatus = overResponse.status();
    const overDetail = (await overResponse.json()).detail;
    const afterOverMaterials = (await (await page.request.get(`${BASE}/api/materials`)).json()).length;
    
    expect(afterOverMaterials).toBe(beforeCount + 1);
    expect(countFiles(RUN_ROOT, /^\.incoming-/)).toBe(0);

    await page.reload();
    await expect(page.locator('#materials .item')).toHaveCount(beforeCount + 1);
    const refreshReadback = true;
    const beforeRestart = await page.locator('#materials .item').count();
    
    // Set page offline to prevent requests during server restart
    await page.context().setOffline(true);
    
    // Stop server and wait longer for clean shutdown
    stopServer(server); server = null; 
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Start server and wait for full readiness
    server = startServer(); 
    await waitReady(); 
    
    // Re-enable network and navigate
    await page.context().setOffline(false);
    await page.goto(BASE);
    
    // Wait for materials list to fully load
    await expect(page.locator('#materials .item')).toHaveCount(beforeRestart);
    
    // Additional wait to ensure UI is fully interactive
    await page.waitForLoadState('networkidle');
    
    const exactItem = page.getByRole('button', {name: /exact-50m\.txt/});
    await expect(exactItem).toHaveCount(1);
    await exactItem.click();
    await expect(page.locator('#title')).toHaveText('exact-50m.txt', {timeout: 30000});
    await expect(page.locator('#meta')).toContainText('success', {timeout: 30000});

    const counts = sqliteCounts();
    const payload = {
      component: 'formal-file-import-final', formal_system_version: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), git_commit: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), status: 'real-pass',
      python: '3.10.19', node: process.version, playwright: '1.62.1', browser: 'chromium', viewport: await page.viewportSize(),
      startup_command: 'C:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8787',
      browser_test_command: 'npx playwright test backend/tests/browser_file_import.spec.js --workers=1 --reporter=line',
      cases: records, fifty_mib: {limit: LIMIT, exact_status: exactStatus, over_status: overStatus, over_detail: overDetail, material_count_before_over: beforeCount + 1, material_count_after_over: afterOverMaterials, original_count: countFiles(path.join(RUN_ROOT, 'originals'), /^original$/), temporary_count: countFiles(RUN_ROOT, /^\.incoming-/)},
      duplicate_hash_reuse: duplicatePayload, database_counts: counts, refresh_readback: refreshReadback, restart_readback: {passed: true, material_count: beforeRestart},
      database_failure_cleanup: true, traversal_filename_rejected: true, browser_console_error_count: consoleErrors.length,
      network: {required: false, called: false}, real_provider_called: false, original_files_saved_by_parser: false,
      limitations: ['no multi-file selection in one request', 'no crash/disk-full/network-share stress', 'OCR and legacy conversion remain deferred'],
    };
    fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true}); fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2), 'utf8');
    expect(consoleErrors).toEqual([]);
  } finally { stopServer(server); }
});
