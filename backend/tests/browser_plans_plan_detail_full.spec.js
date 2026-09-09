const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

let RUN_ROOT = 'H:/studybuddy-test/runs/plans-plan-detail-full';
const PORT = 8901;
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
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('server_not_ready');
}
async function planIdByTitle(request, title) {
  const plans = await request.get(`${BASE}/api/study/plans`).then(r => r.json());
  return plans.find(p => p.title === title).id;
}

test.describe.serial('plans + plan-detail full coverage', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/plans-plan-detail-full-${Date.now()}`;
    fs.rmSync(RUN_ROOT, { recursive: true, force: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => { if (server && !server.killed) server.kill(); server = null; });

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

  test('P-A static structure and empty states', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('h1')).toHaveText('目标与计划');
    await expect(page.locator('.eyebrow')).toHaveText('学习计划 · 目标与节奏');
    await expect(page.locator('.lead')).toContainText('建立学习目标');
    await expect(page.locator('nav.nav a[href="/app/plans.html"]')).toBeVisible();
    await expect(page.locator('[data-od-id="plans-sidebar"]')).toBeVisible();
    await expect(page.locator('[data-od-id="plans-main"]')).toBeVisible();
    await expect(page.locator('[data-od-id="source-links"]')).toBeVisible();
    await expect(page.locator('#goal-status')).toHaveText('暂无目标', { timeout: 5000 });
    await expect(page.locator('#module-status')).toHaveText('暂无模块');
    await expect(status(page)).toHaveText('请先创建学习目标');
    await expect(page.locator('#source-owner')).toBeVisible();
    await expect(page.locator('#source-candidate')).toBeVisible();
    await expect(page.locator('#source-add')).toBeDisabled();
    await expect(page.locator('#source-links')).toBeEmpty();
  });

  test('P-B goal create, view, rename, rename-empty, archive', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#goal-status')).toHaveText('暂无目标', { timeout: 5000 });
    await page.click('#goal-form button[type=submit]');
    expect(await page.locator('#goal-title').evaluate(el => el.validity.valueMissing)).toBeTruthy();
    await expect(page.locator('#goals li')).toHaveCount(0);
    await page.fill('#goal-title', '丁玲玲-2026年秋季学期-进到班上前十');
    await page.click('#goal-form button[type=submit]');
    const goal = page.locator('#goals li.goal-item').first();
    await expect(goal).toContainText('丁玲玲-2026年秋季学期-进到班上前十');
    await expect(goal.locator('.status-badge')).toHaveText('进行中');
    const dialogs = armDialogs(page);
    await page.getByRole('button', { name: '查看目标' }).click();
    await expect(page.locator('#goal-detail')).toContainText('目标：丁玲玲-2026年秋季学期-进到班上前十');
    await expect(page.locator('#goal-detail')).toContainText('进行中');
    dialogs.push({ accept: true, text: '丁玲玲-2026秋季-班级前十' });
    await page.getByRole('button', { name: '重命名目标' }).click();
    await expect(page.locator('#goals li.goal-item').first()).toContainText('丁玲玲-2026秋季-班级前十');
    dialogs.push({ accept: true, text: '  ' });
    await page.getByRole('button', { name: '重命名目标' }).click();
    await expect(page.locator('#goal-status')).toHaveText('目标名称不能为空，请重试');
    await expect(page.locator('#goals li.goal-item').first()).toContainText('丁玲玲-2026秋季-班级前十');
    await page.fill('#goal-title', '临时归档目标');
    await page.click('#goal-form button[type=submit]');
    await expect(page.locator('#goals li.goal-item')).toHaveCount(2);
    dialogs.push({ accept: true });
    await page.locator('#goals li.goal-item', { hasText: '临时归档目标' }).getByRole('button', { name: '归档目标' }).click();
    // archived goals are excluded from the default goals list entirely
    await expect(page.locator('#goals li.goal-item', { hasText: '临时归档目标' })).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator('#goals li.goal-item')).toHaveCount(1);
    await expect(page.locator('#plan-goal option', { hasText: '临时归档目标' })).toHaveCount(0);
  });

  test('P-C module create, view, rename, archive', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(page.locator('#module-status')).toHaveText('暂无模块', { timeout: 5000 });
    await page.fill('#module-title', '语文');
    await page.click('#module-form button[type=submit]');
    const mod = page.locator('#modules li.module-item').first();
    await expect(mod).toContainText('语文');
    await expect(mod.locator('.status-badge')).toHaveText('进行中');
    const dialogs = armDialogs(page);
    await page.getByRole('button', { name: '查看模块' }).click();
    await expect(page.locator('#module-detail')).toContainText('模块：语文');
    dialogs.push({ accept: true, text: '语文（上册）' });
    await page.getByRole('button', { name: '重命名模块' }).click();
    await expect(page.locator('#modules li.module-item').first()).toContainText('语文（上册）');
    dialogs.push({ accept: true, text: '' });
    await page.getByRole('button', { name: '重命名模块' }).click();
    await expect(page.locator('#module-status')).toHaveText('模块名称不能为空，请重试');
    await page.fill('#module-title', '临时模块');
    await page.click('#module-form button[type=submit]');
    await expect(page.locator('#modules li.module-item')).toHaveCount(2);
    dialogs.push({ accept: true });
    await page.locator('#modules li.module-item', { hasText: '临时模块' }).getByRole('button', { name: '归档模块' }).click();
    await expect(page.locator('#modules li.module-item', { hasText: '临时模块' })).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator('#modules li.module-item')).toHaveCount(1);
  });

  test('P-D15 plan form guards on empty title', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.click('#plan-form button[type=submit]');
    expect(await page.locator('#plan-title').evaluate(el => el.validity.valueMissing)).toBeTruthy();
    await expect(page.locator('#plans li')).toHaveCount(0);
  });

  test('P-D16 draft creation and detail open', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await expect(page.locator('#plan-goal option', { hasText: '丁玲玲' })).toHaveCount(1);
    await page.fill('#plan-title', '丁玲玲八上学习计划');
    await page.click('#plan-form button[type=submit]');
    const planItem = page.locator('#plans li.plan-item').first();
    await expect(planItem).toContainText('丁玲玲八上学习计划');
    await expect(planItem).toContainText('0 个项目');
    await expect(planItem).toContainText('草稿');
    await expect(page.locator('#plan-detail')).toBeVisible();
    await expect(page.locator('#plan-detail > h3')).toHaveText('丁玲玲八上学习计划');
    await expect(page.locator('#plan-detail .notice').first()).toContainText('状态：草稿');
    await expect(status(page)).toHaveText('计划草稿已创建');
  });

  test('P-D17/18 selection by click, keyboard, and direct URL', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上学习计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toHaveText('丁玲玲八上学习计划', { timeout: 5000 });
    await page.click('#refresh-all');
    await page.locator('#plans li.plan-item').first().click();
    await expect(page.locator('#plan-detail > h3')).toBeVisible();
    await page.locator('#plans li.plan-item').first().focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#plan-detail > h3')).toBeVisible();
    await page.locator('#plans li.plan-item').first().focus();
    await page.keyboard.press(' ');
    await expect(page.locator('#plan-detail > h3')).toBeVisible();
    await expect(page.locator('#plans li.plan-item').first()).toHaveClass(/selected/);
  });

  test('P-D19 save plan edit (title + description)', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上学习计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    await page.fill('[aria-label="计划名称"]', '丁玲玲八上冲刺计划');
    await page.fill('[aria-label="计划描述"]', '弄懂记叙文，弄懂说明文，弄懂古诗词，加强字词句段的打散组合。');
    await page.getByRole('button', { name: '保存计划编辑' }).click();
    await expect(status(page)).toHaveText('计划编辑保存');
    await expect(page.locator('#plan-detail > h3')).toHaveText('丁玲玲八上冲刺计划');
    await page.reload();
    await expect(page.locator('[aria-label="计划描述"]')).toHaveValue(/弄懂记叙文/, { timeout: 5000 });
  });

  test('P-E23/24/25/28 items add, module binding, save, count refresh', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    const editor = page.locator('#plan-detail');
    const modSelect = editor.locator('#plan-item-module');
    await expect(modSelect.locator('option')).toHaveText(['不绑定模块', '语文（上册）']);
    await page.fill('#plan-item-title', '记叙文');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    await expect(editor.locator('.plan-item-entry')).toHaveCount(1);
    await expect(editor.locator('.plan-item-entry').first()).toContainText('待处理');
    await page.fill('#plan-item-title', '说明文');
    await modSelect.selectOption({ label: '语文（上册）' });
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(editor.locator('.plan-item-entry')).toHaveCount(2);
    const rowOf = title => editor.locator('.plan-item-entry', { has: page.locator(`input[aria-label="学习项 ${title}"]`) });
    const first = rowOf('记叙文');
    await first.locator('input[aria-label^="学习项 "]').fill('记叙文（重点）');
    await first.getByRole('button', { name: '保存学习项' }).click();
    await expect(status(page)).toHaveText('学习项已保存');
    const second = rowOf('说明文');
    await second.locator('input[aria-label="学习项排序"]').fill('1');
    await second.getByRole('button', { name: '保存学习项' }).click();
    await expect(status(page)).toHaveText('学习项已保存');
    await page.reload();
    await expect(page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 记叙文（重点）"]') }).locator('input[aria-label^="学习项 "]')).toHaveValue('记叙文（重点）', { timeout: 5000 });
    await expect(page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 说明文"]') }).locator('input[aria-label="学习项排序"]')).toHaveValue('1');
    await expect(page.locator('#plans li.plan-item').first()).toContainText('2 个项目');
  });

  test('P-F dependencies add-invalid, add, delete', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    await page.locator('#plan-dependency-predecessor').selectOption({ index: 0 });
    await page.locator('#plan-dependency-successor').selectOption({ index: 0 });
    await page.getByRole('button', { name: '添加依赖' }).click();
    await expect(status(page)).toHaveText('依赖关系无效');
    await page.locator('#plan-dependency-predecessor').selectOption({ index: 0 });
    await page.locator('#plan-dependency-successor').selectOption({ index: 1 });
    await page.getByRole('button', { name: '添加依赖' }).click();
    await expect(status(page)).toHaveText('依赖已添加');
    const depRow = page.locator('.plan-item-entry', { hasText: '→' }).first();
    await expect(depRow).toContainText('记叙文（重点） → 说明文');
    const dialogs = armDialogs(page);
    dialogs.push({ accept: true });
    await depRow.getByRole('button', { name: '删除依赖' }).click();
    await expect(status(page)).toHaveText('依赖已删除');
    await expect(page.locator('.plan-item-entry', { hasText: '→' })).toHaveCount(0);
  });

  test('P-G rhythm settings guard, save, export, allocations, failure notice', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('.rhythm-workspace')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: '添加分配' })).toBeDisabled();
    await page.locator('#rhythm-cadence').selectOption('weekly');
    await page.locator('#rhythm-period-start').fill('2026-09-09');
    await page.locator('#rhythm-target-minutes').fill('90');
    await page.getByRole('button', { name: '保存节奏设置' }).click();
    await expect(status(page)).toHaveText('学习节奏已保存');
    await expect(page.getByRole('button', { name: '添加分配' })).toBeEnabled();
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#rhythm-export').click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('studybuddy-rhythm.json');
    await expect(page.locator('#rhythm-item option')).toHaveCount(2);
    await page.locator('#rhythm-minutes').fill('40');
    await page.getByRole('button', { name: '添加分配' }).click();
    await expect(status(page)).toHaveText('学习项已分配');
    await expect(page.locator('.plan-item-entry', { hasText: '已分配 40 分钟' })).toHaveCount(1);
    const row = page.locator('.plan-item-entry', { hasText: '已分配' }).first();
    await row.locator('input[type=number]').fill('50');
    await row.getByRole('button', { name: '调整' }).click();
    await expect(status(page)).toHaveText('学习项分配已调整');
    await expect(page.locator('.plan-item-entry', { hasText: '已分配 50 分钟' })).toHaveCount(1);
    const dialogs = armDialogs(page);
    dialogs.push({ accept: true });
    await page.locator('.plan-item-entry', { hasText: '已分配' }).first().getByRole('button', { name: '删除分配' }).click();
    await expect(status(page)).toHaveText('学习项分配已删除');
    await expect(page.locator('.plan-item-entry', { hasText: '已分配' })).toHaveCount(0);
  });

  test('P-G39 rhythm load failure shows warning without blocking page', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    let failRhythm = true;
    await page.route(`**/api/study/plans/${planId}/rhythm*`, async route => {
      if (failRhythm) await route.abort(); else await route.continue();
    });
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('.rhythm-workspace')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.rhythm-workspace')).toContainText('节奏加载失败，可重试。');
    await expect(page.locator('#plan-detail > h3')).toContainText('丁玲玲八上冲刺计划');
    await expect(page.locator('#goals li.goal-item').first()).toBeVisible();
    failRhythm = false;
    await page.click('#refresh-all');
    await expect(page.locator('#rhythm-cadence')).toBeVisible({ timeout: 5000 });
    await page.unroute(`**/api/study/plans/${planId}/rhythm*`);
  });

  test('P-E26 archive item while draft, P-D20 lifecycle transitions', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    await page.fill('#plan-item-title', '临时项');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    const tRow = page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 临时项"]') });
    await tRow.getByRole('button', { name: '归档学习项' }).click();
    await expect(status(page)).toHaveText('学习项已归档');
    await expect(tRow).toContainText('已归档');
    await expect(tRow.getByRole('button', { name: '保存学习项' })).toHaveCount(0);
    await transition(page, '确认草稿', '状态：已确认');
    await transition(page, '激活计划', '状态：进行中');
    await expect(page.getByRole('button', { name: '暂停计划' })).toBeVisible();
    await expect(page.getByRole('button', { name: '完成计划' })).toBeVisible();
    await transition(page, '暂停计划', '状态：已暂停');
    await transition(page, '恢复计划', '状态：进行中');
    await expect(page.locator('#plan-dependency-predecessor')).toHaveCount(0);
  });

  test('P-D21/22 second plan full chain to archive, edit disabled', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#plan-title', '归档演练计划');
    await page.locator('#plan-goal').selectOption({ index: 0 });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await transition(page, '确认草稿', '状态：已确认');
    await transition(page, '激活计划', '状态：进行中');
    await transition(page, '完成计划', '状态：已完成');
    await expect(page.locator('[aria-label="计划名称"]')).toBeDisabled();
    await expect(page.locator('[aria-label="计划描述"]')).toBeDisabled();
    await expect(page.getByRole('button', { name: '保存计划编辑' })).toBeDisabled();
    const dialogs = armDialogs(page);
    dialogs.push({ accept: true });
    await page.getByRole('button', { name: '归档计划' }).click();
    // archived plans leave the default plan list and close the detail panel
    await expect(page.locator('#plans li.plan-item', { hasText: '归档演练计划' })).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator('#plan-detail')).toBeHidden();
  });

  test('P-E27 complete item on active plan', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail .notice').first()).toContainText('状态：进行中', { timeout: 5000 });
    const row = page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 记叙文（重点）"]') });
    await expect(row).toContainText('待处理');
    await row.getByRole('button', { name: '完成学习项' }).click();
    await expect(status(page)).toHaveText('学习进度已保存');
    const done = page.locator('.plan-item-entry', { has: page.locator('input[aria-label="学习项 记叙文（重点）"]') });
    await expect(done).toContainText('已完成');
    await expect(done.getByRole('button', { name: '完成学习项' })).toHaveCount(0);
  });

  test('P-H source links owner loading and guards', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await expect(page.locator('#source-owner option')).toHaveCount(0);
    await expect(page.locator('#source-links')).toBeEmpty();
    await expect(page.locator('#source-add')).toBeDisabled();
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    const ownerTexts = await page.locator('#source-owner option').allTextContents();
    expect(ownerTexts.some(t => t.startsWith('学习项：'))).toBeTruthy();
    expect(ownerTexts.some(t => t.startsWith('模块：语文（上册）'))).toBeTruthy();
    expect(ownerTexts.some(t => t.includes('临时项'))).toBeFalsy();
    await expect(page.locator('#source-candidate option')).toHaveCount(0);
    await expect(page.locator('#source-add')).toBeDisabled();
    await page.locator('#source-owner').selectOption({ index: 0 });
    await expect(page.locator('#source-status')).toContainText('暂无来源链接', { timeout: 5000 });
    await page.locator('#source-refresh').click();
    await expect(page.locator('#source-status')).not.toContainText('失败', { timeout: 5000 });
  });

  test('P-I45 refresh-all keeps selection', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plans.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail > h3')).toBeVisible({ timeout: 5000 });
    await page.click('#refresh-all');
    await expect(page.locator('#plan-detail > h3')).toBeVisible();
    await expect(page.locator('#plans li.plan-item', { hasText: '丁玲玲八上冲刺计划' })).toHaveClass(/selected/);
  });

  test('P-I46 busy guard disables controls during mutation', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.route('**/api/study/plans', async route => {
      if (route.request().method() === 'POST') {
        await new Promise(r => setTimeout(r, 700));
        await route.continue();
      } else await route.continue();
    });
    await page.fill('#plan-title', 'busy 演练计划');
    await page.locator('#plan-goal').selectOption({ index: 0 });
    await page.click('#plan-form button[type=submit]');
    await expect(page.locator('#goal-title')).toBeDisabled();
    await expect(page.locator('#refresh-all')).toBeEnabled();
    await expect(status(page)).toHaveText('计划草稿已创建', { timeout: 8000 });
    await expect(page.locator('#goal-title')).toBeEnabled();
    await page.unroute('**/api/study/plans');
  });

  test('D-A/B structure, rendering, summary cards on active plan', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${planId}`);
    await expect(page.locator('#page-title')).toHaveText('计划详情');
    await expect(page.locator('.lead')).toContainText('查看计划状态、项目进度和来源状态');
    await expect(page.locator('#back-plan')).toHaveAttribute('href', '/app/plans.html');
    await expect(page.locator('#refresh-progress')).toHaveCount(1);
    await expect(page.locator('#plan-detail')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#plan-status')).toBeHidden();
    await expect(page.locator('#plan-detail h2')).toContainText('丁玲玲八上冲刺计划');
    await expect(page.locator('#plan-detail .badge')).toHaveText('进行中');
    await expect(page.locator('#plan-detail > p.muted')).toContainText('弄懂记叙文');
    await expect(page.locator('#plan-detail')).toContainText('暂无学习项依赖');
    const rows = page.locator('#plan-detail article.card');
    await expect(rows).toHaveCount(3);
    await expect(rows.nth(0)).toContainText('记叙文（重点）');
    await expect(rows.nth(0)).toContainText('状态：已完成');
    await expect(rows.nth(1)).toContainText('说明文');
    await expect(rows.nth(1)).toContainText('状态：待处理');
    await expect(rows.nth(1)).toContainText('来源：未关联来源');
    await expect(rows.nth(2)).toContainText('临时项');
    await expect(rows.nth(2)).toContainText('状态：已归档');
    const values = await page.locator('#progress-summary .rhythm-value').allTextContents();
    expect(values).toEqual(['1', '0', '1', '0', '50%']);
    await expect(page.locator('#progress-events li')).toHaveCount(1);
    await expect(page.locator('#progress-events li').first()).toContainText('记录完成 · 记叙文（重点）');
    await expect(page.locator('#history-status')).toBeHidden();
    await expect(page.getByRole('button', { name: '开始学习' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '记录完成' })).toHaveCount(0);
  });

  test('D-C10 refresh progress button', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${planId}`);
    await expect(page.locator('#plan-detail')).toBeVisible({ timeout: 5000 });
    let calls = 0;
    await page.exposeFunction('__countProgress', () => { calls += 1; });
    await page.route('**/progress', async route => {
      await page.evaluate(() => window.__countProgress());
      await route.continue();
    });
    await page.locator('#refresh-progress').click();
    await page.locator('#refresh-progress').click();
    await page.waitForTimeout(600);
    expect(calls).toBeGreaterThanOrEqual(1);
    await expect(page.locator('#progress-summary')).toBeVisible();
    await page.unroute('**/progress');
  });

  test('D-C12 return_to=today points back link to today', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${planId}&return_to=today`);
    await expect(page.locator('#back-plan')).toHaveAttribute('href', '/app/today.html');
  });

  test('D-C13 start/complete item with item_id on active plan', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    const detail = await page.request.get(`${BASE}/api/study/plans/${planId}`).then(r => r.json());
    const item = detail.items.find(i => i.title === '说明文');
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${planId}&item_id=${item.id}`);
    await expect(page.locator('#plan-detail')).toBeVisible({ timeout: 5000 });
    const row = page.locator('#plan-detail article.card', { hasText: '说明文' });
    const startBtn = row.getByRole('button', { name: '开始学习' });
    const completeBtn = row.getByRole('button', { name: '记录完成' });
    await expect(startBtn).toBeEnabled();
    await startBtn.click();
    await expect(page.locator('#progress-status')).toHaveText('已开始学习');
    await expect(row).toContainText('状态：进行中');
    await expect(startBtn).toBeDisabled();
    await completeBtn.click();
    await expect(page.locator('#progress-status')).toHaveText('已完成学习');
    await expect(row).toContainText('状态：已完成');
    await expect(row.getByRole('button', { name: '开始学习' })).toHaveCount(0);
    await expect(page.locator('#progress-events li')).toHaveCount(3);
    await expect(page.locator('#progress-events li').first()).toContainText('记录完成 · 说明文');
    await expect(page.locator('#progress-events li').nth(1)).toContainText('开始学习 · 说明文');
    const values = await page.locator('#progress-summary .rhythm-value').allTextContents();
    expect(values).toEqual(['2', '0', '0', '0', '100%']);
  });

  test('D-C14 draft plan with item_id renders no progress buttons', async ({ page }) => {
    await page.goto(`${BASE}/app/plans.html`);
    await expect(status(page)).not.toContainText('正在加载', { timeout: 5000 });
    await page.fill('#plan-title', '草稿按钮演练计划');
    await page.locator('#plan-goal').selectOption({ index: 0 });
    await page.click('#plan-form button[type=submit]');
    await expect(status(page)).toHaveText('计划草稿已创建');
    await page.fill('#plan-item-title', '草稿项一');
    await page.getByRole('button', { name: '添加学习项' }).click();
    await expect(status(page)).toHaveText('学习项已添加');
    const draft = (await page.request.get(`${BASE}/api/study/plans`).then(r => r.json())).find(p => p.title === '草稿按钮演练计划');
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${draft.id}&item_id=${draft.items[0].id}`);
    await expect(page.locator('#plan-detail')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: '开始学习' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '记录完成' })).toHaveCount(0);
    await expect(page.locator('#history-status')).toContainText('暂无进度记录', { timeout: 5000 });
    await expect(page.locator('#progress-events li')).toHaveCount(0);
  });

  test('D-D15 missing plan id shows error without retry', async ({ page }) => {
    await page.goto(`${BASE}/app/plan-detail.html`);
    await expect(page.locator('#plan-status')).toContainText('缺少计划标识', { timeout: 5000 });
    await expect(page.locator('#history-status')).toContainText('缺少计划标识');
    await expect(page.locator('#retry-plan')).toBeHidden();
    await expect(page.locator('#plan-detail')).toBeHidden();
  });

  test('D-D16/17/18 invalid load fails, retry recovers, shared retry control', async ({ page }) => {
    const planId = await planIdByTitle(page.request, '丁玲玲八上冲刺计划');
    let failPlan = true;
    await page.route(`**/api/study/plans/${planId}`, async route => {
      if (failPlan && route.request().resourceType() === 'fetch') await route.abort();
      else await route.continue();
    });
    await page.goto(`${BASE}/app/plan-detail.html?plan_id=${planId}`);
    await expect(page.locator('#plan-status')).not.toHaveText('', { timeout: 8000 });
    await expect(page.locator('#retry-plan')).toBeVisible();
    // progress history still loads independently and hides its loading banner
    await expect(page.locator('#history-status')).toBeHidden();
    await expect(page.locator('#progress-events li')).toHaveCount(3);
    failPlan = false;
    await page.locator('#retry-plan').click();
    await expect(page.locator('#plan-detail h2')).toContainText('丁玲玲八上冲刺计划', { timeout: 5000 });
    await expect(page.locator('#plan-status')).toBeHidden();
    await page.unroute(`**/api/study/plans/${planId}`);
  });
});
