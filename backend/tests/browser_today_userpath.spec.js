const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// A-class pure user-path E2E for today.html.
// Rule: no business API calls from test code. The goal, plan, item, rhythm
// setting and allocation are all created through the /app plans page UI. The
// only fault injection is page-level route interception (no data is created or
// read through APIs by the test itself).
// Chain: empty states -> plan created+activated via UI -> "nothing scheduled
//        today" boundary -> allocate today via UI -> task card ->
//        plan-detail start/complete -> return to today -> failure injection +
//        retry -> reload + narrow viewport -> server restart persistence ->
//        pause/resume boundary.
let RUN_ROOT = 'H:/studybuddy-test/runs/today-userpath';
const ART = 'H:/studybuddy-test/artifacts/today-userpath';
const PORT = 8955;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const PLAN_TITLE = '今日链路验证计划';
const ITEM_TITLE = '今日分配的学习项';
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
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

function today() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
}

test.describe.serial('today.html pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/today-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-TD-1 空数据根：三区独立空态与下一步出口', async ({ page }) => {
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#summary-status')).toHaveText('还没有学习计划', { timeout: 10000 });
    await expect(page.locator('#weekly-status')).toHaveText('还没有学习计划，暂无周趋势');
    await expect(page.locator('#task-status')).toHaveText('还没有学习计划');
    const exits = page.locator('#today-exits');
    await expect(exits.getByRole('link', { name: '创建学习计划' })).toHaveAttribute('href', '/app/plans.html');
    await expect(page.locator('#retry-today')).toBeHidden();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-TD-2 经 UI 建立并激活计划：无分配边界 → 安排今日 → 任务卡真实出现', async ({ page }) => {
    // 1) Create goal -> plan -> item -> confirm -> activate via the plans UI.
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载', { timeout: 10000 });
    await page.fill('#goal-title', '今日链路验证目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#plan-status')).toHaveText('目标已创建');
    await page.fill('#plan-title', PLAN_TITLE);
    await page.locator('#plan-goal').selectOption({ label: '今日链路验证目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', ITEM_TITLE);
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
    await page.getByRole('button', { name: '确认草稿' }).click();
    await expect(page.locator('#plan-status')).toHaveText('确认草稿成功');
    await page.getByRole('button', { name: '激活计划' }).click();
    await expect(page.locator('#plan-status')).toHaveText('激活计划成功');

    // 2) Activated but nothing allocated: today must say so and offer next steps.
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE, { timeout: 10000 });
    await expect(page.locator('#weekly-trend .rhythm-card')).toHaveCount(7);
    await expect(page.locator('#task-status')).toHaveText(`计划「${PLAN_TITLE}」今日没有安排学习项`);
    const exits = page.locator('#today-exits');
    await expect(exits.getByRole('link', { name: '查看计划详情' })).toHaveAttribute('href', /plan-detail\.html\?plan_id=.+/);
    await expect(exits.getByRole('link', { name: '安排今日学习' })).toHaveAttribute('href', /plans\.html\?plan_id=.+/);
    await assertNoSensitiveVisibleText(page);

    // 3) Follow the offered exit back to the plan and allocate today via the UI.
    await exits.getByRole('link', { name: '安排今日学习' }).click();
    await expect(page).toHaveURL(/plans\.html\?plan_id=.+/);
    await expect(page.locator('#rhythm-cadence')).toBeVisible({ timeout: 10000 });
    await page.fill('#rhythm-period-start', today());
    await page.getByRole('button', { name: '保存节奏设置' }).click();
    await expect(page.locator('#plan-status')).toHaveText('学习节奏已保存');
    await page.locator('#rhythm-item').selectOption({ label: ITEM_TITLE });
    await expect(page.locator('#rhythm-date')).toHaveValue(today());
    await page.locator('#rhythm-minutes').fill('25');
    await page.getByRole('button', { name: '添加分配' }).click();
    await expect(page.locator('#plan-status')).toHaveText('学习项已分配');

    // 4) Today now shows the real task card with the return link.
    await page.goto(`${BASE}/app/today.html`);
    const task = page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE });
    await expect(task).toContainText(`计划 25 分钟 · ${today()}`, { timeout: 10000 });
    await expect(task).toContainText('来源状态: 未关联来源');
    await expect(task.getByRole('link', { name: '开始学习' })).toHaveAttribute('href',
      new RegExp(`plan-detail\\.html\\?plan_id=.+item_id=.+local_date=${today()}&return_to=today`));
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-TD-3 任务卡 → plan-detail 开始学习/记录完成 → 返回 today 状态即时反映', async ({ page }) => {
    await page.goto(`${BASE}/app/today.html`);
    const task = page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE });
    await expect(task).toBeVisible({ timeout: 10000 });
    await task.getByRole('link', { name: '开始学习' }).click();
    await expect(page).toHaveURL(/plan-detail\.html\?plan_id=.+item_id=.+return_to=today/);
    await page.getByRole('button', { name: '开始学习' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已开始学习', { timeout: 10000 });
    await page.getByRole('button', { name: '记录完成' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已完成学习');
    await page.getByRole('link', { name: '返回计划' }).click();
    await expect(page).toHaveURL(`${BASE}/app/today.html`);
    // The freshly loaded today page must reflect the completion immediately.
    await expect(page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE })).toContainText('查看进度', { timeout: 10000 });
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-TD-4 API 失败注入：三区安全文案 + #retry-today 真实恢复', async ({ page }) => {
    let failing = true;
    await page.route('**/api/study/plans', route => failing
      ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"H:/studybuddy/secret_traceback"}' })
      : route.continue());
    await page.goto(`${BASE}/app/today.html`);
    const retry = page.getByRole('button', { name: '重新加载' });
    await expect(retry).toBeVisible();
    for (const id of ['#summary-status', '#weekly-status', '#task-status']) {
      await expect(page.locator(id)).toContainText('请求失败');
    }
    // Injected backend traceback/path content must never reach the visible page.
    await expect(page.locator('body')).not.toContainText(/secret_traceback|H:\\|H:\//);
    failing = false;
    await page.unroute('**/api/study/plans');
    await retry.click();
    await expect(page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE })).toContainText('查看进度', { timeout: 10000 });
    await expect(retry).toBeHidden();
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-TD-5 刷新恢复 + 窄屏无横向溢出', async ({ page }) => {
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE })).toContainText('查看进度', { timeout: 10000 });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBeTruthy();
    await page.screenshot({ path: `${ART}/today-390.png`, fullPage: true });
    await page.setViewportSize({ width: 1280, height: 800 });
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE);
  });

  test('A-E2E-TD-6 服务真重启后：任务完成状态与概览持久化', async ({ page }) => {
    await stopServer();
    server = startServer();
    await ready();
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE })).toContainText('查看进度', { timeout: 15000 });
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE);
    await expect(page.locator('#weekly-trend .rhythm-card')).toHaveCount(7);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-TD-7 无 active 计划边界：暂停后明确文案与恢复路径', async ({ page }) => {
    // Pause the only plan through the plans page UI.
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#plan-status')).not.toContainText('正在加载', { timeout: 10000 });
    await page.locator('.plan-item', { hasText: PLAN_TITLE }).click();
    await page.getByRole('button', { name: '暂停计划' }).click();
    await expect(page.locator('#plan-status')).toHaveText('暂停计划成功');

    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#summary-status')).toHaveText('计划尚未启动', { timeout: 10000 });
    await expect(page.locator('#weekly-status')).toHaveText('计划尚未启动，暂无周趋势');
    await expect(page.locator('#task-status')).toHaveText('计划尚未启动');
    const exits = page.locator('#today-exits');
    await expect(exits.getByRole('link', { name: '前往激活' })).toHaveAttribute('href', /plans\.html\?plan_id=.+/);
    await assertNoSensitiveVisibleText(page);

    // Resume through the UI and verify today becomes active again.
    await exits.getByRole('link', { name: '前往激活' }).click();
    await expect(page).toHaveURL(/plans\.html\?plan_id=.+/);
    await page.getByRole('button', { name: '恢复计划' }).click();
    await expect(page.locator('#plan-status')).toHaveText('恢复计划成功');
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('#summary')).toContainText(PLAN_TITLE, { timeout: 10000 });
    await expect(page.locator('#tasks .task-item').filter({ hasText: ITEM_TITLE })).toContainText('查看进度');
    await assertNoSensitiveVisibleText(page);
  });
});
