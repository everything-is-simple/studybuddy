const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-p6d-ui';
const PORT = 8796;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'};
  delete env.STUDYBUDDY_AI_MODEL;
  delete env.STUDYBUDDY_AI_BASE_URL;
  delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}

async function ready() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

async function upload(page, name, text) {
  await page.locator('#file').setInputFiles({name, mimeType: 'text/plain', buffer: Buffer.from(text)});
  await page.locator('#file-import').click();
  await expect(page.locator('#status')).toContainText('导入完成', {timeout: 30000});
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer();
  await ready();
});

test.afterEach(() => {
  if (server && !server.killed) server.kill();
  server = null;
});

test('P6-D exposes navigation semantics and stays usable on narrow screens', async ({page}) => {
  await page.goto(BASE);
  await expect(page.locator('header')).toBeVisible();
  await expect(page.locator('nav[aria-label="主要视图"]')).toBeVisible();
  await expect(page.locator('main#main-content')).toBeVisible();
  await expect(page.locator('#active-view')).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('#deleted-view')).toHaveAttribute('aria-current', 'false');
  await expect(page.locator('#search')).toHaveAccessibleName('搜索材料');
  await expect(page.locator('#file')).toHaveAccessibleName('选择要导入的文件');
  await expect(page.locator('#folder')).toHaveAccessibleName('选择要导入的文件夹');
  await upload(page, 'p6d.txt', 'P6-D keyboard and responsive notification evidence.');
  await expect(page.locator('#nav-context')).toContainText('p6d.txt');
  await page.locator('#deleted-view').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#deleted-view')).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('#active-view')).toHaveAttribute('aria-current', 'false');
  await page.locator('#active-view').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#active-view')).toHaveAttribute('aria-current', 'page');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await expect(page.locator('#management button')).toHaveCount(7);
  await expect(page.locator('#batch-export button').first()).toBeVisible();
  await page.locator('#nav-qa').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#qa')).toBeVisible();
});

test('P6-D preserves focus through citation dialog and exposes page-level failure state', async ({page}) => {
  await page.goto(BASE);
  await upload(page, 'focus.txt', 'Focus returns after citation dialog and errors remain visible in page status.');
  await page.locator('#open-qa').click();
  await page.locator('#qa-index').click();
  await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
  await page.locator('#qa-question').fill('focus citation');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('回答已生成');
  const citation = page.locator('#qa-citations button').first();
  await citation.focus();
  await citation.press('Enter');
  await expect(page.locator('[role="dialog"]')).toContainText('引用详情');
  await page.keyboard.press('Escape');
  await expect(page.locator('[role="dialog"]')).toHaveCount(0);
  await expect(page.evaluate(() => document.activeElement?.textContent)).resolves.toContain('引用');
  await page.route('**/api/materials/*/text', route => route.abort());
  await page.locator('#export-text').click();
  await expect(page.locator('#status')).toHaveText('正文导出失败');
  await expect(page.locator('#alert-root')).toHaveText('正文导出失败');
  await expect(page.locator('#toast-root')).toHaveCount(1);
  await expect(page.locator('#qa-thread-title')).toContainText('focus citation');
  await expect(page.locator('#nav-context')).toContainText('范围 1 个材料');
});
