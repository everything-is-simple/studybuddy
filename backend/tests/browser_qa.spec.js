const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-qa-ui';
const PORT = 8795;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer(provider = 'fake') {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  if (provider === 'fake') {
    env.STUDYBUDDY_AI_PROVIDER = 'fake';
    delete env.STUDYBUDDY_AI_MODEL;
    delete env.STUDYBUDDY_AI_BASE_URL;
    delete env.STUDYBUDDY_AI_API_KEY;
  } else if (provider) {
    env.STUDYBUDDY_AI_PROVIDER = provider;
  } else {
    delete env.STUDYBUDDY_AI_PROVIDER;
    delete env.STUDYBUDDY_AI_MODEL;
    delete env.STUDYBUDDY_AI_BASE_URL;
    delete env.STUDYBUDDY_AI_API_KEY;
  }
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
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

test('Provider status is explicit and safe in demo mode', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await expect(page.locator('#provider-status-title')).toContainText('演示模式');
    await expect(page.locator('#provider-status-detail')).toContainText('deterministic/demo');
    await expect(page.locator('#provider-status-detail')).not.toContainText('Authorization');
    await expect(page.locator('body')).not.toContainText('api_key');
    await expect(page.locator('body')).not.toContainText('traceback');
  } finally { stop(server); }
});

test('Provider status reports unconfigured runtime safely', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer('');
  try {
    await ready();
    await page.goto(BASE);
    await expect(page.locator('#provider-status-title')).toContainText('尚未配置');
    await expect(page.locator('#provider-status-detail')).toContainText('材料管理仍可使用');
  } finally { stop(server); }
});

test('Q&A thread workspace creates and switches conversations', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'thread-workspace.txt', 'Thread workspace source establishes a stable answer.');
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('stable answer');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    await expect(page.locator('#qa-thread-title')).not.toHaveText('新对话');
    await expect(page.locator('#qa-timeline')).toContainText('你的问题');
    await expect(page.locator('#qa-timeline')).toContainText('AI 回答');
    await expect(page.locator('#qa-history-list button')).toHaveCount(1);
    await page.locator('#qa-new-thread').click();
    await expect(page.locator('#qa-thread-title')).toHaveText('新对话');
    await expect(page.locator('#qa-timeline')).toContainText('新对话尚未有消息');
    await expect(page.locator('#qa-question')).toBeFocused();
    await page.locator('#qa-history-list button').click();
    await expect(page.locator('#qa-timeline')).toContainText('Thread workspace source');
    await expect(page.locator('#qa-thread-status')).toContainText('2 条消息');
  } finally { stop(server); }
});

test('P6-C keeps material, Q&A citation and export context connected', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await page.locator('#file').setInputFiles([
      {name: 'context-alpha.txt', mimeType: 'text/plain', buffer: Buffer.from('Context alpha contains the citation export evidence.')},
      {name: 'context-beta.txt', mimeType: 'text/plain', buffer: Buffer.from('Context beta is a second selectable material.')},
    ]);
    await page.locator('#file-import').click();
    await expect(page.locator('#status')).toContainText('批量导入完成', {timeout: 30000});
    await expect(page.locator('.material-select')).toHaveCount(2);
    await page.locator('.material-select').nth(0).check();
    await page.locator('.material-select').nth(1).check();
    await page.locator('#open-qa').click();
    await expect(page.locator('#qa-scope-summary')).toContainText('已选择 2 个材料');
    await expect(page).toHaveURL(/scope=/);
    await page.locator('#qa-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('citation export evidence');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    await expect(page.locator('#qa-citations button')).toHaveCount(1);
    await page.locator('#qa-citations button').click();
    await expect(page.locator('#qa-status')).toContainText('已定位引用来源');
    await expect(page.locator('#content mark.citation-highlight')).toContainText('Context alpha');
    await expect(page).toHaveURL(/material=/);
    await page.locator('[role="dialog"] button').click();
    const originalDownload = page.waitForEvent('download');
    await page.locator('#download-original').click();
    expect((await originalDownload).suggestedFilename()).toBe('context-alpha.txt');
    const textDownload = page.waitForEvent('download');
    await page.locator('#export-text').click();
    expect((await textDownload).suggestedFilename()).toBe('context-alpha.txt.extracted.txt');
    await page.locator('#qa-back-material').click();
    await expect(page.locator('#content')).toContainText('Context alpha');
    await page.locator('#open-qa').click();
    await expect(page).toHaveURL(/thread=/);
    await expect(page.locator('#qa-timeline')).toContainText('Fake answer');
    await page.locator('#qa-citations button').click();
    await page.locator('[role="dialog"] button').click();
    await page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name: '删除', exact: true}).click();
    await page.getByRole('button', {name: '回收站'}).click();
    await expect(page.locator('#materials .deleted-item')).toHaveCount(1);
    await page.locator('#materials .deleted-item').click();
    await expect(page.locator('#download-original')).toBeDisabled();
    await expect(page.locator('#export-text')).toBeDisabled();
  } finally { stop(server); }
});

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

