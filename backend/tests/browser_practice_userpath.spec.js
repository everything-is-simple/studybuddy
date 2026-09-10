const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for practice.html + practice-session.html.
// Rule: no business API calls from test code. All data created via page UI.
// Chain: import material -> index -> exercise set -> AI draft -> confirm ->
//        recommendations -> session -> submit -> finish -> result ->
//        mistake -> review -> weak points -> real restart persistence.
let RUN_ROOT = 'H:/studybuddy-test/runs/practice-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/practice-userpath';
const ART = 'H:/studybuddy-test/artifacts/practice-userpath';
const PORT = 8963;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '练习链路测试材料.txt';
const GENERATED_HINT = 'Which statement is supported';
const USER_PROMPT = '电路基础判断题';
const LONG_TITLE = '冲'.repeat(100);
let server;
let materialId = '';
let sessionId1 = '';
let sessionIdEntry = '';

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

function buildFixture() {
  fs.mkdirSync(FIXTURES, { recursive: true });
  fs.writeFileSync(path.join(FIXTURES, TXT_NAME),
    '练习链路测试材料：本材料介绍欧姆定律。欧姆定律指出，通过导体的电流与导体两端的电压成正比，' +
    '与导体的电阻成反比。欧姆定律是电路分析的基础公式，练习题应围绕欧姆定律展开。\n', 'utf8');
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|[A-Z]:\\\\/i);
}

async function importViaUi(page, filePath) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 10000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
}

async function openDetailViaUi(page, itemName) {
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  materialId = decodeURIComponent(page.url().split('material=')[1]);
  await expect(page.locator('#title')).toContainText(itemName, { timeout: 10000 });
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

async function indexMaterialViaUi(page) {
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#index')).toBeEnabled({ timeout: 10000 });
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 30000 });
}

// Creates the exercise set once (idempotent across tests), returns after the
// set is selected so both creation forms are usable.
async function createAndSelectSetViaUi(page, title) {
  await page.goto(`${BASE}/app/exercises.html`);
  // #set-status keeps stale text when hidden once sets exist; wait on the list itself.
  await expect(page.locator('#sets .set-item, #set-status:not([hidden])').first()).toBeVisible({ timeout: 15000 });
  const existing = page.locator('#sets .set-item', { hasText: title });
  if (await existing.count() === 0) {
    await page.fill('#new-set-title', title);
    await page.click('#set-create-form button');
    await expect(page.locator('#exercise-status')).toHaveText('练习集已创建', { timeout: 15000 });
  }
  await existing.first().click();
  await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
}

// Confirms the exercise whose list item matches `promptText`. Uses the inline
// mutate confirm button (the last 确认题目 button), which needs no dialog.
async function confirmExerciseViaUi(page, promptText) {
  await expect(page.locator('#exercises .exercise-item', { hasText: promptText })).toBeVisible({ timeout: 15000 });
  await page.locator('#exercises .exercise-item', { hasText: promptText }).click();
  await expect(page.locator('#exercise-detail')).toContainText('状态：', { timeout: 10000 });
  await page.getByRole('button', { name: '确认题目' }).last().click();
  await expect(page.locator('#exercise-status')).toHaveText('题目已确认', { timeout: 15000 });
  await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
}

const VIEWPORTS = [
  { name: '1280x720', width: 1280, height: 720 },
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '768x1024', width: 768, height: 1024 },
  { name: '390x844', width: 390, height: 844 },
];

