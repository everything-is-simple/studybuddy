const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-matrix';
const PORT = 8826;
const BASE = `http://127.0.0.1:${PORT}`;
const PAGES = ['plans.html', 'notes.html', 'cards.html', 'exercises.html', 'practice.html'];
const WIDTHS = [360, 390, 430, 600, 768, 820, 1024, 1366, 1440, 1920];
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 15000 }).toBe(true); }
test.beforeEach(async () => { fs.rmSync(ROOT, { recursive: true, force: true }); server = startServer(); await ready(); });
test.afterEach(() => { if (server && !server.killed) server.kill(); server = null; });

test('learning pages remain usable across the approved viewport matrix', async ({ page }) => {
  for (const name of PAGES) {
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(`${BASE}/app/${name}`);
      await expect(page.locator('main')).toBeVisible();
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      const toggle = page.getByRole('button', { name: '更多' });
      if (width <= 920) { await expect(toggle).toBeVisible(); await toggle.press('Enter'); await expect(page.locator('#primary-navigation')).toHaveClass(/is-open/); }
      await page.keyboard.press('Tab');
      await expect(page.locator(':focus-visible')).toHaveCount(1);
    }
  }
});

test('learning page list failures are safe and expose retry-capable controls', async ({ page }) => {
  const cases = [
    ['plans.html', '**/api/study/goals', '#goal-status', '#refresh-all'],
    ['notes.html', '**/api/study/notes', '#note-status', '#refresh-notes'],
    ['cards.html', '**/api/study/decks', '#deck-status', '#refresh-decks'],
    ['exercises.html', '**/api/study/exercise-sets', '#set-status', '#refresh-sets'],
    ['practice.html', '**/api/study/practice-sessions', '#session-status', '#refresh-sessions'],
  ];
  for (const [name, route, status, retry] of cases) {
    await page.route(route, routeCall => routeCall.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'private_backend_error', path: 'C:/secret', traceback: 'hidden' }) }));
    await page.goto(`${BASE}/app/${name}`);
    await expect(page.locator(status)).toContainText('请求失败');
    await expect(page.locator(retry)).toBeEnabled();
    await expect(page.locator('body')).not.toContainText(/private_backend_error|C:\/|traceback/i);
    await page.unroute(route);
  }
});