test('Q&A UI safely handles provider failure, retry and duplicate clicks', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'provider-failure.txt', 'Trusted citation evidence establishes the answer.');
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('Trusted citation');
    let calls = 0;
    let fail = true;
    await page.route('**/api/qa/ask', async route => {
      calls++;
      if (fail) {
        await route.fulfill({status: 504, contentType: 'application/json', body: JSON.stringify({detail: 'provider_timeout', path: 'C:/secret', traceback: 'private'})});
      } else {
        await route.continue();
      }
    });
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('响应超时');
    await expect(page.locator('#qa-retry')).toBeVisible();
    await expect(page.locator('#qa-question')).toHaveValue('Trusted citation');
    await expect(page.locator('#qa-status')).not.toContainText('provider_timeout');
    await expect(page.locator('body')).not.toContainText('C:/secret');
    await expect(page.locator('body')).not.toContainText('traceback');
    fail = false;
    await page.locator('#qa-retry').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    expect(calls).toBe(2);
    await page.unroute('**/api/qa/ask');

    let duplicateCalls = 0;
    await page.route('**/api/qa/ask', async route => {
      duplicateCalls++;
      await new Promise(resolve => setTimeout(resolve, 300));
      await route.continue();
    });
    await page.locator('#qa-question').fill('Trusted citation');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-ask')).toBeDisabled();
    await page.locator('#qa-ask').click({force: true});
    await expect(page.locator('#qa-status')).toContainText('回答已生成');
    expect(duplicateCalls).toBe(1);
  } finally { stop(server); }
});

test('Q&A UI maps rate-limit and unavailable errors safely', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'provider-errors.txt', 'Trusted citation evidence establishes the answer.');
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('Trusted citation');
    const errors = [
      [429, 'provider_rate_limited', '请求过于频繁'],
      [503, 'provider_unavailable', '暂时不可用'],
    ];
    for (const [status, code, message] of errors) {
      await page.route('**/api/qa/ask', route => route.fulfill({status, contentType: 'application/json', body: JSON.stringify({detail: code, raw_provider_error: 'private'})}));
      await page.locator('#qa-ask').click();
      await expect(page.locator('#qa-status')).toContainText(message);
      await expect(page.locator('#qa-status')).not.toContainText(code);
      await expect(page.locator('body')).not.toContainText('private');
      await page.unroute('**/api/qa/ask');
    }
  } finally { stop(server); }
});

test('opt-in targeted Provider browser path shows answer and locates citation', async ({page}) => {
  const target = process.env.STUDYBUDDY_REAL_PROVIDER_UI_TARGET;
  test.skip(process.env.STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE !== '1' || !target, 'opt-in targeted provider browser smoke');
  test.skip(process.env.STUDYBUDDY_AI_PROVIDER !== target, 'real provider configuration does not match target');
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  let server = startServer(target);
  try {
    await ready();
    await page.goto(BASE);
    await upload(page, 'provider-ui-smoke.txt', 'Synthetic study note: the controlled experiment establishes a stable result.');
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
    await page.locator('#qa-question').fill('controlled experiment establishes');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成', {timeout: 30000});
    await expect(page.locator('#qa-answer')).not.toBeEmpty();
    await expect(page.locator('#qa-citations button')).toHaveCount(1);
    await page.locator('#qa-citations button').click();
    await expect(page.locator('#qa-status')).toContainText('已定位引用来源');
    await expect(page.locator('#content mark.citation-highlight')).toContainText('controlled experiment establishes');
    const body = await page.locator('body').innerText();
    expect(body).not.toContain('sk-');
    expect(body.toLowerCase()).not.toContain('traceback');
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
