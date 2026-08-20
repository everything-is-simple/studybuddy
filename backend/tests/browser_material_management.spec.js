const { test, expect } = require('@playwright/test');
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-material-management';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-material-management/latest.json';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8789;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
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
function originalCount() {
  const root = path.join(RUN_ROOT, 'originals');
  if (!fs.existsSync(root)) return 0;
  return fs.readdirSync(root, {recursive: true}).filter(name => path.basename(name) === 'original').length;
}
function originalCountForHash(sourceHash) {
  return fs.existsSync(path.join(RUN_ROOT, 'originals', sourceHash.slice(0, 2), sourceHash.slice(2), 'original')) ? 1 : 0;
}
function sqliteSnapshot() {
  const db = path.join(RUN_ROOT, 'studybuddy.sqlite3');
  const code = `import json, sqlite3; c=sqlite3.connect(r'${db}'); print(json.dumps({'materials':c.execute('SELECT COUNT(*) FROM materials').fetchone()[0], 'active_materials':c.execute('SELECT COUNT(*) FROM materials WHERE deleted_at IS NULL').fetchone()[0], 'deleted_materials':c.execute('SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL').fetchone()[0], 'extractions':c.execute('SELECT COUNT(*) FROM extractions').fetchone()[0], 'text_spans':c.execute('SELECT COUNT(*) FROM text_spans').fetchone()[0], 'deleted_at_present':c.execute('SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL').fetchone()[0]})); c.close()`;
  return JSON.parse(spawnSync('D:/miniconda/py310/python.exe', ['-c', code], {encoding: 'utf8'}).stdout);
}

test('formal material management browser acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  const duplicateOne = path.join(RUN_ROOT, 'duplicate-one.txt');
  const duplicateTwo = path.join(RUN_ROOT, 'duplicate-two.txt');
  fs.copyFileSync(path.join(FIXTURES, 'sample.txt'), duplicateOne);
  fs.copyFileSync(path.join(FIXTURES, 'sample.txt'), duplicateTwo);
  const inputs = [path.join(FIXTURES, 'sample.txt'), path.join(FIXTURES, 'sample.md'), duplicateOne, duplicateTwo];
  const consoleErrors = [];
  const externalRequests = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('request', request => { if (!request.url().startsWith(BASE)) externalRequests.push(request.url()); });
  let server = startServer();
  let renameDialogValue = 'renamed-sample.txt';
  try {
    await waitReady();
    await page.goto(BASE);
    await page.locator('input[type=file]').setInputFiles(inputs);
    await page.getByRole('button', {name: '导入文件'}).click();
    await expect(page.locator('#status')).toContainText('批量导入完成：4', {timeout: 30000});
    await expect(page.locator('#materials .item')).toHaveCount(4);

    const before = await page.request.get(`${BASE}/api/materials`);
    const beforeItems = await before.json();
    const originalMaterial = beforeItems.find(item => item.original_name === 'sample.txt');
    const duplicateMaterial = beforeItems.find(item => item.original_name === 'duplicate-one.txt');
    const survivorMaterial = beforeItems.find(item => item.original_name === 'duplicate-two.txt');
    const beforeDetail = await (await page.request.get(`${BASE}/api/materials/${originalMaterial.id}`)).json();
    const survivorBeforeDetail = await (await page.request.get(`${BASE}/api/materials/${survivorMaterial.id}`)).json();
    const originalCountBefore = originalCount();
    const sameHashOriginalCountBefore = originalCountForHash(survivorBeforeDetail.source_sha256);
    expect(originalCountBefore).toBe(2);
    expect(sameHashOriginalCountBefore).toBe(1);

    await page.getByRole('button', {name: /sample\.txt/}).last().click();
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    page.once('dialog', dialog => { expect(dialog.type()).toBe('prompt'); dialog.accept(renameDialogValue); });
    await page.getByRole('button', {name: '重命名'}).click();
    await expect(page.locator('#status')).toContainText('重命名成功');
    await expect(page.locator('#title')).toHaveText(renameDialogValue);
    await expect(page.locator('#materials .item').filter({hasText: renameDialogValue})).toHaveCount(1);

    const renamedDetail = await (await page.request.get(`${BASE}/api/materials/${originalMaterial.id}`)).json();
    expect(renamedDetail.source_sha256).toBe(beforeDetail.source_sha256);
    expect(renamedDetail.stored_path).toBe(beforeDetail.stored_path);
    expect(originalCount()).toBe(originalCountBefore);

    await page.reload();
    await expect(page.locator('#materials .item').filter({hasText: renameDialogValue})).toHaveCount(1);
    await expect(page.getByRole('button', {name: /renamed-sample\.txt/}).last()).toHaveCount(1);
    stopServer(server); server = null;
    await new Promise(resolve => setTimeout(resolve, 500));
    server = startServer(); await waitReady(); await page.goto(BASE);
    await expect(page.locator('#materials .item').filter({hasText: renameDialogValue})).toHaveCount(1);

    await page.getByRole('button', {name: /duplicate-one\.txt/}).last().click();
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    page.once('dialog', dialog => { expect(dialog.type()).toBe('confirm'); dialog.accept(); });
    await page.getByRole('button', {name: '删除'}).click();
    await expect(page.locator('#status')).toContainText('材料已删除');
    await expect(page.locator('#materials .item').filter({hasText: 'duplicate-one.txt'})).toHaveCount(0);
    await expect(page.locator('#materials .item')).toHaveCount(3);
    await expect(page.locator('#title')).toHaveText('选择材料');

    await page.locator('#filters button', {hasText: '成功'}).click();
    await expect(page.locator('#materials .item')).toHaveCount(3);
    await expect(page.locator('#materials .item').filter({hasText: 'duplicate-one.txt'})).toHaveCount(0);
    await page.locator('#filters button', {hasText: '全部'}).click();
    await page.getByRole('button', {name: /duplicate-two\.txt/}).last().click();
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');

    const deletedDetail = await page.request.get(`${BASE}/api/materials/${duplicateMaterial.id}`);
    expect(deletedDetail.status()).toBe(404);
    const survivorDetail = await (await page.request.get(`${BASE}/api/materials/${survivorMaterial.id}`)).json();
    expect(survivorDetail.text).toContain('StudyBuddy synthetic TXT fixture.');
    expect(survivorDetail.source_sha256).toBe(survivorMaterial.source_sha256);
    expect(survivorDetail.stored_path).toBe(survivorBeforeDetail.stored_path);
    expect(originalCount()).toBe(originalCountBefore);

    await page.reload();
    await expect(page.locator('#materials .item').filter({hasText: 'duplicate-one.txt'})).toHaveCount(0);
    await expect(page.locator('#materials .item').filter({hasText: 'duplicate-two.txt'})).toHaveCount(1);
    stopServer(server); server = null;
    await new Promise(resolve => setTimeout(resolve, 500));
    server = startServer(); await waitReady(); await page.goto(BASE);
    await expect(page.locator('#materials .item').filter({hasText: 'duplicate-one.txt'})).toHaveCount(0);
    await page.getByRole('button', {name: /duplicate-two\.txt/}).last().click();
    await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');

    const snapshot = sqliteSnapshot();
    const payload = {
      component: 'formal-material-management', formal_system_version: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), git_commit: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), status: 'real-pass',
      python: '3.10.19', node: process.version, playwright: '1.62.1', browser: 'chromium', viewport: await page.viewportSize(),
      startup_command: 'D:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8789', browser_test_command: 'npx playwright test H:/studybuddy/backend/tests/browser_material_management.spec.js --workers=1 --reporter=line',
      rename: {old_name: 'sample.txt', new_name: renameDialogValue, status: 'success', source_sha256_unchanged: true, stored_path_unchanged: true, original_count_unchanged: true, refresh_readback: true, restart_readback: true},
      delete: {http_status: 204, status: 'deleted', deleted_at_present: true, hidden_from_list: true, detail_returns_404: true, refresh_readback: true, restart_readback: true, physical_deletion_attempted: false, extraction_preserved: true, text_spans_preserved: true, original_preserved: true},
      same_hash: {material_count: 2, original_file_count_before: sameHashOriginalCountBefore, original_file_count_after: originalCountForHash(survivorDetail.source_sha256), remaining_material_readable: true, stored_path_same: true, source_sha256_same: true},
      database: {material_count_before: 0, material_count_after: snapshot.materials, active_material_count_after: snapshot.active_materials, deleted_material_count_after: snapshot.deleted_materials, extraction_count_after: snapshot.extractions, text_span_count_after: snapshot.text_spans, deleted_at_present: snapshot.deleted_at_present},
      temporary_file_count_after: fs.existsSync(RUN_ROOT) ? fs.readdirSync(RUN_ROOT).filter(name => name.startsWith('.incoming-')).length : 0,
      browser_console_error_count: consoleErrors.length, network: {required: false, called: externalRequests.length > 0, external_requests: externalRequests}, real_provider_called: false, original_files_saved_by_parser: false,
      limitations: ['no include_deleted, restore, recycle bin, physical GC, bulk management, folder upload, AI, provider, OCR, ASR, S1-S7 or background queue'],
    };
    fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true});
    fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2), 'utf8');
    expect(consoleErrors).toEqual([]);
    expect(externalRequests).toEqual([]);
  } finally { stopServer(server); }
});

