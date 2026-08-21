const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-qa-ui';
const PORT = 8795;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer(provider = 'fake') {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  if (provider) env.STUDYBUDDY_AI_PROVIDER = provider;
  else delete env.STUDYBUDDY_AI_PROVIDER;
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function ready() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stop(server) { if (server && !server.killed) server.kill(); }

async function upload(page, name, text) {
  await page.locator('#file').setInputFiles({name, mimeType: 'text/plain', buffer: Buffer.from(text)});
  await page.locator('#file-import').click();
  await expect(page.locator('#status')).toContainText('导入完成', {timeout: 30000});
}

test('Q&A UI requires explicit indexing and locates citations', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  const consoleErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('pageerror', error => consoleErrors.push(error.message));
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'qa.txt', 'Trusted citation evidence establishes the answer.');
    await expect(page.locator('#qa-status')).toContainText('请先建立 AI 索引');
    await expect(page.locator('#qa-ask')).toBeDisabled();
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await expect(page.locator('#qa-ask')).toBeEnabled();
    await page.locator('#qa-question').fill('Trusted citation');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    await expect(page.locator('#qa-answer')).toContainText('Fake answer');
    await expect(page.locator('#qa-citations button')).toHaveCount(1);
    await page.locator('#qa-citations button').click();
    await expect(page.locator('#qa-status')).toContainText('已定位引用来源');
    await expect(page.locator('#content mark.citation-highlight')).toContainText('Trusted citation evidence');
    expect(consoleErrors).toEqual([]);
  } finally { stop(server); }
});

test('Q&A UI supports multi-material scope, history, citation detail and narrow layout', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await page.locator('#file').setInputFiles([
      {name: 'alpha.txt', mimeType: 'text/plain', buffer: Buffer.from('Alpha material establishes the first answer source.')},
      {name: 'beta.txt', mimeType: 'text/plain', buffer: Buffer.from('Beta material establishes the second answer source.')},
    ]);
    await page.locator('#file-import').click();
    await expect(page.locator('#status')).toContainText('批量导入完成', {timeout: 30000});
    await expect(page.locator('#qa-scope-list input')).toHaveCount(2);
    await page.locator('#qa-scope-list input').nth(0).check();
    await page.locator('#qa-scope-list input').nth(1).check();
    await page.locator('#qa-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('material establishes');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    await expect(page.locator('#qa-citations button')).toHaveCount(2);
    await page.locator('#qa-citations button').first().click();
    await expect(page.locator('[role="dialog"]')).toContainText('引用详情');
    await page.keyboard.press('Escape');
    await expect(page.locator('[role="dialog"]')).toHaveCount(0);
    await expect(page.locator('#qa-history-list button')).toHaveCount(1);
    await page.locator('#qa-history-list button').click();
    await expect(page.locator('#qa-answer')).toContainText('Fake answer');
    await page.setViewportSize({width: 390, height: 844});
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow).toBe(false);
  } finally { stop(server); }
});

test('Q&A UI safely reports an unconfigured provider', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer('');
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'provider.txt', 'Trusted citation evidence establishes the answer.');
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('Trusted citation');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('AI 服务尚未配置');
    await expect(page.locator('#qa-question')).toHaveValue('Trusted citation');
    await expect(page.locator('#qa-status')).not.toContainText('provider_not_configured');
  } finally { stop(server); }
});
