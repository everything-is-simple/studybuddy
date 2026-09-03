const { test, expect } = require('@playwright/test');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = 'H:/studybuddy-test/runs/p1-4-real-input-restart';
const FIXTURES = 'H:/studybuddy-test/runs/p1-4-real-input-fixtures';
const PORT = 8857;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'};
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}

async function ready() {
  await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, {timeout: 20000}).toBe(true);
}

async function stopServer() {
  if (!server || server.killed) { server = null; return; }
  await new Promise(resolve => {
    let settled = false;
    const finish = () => { if (!settled) { settled = true; resolve(); } };
    server.once('exit', finish); server.kill(); setTimeout(finish, 5000);
  });
  server = null;
}

function chromium() {
  const base = path.join(process.env.LOCALAPPDATA || os.homedir(), 'ms-playwright');
  const roots = fs.existsSync(base) ? fs.readdirSync(base).filter(name => name.startsWith('chromium')) : [];
  for (const dir of roots) {
    for (const inner of ['chrome-win64', 'chrome-win']) {
      const candidate = path.join(base, dir, inner, 'chrome.exe');
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return null;
}

// Real containers are generated on demand: DOCX/PPTX through their official
// libraries, PDF through a browser-rendered multi-page document. Nothing is
// committed and the live data root is never touched.
function buildFixtures() {
  fs.rmSync(FIXTURES, {recursive: true, force: true});
  fs.mkdirSync(FIXTURES, {recursive: true});
  const browser = chromium();
  expect(browser, 'managed Chromium binary is required for the real PDF fixture').toBeTruthy();
  const html = `<html><head><meta charset="utf-8"><style>body{font-family:serif}.cols{column-count:2}.page{page-break-after:always}</style></head><body>
<div class="page"><h1>Study Handbook</h1><p>Table of contents</p><ol><li>Chapter 1 Stability</li><li>Chapter 2 Retrieval</li></ol><p>page 1</p></div>
<div class="page"><h2>Chapter 1 Stability</h2><div class="cols"><p>Verified stability keeps predictable behaviour under disturbance.</p><p>The second column continues the same chapter.</p></div><p>page 2</p></div>
<div><h2>Chapter 2 Retrieval</h2><p>Hybrid citation retrieval stability keeps every answer traceable to its original text span.</p><p>page 3</p></div></body></html>`;
  const source = path.join(FIXTURES, 'handbook.html');
  fs.writeFileSync(source, html, 'utf8');
  execFileSync(browser, ['--headless', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer',
    `--print-to-pdf=${path.join(FIXTURES, 'real-handbook.pdf')}`, `file:///${source.replace(/\\/g, '/')}`], {timeout: 180000});
  fs.rmSync(source, {force: true});
  const script = `
import sys
from pathlib import Path
from docx import Document
from pptx import Presentation
out = Path(sys.argv[1])
d = Document()
d.add_heading('Study notes with citation retrieval stability', 0)
d.add_paragraph('第一段：可验证稳定性要求每个断言都能追溯到观察结果。')
t = d.add_table(rows=1, cols=2)
t.cell(0, 0).text = 'rule'
t.cell(0, 1).text = '引用必须能定位回原文'
d.save(out / 'real-notes.docx')
p = Presentation()
first = p.slides.add_slide(p.slide_layouts[1])
first.shapes.title.text = '第一页 学习节奏'
first.placeholders[1].text = 'citation retrieval stability keeps today plan explainable'
second = p.slides.add_slide(p.slide_layouts[1])
second.shapes.title.text = '第二页 引用与检索'
second.placeholders[1].text = '引用必须定位回原文 span'
p.save(out / 'real-deck.pptx')
(out / '中文资料-长文件名-用于验证解析检索与引用定位.txt').write_text('第一节 可验证稳定性。\\n第二节 citation retrieval stability 必须定位回原文。\\n', encoding='utf-8')
(out / 'real-guide.md').write_text('# 学习指南\\n\\n- citation retrieval stability\\n- 引用必须能定位回原文\\n', encoding='utf-8')
(out / 'legacy.doc').write_bytes(b'\\xd0\\xcf\\x11\\xe0legacy')
(out / 'note.rtf').write_bytes(rb'{\\rtf1 hello}')
`;
  const scriptPath = path.join(FIXTURES, 'build_fixtures.py');
  fs.writeFileSync(scriptPath, script, 'utf8');
  execFileSync(PYTHON, [scriptPath, FIXTURES], {timeout: 180000});
  fs.rmSync(scriptPath, {force: true});
}

test.beforeAll(() => { buildFixtures(); });
test.beforeEach(async () => { await stopServer(); fs.rmSync(ROOT, {recursive: true, force: true}); server = startServer(); await ready(); });
test.afterEach(async () => { await stopServer(); });

const REAL_FILES = ['real-handbook.pdf', 'real-notes.docx', 'real-deck.pptx', 'real-guide.md', '中文资料-长文件名-用于验证解析检索与引用定位.txt'];

test('P1-4 C0 mixed real files import through /app and stay readable after a restart', async ({page}) => {
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.goto(`${BASE}/app/materials.html`);
  await page.setInputFiles('#file-input', REAL_FILES.map(name => path.join(FIXTURES, name)));
  await expect(page.locator('#upload-status')).toContainText(`已导入 ${REAL_FILES.length}/${REAL_FILES.length}`, {timeout: 60000});
  await expect(page.locator('#items li')).toHaveCount(REAL_FILES.length, {timeout: 20000});
  for (const name of REAL_FILES) await expect(page.locator('#items')).toContainText(name);

  await page.fill('#search-input', '中文资料');
  await page.click('#apply-filters');
  await expect(page.locator('#items li')).toHaveCount(1, {timeout: 20000});

  const listed = await (await page.request.get(`${BASE}/api/materials`)).json();
  const pdf = listed.find(row => row.original_name === 'real-handbook.pdf');
  expect(pdf.status).toBe('success');

  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(pdf.id)}`);
  await expect(page.locator('#body')).toContainText('Chapter 1 Stability', {timeout: 20000});
  await expect(page.locator('#content')).toContainText('片段数量');
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', {timeout: 30000});

  await stopServer();
  server = startServer();
  await ready();

  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#items li')).toHaveCount(REAL_FILES.length, {timeout: 20000});
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(pdf.id)}`);
  await expect(page.locator('#body')).toContainText('Chapter 2 Retrieval', {timeout: 20000});
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', {timeout: 30000});
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
  expect(failures).toEqual([]);
});

