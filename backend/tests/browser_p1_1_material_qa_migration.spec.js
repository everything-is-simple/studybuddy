const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/p1-1-material-qa-migration';
const PORT = 8876;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'};
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function ready() {
  await expect.poll(async () => { try { return (await fetch(`${BASE}/api/health`)).ok; } catch (_) { return false; } }, {timeout: 15000}).toBe(true);
}
test.beforeEach(async () => { fs.rmSync(ROOT, {recursive: true, force: true}); server = startServer(); await ready(); });
test.afterEach(() => { if (server && !server.killed) server.kill(); server = null; });

async function createMaterial(page) {
  const response = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'p1-source.txt', mimeType: 'text/plain', buffer: Buffer.from('P1 citation evidence identifies the indexed body location. This verified study source contains enough public text for lexical retrieval. The indexed body location is supported by the citation evidence in this material.')}}});
  expect(response.ok()).toBe(true);
  const material = await response.json();
  return String(material.id || material.material_id);
}

test('P1-1 material detail indexes a material and presents its parsed body', async ({page}) => {
  const materialId = await createMaterial(page);
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#body')).toContainText('P1 citation evidence');
  await expect(page.locator('#index')).toBeEnabled();
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', {timeout: 15000});
  await expect(page.locator('#qa')).toHaveAttribute('href', new RegExp(`material=${materialId}`));
});

test('P1-1 Q&A citation detail navigates to and highlights the cited body location', async ({page}) => {
  const materialId = await createMaterial(page);
  const indexed = await page.request.post(`${BASE}/api/materials/${materialId}/ai-index`);
  expect(indexed.ok()).toBe(true);
  const status = await page.request.get(`${BASE}/api/materials/${materialId}/ai-index`);
  expect((await status.json()).status).toBe('ready');
  const retrieval = await page.request.post(`${BASE}/api/retrieval`, {data: {query: 'citation evidence indexed body location', material_ids: [materialId], mode: 'lexical', top_k: 5}});
  expect(retrieval.ok()).toBe(true);
  expect((await retrieval.json()).hits.length).toBeGreaterThan(0);
  await page.goto(`${BASE}/app/qa.html?material=${encodeURIComponent(materialId)}`);
  await page.locator('#question').fill('citation evidence indexed body location');
  await page.locator('#retrieval-mode').selectOption('lexical');
  await page.locator('#submit-btn').click();
  await expect(page.locator('#submit-status')).toContainText('回答已生成', {timeout: 15000});
  await expect(page.getByRole('button', {name: '查看对话与引用'})).toHaveCount(1);
  await page.getByRole('button', {name: '查看对话与引用'}).click();
  const citation = page.locator('.thread-detail .citation-link');
  await expect(citation).toHaveCount(1);
  await citation.click();
  await expect(page).toHaveURL(/material-detail\.html\?material=.*&citation=/);
  await expect(page.locator('#body mark.citation-highlight')).toContainText('P1 citation evidence');
  await expect(page.locator('#body-location')).toContainText('已定位引用来源');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT|api_key/i);
});

test('P1-1 citation availability remains explicit without exposing internal errors', async ({page}) => {
  await page.route('**/api/materials/material-1', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({id: 'material-1', original_name: 'source.txt', status: 'ready', text: 'Public source text.', text_length: 19, span_count: 1, warnings: []})}));
  await page.route('**/api/materials/material-1/ai-index', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({status: 'ready'})}));
  await page.route('**/api/qa/citations/citation-missing', route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'private_backend_failure', traceback: 'hidden', path: 'H:/secret'})}));
  await page.goto(`${BASE}/app/material-detail.html?material=material-1&citation=citation-missing`);
  await expect(page.locator('#body-location')).toContainText('引用定位失败');
  await expect(page.locator('body')).not.toContainText(/private_backend_failure|traceback|H:\/secret/i);
});

test('P1-1 materials page reports an accurate single-file import count', async ({page}) => {
  await page.goto(`${BASE}/app/materials.html`);
  await page.setInputFiles('#file-input', {name: 'p1-single.txt', mimeType: 'text/plain', buffer: Buffer.from('Single file import reports an accurate success count.')});
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1 个文件', {timeout: 15000});
  await expect(page.locator('#items li')).toHaveCount(1);
  await expect(page.locator('#upload-status')).not.toHaveClass(/warn/);
});

test('P1-1 material detail reports empty-text index status instead of claiming ready', async ({page}) => {
  const response = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'p1-empty.txt', mimeType: 'text/plain', buffer: Buffer.from('')}}});
  expect(response.ok()).toBe(true);
  const material = await response.json();
  expect(material.status).toBe('empty');
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(String(material.id || material.material_id))}`);
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('没有可用于问答的正文', {timeout: 15000});
  await expect(page.locator('#index-status')).not.toContainText('AI 索引已建立');
});