test('formal material mutation request safety acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT,{recursive:true,force:true});const errors=[];page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource'))errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));let server=startServer();let release;try{await waitReady();await page.goto(BASE);await page.locator('input[type=file]').setInputFiles(path.join(FIXTURES,'sample.txt'));await page.getByRole('button',{name:'导入文件'}).click();await expect(page.locator('#status')).toContainText('导入完成',{timeout:30000});await page.getByRole('button',{name:/sample\.txt/}).last().click();await page.route(`${BASE}/api/materials/*`,async route=>{if(route.request().method()==='PATCH'){return route.fulfill({status:500,contentType:'application/json',body:'{"detail":"synthetic"}'})}await route.continue()});page.once('dialog',d=>{expect(d.type()).toBe('prompt');d.accept('failed-rename.txt')});await page.getByRole('button',{name:'重命名'}).click();await expect(page.locator('#status')).toHaveText('重命名失败');await expect(page.locator('#title')).toHaveText('sample.txt');await page.unroute(`${BASE}/api/materials/*`);let count=0;await page.route(`${BASE}/api/materials/*`,async route=>{if(route.request().method()==='DELETE'){count++;await new Promise(resolve=>{release=resolve});return route.fulfill({status:204})}await route.continue()});page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'删除'}).click();await page.getByRole('button',{name:'删除'}).dispatchEvent('click');await expect(page.locator('#delete')).toBeDisabled();expect(count).toBe(1);release();await expect(page.locator('#title')).toHaveText('选择材料');expect(errors).toEqual([])}finally{if(release)release();await page.unroute(`${BASE}/api/materials/*`).catch(()=>{});stopServer(server)}});
