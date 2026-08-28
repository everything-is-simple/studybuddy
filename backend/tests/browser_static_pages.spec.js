const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-static-pages';
const PORT = 8801;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT };
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
async function waitReady() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stopServer(server) { if (server && !server.killed) server.kill(); }

test('A3-2 static pages: route reachability, content, narrow screen, keyboard, privacy', async ({ page }) => {
  fs.rmSync(RUN_ROOT, { recursive: true, force: true });
  fs.mkdirSync(RUN_ROOT, { recursive: true });

  const consoleErrors = [];
  const pageErrors = [];
  const externalRequests = [];
  page.on('console', m => {
    if (m.type() === 'error' && !m.text().includes('Failed to load resource')) {
      consoleErrors.push(m.text());
    }
  });
  page.on('pageerror', e => pageErrors.push(e.message));
  page.on('request', r => { if (!r.url().startsWith(BASE)) externalRequests.push(r.url()); });
  page.on('response', async response => {
    if (response.status() === 404 && response.url().startsWith(BASE)) {
      const url = response.url();
      // Intentional 404s for invalid material ID tests
      if (url.includes('/api/materials/nonexistent') || url.includes('/api/materials/fake')) return;
      consoleErrors.push(`404: ${url}`);
    }
  });

  let server = startServer();
  try {
    await waitReady();

    // ── 1. Root / still returns full workspace ──────────────────────────────
    await page.goto(BASE);
    await expect(page).toHaveTitle(/StudyBuddy/i);
    await expect(page.locator('#file')).toBeVisible();
    const workspaceHtml = await page.content();
    expect(workspaceHtml).toContain('文件导入');
    expect(workspaceHtml).not.toContain('A3-1');
    stopServer(server); server = null;
    await new Promise(r => setTimeout(r, 500));
    server = startServer();
    await waitReady();

    // ── 2. /app/ today page ────────────────────────────────────────────────
    await page.goto(`${BASE}/app/`);
    await expect(page).toHaveTitle(/StudyBuddy.*今天/i);
    await expect(page.locator('.brand')).toHaveText('StudyBuddy');
    await expect(page.locator('[data-nav]')).toBeVisible();
    await expect(page.locator('[data-system-status]')).toBeVisible();
    await expect(page.locator('[data-od-id="today-main"]')).toBeVisible();
    await expect(page.locator('a[href="/app/materials.html"]').first()).toBeVisible();
    await expect(page.locator('.footer-note')).toContainText('原入口');

    // Nav links all resolve
    const navLinks = await page.locator('[data-nav] a').all();
    expect(navLinks.length).toBeGreaterThanOrEqual(4);
    for (const link of navLinks) {
      const href = await link.getAttribute('href');
      expect(href).toMatch(/^\/app\//);
    }

    // System status shows something reasonable (not a raw path or SQL)
    const statusText = await page.locator('[data-system-status]').textContent();
    expect(statusText).toMatch(/就绪|未知|不可用|状态/);
    expect(statusText).not.toMatch(/H:/);
    expect(statusText).not.toMatch(/sqlite|SELECT|FROM/);

    // ── 3. /app/materials.html ─────────────────────────────────────────────
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page).toHaveTitle(/StudyBuddy.*资料/i);
    await expect(page.locator('#refresh')).toBeVisible();
    await expect(page.locator('#state')).toBeVisible();
    await expect(page.locator('#items')).toBeVisible();
    // State should show something other than an error on clean start
    const stateText = await page.locator('#state').textContent();
    expect(stateText).toMatch(/加载中|暂无材料|\d+ 份材料/);
    expect(stateText).not.toMatch(/H:/);
    expect(stateText).not.toMatch(/sqlite|SELECT|FROM/);

    // Refresh button is clickable
    await expect(page.locator('#refresh')).toBeEnabled();
    await page.locator('#refresh').click();
    await expect(page.locator('#state')).not.toHaveText('加载中…');

    // Footer note preserves migration boundary
    await expect(page.locator('.footer-note')).toContainText('原工作区');

    // ── 4. /app/material-detail.html without id ────────────────────────────
    await page.goto(`${BASE}/app/material-detail.html`);
    await expect(page).toHaveTitle(/StudyBuddy.*材料详情/i);
    await expect(page.locator('#title')).toContainText('缺少材料标识');
    const qaBtn = page.locator('#qa');
    expect(await qaBtn.getAttribute('href')).toBeNull();

    // ── 5. /app/material-detail.html with invalid id ───────────────────────
    await page.goto(`${BASE}/app/material-detail.html?material=nonexistent-id-xyz`);
    await expect(page.locator('#title')).toContainText('材料不可用');
    const detailState = await page.locator('#state').textContent();
    expect(detailState).toMatch(/请求失败|不可用|已删除/);
    expect(detailState).not.toMatch(/H:/);
    expect(detailState).not.toMatch(/sqlite|SELECT|FROM/);
    expect(detailState).not.toMatch(/password|secret|key|token/);

    // ── 6. /app/qa.html ────────────────────────────────────────────────────
    await page.goto(`${BASE}/app/qa.html`);
    await expect(page).toHaveTitle(/StudyBuddy.*问答/i);
    await expect(page.locator('[data-od-id="qa-thread"]')).toBeVisible();
    // Should show empty or loading state, not crash
    const qaState = await page.locator('[role="status"]').textContent();
    expect(qaState).toMatch(/加载中|暂无|条对话/);
    expect(qaState).not.toMatch(/H:/);
    expect(qaState).not.toMatch(/sqlite|SELECT|FROM/);

    // ── 7. Narrow viewport (360px) ─────────────────────────────────────────
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#refresh')).toBeVisible();
    await expect(page.locator('#refresh')).toBeEnabled();
    await expect(page.locator('.brand')).toBeVisible();
    await expect(page.locator('[data-nav] a').first()).toBeVisible();
    // No horizontal scroll
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const clientWidth = await page.evaluate(() => document.body.clientWidth);
    expect(bodyWidth).toBeLessThanOrEqual(clientWidth + 2);

    // ── 8. Keyboard navigation ─────────────────────────────────────────────
    await page.keyboard.press('Tab');
    // First focus target should be the brand link
    const focusedTag = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.tagName.toLowerCase() : 'none';
    });
    expect(['a', 'button', 'input']).toContain(focusedTag);

    // Tab through to refresh button and activate
    for (let i = 0; i < 10; i++) await page.keyboard.press('Tab');
    const refreshFocused = await page.evaluate(() => document.activeElement?.id === 'refresh');
    if (refreshFocused) {
      await page.keyboard.press('Enter');
      await page.waitForTimeout(300);
      const newState = await page.locator('#state').textContent();
      expect(newState).not.toBe('加载中…');
    }

    // ── 9. Privacy: no raw paths, SQL, or secrets in any page text ──────────
    const privacyPatterns = [
      /H:\\\\studybuddy/,
      /C:\\\\miniconda/,
      /sqlite3|pragma\s+table_info/i,
      /password|secret|token|api[_-]?key/i,
      /Traceback|File ".*\.py"/i,
    ];
    await page.goto(`${BASE}/app/`);
    const rootText = await page.locator('body').textContent();
    for (const pat of privacyPatterns) {
      expect(rootText).not.toMatch(pat);
    }
    await page.goto(`${BASE}/app/material-detail.html?material=fake`);
    const detailText = await page.locator('body').textContent();
    for (const pat of privacyPatterns) {
      expect(detailText).not.toMatch(pat);
    }

    // ── 10. No external network requests ───────────────────────────────────
    expect(externalRequests).toEqual([]);
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);

  } finally {
    stopServer(server);
  }
});
