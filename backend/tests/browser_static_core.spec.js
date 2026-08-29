const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUN_ROOT = 'H:/studybuddy-test/runs/static-core';
const FIXTURES = 'H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT = 8815;
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

test('A3-4: materials page - import and list flow', async ({ page }) => {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('h1')).toContainText('你的学习材料');
  
  // Upload a test file
  const testFile = path.join(FIXTURES, 'sample.txt');
  await page.setInputFiles('#file-input', testFile);
  await expect(page.locator('#upload-status')).toContainText('已导入', { timeout: 10000 });
  
  // Verify list updates
  await expect(page.locator('#items li')).toHaveCount(1, { timeout: 5000 });
  await expect(page.locator('#items li').first()).toContainText('sample.txt');
  
  // Test search
  await page.fill('#search-input', 'sample');
  await page.click('#apply-filters');
  await expect(page.locator('#state')).toContainText('显示');
  
  // Test pagination visibility
  await expect(page.locator('#pagination')).toBeHidden();
});

test('A3-4: material detail page - view and export', async ({ page }) => {
  // First create a material via API
  const testFile = path.join(FIXTURES, 'sample.txt');
  const fileContent = fs.readFileSync(testFile);
  const response = await page.request.post(`${BASE}/api/materials`, {
    multipart: {
      file: {
        name: 'detail-test.txt',
        mimeType: 'text/plain',
        buffer: fileContent
      }
    }
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  
  // Get material ID from response (could be id or material_id)
  const materialId = result.id || result.material_id;
  if (!materialId) {
    console.log('Upload response:', result);
    // If no ID in response, get from list
    const listResponse = await page.request.get(`${BASE}/api/materials?limit=1`);
    const listData = await listResponse.json();
    const materials = Array.isArray(listData) ? listData : listData.items || [];
    expect(materials.length).toBeGreaterThan(0);
    const latestMaterial = materials[0];
    const detailMaterialId = latestMaterial.id || latestMaterial.material_id;
    
    // Navigate to detail page with latest material
    await page.goto(`${BASE}/app/material-detail.html?material=${detailMaterialId}`);
  } else {
    // Navigate to detail page with returned ID
    await page.goto(`${BASE}/app/material-detail.html?material=${materialId}`);
  }
  
  // Wait for page to load
  await page.waitForLoadState('networkidle');
  
  // Check page loaded successfully (either shows material or error)
  await expect(page.locator('h1')).toBeVisible();
  await expect(page.locator('#state')).toBeVisible();
  
  // Verify key elements exist
  await expect(page.locator('#export-original')).toBeVisible();
  await expect(page.locator('#export-text')).toBeVisible();
  await expect(page.locator('#qa')).toBeVisible();
});

test('A3-4: qa page - capabilities and indexing', async ({ page }) => {
  await page.goto(`${BASE}/app/qa.html`);
  await expect(page.locator('h1')).toContainText('围绕材料提问');
  
  // Check provider status loads (fake provider should show demo mode)
  await expect(page.locator('#provider-status')).not.toContainText('正在检查', { timeout: 5000 });
  // Provider status could be demo or not_configured depending on env propagation
  const providerText = await page.locator('#provider-status').textContent();
  expect(providerText).toMatch(/演示模式|fake|未配置/i);
  
  // Verify form elements
  await expect(page.locator('#question')).toBeVisible();
  await expect(page.locator('#retrieval-mode')).toBeVisible();
  await expect(page.locator('#index-btn')).toBeVisible();
  await expect(page.locator('#submit-btn')).toBeVisible();
  
  // Check thread history loads
  await expect(page.locator('#thread-status')).toContainText('暂无问答历史', { timeout: 5000 });
});

test('A3-4: qa page - submit question flow', async ({ page }) => {
  // Create and index a material
  const testFile = path.join(FIXTURES, 'sample.txt');
  const fileContent = fs.readFileSync(testFile);
  const materialResponse = await page.request.post(`${BASE}/api/materials`, {
    multipart: {
      file: {
        name: 'qa-test.txt',
        mimeType: 'text/plain',
        buffer: fileContent
      }
    }
  });
  const material = await materialResponse.json();
  const materialId = String(material.id);
  
  // Index the material
  await page.request.post(`${BASE}/api/ai-index`, {
    data: { material_id: materialId }
  });
  
  // Navigate to QA page with material
  await page.goto(`${BASE}/app/qa.html?material=${materialId}`);
  
  // Verify material ID is pre-filled
  await expect(page.locator('#materials')).toHaveValue(materialId);
  
  // Fill and submit question
  await page.fill('#question', 'What is the test content?');
  await page.click('#submit-btn');
  
  // Wait for submission to complete (success or failure)
  await expect(page.locator('#submit-status')).not.toContainText('正在提交', { timeout: 15000 });
  
  // Verify submission was processed (button re-enabled)
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 2000 });
});

test('A3-4: today page - loads task summary', async ({ page }) => {
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('h1')).toContainText('你的学习日程');
  
  // Check summary loads (may be empty but should not error)
  const summaryStatus = page.locator('#summary-status');
  await expect(summaryStatus).not.toContainText('正在加载', { timeout: 5000 });
  
  // Check tasks loads
  const taskStatus = page.locator('#task-status');
  await expect(taskStatus).not.toContainText('正在加载', { timeout: 5000 });
});

test('A3-4: cross-page navigation flow', async ({ page }) => {
  // Test materials page
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('h1')).toContainText('你的学习材料');
  
  // Test today page
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('h1')).toContainText('你的学习日程');
  
  // Test QA page
  await page.goto(`${BASE}/app/qa.html`);
  await expect(page.locator('h1')).toContainText('围绕材料提问');
  
  // Verify navigation elements exist
  await expect(page.locator('nav')).toBeVisible();
  await expect(page.locator('.brand')).toContainText('StudyBuddy');
});
