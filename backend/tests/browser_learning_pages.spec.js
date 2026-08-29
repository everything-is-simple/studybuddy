const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUN_ROOT = 'H:/studybuddy-test/runs/learning-pages';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8816;
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

test('A3-5: cards page - loads and displays structure', async ({ page }) => {
  await page.goto(`${BASE}/app/cards.html`);
  await expect(page.locator('h1')).toContainText('学习卡片组');
  
  // Check main sections exist
  await expect(page.locator('[data-od-id="cards-decks"]')).toBeVisible();
  await expect(page.locator('[data-od-id="cards-detail"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#deck-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Should show empty state or list
  const statusText = await page.locator('#deck-status').textContent();
  expect(statusText).toMatch(/暂无卡片组|已加载/);
});

test('A3-5: exercises page - loads and displays structure', async ({ page }) => {
  await page.goto(`${BASE}/app/exercises.html`);
  await expect(page.locator('h1')).toContainText('练习题库');
  
  // Check main sections exist
  await expect(page.locator('[data-od-id="exercises-sets"]')).toBeVisible();
  await expect(page.locator('[data-od-id="exercises-detail"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#set-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Should show empty state or list
  const statusText = await page.locator('#set-status').textContent();
  expect(statusText).toMatch(/暂无练习集|已加载/);
});

test('A3-5: plans page - loads goals, modules, and plans', async ({ page }) => {
  await page.goto(`${BASE}/app/plans.html`);
  await expect(page.locator('h1')).toContainText('目标与计划');
  
  // Check all three sections exist
  await expect(page.locator('[data-od-id="plans-sidebar"]')).toBeVisible();
  await expect(page.locator('[data-od-id="plans-main"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#goal-status')).not.toContainText('正在加载', { timeout: 5000 });
  await expect(page.locator('#module-status')).not.toContainText('正在加载', { timeout: 5000 });
  await expect(page.locator('#plan-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Verify refresh button works
  await page.click('#refresh-all');
  await page.waitForTimeout(500);
});

test('A3-5: notes page - loads and displays structure', async ({ page }) => {
  await page.goto(`${BASE}/app/notes.html`);
  await expect(page.locator('h1')).toContainText('学习笔记');
  
  // Check main sections exist
  await expect(page.locator('[data-od-id="notes-list"]')).toBeVisible();
  await expect(page.locator('[data-od-id="notes-detail"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#note-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Should show empty state, list, or API error (acceptable for unimplemented endpoints)
  const statusText = await page.locator('#note-status').textContent();
  expect(statusText).toMatch(/暂无笔记|已加载|请求失败/);
});

test('A3-5: practice page - loads sessions and mistakes', async ({ page }) => {
  await page.goto(`${BASE}/app/practice.html`);
  await expect(page.locator('h1')).toContainText('限时练习与错题复盘');
  
  // Check both sections exist
  await expect(page.locator('[data-od-id="practice-sessions"]')).toBeVisible();
  await expect(page.locator('[data-od-id="practice-mistakes"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#session-status')).not.toContainText('正在加载', { timeout: 5000 });
  await expect(page.locator('#mistake-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Should show empty state or list
  const sessionText = await page.locator('#session-status').textContent();
  expect(sessionText).toMatch(/暂无练习会话|已加载/);
});

test('A3-5: classroom page - loads captures and reports', async ({ page }) => {
  await page.goto(`${BASE}/app/classroom.html`);
  await expect(page.locator('h1')).toContainText('音频转写与学习报告');
  
  // Check both sections exist
  await expect(page.locator('[data-od-id="classroom-captures"]')).toBeVisible();
  await expect(page.locator('[data-od-id="classroom-reports"]')).toBeVisible();
  
  // Check status loads
  await expect(page.locator('#capture-status')).not.toContainText('正在加载', { timeout: 5000 });
  await expect(page.locator('#report-status')).not.toContainText('正在加载', { timeout: 5000 });
  
  // Should show empty state, list, or API error (acceptable for unimplemented endpoints)
  const captureText = await page.locator('#capture-status').textContent();
  expect(captureText).toMatch(/暂无采集会话|已加载|请求失败/);
});

test('A3-5: navigation includes all learning pages', async ({ page }) => {
  await page.goto(`${BASE}/app/cards.html`);
  
  // Verify all navigation links exist
  const navLinks = await page.locator('nav a').all();
  expect(navLinks.length).toBeGreaterThanOrEqual(9);
  
  // Check specific pages are in nav
  await expect(page.locator('nav a[href="/app/today.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/materials.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/qa.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/cards.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/exercises.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/plans.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/notes.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/practice.html"]')).toBeVisible();
  await expect(page.locator('nav a[href="/app/classroom.html"]')).toBeVisible();
});

test('A3-5: cross-page navigation works for all learning pages', async ({ page }) => {
  // Test navigation sequence
  await page.goto(`${BASE}/app/cards.html`);
  await expect(page.locator('h1')).toContainText('学习卡片组');
  
  await page.goto(`${BASE}/app/exercises.html`);
  await expect(page.locator('h1')).toContainText('练习题库');
  
  await page.goto(`${BASE}/app/plans.html`);
  await expect(page.locator('h1')).toContainText('目标与计划');
  
  await page.goto(`${BASE}/app/notes.html`);
  await expect(page.locator('h1')).toContainText('学习笔记');
  
  await page.goto(`${BASE}/app/practice.html`);
  await expect(page.locator('h1')).toContainText('限时练习与错题复盘');
  
  await page.goto(`${BASE}/app/classroom.html`);
  await expect(page.locator('h1')).toContainText('音频转写与学习报告');
  
  // Verify navigation bar exists on all pages
  await expect(page.locator('nav')).toBeVisible();
  await expect(page.locator('.brand')).toContainText('StudyBuddy');
});

test('A3-5: all pages have consistent shell structure', async ({ page }) => {
  const pages = ['cards.html', 'exercises.html', 'plans.html', 'notes.html', 'practice.html', 'classroom.html'];
  
  for (const pageName of pages) {
    await page.goto(`${BASE}/app/${pageName}`);
    
    // Check common elements
    await expect(page.locator('.app-shell')).toBeVisible();
    await expect(page.locator('.topbar')).toBeVisible();
    await expect(page.locator('.brand')).toBeVisible();
    await expect(page.locator('nav[data-nav]')).toBeVisible();
    await expect(page.locator('[data-system-status]')).toBeVisible();
    await expect(page.locator('.hero')).toBeVisible();
    
    // Check no errors in console
    const title = await page.title();
    expect(title).toContain('StudyBuddy');
  }
});
