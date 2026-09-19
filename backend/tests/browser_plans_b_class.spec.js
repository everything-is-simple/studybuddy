const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// B-class independent review for plans.html. Stale-response boundaries use
// route mocks over the real server; all business data is created through the
// page UI only. These tests re-read the page contract independently of the
// A-class userpath spec.
let ROOT = 'H:/studybuddy-test/runs/plans-b-class';
const PORT = 8970;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT };
  env.STUDYBUDDY_AI_PROVIDER = 'fake';
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 20000 }).toBe(true);
}

function stopServer() {
  return new Promise(resolve => {
    if (!server || server.killed) { server = null; return resolve(); }
    let settled = false;
    const finish = () => { if (!settled) { settled = true; server = null; resolve(); } };
    server.once('exit', finish);
    server.kill();
    setTimeout(finish, 5000);
  });
}

// The page silently drops mutations while a previous mutation is still
// in flight (busy guard, by design). Every helper therefore waits for the
// explicit success status message, which the page sets only after the full
// reload + detail re-render completes and busy is cleared again.
async function createGoal(page, title) {
  await page.fill('#goal-title', title);
  await page.click('#goal-form button[type="submit"]');
  await expect(page.locator('#plan-status')).toHaveText('目标已创建', { timeout: 10000 });
  await expect(page.locator('#goals li').filter({ hasText: title }).first()).toBeVisible({ timeout: 10000 });
}

async function createPlan(page, title) {
  await page.fill('#plan-title', title);
  await page.selectOption('#plan-goal', { index: 0 });
  await page.click('#plan-form button[type="submit"]');
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建', { timeout: 10000 });
  await expect(page.locator('#plans li').filter({ hasText: title }).first()).toBeVisible({ timeout: 10000 });
}

async function addPlanItem(page, title) {
  await page.fill('#plan-item-title', title);
  await page.click('#plan-item-add');
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加', { timeout: 10000 });
  // Item titles are rendered as input values, not text content.
  await expect(page.locator('.plan-item-entry input').first()).toHaveValue(title, { timeout: 10000 });
}

test.describe.serial('plans.html B-class independent review', () => {
  test.beforeAll(async () => {
    ROOT = `H:/studybuddy-test/runs/plans-b-class-${Date.now()}`;
    fs.mkdirSync(ROOT, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('B-PLAN-1 迟到计划列表失败不得覆盖新加载状态', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载计划…', { timeout: 10000 });
    await createGoal(page, 'B类目标一');
    await createPlan(page, 'B类计划一');
    // One-shot delayed failure for the plans list; the refresh that follows
    // must complete first, and the late failure must be discarded.
    let captured = false;
    await page.route('**/api/study/plans', async route => {
      if (route.request().method() === 'GET' && !captured) {
        captured = true;
        await new Promise(resolve => setTimeout(resolve, 800));
        return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'database_unavailable' }) });
      }
      return route.fallback();
    });
    await page.locator('#refresh-all').click();
    await page.locator('#refresh-all').click();
    await expect(page.locator('#plans li').filter({ hasText: 'B类计划一' })).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(1100);
    // The late failure must not corrupt the freshly loaded state.
    await expect(page.locator('#plan-status')).not.toContainText('数据暂时不可用');
    await expect(page.locator('#goal-status')).toHaveText('');
    await expect(page.locator('#module-status')).toHaveText('暂无模块');
    await expect(page.locator('#plans li').filter({ hasText: 'B类计划一' })).toBeVisible();
    await page.unroute('**/api/study/plans');
  });

  test('B-PLAN-2 快速切换计划时迟到来源链接不得串页', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载计划…', { timeout: 10000 });
    await createGoal(page, '来源竞态目标');
    await createPlan(page, '计划甲');
    await addPlanItem(page, '甲的学习项');
    await createPlan(page, '计划乙');
    await addPlanItem(page, '乙的学习项');
    // Current page behavior (post b39bba8): 计划甲's selection is discarded
    // BEFORE it issues any sources request, so the first sources query after
    // route install would belong to 计划乙 itself. To still exercise the
    // late-response guard, capture 计划甲's query and HOLD it in flight, then
    // switch to 计划乙, let 乙's own query pass through, and only release the
    // stale 甲 response afterwards.
    let captured = false;
    let releaseHold = () => {};
    const holdCaptured = new Promise(resolve => { releaseHold = resolve; });
    let releaseResponse = () => {};
    await page.route('**/api/study/sources?*', async route => {
      if (!captured) {
        captured = true;
        releaseHold();
        await new Promise(resolve => { releaseResponse = resolve; });
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([
          { id: 's-late', material_id: 'LATE-PLAN-JIA', chunk_id: 'c-late', status: 'valid' },
        ]) });
      }
      return route.fallback();
    });
    await page.locator('#plans li').filter({ hasText: '计划甲' }).first().click();
    // 计划甲's sources query is now held in flight with no response yet.
    await holdCaptured;
    // Switch to 计划乙 while 计划甲's query is still pending.
    await page.locator('#plans li').filter({ hasText: '计划乙' }).first().click();
    await expect(page.locator('#plan-detail h3').first()).toHaveText('计划乙', { timeout: 5000 });
    await expect(page.locator('#source-status')).toContainText('暂无来源链接', { timeout: 5000 });
    // Only now release 计划甲's stale response.
    releaseResponse();
    await page.waitForTimeout(300);
    // The late 计划甲 response must be discarded: the visible plan stays 乙.
    await expect(page.locator('#plan-detail h3').first()).toHaveText('计划乙');
    await expect(page.locator('#source-links')).not.toContainText('LATE-PLAN-JIA');
    await expect(page.locator('#source-status')).toContainText('暂无来源链接');
    await page.unroute('**/api/study/sources?*');
  });

  test('B-PLAN-3 恶意目标与计划标题按纯文本渲染，不创建 HTML 节点', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载计划…', { timeout: 10000 });
    const payload = '<img src=x onerror="window.__planXss=1"><script>window.__planXss=2</script>';
    await createGoal(page, payload);
    await createPlan(page, payload + '计划');
    expect(await page.locator('#goals img, #goals script').count()).toBe(0);
    expect(await page.locator('#plans img, #plans script').count()).toBe(0);
    expect(await page.evaluate(() => window.__planXss)).toBeUndefined();
    await expect(page.locator('#goals li').first()).toContainText('<img src=x');
    await expect(page.locator('#plans li').first()).toContainText('<img src=x');
  });

  test('B-PLAN-4 慢创建期间表单控件禁用且不产生重复目标', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载计划…', { timeout: 10000 });
    await page.route('**/api/study/goals', async route => {
      if (route.request().method() === 'POST') {
        await new Promise(resolve => setTimeout(resolve, 800));
      }
      return route.fallback();
    });
    await page.fill('#goal-title', '慢创建目标');
    await page.click('#goal-form button[type="submit"]');
    // During the in-flight create every form control except 刷新数据 is disabled.
    await expect(page.locator('#goal-title')).toBeDisabled();
    await expect(page.locator('#goal-form button[type="submit"]')).toBeDisabled();
    await expect(page.locator('#plan-title')).toBeDisabled();
    await expect(page.locator('#refresh-all')).toBeEnabled();
    await expect(page.locator('#goals li').filter({ hasText: '慢创建目标' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#plan-status')).toContainText('目标已创建');
    // The disabled form made a duplicate submit impossible.
    await expect(page.locator('#goals li').filter({ hasText: '慢创建目标' })).toHaveCount(1);
    await expect(page.locator('#goal-title')).toBeEnabled();
    await page.unroute('**/api/study/goals');
  });
});
