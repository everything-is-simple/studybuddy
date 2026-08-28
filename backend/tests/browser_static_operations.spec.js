const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/static-operations';
const PORT = 8888;
const BASE = `http://127.0.0.1:${PORT}`;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true
  });
}

async function waitReady() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

function stopServer(server) { if (server && !server.killed) server.kill(); }

test('A3-3: materials.html has real operation UI elements', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  const server = startServer();
  
  try {
    await waitReady();
    await page.goto(`${BASE}/app/materials.html`);
    
    // Core page structure
    await expect(page.locator('h1')).toContainText('你的学习材料');
    
    // Upload UI
    await expect(page.locator('#upload-area')).toBeVisible();
    await expect(page.locator('#file-input')).toBeAttached();
    await expect(page.locator('#upload-status')).toBeAttached();
    
    // Search and filter controls
    await expect(page.locator('#search-input')).toBeVisible();
    await expect(page.locator('#status-filter')).toBeVisible();
    await expect(page.locator('#apply-filters')).toBeVisible();
    
    // View controls
    await expect(page.locator('#view-deleted')).toBeVisible();
    await expect(page.locator('#view-deleted')).toContainText('查看回收站');
    
    // List structure
    await expect(page.locator('#items')).toBeVisible();
    await expect(page.locator('#list-title')).toContainText('材料列表');
    await expect(page.locator('#state')).toBeVisible();
    
    // Pagination controls
    await expect(page.locator('#pagination')).toBeAttached();
    
  } finally {
    stopServer(server);
  }
});

test('A3-3: material-detail.html has export operation UI elements', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  const server = startServer();
  
  try {
    await waitReady();
    
    // Navigate with a fake ID to check UI structure
    await page.goto(`${BASE}/app/material-detail.html?material=test-id`);
    
    // Page structure should be present even if material doesn't exist
    await expect(page.locator('h1')).toBeVisible();
    
    // Export buttons should be in DOM (may be disabled)
    await expect(page.locator('#export-original')).toBeAttached();
    await expect(page.locator('#export-text')).toBeAttached();
    
  } finally {
    stopServer(server);
  }
});

test('A3-3: qa.html page structure is present', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  const server = startServer();
  
  try {
    await waitReady();
    
    await page.goto(`${BASE}/app/qa.html`);
    
    // Page loads successfully
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('body')).toContainText('材料');
    
  } finally {
    stopServer(server);
  }
});

test('A3-3: static pages support JavaScript API calls', async ({page}) => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  fs.mkdirSync(RUN_ROOT, {recursive: true});
  const server = startServer();
  
  try {
    await waitReady();
    
    await page.goto(`${BASE}/app/materials.html`);
    
    // Check that sbApi is loaded from api.js
    const hasApi = await page.evaluate(() => {
      return typeof window.sbApi !== 'undefined' && 
             typeof window.sbApi.json === 'function';
    });
    expect(hasApi).toBe(true);
    
    // Check that page loads data
    await expect(page.locator('#state')).not.toHaveText('加载中…', {timeout: 10000});
    
  } finally {
    stopServer(server);
  }
});
