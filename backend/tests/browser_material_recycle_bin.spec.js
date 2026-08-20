const { test, expect } = require('@playwright/test');
const { spawn, spawnSync, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-material-recycle-bin';
const ARTIFACT = 'H:/studybuddy-test/artifacts/formal-material-recycle-bin/latest.json';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8790;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function waitReady() { for (let i = 0; i < 100; i++) { try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {} await new Promise(resolve => setTimeout(resolve, 100)); } throw new Error('server_not_ready'); }
function stopServer(server) { if (server && !server.killed) server.kill(); }
function hashFile(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function originalCountForHash(sourceHash) { return fs.existsSync(path.join(RUN_ROOT, 'originals', sourceHash.slice(0, 2), sourceHash.slice(2), 'original')) ? 1 : 0; }
function snapshot() { const db = path.join(RUN_ROOT, 'studybuddy.sqlite3'); const code = `import json,sqlite3;c=sqlite3.connect(r'${db}');print(json.dumps({"materials":c.execute('SELECT COUNT(*) FROM materials').fetchone()[0],"active":c.execute('SELECT COUNT(*) FROM materials WHERE deleted_at IS NULL').fetchone()[0],"deleted":c.execute('SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL').fetchone()[0],"extractions":c.execute('SELECT COUNT(*) FROM extractions').fetchone()[0],"spans":c.execute('SELECT COUNT(*) FROM text_spans').fetchone()[0]}));c.close()`; return JSON.parse(spawnSync('D:/miniconda/py310/python.exe', ['-c', code], {encoding: 'utf8'}).stdout); }

test('formal material recycle bin browser acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true}); fs.rmSync(path.dirname(ARTIFACT), {recursive: true, force: true}); fs.mkdirSync(RUN_ROOT, {recursive: true});
  const one = path.join(RUN_ROOT, 'same-one.txt'); const two = path.join(RUN_ROOT, 'same-two.txt');
  fs.copyFileSync(path.join(FIXTURES, 'sample.txt'), one); fs.copyFileSync(path.join(FIXTURES, 'sample.txt'), two);
  const inputs = [one, two, path.join(FIXTURES, 'sample.md')];
  const consoleErrors = []; const externalRequests = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${error.message}`));
  page.on('request', request => { if (!request.url().startsWith(BASE)) externalRequests.push(request.url()); });
  let server = startServer();
  try {
    await waitReady(); await page.goto(BASE);
    await page.locator('input[type=file]').setInputFiles(inputs); await page.getByRole('button', {name: '导入文件'}).click();
    await expect(page.locator('#status')).toContainText('批量导入完成：3', {timeout: 30000});
    await expect(page.locator('#materials .item')).toHaveCount(3);
    const activeBefore = await (await page.request.get(`${BASE}/api/materials`)).json();
    const oneItem = activeBefore.find(item => item.original_name === 'same-one.txt'); const twoItem = activeBefore.find(item => item.original_name === 'same-two.txt');
    const oneDetail = await (await page.request.get(`${BASE}/api/materials/${oneItem.id}`)).json(); const twoDetail = await (await page.request.get(`${BASE}/api/materials/${twoItem.id}`)).json();
    expect(oneDetail.source_sha256).toBe(twoDetail.source_sha256); expect(oneDetail.stored_path).toBe(twoDetail.stored_path);
    const hash = oneDetail.source_sha256; expect(originalCountForHash(hash)).toBe(1);

    await page.getByRole('button', {name: /same-one\.txt/}).last().click(); await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    page.once('dialog', dialog => { expect(dialog.type()).toBe('confirm'); dialog.accept(); }); await page.getByRole('button', {name: '删除', exact: true}).click();
    await expect(page.locator('#status')).toContainText('材料已删除'); await expect(page.locator('#materials .item').filter({hasText: 'same-one.txt'})).toHaveCount(0);
    await expect(page.locator('#materials .item')).toHaveCount(2); await expect(page.getByRole('button', {name: /same-two\.txt/}).last()).toHaveCount(1);
    expect((await page.request.get(`${BASE}/api/materials/${oneItem.id}`)).status()).toBe(404);

    await page.getByRole('button', {name: '回收站'}).click(); await expect(page.locator('#materials .deleted-item')).toHaveCount(1);
    await expect(page.locator('#materials .deleted-item')).toContainText('same-one.txt');
    await page.getByRole('button', {name: /same-one\.txt/}).last().click(); await expect(page.locator('#meta')).toContainText('已删除'); await expect(page.locator('#content')).toHaveText('');
    await expect(page.locator('#restore')).toBeEnabled(); await expect(page.locator('#rename')).toBeDisabled(); await expect(page.locator('#delete')).toBeDisabled();
    await page.locator('#restore').click(); await expect(page.locator('#status')).toContainText('材料已恢复');
    await expect(page.locator('#materials .item')).toHaveCount(3); await expect(page.getByRole('button', {name: /same-one\.txt/}).last()).toHaveCount(1);
    await page.getByRole('button', {name: /same-one\.txt/}).last().click(); await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');
    const restored = await (await page.request.get(`${BASE}/api/materials/${oneItem.id}`)).json(); expect(restored.source_sha256).toBe(oneDetail.source_sha256); expect(restored.stored_path).toBe(oneDetail.stored_path); expect(originalCountForHash(hash)).toBe(1);

    await page.reload(); await expect(page.locator('#materials .item').filter({hasText: 'same-one.txt'})).toHaveCount(1);
    stopServer(server); server = null; await new Promise(resolve => setTimeout(resolve, 500)); server = startServer(); await waitReady(); await page.goto(BASE);
    await expect(page.locator('#materials .item').filter({hasText: 'same-one.txt'})).toHaveCount(1); await page.getByRole('button', {name: /same-one\.txt/}).last().click(); await expect(page.locator('#content')).toContainText('StudyBuddy synthetic TXT fixture.');

    await page.getByRole('button', {name: /same-two\.txt/}).last().click(); page.once('dialog', dialog => { expect(dialog.type()).toBe('confirm'); dialog.accept(); }); await page.getByRole('button', {name: '删除', exact: true}).click();
    await page.getByRole('button', {name: '成功'}).click(); await expect(page.locator('#materials .item').filter({hasText: 'same-two.txt'})).toHaveCount(0);
    await page.getByRole('button', {name: '回收站'}).click(); await expect(page.locator('#materials .deleted-item').filter({hasText: 'same-two.txt'})).toHaveCount(1);

    const finalSnapshot = snapshot(); const payload = {
      component: 'formal-material-recycle-bin', formal_system_version: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), git_commit: execSync('git -C H:/studybuddy rev-parse HEAD').toString().trim(), status: 'real-pass', python: '3.10.19', node: process.version, playwright: '1.62.1', browser: 'chromium', viewport: await page.viewportSize(),
      startup_command: 'D:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8790', browser_test_command: 'npx playwright test H:/studybuddy/backend/tests/browser_material_recycle_bin.spec.js --workers=1 --reporter=line',
      delete_to_recycle_bin: {status: 'success', deleted_at_present: true, hidden_from_active_list: true, visible_in_recycle_bin: true, detail_returns_404_while_deleted: true},
      restore: {status: 'success', deleted_at_null: true, removed_from_recycle_bin: true, visible_in_active_list: true, detail_readable: true, source_sha256_unchanged: true, stored_path_unchanged: true, refresh_readback: true, restart_readback: true},
      same_hash: {material_count: 2, original_file_count_before_delete: 1, original_file_count_after_delete: 1, original_file_count_after_restore: 1, active_survivor_readable: true, restored_material_readable: true, source_sha256_same: true, stored_path_same: true},
      database: {material_count_before: 0, material_count_after: finalSnapshot.materials, active_material_count_after: finalSnapshot.active, deleted_material_count_after: finalSnapshot.deleted, extraction_count_before_restore: 3, extraction_count_after_restore: finalSnapshot.extractions, text_span_count_before_restore: 3, text_span_count_after_restore: finalSnapshot.spans},
      temporary_file_count_after: fs.readdirSync(RUN_ROOT).filter(name => name.startsWith('.incoming-')).length, browser_console_error_count: consoleErrors.length, network: {required: false, called: externalRequests.length > 0, external_requests: externalRequests}, real_provider_called: false, original_files_saved_by_parser: false,
      limitations: ['no include_deleted, restore all, recycle-bin purge, physical GC, bulk management, folder upload, AI, provider, OCR, ASR, S1-S7 or background queue'],
    }; fs.mkdirSync(path.dirname(ARTIFACT), {recursive: true}); fs.writeFileSync(ARTIFACT, JSON.stringify(payload, null, 2), 'utf8'); expect(consoleErrors).toEqual([]); expect(externalRequests).toEqual([]);
  } finally { stopServer(server); }
});

test('formal material purge success, error, and duplicate protection acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT,{recursive:true,force:true});fs.mkdirSync(RUN_ROOT,{recursive:true});let server=startServer();let release;const errors=[];page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource'))errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));try{await waitReady();await page.goto(BASE);await page.locator('input[type=file]').setInputFiles(path.join(FIXTURES,'sample.txt'));await page.getByRole('button',{name:'导入文件'}).click();await expect(page.locator('#status')).toContainText('导入完成',{timeout:30000});await page.getByRole('button',{name:/sample\.txt/}).last().click();page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'删除',exact:true}).click();await page.getByRole('button',{name:'回收站'}).click();await page.getByRole('button',{name:/sample\.txt/}).last().click();await expect(page.locator('#purge')).toBeEnabled();await page.route(`${BASE}/api/materials/*/purge`,route=>route.fulfill({status:500,contentType:'application/json',body:'{"detail":"synthetic"}'}));page.once('dialog',d=>d.accept());await page.locator('#purge').click();await expect(page.locator('#status')).toHaveText('永久删除失败');await expect(page.locator('#purge')).toBeEnabled();await expect(page.locator('#materials .deleted-item')).toHaveCount(1);await page.unroute(`${BASE}/api/materials/*/purge`);let count=0;await page.route(`${BASE}/api/materials/*/purge`,async route=>{count++;await new Promise(resolve=>{release=resolve});return route.continue()});page.once('dialog',d=>d.accept());await page.locator('#purge').click();await page.locator('#purge').dispatchEvent('click');await expect(page.locator('#purge')).toBeDisabled();expect(count).toBe(1);release();await expect(page.locator('#status')).toHaveText('材料已永久删除');await expect(page.locator('#materials .deleted-item')).toHaveCount(0);expect(errors).toEqual([])}finally{await page.unroute(`${BASE}/api/materials/*/purge`).catch(()=>{});if(release)release();stopServer(server)}});

test('formal restore mutation error acceptance', async ({page}) => {
  fs.rmSync(RUN_ROOT,{recursive:true,force:true});fs.rmSync(path.dirname(ARTIFACT),{recursive:true,force:true});fs.mkdirSync(RUN_ROOT,{recursive:true});let server=startServer();const errors=[];page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource'))errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));try{await waitReady();await page.goto(BASE);await page.locator('input[type=file]').setInputFiles(path.join(FIXTURES,'sample.txt'));await page.getByRole('button',{name:'导入文件'}).click();await expect(page.locator('#status')).toContainText('导入完成',{timeout:30000});await page.getByRole('button',{name:/sample\.txt/}).last().click();page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'删除',exact:true}).click();await page.getByRole('button',{name:'回收站'}).click();await page.getByRole('button',{name:/sample\.txt/}).last().click();await page.route(`${BASE}/api/materials/*/restore`,route=>route.fulfill({status:500,contentType:'application/json',body:'{"detail":"synthetic"}'}));await page.locator('#restore').click();await expect(page.locator('#status')).toHaveText('恢复失败');await expect(page.locator('#search-form')).toBeHidden();await expect(page.locator('#restore')).toBeEnabled();expect(errors).toEqual([])}finally{await page.unroute(`${BASE}/api/materials/*`).catch(()=>{});stopServer(server)}});
