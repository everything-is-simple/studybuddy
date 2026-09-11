const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// A-class pure user-path E2E for plans.html + plan-detail.html.
// Rule: no business API calls from test code. All data created via page UI.
// Plan doc (7 dimensions): docs/roles/[需求+测试看]UI_TEST_PLAN_PLANS_PAGES.md
let RUN_ROOT = 'H:/studybuddy-test/runs/plans-plan-detail-userpath';
const PORT = 8903;
const BASE = `http://127.0.0.1:${PORT}`;
const ART = 'H:/studybuddy-test/artifacts/plans-userpath';
const FIXTURE = 'H:/studybuddy-test/fixtures/真实链路测试材料.txt';
const TODAY = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' });
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
  for (let i = 0; i < 150; i += 1) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('server_not_ready');
}
function stopServer() {
  return new Promise(resolve => {
    if (!server || server.killed) { server = null; return resolve(); }
    server.once('exit', () => { server = null; resolve(); });
    server.kill();
  });
}

test.describe.serial('plans + plan-detail pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/plans-plan-detail-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  function armDialogs(page) {
    const queue = [];
    page.on('dialog', d => {
      const next = queue.shift() || { accept: false };
      if (d.type() === 'prompt') next.accept ? d.accept(next.text || '') : d.dismiss();
      else next.accept ? d.accept() : d.dismiss();
    });
    return queue;
  }
  const status = page => page.locator('#plan-status');
  const detailNotice = page => page.locator('#plan-detail .notice').first();
  async function transition(page, label, expectedStatus) {
    const notice = detailNotice(page);
    for (let i = 0; i < 3; i++) {
      try {
        await page.getByRole('button', { name: label }).click({ timeout: 3000 });
        await expect(notice).toContainText(expectedStatus, { timeout: 3000 });
        return;
      } catch (_) { }
    }
    await expect(notice).toContainText(expectedStatus, { timeout: 5000 });
  }
  async function openDetail(page, planTitle) {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    const item = page.locator('#plans li.plan-item', { hasText: planTitle });
    await item.locator('a', { hasText: '打开详情' }).click();
    await page.waitForURL(/plan-detail\.html\?plan_id=/);
    await expect(page.locator('#plan-detail')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#plan-detail h2')).toContainText(planTitle);
  }
  async function openDetailPanel(page, planTitle) {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    const item = page.locator('#plans li.plan-item', { hasText: planTitle });
    await item.click();
    await expect(page.locator('#plan-detail > h3')).toHaveText(planTitle, { timeout: 5000 });
  }
  async function createPlanWithItem(page, goalTitle, planTitle, itemTitle) {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#goal-title', goalTitle);
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item', { hasText: goalTitle })).toBeVisible();
    await page.fill('#plan-title', planTitle);
    await page.locator('#plan-goal').selectOption({ label: goalTitle });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', itemTitle);
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
  }
  async function assertNoSensitiveVisibleText(page) {
    const visible = await page.locator('body').innerText();
    expect(visible).not.toMatch(/traceback|sqlite|select |insert |update |delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
  }
  async function assertFocusStyle(page, selector) {
    await page.locator(selector).focus();
    const style = await page.locator(selector).evaluate(el => {
      const css = getComputedStyle(el);
      return { outlineStyle: css.outlineStyle, outlineWidth: css.outlineWidth, boxShadow: css.boxShadow };
    });
    expect(style.outlineStyle !== 'none' || style.outlineWidth !== '0px' || style.boxShadow !== 'none').toBeTruthy();
  }

  test('A-E2E-PLAN-FULL-LIFECYCLE', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#goal-status')).toHaveText('暂无目标', { timeout: 5000 });
    await page.fill('#goal-title', 'A类用户路径目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item').first()).toContainText('A类用户路径目标');
    await page.fill('#module-title', 'A类用户路径模块');
    await page.click('#module-form button[type=submit]');
    await expect(page.locator('#modules li.module-item').first()).toContainText('A类用户路径模块');
    await page.fill('#plan-title', 'A类完整生命周期计划');
    await page.locator('#plan-goal').selectOption({ label: 'A类用户路径目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', '记叙文');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    await page.fill('#plan-item-title', '说明文');
    await page.locator('#plan-item-module').selectOption({ label: 'A类用户路径模块' });
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(page.locator('#plan-detail .plan-item-entry')).toHaveCount(2);
    await page.locator('#plan-dependency-predecessor').selectOption({ index: 0 });
    await page.locator('#plan-dependency-successor').selectOption({ index: 1 });
    await page.getByRole('button', { name: '添加依赖' }).click();
    await expect(status(page)).toHaveText('依赖已添加');
    await expect(page.locator('.plan-item-entry', { hasText: '→' })).toContainText('记叙文 → 说明文');
    await page.locator('#rhythm-cadence').selectOption('daily');
    await page.locator('#rhythm-period-start').fill(TODAY);
    await page.locator('#rhythm-target-minutes').fill('60');
    await page.getByRole('button', { name: '保存节奏设置' }).click();
    await expect(status(page)).toHaveText('学习节奏已保存');
    await page.locator('#rhythm-item').selectOption({ label: '记叙文' });
    await page.locator('#rhythm-date').fill(TODAY);
    await page.locator('#rhythm-minutes').fill('30');
    await page.getByRole('button', { name: '添加分配' }).click();
    await expect(status(page)).toHaveText('学习项已分配');
    await transition(page, '确认草稿', '状态：已确认');
    await transition(page, '激活计划', '状态：进行中');
    await page.goto(`${BASE}/app/today.html`);
    const task = page.locator('.task-item', { hasText: '记叙文' });
    await expect(task).toBeVisible({ timeout: 8000 });
    await task.locator('a.btn-primary').click();
    await page.waitForURL(/plan-detail\.html\?.*item_id=/);
    expect(page.url()).toContain('return_to=today');
    await expect(page.locator('#back-plan')).toHaveAttribute('href', '/app/today.html');
    const row = page.locator('#plan-detail article.card', { hasText: '记叙文' });
    await row.getByRole('button', { name: '开始学习' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已开始学习');
    await expect(row).toContainText('状态：进行中');
    await expect(row.getByRole('button', { name: '开始学习' })).toBeDisabled();
    await row.getByRole('button', { name: '记录完成' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已完成学习');
    await expect(row).toContainText('状态：已完成');
    await expect(row.getByRole('button', { name: '记录完成' })).toHaveCount(0);
    await openDetailPanel(page, 'A类完整生命周期计划');
    const done = page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 记叙文"]') });
    await expect(done).toContainText('已完成');
    await transition(page, '暂停计划', '状态：已暂停');
    await transition(page, '恢复计划', '状态：进行中');
    await transition(page, '完成计划', '状态：已完成');
    await expect(page.locator('[aria-label="计划名称"]')).toBeDisabled();
    await expect(page.locator('[aria-label="计划描述"]')).toBeDisabled();
    await expect(page.getByRole('button', { name: '保存计划编辑' })).toBeDisabled();
    const dialogs = armDialogs(page);
    dialogs.push({ accept: true });
    await page.getByRole('button', { name: '归档计划' }).click();
    await expect(page.locator('#plans li.plan-item', { hasText: 'A类完整生命周期计划' })).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator('#plan-detail')).toBeHidden();
  });

  test('A-E2E-REAL-SOURCE-LINK', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#goal-title', '来源链路目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item', { hasText: '来源链路目标' })).toBeVisible();
    await page.fill('#plan-title', '来源链路计划');
    await page.locator('#plan-goal').selectOption({ label: '来源链路目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', '来源学习项');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    await page.goto(`${BASE}/app/materials.html`);
    await page.setInputFiles('#file-input', FIXTURE);
    const matLink = page.locator('#items a', { hasText: '真实链路测试材料' }).first();
    await expect(matLink).toBeVisible({ timeout: 20000 });
    await matLink.click();
    await page.waitForURL(/material-detail\.html\?material=/);
    await page.locator('#index').click();
    await expect(page.locator('#index-status')).toContainText('索引已建立', { timeout: 30000 });
    await openDetail(page, '来源链路计划');
    await expect(page.locator('#plan-detail article.card', { hasText: '来源学习项' })).toContainText('来源：未关联来源');
    await page.goBack();
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await openDetailPanel(page, '来源链路计划');
    await page.locator('#source-owner').selectOption({ label: '学习项：来源学习项' });
    await expect(page.locator('#source-candidate option', { hasText: '真实链路测试材料' })).toHaveCount(1, { timeout: 10000 });
    await expect(page.locator('#source-add')).toBeEnabled();
    await page.locator('#source-add').click();
    await expect(page.locator('#source-status')).toHaveText('来源链接已添加');
    await expect(page.locator('#source-links li')).toHaveCount(1);
    await expect(page.locator('#source-links li').first()).toContainText('chunk_');
    await openDetail(page, '来源链路计划');
    const card = page.locator('#plan-detail article.card', { hasText: '来源学习项' });
    // valid source links render no warning line (appendSource hides 'valid' state)
    await expect(card).not.toContainText('来源：未关联来源');
    await expect(card).not.toContainText('来源：');
    await page.reload();
    await expect(page.locator('#plan-detail article.card', { hasText: '来源学习项' })).not.toContainText('来源：未关联来源', { timeout: 5000 });
    await stopServer();
    server = startServer();
    await ready();
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${new URL(page.url()).searchParams.get('plan_id')}`);
    await expect(page.locator('#plan-detail article.card', { hasText: '来源学习项' })).not.toContainText('来源：未关联来源', { timeout: 5000 });
    await page.goBack();
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await openDetailPanel(page, '来源链路计划');
    await page.locator('#source-owner').selectOption({ label: '学习项：来源学习项' });
    await expect(page.locator('#source-links li')).toHaveCount(1, { timeout: 5000 });
    const dialogs = armDialogs(page);
    dialogs.push({ accept: true });
    await page.locator('#source-links li').first().getByRole('button', { name: '删除' }).click();
    await expect(page.locator('#source-status')).toHaveText('来源链接已删除');
    await expect(page.locator('#source-links li')).toHaveCount(0);
    await openDetail(page, '来源链路计划');
    await expect(page.locator('#plan-detail article.card', { hasText: '来源学习项' })).toContainText('来源：未关联来源');
  });

  test('A-E2E-RESPONSIVE-AND-KEYBOARD', async ({ page }) => {
    const sizes = [[1280, 720], [1440, 900], [1920, 1080], [768, 1024], [390, 844]];
    await createPlanWithItem(page, '响应式独立目标', '响应式独立计划', '响应式学习项');
    for (const [w, h] of sizes) {
      await page.setViewportSize({ width: w, height: h });
      await page.goto(`${BASE}/app/plans.html`);
      await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
      expect(await page.locator('body').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
      await expect(page.locator('#plan-form button[type=submit]')).toBeVisible();
      await expect(page.locator('#refresh-all')).toBeVisible();
      await page.screenshot({ path: `${ART}/plans-${w}x${h}.png`, fullPage: true });
      await openDetail(page, '响应式独立计划');
      expect(await page.locator('body').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
      await expect(page.locator('#back-plan')).toBeVisible();
      await expect(page.locator('#refresh-progress')).toBeVisible();
      await expect(page.locator('#plan-detail article.card').first()).toBeVisible();
      await page.screenshot({ path: `${ART}/plan-detail-${w}x${h}.png`, fullPage: true });
    }
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.locator('#source-candidate').focus();
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement.id)).not.toBe('source-add');
    await page.focus('#goal-title');
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement.closest('form') && document.activeElement.closest('form').id)).toBe('goal-form');
    await page.fill('#goal-title', '键盘路径目标');
    await page.keyboard.press('Enter');
    await expect(page.locator('#goals li.goal-item', { hasText: '键盘路径目标' })).toBeVisible({ timeout: 5000 });
    await page.focus('#goal-title');
    let tabTarget = '';
    for (let i = 0; i < 30 && tabTarget !== 'module-title'; i++) {
      await page.keyboard.press('Tab');
      tabTarget = await page.evaluate(() => document.activeElement.id || '');
    }
    expect(tabTarget).toBe('module-title');
    const planItem = page.locator('#plans li.plan-item', { hasText: '响应式独立计划' });
    await planItem.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#plan-detail > h3')).toHaveText('响应式独立计划');
    await page.keyboard.press('Escape');
    await planItem.focus();
    await page.keyboard.press(' ');
    await expect(planItem).toHaveClass(/selected/);
    await planItem.focus();
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement.textContent)).toBe('打开详情');
    const dialogs = armDialogs(page);
    await page.locator('#goals li.goal-item', { hasText: '键盘路径目标' }).getByRole('button', { name: '重命名目标' }).click();
    await expect(page.locator('#goals li.goal-item', { hasText: '键盘路径目标' })).toBeVisible();
    await expect(page.locator('#goals li.goal-item', { hasText: '键盘路径目标' })).toContainText('键盘路径目标');
    await assertNoSensitiveVisibleText(page);
    await page.fill('#plan-title', '长标题验证'.repeat(20));
    await page.locator('#plan-goal').selectOption({ label: '键盘路径目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建', { timeout: 8000 });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.click('#refresh-all');
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    expect(await page.locator('body').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await assertFocusStyle(page, '#goal-title');
    const longTitle = '长标题验证'.repeat(20);
    const longPlan = page.locator('#plans li.plan-item', { hasText: longTitle });
    await longPlan.locator('a', { hasText: '打开详情' }).click();
    await page.waitForURL(/plan-detail\.html\?plan_id=/);
    await expect(page.locator('#plan-detail h2')).toContainText('长标题验证');
    await expect(page.locator('#back-plan')).toBeVisible();
    await expect(page.locator('#refresh-progress')).toBeVisible();
    expect(await page.locator('body').evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await assertFocusStyle(page, '#refresh-progress');
  });

  test('A-E2E-URL-PLAN-ID-NEW-PLAN-WINS', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#goal-title', 'URL 优先级回归目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item', { hasText: 'URL 优先级回归目标' })).toBeVisible();
    await page.fill('#plan-title', '旧计划详情');
    await page.locator('#plan-goal').selectOption({ label: 'URL 优先级回归目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await expect(page.locator('#plan-detail > h3')).toHaveText('旧计划详情', { timeout: 5000 });
    const oldPlanId = new URL(page.url()).searchParams.get('plan_id');
    expect(oldPlanId).toBeTruthy();

    // Keep the old plan_id in the URL while creating another plan through the
    // visible form. The new plan must become the selected detail immediately.
    await page.fill('#plan-title', '新计划详情');
    await page.locator('#plan-goal').selectOption({ label: 'URL 优先级回归目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await expect(page.locator('#plan-detail > h3')).toHaveText('新计划详情', { timeout: 5000 });
    const newPlanId = new URL(page.url()).searchParams.get('plan_id');
    expect(newPlanId).toBeTruthy();
    expect(newPlanId).not.toBe(oldPlanId);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PERSIST-REAL-RESTART', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#goal-title', '重启持久化目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item', { hasText: '重启持久化目标' })).toBeVisible();
    await page.fill('#plan-title', '重启持久化计划');
    await page.locator('#plan-goal').selectOption({ label: '重启持久化目标' });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', '持久化学习项');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    await page.locator('#rhythm-cadence').selectOption('weekly');
    await page.locator('#rhythm-period-start').fill(TODAY);
    await page.locator('#rhythm-target-minutes').fill('120');
    await page.getByRole('button', { name: '保存节奏设置' }).click();
    await expect(status(page)).toHaveText('学习节奏已保存');
    await page.locator('#rhythm-item').selectOption({ label: '持久化学习项' });
    await page.locator('#rhythm-date').fill(TODAY);
    await page.locator('#rhythm-minutes').fill('45');
    await page.getByRole('button', { name: '添加分配' }).click();
    await expect(status(page)).toHaveText('学习项已分配');
    await expect(page.locator('.plan-item-entry', { hasText: '已分配 45 分钟' })).toHaveCount(1);
    await transition(page, '确认草稿', '状态：已确认');
    await transition(page, '激活计划', '状态：进行中');
    await page.goto(`${BASE}/app/today.html`);
    const persistedTask = page.locator('.task-item', { hasText: '持久化学习项' });
    await expect(persistedTask).toBeVisible({ timeout: 8000 });
    await persistedTask.locator('a.btn-primary').click();
    await page.waitForURL(/plan-detail\.html\?.*item_id=/);
    await page.getByRole('button', { name: '开始学习' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已开始学习');
    await page.getByRole('button', { name: '记录完成' }).click();
    await expect(page.locator('#progress-status')).toHaveText('已完成学习');
    await stopServer();
    server = startServer();
    await ready();
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#goals li.goal-item', { hasText: '重启持久化目标' })).toBeVisible({ timeout: 8000 });
    const item = page.locator('#plans li.plan-item', { hasText: '重启持久化计划' });
    await expect(item).toContainText('1 个项目');
    await expect(item).toContainText('进行中');
    await item.locator('a', { hasText: '打开详情' }).click();
    await expect(page.locator('#plan-detail h2')).toContainText('重启持久化计划', { timeout: 5000 });
    await expect(page.locator('#plan-detail article.card', { hasText: '持久化学习项' })).toContainText('状态：已完成');
    await expect(page.locator('#plan-detail .badge')).toHaveText('进行中');
    await expect(page.locator('#progress-events li').first()).toContainText('记录完成 · 持久化学习项');
    await expect(page.locator('#progress-summary .rhythm-value').first()).toHaveText('1');
    await page.goBack();
    await openDetailPanel(page, '重启持久化计划');
    await expect(page.locator('#rhythm-cadence')).toHaveValue('weekly', { timeout: 5000 });
    await expect(page.locator('#rhythm-period-start')).toHaveValue(TODAY);
    await expect(page.locator('#rhythm-target-minutes')).toHaveValue('120');
    await expect(page.locator('.plan-item-entry', { hasText: '已分配 45 分钟' })).toHaveCount(1);
    await page.goto(`${BASE}/app/today.html`);
    await expect(page.locator('.task-item', { hasText: '持久化学习项' })).toBeVisible({ timeout: 8000 });
  });
});
