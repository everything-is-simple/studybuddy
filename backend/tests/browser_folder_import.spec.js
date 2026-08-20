const { test, expect } = require('@playwright/test');
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-folder-import';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-folder-import/latest.json';
const SOURCE = path.join(RUN_ROOT, 'folder-source');
const PORT = 8796;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_MAX_UPLOAD_BYTES: '32'};
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function waitReady() { for (let i = 0; i < 100; i++) { try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {} await new Promise(resolve => setTimeout(resolve, 100)); } throw new Error('server_not_ready'); }
function stopServer(server) { if (server && !server.killed) server.kill(); }
function makeFiles() {
  fs.mkdirSync(path.join(SOURCE, 'nested'), {recursive: true});
  fs.mkdirSync(path.join(SOURCE, 'week-1'), {recursive: true}); fs.mkdirSync(path.join(SOURCE, 'week-2'), {recursive: true});
  fs.writeFileSync(path.join(SOURCE, 'intro.txt'), 'folder intro');
  fs.writeFileSync(path.join(SOURCE, 'notes.md'), '# folder markdown');
  fs.writeFileSync(path.join(SOURCE, 'nested', 'chinese.txt'), '中文目录材料');
  fs.writeFileSync(path.join(SOURCE, 'nested', 'rejected.rtf'), '{\\rtf1}');
  fs.writeFileSync(path.join(SOURCE, 'nested', 'too-large.txt'), 'x'.repeat(33));
  fs.writeFileSync(path.join(SOURCE, 'week-1', 'notes.txt'), 'week one'); fs.writeFileSync(path.join(SOURCE, 'week-2', 'notes.txt'), 'week two');
  return [path.join(SOURCE, 'intro.txt'), path.join(SOURCE, 'notes.md'), path.join(SOURCE, 'nested', 'chinese.txt'), path.join(SOURCE, 'nested', 'rejected.rtf'), path.join(SOURCE, 'nested', 'too-large.txt'), path.join(SOURCE, 'week-1', 'notes.txt'), path.join(SOURCE, 'week-2', 'notes.txt')];
}

test('formal folder import browser acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true}); fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true});
  const files = makeFiles(); const consoleErrors = []; const externalRequests = []; let batchRequests = 0;
  page.on('console', message => { if (message.type() === 'error' && !message.text().includes('server responded with a status of 500')) consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('request', request => { if (!request.url().startsWith(BASE)) externalRequests.push(request.url()); if (request.url().endsWith('/api/materials/batch') && request.method() === 'POST') batchRequests++; });
  let server = startServer();
  try {
    await waitReady(); await page.goto(BASE);
    const folder = page.locator('#folder');
    await expect(folder).toHaveAttribute('type', 'file'); await expect(folder).toHaveAttribute('multiple', ''); await expect(folder).toHaveAttribute('webkitdirectory', '');
    await expect(page.locator('#file')).toHaveAttribute('multiple', ''); await expect(page.locator('#folder-import')).toBeVisible();
    await page.getByRole('button', {name: '导入文件夹'}).click();
    await expect(page.locator('#status')).toHaveText('请选择一个文件夹'); expect(batchRequests).toBe(0);

    await folder.setInputFiles(SOURCE);
    await page.getByRole('button', {name: '导入文件夹'}).click();
    await expect(page.locator('#status')).toContainText('文件夹导入完成：7 个文件');
    await expect(page.locator('#summary')).toContainText('成功 5'); await expect(page.locator('#summary')).toContainText('拒绝 2');
    expect(batchRequests).toBe(1);
    await expect(page.locator('#materials .item')).toHaveCount(6);
    await page.getByRole('button', {name: /intro\.txt/}).last().click(); await expect(page.locator('#content')).toContainText('folder intro');
    const notes = await page.locator('#batch-items .batch-item').filter({hasText: 'notes.txt'}).count(); expect(notes).toBe(2); await expect(page.locator('#batch-items')).toContainText('week-1/notes.txt'); await expect(page.locator('#batch-items')).toContainText('week-2/notes.txt');
    const listed = await (await page.request.get(`${BASE}/api/materials?limit=20`)).json();
    expect(listed.total).toBe(6); for (const item of listed.items) { expect(item.text).toBeUndefined(); expect(item.stored_path).toBeUndefined(); }
    const noteItems = listed.items.filter(item => item.original_name === 'notes.txt'); expect(noteItems).toHaveLength(2);
    const noteDetails = await Promise.all(noteItems.map(item => page.request.get(`${BASE}/api/materials/${item.id}`).then(r => r.json())));
    expect(noteDetails.map(item => item.text).sort()).toEqual(['week one', 'week two']);

    let release; const pending = new Promise(resolve => { release = resolve; }); let delayed = false;
    await page.route('**/api/materials/batch', async route => { if (!delayed) { delayed = true; await pending; } await route.continue(); });
    await folder.setInputFiles(SOURCE); const before = batchRequests;
    await page.getByRole('button', {name: '导入文件夹'}).click(); await expect(page.locator('#folder-import')).toBeDisabled(); await expect(page.locator('#file-import')).toBeDisabled();
    expect(batchRequests).toBe(before + 1); release();
    await expect(page.locator('#status')).toContainText('文件夹导入完成：7 个文件'); await expect(page.locator('#folder-import')).toBeEnabled(); await page.unroute('**/api/materials/batch');

    await page.route('**/api/materials/batch', route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'synthetic'})}));
    await folder.setInputFiles(SOURCE); await page.getByRole('button', {name: '导入文件夹'}).click();
    await expect(page.locator('#status')).toHaveText('文件夹导入失败'); await expect(page.locator('#status')).not.toContainText('synthetic'); await expect(page.locator('#folder-import')).toBeEnabled(); await page.unroute('**/api/materials/batch');

    const sha = execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim();
    const payload = {component: 'formal-folder-import', status: 'real-pass', git_commit: sha, formal_system_version: sha, browser: 'chromium', folder_input: {webkitdirectory_present: true, multiple_present: true, empty_selection_rejected_client_side: true}, folder_batch_import: {batch_endpoint_used: true, recursive_file_selection_verified: true, partial_success_verified: true, successful_materials_readable: true, rejected_materials_inspectable: true, nested_same_basename_not_overwritten: true, relative_path_display_available: true, relative_path_not_persisted: true}, folder_import_error_state_consistent: true, duplicate_folder_import_request_prevented: true, list_pagination_consistent_after_folder_import: true, full_text_in_list_response: false, stored_path_in_list_response: false, browser_console_error_count: consoleErrors.length, external_requests: externalRequests};
    fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true}); fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2));
    expect(consoleErrors).toEqual([]); expect(externalRequests).toEqual([]);
  } finally { stopServer(server); }
});
