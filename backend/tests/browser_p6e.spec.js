const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-p6e-ui';
const PORT = 8797;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer(provider) {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  if (provider === 'fake') {
    env.STUDYBUDDY_AI_PROVIDER = 'fake';
    delete env.STUDYBUDDY_AI_MODEL;
    delete env.STUDYBUDDY_AI_BASE_URL;
    delete env.STUDYBUDDY_AI_API_KEY;
  } else if (provider === '') {
    delete env.STUDYBUDDY_AI_PROVIDER;
    delete env.STUDYBUDDY_AI_MODEL;
    delete env.STUDYBUDDY_AI_BASE_URL;
    delete env.STUDYBUDDY_AI_API_KEY;
  }
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}

async function ready() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

async function stopServer(process) {
  if (!process || process.killed) return;
  await new Promise(resolve => {
    let settled = false;
    const finish = () => { if (!settled) { settled = true; resolve(); } };
    process.once('exit', finish);
    process.kill();
    setTimeout(finish, 1000);
  });
  await new Promise(resolve => setTimeout(resolve, 250));
}

async function upload(page, name, text) {
  await page.locator('#file').setInputFiles({name, mimeType: 'text/plain', buffer: Buffer.from(text)});
  await page.locator('#file-import').click();
  await expect(page.locator('#status')).toContainText('导入完成', {timeout: 30000});
  await expect(page.locator('#title')).toHaveText(name);
  await expect(page.locator('#meta')).toContainText('success');
}

async function establishIndex(page) {
  await page.locator('#open-qa').click();
  await page.locator('#ai-index').click();
  await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer('fake');
  await ready();
});

test.afterEach(async () => {
  await stopServer(server);
  server = null;
});

