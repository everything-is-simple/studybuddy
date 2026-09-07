const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/p2-fe-b3-templates';
const PORT = 8836;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 15000 }).toBe(true);
}

test.beforeEach(async () => { fs.rmSync(ROOT, { recursive: true, force: true }); server = startServer(); await ready(); });
test.afterEach(() => { if (server && !server.killed) server.kill(); server = null; });

test('B3 shared templates are loaded by six migrated pages', async ({ page }) => {
  for (const path of ['today.html', 'reports.html', 'practice-result.html', 'practice-session.html', 'review.html', 'plan-detail.html']) {
    await page.goto(`${BASE}/app/${path}`);
    await expect.poll(() => page.evaluate(() => Boolean(window.sbTemplates))).toBe(true);
    expect(await page.locator('script[src="/app/js/templates.js"]').count()).toBe(1);
  }
});

test('B3 templates preserve base classes and provide state/retry APIs', async ({ page }) => {
  await page.goto(`${BASE}/app/today.html`);
  const result = await page.evaluate(() => {
    const box = document.createElement('div');
    box.className = 'notice mt-12';
    document.body.append(box);
    sbTemplates.setState(box, 'loading', { message: '加载中' });
    const loading = { className: box.className, text: box.textContent };
    let retried = false;
    sbTemplates.setState(box, 'failed', { error: '请求失败', retry: () => { retried = true; } });
    box.querySelector('button').click();
    return { loading, failedClass: box.className, failedText: box.firstChild.textContent, retried, hasSetState: typeof sbTemplates.setState === 'function' };
  });
  expect(result.loading).toStrictEqual({ className: 'notice mt-12 status-loading', text: '加载中' });
  expect(result.failedClass).toBe('notice mt-12 warn');
  expect(result.failedText).toContain('请求失败');
  expect(result.retried).toBe(true);
  expect(result.hasSetState).toBe(true);
});
