const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase7-ui';
const PORT = 8796;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer(embedding) {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT,
    STUDYBUDDY_AI_PROVIDER: 'fake'};
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  delete env.STUDYBUDDY_EMBEDDING_BASE_URL; delete env.STUDYBUDDY_EMBEDDING_API_KEY;
  if (embedding) {
    env.STUDYBUDDY_EMBEDDING_PROVIDER = 'fake';
    env.STUDYBUDDY_EMBEDDING_MODEL = 'fake-embedding-v1';
  } else {
    delete env.STUDYBUDDY_EMBEDDING_PROVIDER;
    delete env.STUDYBUDDY_EMBEDDING_MODEL;
  }
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)],
    {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function ready() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stop(server) { if (server && !server.killed) server.kill(); }
async function uploadAndIndex(page) {
  await page.locator('#file').setInputFiles({name: 'phase7.txt', mimeType: 'text/plain', buffer: Buffer.from('Phase seven retrieval mode evidence supports the answer.')});
  await page.locator('#file-import').click();
  await expect(page.locator('#status')).toContainText('导入完成', {timeout: 30000});
  await page.locator('#ai-index').click();
  await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
}

 test('retrieval mode UI routes lexical vector and hybrid requests', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  const server = startServer(true);
  try {
    await ready(); await page.goto(BASE); await uploadAndIndex(page);
    for (const mode of ['lexical', 'vector', 'hybrid']) {
      await page.locator('#qa-retrieval-mode').selectOption(mode);
      await page.locator('#qa-question').fill('retrieval mode evidence');
      await page.locator('#qa-ask').click();
      await expect(page.locator('#qa-status')).toContainText('回答已生成');
      await expect(page.locator('#qa-answer')).toContainText('Fake answer');
    }
    await expect(page.locator('#qa-retrieval-mode')).toHaveValue('hybrid');
  } finally { stop(server); }
});

test('hybrid fallback is visible and vector mode remains explicit failure', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  const server = startServer(false);
  try {
    await ready(); await page.goto(BASE); await uploadAndIndex(page);
    await page.locator('#qa-retrieval-mode').selectOption('hybrid');
    await page.locator('#qa-question').fill('retrieval mode evidence');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('已回退');
    await page.locator('#qa-retrieval-mode').selectOption('vector');
    await page.locator('#qa-question').fill('retrieval mode evidence');
    await page.locator('#qa-ask').click();
    await expect(page.locator('#qa-status')).toContainText('Embedding 尚未配置');
  } finally { stop(server); }
});