test.describe.serial('practice + practice-session pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/practice-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixture();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-PRAC-1 导入→索引→练习集→AI 草稿→确认（纯页面 UI）', async ({ page }) => {
    await importViaUi(page, path.join(FIXTURES, TXT_NAME));
    await openDetailViaUi(page, TXT_NAME);
    await indexMaterialViaUi(page);
    await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });

    await createAndSelectSetViaUi(page, '练习链路练习集');
    await page.fill('#exercise-topic', '欧姆定律');
    await page.fill('#exercise-material-ids', materialId);
    await page.click('#exercise-generate-form button[type=submit]');
    await expect(page.locator('#exercise-status')).toHaveText('题目草稿已生成', { timeout: 30000 });
    await confirmExerciseViaUi(page, GENERATED_HINT);
    await expect(page.locator('#exercise-detail')).toContainText('选择题', { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PRAC-2 推荐练习→创建会话→逐题作答→完成→结果页', async ({ page }) => {
    // Second (user-created) exercise so the session has two items and a
    // deterministic correct answer for the result assertion.
    await createAndSelectSetViaUi(page, '练习链路练习集');
    await page.locator('#new-exercise-type').selectOption('multiple_choice');
    await page.fill('#new-exercise-prompt', USER_PROMPT);
    await page.fill('#new-exercise-answer', '0');
    await page.click('#exercise-create-form button');
    await expect(page.locator('#exercise-status')).toHaveText('题目已创建', { timeout: 15000 });
    await confirmExerciseViaUi(page, USER_PROMPT);

    await page.goto(`${BASE}/app/practice.html`);
    await expect(page.locator('#recommendations .recommendation-item', { hasText: GENERATED_HINT })).toBeVisible({ timeout: 15000 });
    await expect(page.locator('#recommendations .recommendation-item', { hasText: USER_PROMPT })).toBeVisible({ timeout: 15000 });
    await page.locator('#recommendations .recommendation-item', { hasText: GENERATED_HINT }).locator('input').check();
    await page.locator('#recommendations .recommendation-item', { hasText: USER_PROMPT }).locator('input').check();
    await page.getByRole('button', { name: '创建练习会话' }).click();
    await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 15000 });
    sessionId1 = page.url().split('session_id=')[1];

    await expect(page.locator('#session-detail button', { hasText: '开始练习' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: '开始练习' }).click();
    await expect(page.locator('.practice-question')).toBeVisible({ timeout: 15000 });
    for (let i = 0; i < 2; i++) {
      await expect(page.locator('.practice-question h3')).toHaveText(new RegExp(`第 ${i + 1} 题 / 2`), { timeout: 15000 });
      const prompt = await page.locator('.practice-question p').first().innerText();
      const generated = prompt.includes(GENERATED_HINT);
      // Generated fake question: answer_key=0, so option index 1 is wrong.
      // User-created question: answer_key=0, so option index 0 is correct.
      await page.locator('#answer').selectOption(generated ? '1' : '0');
      await page.getByRole('button', { name: '提交答案' }).click();
      if (i === 0) {
        // Submitting a non-last item auto-advances through a reload, so the
        // stable signal is the next question rendering (the success toast is
        // transient and replaced by 正在加载会话…).
        await expect(page.locator('.practice-question h3')).toHaveText('第 2 题 / 2', { timeout: 15000 });
      } else {
        await expect(page.locator('#session-status')).toContainText('答案已提交', { timeout: 15000 });
      }
    }
    await page.getByRole('button', { name: '完成会话' }).click();
    await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('得分：1 / 2', { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('已提交：2');
    await expect(page.locator('body')).not.toContainText(/answer_key|answer_json|traceback/i);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PRAC-3 错题库显示真实题面→复盘→薄弱点汇总', async ({ page }) => {
    await page.goto(`${BASE}/app/practice.html`);
    const mistakeItem = page.locator('#mistakes .mistake-item', { hasText: GENERATED_HINT });
    await expect(mistakeItem).toBeVisible({ timeout: 15000 });
    await expect(mistakeItem).toContainText('查看错题');
    await mistakeItem.getByRole('link', { name: '查看错题' }).click();
    await page.waitForURL(/review\.html\?mistake_id=/);
    await expect(page.locator('#review-list')).toContainText(GENERATED_HINT, { timeout: 15000 });
    await expect(page.locator('#review-list')).toContainText('状态：待处理');
    await expect(page.locator('#weak-points .item-card', { hasText: '出现 1 次' })).toBeVisible({ timeout: 15000 });
    await assertNoSensitiveVisibleText(page);

    // Finished session stays visible in the list with inline result view.
    await page.goto(`${BASE}/app/practice.html`);
    const sessionItem = page.locator('#sessions .session-item', { hasText: '推荐练习' });
    await expect(sessionItem).toBeVisible({ timeout: 15000 });
    await expect(sessionItem).toContainText('已完成');
    await sessionItem.locator('.status-badge').click();
    await expect(page.locator('#detail-content')).toContainText('状态：', { timeout: 10000 });
    await page.locator('#detail-content').getByRole('button', { name: '查看结果' }).click();
    await expect(page.locator('#detail-content')).toContainText('得分: 1 / 2', { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PRAC-4 练习集「开始作答」→单题会话入口（缺陷 1 回归）', async ({ page }) => {
    await page.goto(`${BASE}/app/exercises.html`);
    await page.locator('#sets .set-item', { hasText: '练习链路练习集' }).click();
    await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
    await page.locator('#exercises .exercise-item', { hasText: GENERATED_HINT }).click();
    await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
    await page.getByRole('button', { name: '开始作答' }).click();
    await page.waitForURL(/practice\.html\?exercise_id=/);
    await expect(page.locator('[data-od-id="practice-exercise-entry"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#exercise-entry')).toContainText(GENERATED_HINT, { timeout: 10000 });
    await page.getByRole('button', { name: '为该题目创建练习会话' }).click();
    await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 15000 });
    sessionIdEntry = page.url().split('session_id=')[1];
    expect(sessionIdEntry).not.toBe(sessionId1);

    await page.getByRole('button', { name: '开始练习' }).click();
    await expect(page.locator('.practice-question')).toBeVisible({ timeout: 15000 });
    await page.locator('#answer').selectOption('1');
    await page.getByRole('button', { name: '提交答案' }).click();
    await expect(page.locator('#session-status')).toContainText('答案已提交', { timeout: 15000 });
    await page.getByRole('button', { name: '完成会话' }).click();
    await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });

    // Boundary: unknown exercise id shows a safe message, not an internal code.
    await page.goto(`${BASE}/app/practice.html?exercise_id=nonexistent-exercise`);
    await expect(page.locator('#exercise-entry-status')).toHaveText('题目不存在', { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PRAC-5 失败注入：安全文案、不泄露、取消注入后真实恢复', async ({ page }) => {
    await page.route('**/api/study/practice-sessions', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.route('**/api/study/mistakes', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.route('**/api/study/practice-recommendations*', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.goto(`${BASE}/app/practice.html`);
    await expect(page.locator('#session-status')).toContainText('请求失败', { timeout: 15000 });
    await expect(page.locator('#mistake-status')).toContainText('请求失败', { timeout: 15000 });
    await expect(page.locator('#recommendation-status')).toContainText('请求失败', { timeout: 15000 });
    await assertNoSensitiveVisibleText(page);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#refresh-sessions').click();
    await expect(page.locator('#sessions .session-item', { hasText: '推荐练习' })).toBeVisible({ timeout: 15000 });
    await page.locator('#refresh-mistakes').click();
    await expect(page.locator('#mistakes .mistake-item', { hasText: GENERATED_HINT })).toBeVisible({ timeout: 15000 });
    await page.locator('#refresh-recommendations').click();
    await expect(page.locator('#recommendations .recommendation-item').first()).toBeVisible({ timeout: 15000 });

    // Session detail failure recovers through the page retry button.
    let reads = 0;
    await page.route(`**/api/study/practice-sessions/${sessionId1}*`, route => {
      reads += 1;
      if (reads === 1) {
        return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_backend_error' }) });
      }
      return route.fallback();
    });
    await page.goto(`${BASE}/app/practice-session.html?session_id=${sessionId1}`);
    await expect(page.locator('#session-status')).toContainText('请求失败', { timeout: 15000 });
    await expect(page.locator('#retry-session')).toBeVisible();
    await assertNoSensitiveVisibleText(page);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-session').click();
    await expect(page.locator('#session-detail')).toContainText('已完成', { timeout: 15000 });
  });

  test('A-E2E-PRAC-6 响应式 5 档 + 键盘 + 焦点样式 + 冲刺目标长标题', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${BASE}/app/practice.html`);
    await expect(page.locator('#sessions .session-item').first()).toBeVisible({ timeout: 15000 });
    // Keyboard: create a cram goal via Enter submit with a 100-char title.
    await page.locator('#cram-title').focus();
    await page.locator('#cram-title').fill(LONG_TITLE);
    await page.fill('#cram-date', '2099-12-31');
    await page.keyboard.press('Enter');
    await expect(page.locator('#cram-status')).toContainText('冲刺目标已创建', { timeout: 15000 });
    await expect(page.locator('#cram-goals .session-item', { hasText: LONG_TITLE })).toBeVisible();
    // Focus style: outline or box-shadow must be visible on the focused input.
    await page.locator('#cram-title').focus();
    expect(await page.evaluate(assertFocusStyleStr)).toBe(true);
    await page.locator('#refresh-cram').focus();
    expect(await page.evaluate(assertFocusStyleStr)).toBe(true);

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await expect.poll(() => page.evaluate(() =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      await page.screenshot({ path: path.join(ART, `practice-${vp.name}.png`), fullPage: true });
      await page.goto(`${BASE}/app/practice-session.html?session_id=${sessionId1}`);
      await expect(page.locator('#session-detail')).toBeVisible({ timeout: 15000 });
      await expect.poll(() => page.evaluate(() =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
      await page.screenshot({ path: path.join(ART, `session-${vp.name}.png`), fullPage: true });
    }
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-PRAC-7 服务真重启后会话/错题/薄弱点全部持久化', async ({ page }) => {
    await stopServer();
    server = startServer();
    await ready();

    await page.goto(`${BASE}/app/practice.html`);
    await expect(page.locator('#sessions .session-item', { hasText: '推荐练习' })).toBeVisible({ timeout: 20000 });
    await expect(page.locator('#sessions .session-item', { hasText: '单题练习' })).toBeVisible({ timeout: 15000 });
    await expect(page.locator('#mistakes .mistake-item', { hasText: GENERATED_HINT })).toBeVisible({ timeout: 15000 });

    await page.locator('#sessions .session-item', { hasText: '推荐练习' }).locator('.status-badge').click();
    await expect(page.locator('#detail-content')).toContainText('已完成', { timeout: 10000 });
    await page.locator('#detail-content').getByRole('button', { name: '查看结果' }).click();
    await expect(page.locator('#detail-content')).toContainText('得分: 1 / 2', { timeout: 10000 });

    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list')).toContainText(GENERATED_HINT, { timeout: 15000 });
    await expect(page.locator('#weak-points .item-card', { hasText: '出现 2 次' })).toBeVisible({ timeout: 15000 });
    await assertNoSensitiveVisibleText(page);
  });
});

// Evaluated inside the page against document.activeElement.
function assertFocusStyleStr() {
  const el = document.activeElement;
  if (!el || el === document.body) return false;
  const computed = window.getComputedStyle(el);
  return (computed.outlineStyle !== 'none' && computed.outlineWidth !== '0px')
    || computed.boxShadow !== 'none';
}
