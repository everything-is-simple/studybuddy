const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-shared-layer';
const PORT = 8824;
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

test('shared layer loads tokens and removes HTML inline styles', async ({ page }) => {
  await page.goto(`${BASE}/app/capture.html`);
  await expect(page.locator('link[href="/app/css/tokens.css"]')).toHaveCount(1);
  await expect(page.locator('[style]')).toHaveCount(0);
  await expect(page.locator('dialog.dialog.dialog-small')).toHaveCount(1);
  await expect(page.locator('dialog.dialog.dialog-wide')).toHaveCount(1);
});

test('mobile navigation toggle is keyboard reachable and has correct ARIA state', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/app/materials.html`);
  const toggle = page.getByRole('button', { name: '更多' });
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.press('Enter');
  const collapse = page.getByRole('button', { name: '收起' });
  await expect(collapse).toBeVisible();
  await expect(collapse).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#primary-navigation')).toHaveClass(/is-open/);
});

test('shared request layer applies idempotency, page scope, and cancellation', async ({ page }) => {
  await page.goto(`${BASE}/app/qa.html`);
  const result = await page.evaluate(async () => {
    const seen = [];
    const originalFetch = window.fetch;
    window.fetch = async (_url, options) => {
      seen.push({ key: new Headers(options.headers).get('Idempotency-Key'), aborted: options.signal.aborted });
      return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } });
    };
    const scope = sbApi.setPageScope('shared-layer-test');
    await sbApi.json('/api/test-write', { method: 'POST', body: '{}' });
    scope.cancel();
    window.fetch = originalFetch;
    return { seen, aborted: scope.signal.aborted };
  });
  expect(result.seen).toHaveLength(1);
  expect(result.seen[0].key).toMatch(/^ui-/);
  expect(result.aborted).toBe(true);
});
