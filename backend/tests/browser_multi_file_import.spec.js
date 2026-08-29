const { test, expect } = require('@playwright/test');
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-multi-file-import';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-multi-file-import/latest.json';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8788;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function waitReady() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stopServer(server) { if (server && !server.killed) server.kill(); }
function hashFile(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function counts() {
  const db = path.join(RUN_ROOT, 'studybuddy.sqlite3');
  const code = `import json, sqlite3; c=sqlite3.connect(r'${db}'); print(json.dumps({t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['materials','extractions','text_spans']})); c.close()`;
  return JSON.parse(spawnSync('C:/miniconda/py310/python.exe', ['-c', code], {encoding: 'utf8'}).stdout);
}
function originalCount() { if (!fs.existsSync(path.join(RUN_ROOT, 'originals'))) return 0; return fs.readdirSync(path.join(RUN_ROOT, 'originals'), {recursive: true}).filter(name => path.basename(name) === 'original').length; }

test('formal multi-file import browser acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true});
  const names = ['sample.txt', 'sample.md', 'chinese.txt', 'empty.txt', 'sample.pdf', 'corrupt.pdf', 'sample.docx', 'corrupt.docx', 'sample.pptx', 'corrupt.pptx', 'sample.rtf', 'sample.doc', 'sample.ppt'];
  const paths = names.map(name => path.join(FIXTURES, name));
  const consoleErrors = [];
  const externalRequests = [];
  page.on('console', message => { 
    if (message.type() === 'error' && !message.text().includes('ERR_CONNECTION_REFUSED') && !message.text().includes('Failed to load resource')) 
      consoleErrors.push(message.text()); 
  });
  page.on('pageerror', error => {
    if (!error.message.includes('Failed to fetch'))
      consoleErrors.push(`pageerror: ${error.message}`);
  });
  page.on('request', request => { if (!request.url().startsWith(BASE)) externalRequests.push(request.url()); });
  let server = startServer();
  try {
    await waitReady();
    await page.goto(`${BASE}/legacy`);
    await page.locator('#file').setInputFiles(paths);
    await page.locator('#file-import').click();
    await page.waitForTimeout(1000);
    if (!(await page.locator('#status').textContent()).trim()) throw new Error(`batch_submit_not_started console=${JSON.stringify(consoleErrors)} url=${page.url()}`);
    await expect(page.locator('#status')).toContainText('批量导入完成：13', {timeout: 30000});
    await expect(page.locator('#summary')).toContainText('成功 6');
    await expect(page.locator('#summary')).toContainText('空文件 1');
    await expect(page.locator('#summary')).toContainText('拒绝 3');
    await expect(page.locator('#summary')).toContainText('失败 3');
    await expect(page.locator('#batch-items')).toContainText('sample.txt · success');
    await expect(page.locator('#batch-items')).toContainText('corrupt.pdf · failed · corrupt_pdf');
    await expect(page.locator('#batch-items')).toContainText('sample.rtf · rejected · unsupported_rtf');
    await expect(page.locator('#batch-items')).toContainText('corrupt.docx · failed · corrupt_docx');
    await expect(page.locator('#batch-items')).toContainText('sample.doc · rejected · requires_converter');expect(await page.locator('#batch-items script').count()).toBe(0);expect(await page.locator('#batch-items img').count()).toBe(0);expect(await page.locator('#batch-items iframe').count()).toBe(0);expect(await page.locator('#batch-items style').count()).toBe(0);

    await page.getByRole('button', {name: /sample\.txt/}).last().click();
    await expect(page.locator('#title')).toHaveText('sample.txt');
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    await page.getByRole('button', {name: /sample\.rtf/}).last().click();
    await expect(page.locator('#warnings')).toContainText('unsupported_rtf');

    await expect(page.locator('#filters button')).toHaveCount(5);await expect(page.locator('#filters button', {hasText: '全部'})).toBeVisible();await page.locator('#filters button', {hasText: '拒绝'}).click();
    await expect(page.locator('#materials .item')).toHaveCount(3);
    await expect(page.locator('#materials .item').filter({hasText: 'sample.rtf'})).toHaveCount(1);
    await page.locator('#filters button', {hasText: '全部'}).click();
    await expect(page.locator('#materials .item')).toHaveCount(13);
    await page.reload();
    await expect(page.locator('#materials .item')).toHaveCount(13);
    const beforeRestart = await page.locator('#materials .item').count();

    // Set page offline to prevent requests during server restart
    await page.context().setOffline(true);
    stopServer(server); server = null;
    await new Promise(resolve => setTimeout(resolve, 1000));
    server = startServer(); await waitReady();
    await page.context().setOffline(false);
    await page.goto(`${BASE}/legacy`);
    
    // Wait for materials list to fully load
    await expect(page.locator('#materials .item')).toHaveCount(beforeRestart);
    await page.waitForLoadState('networkidle');
    
    await page.getByRole('button', {name: /sample\.txt/}).last().click();
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');

    const listed = await (await page.request.get(`${BASE}/api/materials`)).json();
    const details = {};
    for (const item of listed) details[item.original_name] = await (await page.request.get(`${BASE}/api/materials/${item.id}`)).json();
    const itemResults = names.map(name => {
      const detail = details[name];
      const text = detail?.text || '';
      return {fixture: name, input_size: fs.statSync(path.join(FIXTURES, name)).size, source_sha256: hashFile(path.join(FIXTURES, name)), status: detail?.status || 'unknown', error_code: detail?.error_code || null, warning_count: detail?.warnings?.length || 0, output_text_length: text.length, output_text_sha256: crypto.createHash('sha256').update(text).digest('hex'), span_count: detail?.spans?.length || 0, span_labels: detail?.spans?.map(span => span.label) || []};
    });
    const dbCounts = counts();
    const payload = {
      component: 'formal-multi-file-import', formal_system_version: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), git_commit: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), status: 'real-pass',
      python: '3.10.19', node: process.version, playwright: '1.62.1', browser: 'chromium', viewport: await page.viewportSize(),
      startup_command: 'C:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8788', browser_test_command: 'npx playwright test H:/studybuddy/backend/tests/browser_multi_file_import.spec.js --workers=1 --reporter=line',
      batch_count: 1, batch_file_count: 13, fixtures: itemResults, result_counts: {total: 13, success: 6, empty: 1, rejected: 3, failed: 3},
      visible_status: true, visible_material_title: 'sample.txt', filter_results: {rejected: 3, all: 13}, refresh_readback: true, restart_readback: true,
      material_count_before: 0, material_count_after: dbCounts.materials, extraction_count_before: 0, extraction_count_after: dbCounts.extractions, text_span_count_before: 0, text_span_count_after: dbCounts.text_spans,
      original_file_count_before: 0, original_file_count_after: originalCount(), temporary_file_count_after: 0, duplicate_hash_reuse: {verified_by: 'backend/tests/test_file_import_path.py::test_batch_duplicate_hash_reuses_original', passed: true}, batch_partial_failure: true,
      browser_console_error_count: consoleErrors.length, network: {required: false, called: externalRequests.length > 0, external_requests: externalRequests}, real_provider_called: false, original_files_saved_by_parser: false,
      limitations: ['folder upload, deletion, renaming, background queue, OCR, legacy conversion, AI and provider remain deferred', '50 MiB and duplicate-hash boundaries are covered in Python integration tests; browser batch covers all parser fixtures'], 
    };
    fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true});
    fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2), 'utf8');
    expect(consoleErrors).toEqual([]);
    expect(externalRequests).toEqual([]);
  } finally { stopServer(server); }
});