test('P1-4 C0 real PDF citation returns to the same body offset after a restart', async ({page}) => {
  const created = await page.request.post(`${BASE}/api/materials`, {multipart: {file: {name: 'real-handbook.pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(path.join(FIXTURES, 'real-handbook.pdf'))}}});
  expect(created.ok()).toBe(true);
  const materialId = (await created.json()).material_id;
  expect((await (await page.request.post(`${BASE}/api/materials/${materialId}/ai-index`)).json()).status).toBe('ready');

  await page.goto(`${BASE}/app/qa.html?material=${encodeURIComponent(materialId)}`);
  await page.locator('#question').fill('citation retrieval stability');
  await page.locator('#retrieval-mode').selectOption('lexical');
  await page.locator('#submit-btn').click();
  await expect(page.locator('#submit-status')).toContainText('回答已生成', {timeout: 30000});
  await page.getByRole('button', {name: '查看对话与引用'}).first().click();
  const citation = page.locator('.thread-detail .citation-link').first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(page).toHaveURL(/material-detail\.html\?material=.*&citation=/);
  await expect(page.locator('#body mark.citation-highlight')).toBeVisible({timeout: 20000});
  const highlighted = (await page.locator('#body mark.citation-highlight').innerText()).trim();
  expect(highlighted.length).toBeGreaterThan(0);
  const citedUrl = page.url();

  await stopServer();
  server = startServer();
  await ready();

  await page.goto(citedUrl);
  await expect(page.locator('#body-location')).toContainText('已定位引用来源', {timeout: 20000});
  const afterRestart = (await page.locator('#body mark.citation-highlight').innerText()).trim();
  expect(afterRestart).toBe(highlighted);
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
});

test('P1-4 C0 unsupported real formats stay honest in the /app import result', async ({page}) => {
  await page.goto(`${BASE}/app/materials.html`);
  await page.setInputFiles('#file-input', [path.join(FIXTURES, 'legacy.doc'), path.join(FIXTURES, 'note.rtf')]);
  await expect(page.locator('#upload-status')).toContainText('已导入 0/2', {timeout: 30000});
  await expect(page.locator('#upload-status')).toHaveClass(/warn/);
  await expect(page.locator('#items li')).toHaveCount(2, {timeout: 20000});
  await expect(page.locator('#items')).toContainText('legacy.doc');
  await expect(page.locator('#items')).toContainText('已拒绝');
  // C2 maps parser rejection codes to actionable user-facing guidance.
  await expect(page.locator('.upload-failures')).toContainText('请转换为 PDF 或 DOCX');
  await expect(page.locator('.upload-failures')).not.toContainText('requires_converter');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
});