test('P6-E completes import to citation, source location, navigation, refresh and export', async ({page}) => {
  await page.goto(BASE);
  await upload(page, 'p6e-primary.txt', 'P6-E synthetic source: retrieval and citation establish the complete workflow result.');
  await expect(page.locator('#qa-status')).toContainText('请先建立 AI 索引');
  await establishIndex(page);
  await page.locator('#qa-question').fill('complete workflow result');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('回答已生成');
  await expect(page.locator('#qa-answer')).toContainText('Fake answer');
  await expect(page.locator('#qa-citations button')).toHaveCount(1);
  await page.locator('#qa-citations button').click();
  await expect(page.locator('#qa-status')).toContainText('已定位引用来源');
  await expect(page.locator('#content mark.citation-highlight')).toContainText('retrieval and citation');
  await expect(page).toHaveURL(/material=/);
  await page.locator('[role="dialog"] button').click();
  await page.locator('#qa-back-material').click();
  await expect(page.locator('#title')).toHaveText('p6e-primary.txt');
  await page.locator('#open-qa').click();
  await expect(page.locator('#qa-timeline')).toContainText('Fake answer');
  await expect(page).toHaveURL(/thread=/);
  await page.goBack();
  await expect(page.locator('#title')).toHaveText('p6e-primary.txt');
  await page.goForward();
  await expect(page.locator('#qa-timeline')).toContainText('Fake answer');
  const download = page.waitForEvent('download');
  await page.locator('#export-text').click();
  expect((await download).suggestedFilename()).toBe('p6e-primary.txt.extracted.txt');
  await page.reload();
  await expect(page.locator('#qa-timeline')).toContainText('Fake answer');
  await expect(page.locator('#nav-context')).toContainText('p6e-primary.txt');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('P6-E distinguishes retrieval empty and unconfigured Provider without unsafe output', async ({page}) => {
  await page.goto(BASE);
  await upload(page, 'p6e-empty.txt', 'Only indexed source words are present here.');
  await establishIndex(page);
  await page.locator('#qa-question').fill('absent-token-p6e');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('未找到相关内容');
  await expect(page.locator('#qa-retry')).toBeVisible();
  await expect(page.locator('#qa-answer')).toBeEmpty();
  await expect(page.locator('#qa-citations button')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('retrieval_empty');
  await page.reload();
  await page.locator('#open-qa').click();
  await expect(page.locator('#qa-status')).toContainText('可以基于选中材料提问');

  await stopServer(server);
  server = null;
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer('');
  await ready();
  await page.goto(BASE);
  await upload(page, 'p6e-unconfigured.txt', 'Provider is intentionally not configured for this safe failure path.');
  await establishIndex(page);
  await page.locator('#qa-question').fill('Provider intentionally configured');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('AI 服务尚未配置');
  await expect(page.locator('#qa-question')).toHaveValue('Provider intentionally configured');
  await expect(page.locator('body')).not.toContainText('Authorization');
  await expect(page.locator('body')).not.toContainText('traceback');
  await expect(page.locator('body')).not.toContainText('studybuddy.sqlite');
});

test('P6-E preserves retry, idempotent UI and stale thread context', async ({page}) => {
  await page.goto(BASE);
  await upload(page, 'p6e-failure.txt', 'P6-E retry and stale response synthetic source.');
  await establishIndex(page);
  await page.locator('#qa-question').fill('retry stale response');
  let fail = true;
  let calls = 0;
  await page.route('**/api/qa/ask', async route => {
    calls++;
    if (fail) return route.fulfill({status: 504, contentType: 'application/json', body: JSON.stringify({detail: 'provider_timeout', private_path: 'C:/private'})});
    await route.continue();
  });
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('响应超时');
  await expect(page.locator('#qa-retry')).toBeVisible();
  await expect(page.locator('#qa-status')).toContainText('响应超时');
  await expect(page.locator('body')).not.toContainText('C:/private');
  fail = false;
  await page.locator('#qa-retry').click();
  await expect(page.locator('#qa-status')).toContainText('回答已生成');
  expect(calls).toBe(2);
  await page.unroute('**/api/qa/ask');

  let delayedCalls = 0;
  await page.route('**/api/qa/ask', async route => {
    delayedCalls++;
    await new Promise(resolve => setTimeout(resolve, 500));
    await route.continue();
  });
  await page.locator('#qa-question').fill('stale response question');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-ask')).toBeDisabled();
  await page.locator('#qa-new-thread').click();
  await expect(page.locator('#qa-thread-title')).toHaveText('新对话');
  await expect(page.locator('#qa-timeline')).toContainText('新对话尚未有消息');
  await new Promise(resolve => setTimeout(resolve, 800));
  expect(delayedCalls).toBe(1);
  await expect(page.locator('#qa-thread-title')).toHaveText('新对话');
  await expect(page.locator('#qa-timeline')).not.toContainText('stale response question');
  await page.unroute('**/api/qa/ask');
});

test('P6-E marks deleted source unavailable and prevents unsafe export', async ({page}) => {
  await page.goto(BASE);
  await upload(page, 'p6e-source.txt', 'P6-E source lifecycle citation text.');
  await establishIndex(page);
  await page.locator('#qa-question').fill('source lifecycle citation');
  await page.locator('#qa-ask').click();
  await expect(page.locator('#qa-status')).toContainText('回答已生成');
  await page.locator('#qa-citations button').click();
  await expect(page.locator('#qa-status')).toContainText('已定位引用来源');
  await page.locator('[role="dialog"] button').click();
  await page.locator('#qa-back-material').click();
  await page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: '删除', exact: true}).click();
  await expect(page.locator('#status')).toContainText('材料已删除');
  await page.getByRole('button', {name: '回收站'}).click();
  await page.getByRole('button', {name: /p6e-source\.txt/}).last().click();
  await expect(page.locator('#download-original')).toBeDisabled();
  await expect(page.locator('#export-text')).toBeDisabled();
  await expect(page.locator('#meta')).toContainText('已删除');
});
