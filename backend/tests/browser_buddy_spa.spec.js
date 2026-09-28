const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = `H:/studybuddy-test/runs/buddy-spa-${Date.now()}`;
const PORT = 8962;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  return spawn(process.env.STUDYBUDDY_TEST_PYTHON || 'D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
function stop() { if (server && !server.killed) server.kill(); server = null; }

test.describe('Buddy native SPA shell', () => {
  test.beforeAll(async () => { fs.mkdirSync(RUN_ROOT, { recursive: true }); server = startServer(); await ready(); });
  test.afterAll(() => stop());

  test('切换 Buddy 页面使用 History API 且不刷新顶层文档', async ({ page }) => {
    let topLoads = 0;
    page.on('load', () => { topLoads += 1; });
    await page.goto(`${BASE}/app/buddy.html?view=today`);
    await expect(page.locator('#buddy-status')).toHaveText('今天页面已打开');
    await expect(page.locator('#buddy-frame')).toHaveAttribute('src', '/app/today.html');
    const frame = page.frameLocator('#buddy-frame');
    await expect(frame.locator('h1')).toHaveText('今天学什么？');
    await page.getByRole('link', { name: '学生' }).click();
    await expect(page).toHaveURL(/buddy\.html\?view=student/);
    await expect(page.locator('#buddy-status')).toHaveText('学生页面已打开');
    await expect(page.locator('#buddy-frame')).toHaveAttribute('src', '/app/student.html');
    await expect(page.frameLocator('#buddy-frame').locator('#student-greeting')).toHaveText('早上好！');
    await page.getByRole('link', { name: '家长' }).click();
    await expect(page).toHaveURL(/buddy\.html\?view=parent/);
    await expect(page.locator('#buddy-frame')).toHaveAttribute('src', '/app/parent.html');
    await expect(page.frameLocator('#buddy-frame').locator('h1')).toHaveText('学习安排');
    expect(topLoads).toBe(1);
  });

  test('学生/家长视图切换会持久化且学生模式隐藏管理入口', async ({ page }) => {
    await page.goto(`${BASE}/app/buddy.html`);
    await expect(page).toHaveURL(/buddy\.html\?view=student/);
    await expect(page.locator('[data-switch-view="student"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-management-link="true"]')).toBeHidden();
    await page.locator('[data-switch-view="parent"]').click();
    await expect(page).toHaveURL(/buddy\.html\?view=parent/);
    await expect(page.locator('[data-management-link="true"]')).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/buddy\.html\?view=parent/);
    await expect(page.locator('[data-switch-view="parent"]')).toHaveAttribute('aria-pressed', 'true');
  });

  test('390px 视口使用汉堡导航且无横向溢出', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/app/buddy.html?view=parent`);
    const toggle = page.locator('[data-mobile-nav-toggle]');
    await expect(toggle).toBeVisible();
    await expect(page.locator('#buddy-navigation')).toBeHidden();
    await toggle.click();
    await expect(page.locator('#buddy-navigation')).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
    await page.locator('#buddy-navigation a[data-view="student"]').click();
    await expect(page.locator('#buddy-navigation')).toBeHidden();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });
});
