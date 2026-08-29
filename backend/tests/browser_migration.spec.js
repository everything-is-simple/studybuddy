const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/migration';
const PORT = 8817;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT };
  env.STUDYBUDDY_AI_PROVIDER = 'fake';
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  for (let i = 0; i < 120; i += 1) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) { }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

function stop() { if (server && !server.killed) server.kill(); server = null; }

test.beforeEach(async () => { fs.rmSync(RUN_ROOT, { recursive: true, force: true }); server = startServer(); await ready(); });
test.afterEach(stop);

test('A3-6: root route redirects to new static frontend', async ({ page }) => {
  const response = await page.goto(BASE + '/');
  
  // Should redirect to /app/today.html
  expect(page.url()).toMatch(/\/app\/today\.html$/);
  
  // Should show the new UI
  await expect(page.locator('h1')).toContainText('你的学习日程');
  await expect(page.locator('.app-shell')).toBeVisible();
  await expect(page.locator('nav[data-nav]')).toBeVisible();
});

test('A3-6: legacy route still accessible', async ({ page }) => {
  await page.goto(`${BASE}/legacy`);
  
  // Should show the old embedded UI
  await expect(page.locator('h1')).toContainText('文件导入与问答', { timeout: 5000 });
  
  // Old UI has different structure
  const bodyText = await page.locator('body').textContent();
  expect(bodyText).toContain('材料');
});

test('A3-6: direct /app/ access still works', async ({ page }) => {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('h1')).toContainText('你的学习材料');
  
  await page.goto(`${BASE}/app/qa.html`);
  await expect(page.locator('h1')).toContainText('围绕材料提问');
});

test('A3-6: navigation from root works correctly', async ({ page }) => {
  await page.goto(BASE + '/');
  
  // Should land on today page
  await expect(page.locator('h1')).toContainText('你的学习日程');
  
  // Navigate to materials via nav
  await page.click('nav a[href="/app/materials.html"]');
  await expect(page).toHaveURL(new RegExp('/app/materials.html'));
  await expect(page.locator('h1')).toContainText('你的学习材料');
  
  // Navigate to cards
  await page.click('nav a[href="/app/cards.html"]');
  await expect(page).toHaveURL(new RegExp('/app/cards.html'));
  await expect(page.locator('h1')).toContainText('学习卡片组');
});

test('A3-6: old UI functionality preserved in legacy route', async ({ page }) => {
  await page.goto(`${BASE}/legacy`);
  
  // Check old UI page loads successfully
  await expect(page.locator('h1')).toContainText('文件导入与问答', { timeout: 5000 });
  
  // Check some form elements exist (IDs may vary, so just verify page structure)
  const bodyText = await page.locator('body').textContent();
  expect(bodyText).toContain('材料');
  expect(bodyText).toContain('问答');
});

test('A3-6: API endpoints unaffected by route change', async ({ page }) => {
  // Test that API still works after migration
  const response = await page.request.get(`${BASE}/api/health`);
  expect(response.ok()).toBeTruthy();
  
  const readiness = await page.request.get(`${BASE}/api/readiness`);
  expect(readiness.ok()).toBeTruthy();
  
  const materials = await page.request.get(`${BASE}/api/materials`);
  expect(materials.ok()).toBeTruthy();
});
