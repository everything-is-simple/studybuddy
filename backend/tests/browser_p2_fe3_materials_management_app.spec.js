const {test, expect} = require('@playwright/test');
const {spawn, spawnSync} = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = 'H:/studybuddy-test/runs/p2-fe3-materials-management-app';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8792;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT};
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function ready() { for (let i = 0; i < 100; i++) { try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {} await new Promise(r => setTimeout(r, 100)); } throw new Error('server_not_ready'); }
function stop(server) { if (server && !server.killed) server.kill(); }
function reset() { fs.rmSync(ROOT, {recursive: true, force: true}); fs.mkdirSync(ROOT, {recursive: true}); }
async function importFiles(page, names = ['sample.txt', 'sample.md']) {
  await page.locator('#file-input').setInputFiles(names.map(name => path.join(FIXTURES, name)));
  await expect(page.locator('#upload-status')).toContainText(`已导入 ${names.length}/${names.length}`, {timeout: 30000});
  await expect(page.locator('#items li')).toHaveCount(names.length);
}
async function zipNames(filePath) {
  const code = `import json,zipfile;print(json.dumps(sorted(zipfile.ZipFile(r'''${filePath}''').namelist())))`;
  return JSON.parse(spawnSync('C:/miniconda/py310/python.exe', ['-c', code], {encoding: 'utf8'}).stdout);
}
async function downloadNames(page, selector) {
  const promise = page.waitForEvent('download');
  await page.locator(selector).click();
  const download = await promise;
  expect(download.suggestedFilename()).toBe('studybuddy-materials.zip');
  return zipNames(await download.path());
}

test('formal app delete and restore lifecycle', async ({page}) => {
  reset(); let server = startServer();
  try {
    await ready(); await page.goto(`${BASE}/app/materials.html`); await importFiles(page);
    const rows = page.locator('#items li');
    const deleteButton = rows.filter({hasText: 'sample.txt'}).getByRole('button', {name: '删除'});
    page.once('dialog', dialog => { expect(dialog.type()).toBe('confirm'); dialog.accept(); });
    await deleteButton.click();
    await expect(rows.filter({hasText: 'sample.txt'})).toHaveCount(0);
    await expect(rows.filter({hasText: 'sample.md'})).toHaveCount(1);
    await page.locator('#view-deleted').click();
    await expect(page.locator('#list-title')).toHaveText('回收站');
    await expect(rows.filter({hasText: 'sample.txt'})).toHaveCount(1);
    await expect(rows.filter({hasText: 'sample.txt'}).getByRole('button', {name: '删除'})).toHaveCount(0);
    const restore = rows.filter({hasText: 'sample.txt'}).getByRole('button', {name: '恢复'});
    await restore.click();
    await expect(rows.filter({hasText: 'sample.txt'})).toHaveCount(0);
    await page.locator('#view-deleted').click();
    await expect(rows.filter({hasText: 'sample.txt'})).toHaveCount(1);
    await page.reload();
    await expect(rows.filter({hasText: 'sample.txt'})).toHaveCount(1);
    await expect(page.locator('#items')).toContainText('sample.md');
    for (const width of [360, 390, 430, 768, 1366, 1920]) {
      await page.setViewportSize({width, height: 800});
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
    }
  } finally { stop(server); }
});

test('formal app ZIP export variants, failure recovery and selection protection', async ({page}) => {
  reset(); let server = startServer();
  try {
    await ready(); await page.goto(`${BASE}/app/materials.html`); await importFiles(page);
    await page.locator('#select-page').check();
    await expect(page.locator('#selection-status')).toHaveText('已选择 2 份');
    expect(await downloadNames(page, '#export-originals')).toEqual(['originals/sample.md', 'originals/sample.txt']);
    expect(await downloadNames(page, '#export-texts')).toEqual(['text/sample.md.extracted.txt', 'text/sample.txt.extracted.txt']);
    expect(await downloadNames(page, '#export-all')).toEqual(['originals/sample.md', 'originals/sample.txt', 'text/sample.md.extracted.txt', 'text/sample.txt.extracted.txt']);
    await page.route(`${BASE}/api/materials/export`, route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'synthetic/private/path'})}));
    await page.locator('#export-all').click();
    await expect(page.locator('#export-status')).toContainText('请求失败，请重试');
    await expect(page.locator('#export-status')).not.toContainText('synthetic/private/path');
    await expect(page.locator('#export-all')).toBeEnabled();
    await page.unroute(`${BASE}/api/materials/export`);
  } finally { await page.unroute(`${BASE}/api/materials/export`).catch(() => {}); stop(server); }
});

test('formal app delete and restore failures are retryable and single-submit', async ({page}) => {
  reset(); let server = startServer(); let deleteCount = 0;
  try {
    await ready(); await page.goto(`${BASE}/app/materials.html`); await importFiles(page, ['sample.txt']);
    await page.route(`${BASE}/api/materials/*`, async route => {
      if (route.request().method() === 'DELETE') { deleteCount++; await new Promise(resolve => setTimeout(resolve, 300)); return route.continue(); }
      return route.continue();
    });
    const button = page.locator('#items li').getByRole('button', {name: '删除'});
    page.once('dialog', dialog => dialog.accept());
    await button.click(); await expect(button).toBeDisabled(); await button.dispatchEvent('click');
    expect(deleteCount).toBe(1);
    await expect(page.locator('#state')).toHaveText('暂无材料');
    await page.unroute(`${BASE}/api/materials/*`);

    await importFiles(page, ['sample.md']);
    page.once('dialog', dialog => dialog.accept()); await page.locator('#items li').getByRole('button', {name: '删除'}).click();
    await page.locator('#view-deleted').click();
    await page.route(`${BASE}/api/materials/*/restore`, route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'synthetic/private/path'})}));
    const restore = page.locator('#items li').filter({hasText: 'sample.md'}).getByRole('button', {name: '恢复'});
    page.once('dialog', dialog => { expect(dialog.type()).toBe('alert'); dialog.accept(); });
    await restore.click();
    await expect(restore).toBeEnabled();
    await page.unroute(`${BASE}/api/materials/*/restore`);
  } finally { await page.unroute(`${BASE}/api/materials/*`).catch(() => {}); stop(server); }
});
