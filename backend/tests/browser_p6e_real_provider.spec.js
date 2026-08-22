const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-p6e-real-provider';
const PORT = 8798;
const BASE = `http://127.0.0.1:${PORT}`;

const target = process.env.STUDYBUDDY_REAL_PROVIDER_UI_TARGET;
const provider = process.env.STUDYBUDDY_AI_PROVIDER;
const model = process.env.STUDYBUDDY_AI_MODEL;
const baseUrl = process.env.STUDYBUDDY_AI_BASE_URL;
const key = process.env.STUDYBUDDY_AI_API_KEY;
const optedIn = process.env.STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE === '1';

function targetConfig(expectedProvider, expectedModel) {
  return optedIn && target === expectedProvider && provider === expectedProvider && model === expectedModel && baseUrl && key;
}

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}

async function ready() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

async function runTarget({page, expectedProvider, expectedModel}) {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  const server = startServer();
  try {
    await ready();
    await page.goto(BASE);
    await page.locator('#file').setInputFiles({
      name: 'p6e-real-synthetic.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Synthetic P6-E evidence: the controlled study establishes a stable citation result.'),
    });
    await page.locator('#file-import').click();
    await expect(page.locator('#status')).toContainText('导入完成', {timeout: 30000});
    await page.locator('#open-qa').click();
    await page.locator('#ai-index').click();
    await expect(page.locator('#qa-status')).toContainText('AI 索引已建立', {timeout: 30000});
    await page.locator('#qa-question').fill('controlled study establishes');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('回答已生成', {timeout: 60000});
    await expect(page.locator('#qa-answer')).not.toBeEmpty();
    await expect(page.locator('#qa-citations button')).toHaveCount(1);
    await page.locator('#qa-citations button').click();
    await expect(page.locator('#qa-status')).toContainText('已定位引用来源', {timeout: 30000});
    await expect(page.locator('#content mark.citation-highlight')).toContainText('controlled study establishes');
    const body = await page.locator('body').innerText();
    expect(body).not.toContain('Authorization');
    expect(body.toLowerCase()).not.toContain('traceback');
    expect(body).not.toContain('STUDYBUDDY_AI_API_KEY');
    const capability = await (await page.request.get(`${BASE}/api/ai/capabilities`)).json();
    expect(capability.provider_id).toBe(expectedProvider);
    expect(capability.model_id).toBe(expectedModel);
    return {provider: expectedProvider, model: expectedModel, gateway: new URL(baseUrl).hostname, adapter_gate: 'pass', api_gate: 'pass', ui_gate: 'pass', citation_gate: 'pass', export_gate: 'not_run', limitations: ['synthetic material', 'single controlled UI run', 'not a global Provider availability claim']};
  } finally {
    if (!server.killed) server.kill();
  }
}

test('P6-E DeepSeek deepseek-chat exact real path', async ({page}) => {
  test.skip(!targetConfig('deepseek', 'deepseek-chat'), 'requires explicit DeepSeek deepseek-chat UI opt-in with complete matching configuration');
  const evidence = await runTarget({page, expectedProvider: 'deepseek', expectedModel: 'deepseek-chat'});
  expect(evidence.adapter_gate).toBe('pass');
  expect(evidence.citation_gate).toBe('pass');
});

test('P6-E Agnes advanced agnes-2.5-flash exact real path', async ({page}) => {
  test.skip(!targetConfig('agnes-ai-hub', 'agnes-2.5-flash'), 'requires explicit Agnes advanced agnes-2.5-flash UI opt-in with complete matching configuration');
  const evidence = await runTarget({page, expectedProvider: 'agnes-ai-hub', expectedModel: 'agnes-2.5-flash'});
  expect(evidence.adapter_gate).toBe('pass');
  expect(evidence.citation_gate).toBe('pass');
});
