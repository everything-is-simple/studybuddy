const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// A-class pure user-path E2E for exercises.html + practice-result.html.
// Rule: no business API calls from test code. All data created via page UI.
// Chain: import material -> index -> exercise set -> user exercises + AI draft
//        -> confirm -> practice entry -> session -> submit -> result ->
//        review -> real restart persistence.
// Privacy note: exercises.html inline script contains the literal string
// "answer_key" (create payload), so content() leak checks are only asserted
// on practice-result.html; exercises.html uses visible-text scans only.
let RUN_ROOT = 'H:/studybuddy-test/runs/exercises-result-userpath';
const FIXTURES = 'H:/studybuddy-test/fixtures/exercises-result-userpath';
const ART = 'H:/studybuddy-test/artifacts/exercises-result-userpath';
const PORT = 8973;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = '练习集审查材料.txt';
const GENERATED_HINT = 'Which statement is supported';
const MC_PROMPT = '电路基础判断题';
const MC_EDITED = '电路基础判断题（修订版）';
const SA_PROMPT = '欧姆定律公式是什么？';
const SA_ANSWER = '电流等于电压除以电阻';
const SET_TITLE = 'A审练习集';
let server;
let materialId = '';
let sessionIdMc = '';
let sessionIdSa = '';

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
    '练习集审查材料：本材料介绍欧姆定律。欧姆定律指出，通过导体的电流与导体两端的电压成正比，' +
    '与导体的电阻成反比。欧姆定律是电路分析的基础公式，练习题应围绕欧姆定律展开。\n', 'utf8');
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|answer_key|answer_json|correct_option|[A-Z]:\\\\/i);
}

async function assertResultPrivacy(page) {
  const html = await page.content();
  expect(html).not.toContain('answer_key');
  expect(html).not.toContain('answer_json');
  expect(page.url()).not.toContain('answer');
  await assertNoSensitiveVisibleText(page);
}

async function assertNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function assertFocusStyle(page, selector) {
  await page.focus(selector);
  const style = await page.evaluate(sel => {
    const s = getComputedStyle(document.querySelector(sel));
    return { outline: `${s.outlineStyle} ${s.outlineWidth}`, shadow: s.boxShadow };
  }, selector);
  const outlineVisible = !/^none/i.test(style.outline) && !/ 0px/.test(style.outline);
  expect(outlineVisible || (style.shadow && style.shadow !== 'none')).toBeTruthy();
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
}

async function indexMaterialViaUi(page) {
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#index')).toBeEnabled({ timeout: 10000 });
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 30000 });
  await expect(page.locator('#stage-index')).toContainText(/片段 [1-9]/, { timeout: 10000 });
}

async function createAndSelectSetViaUi(page, title) {
  await page.goto(`${BASE}/app/exercises.html`);
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

async function createExerciseViaUi(page, type, prompt, answer) {
  await page.locator('#new-exercise-type').selectOption(type);
  await page.fill('#new-exercise-prompt', prompt);
  await page.fill('#new-exercise-answer', answer);
  await page.click('#exercise-create-form button[type=submit]');
  await expect(page.locator('#exercise-status')).toHaveText('题目已创建', { timeout: 15000 });
}

async function confirmExerciseViaUi(page, promptText) {
  await expect(page.locator('#exercises .exercise-item', { hasText: promptText })).toBeVisible({ timeout: 15000 });
  await page.locator('#exercises .exercise-item', { hasText: promptText }).click();
  await expect(page.locator('#exercise-detail')).toContainText('状态：', { timeout: 10000 });
  await expect(page.getByRole('button', { name: '确认题目' })).toHaveCount(1);
  await page.getByRole('button', { name: '确认题目' }).click();
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

test.describe.serial('exercises + practice-result pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/exercises-result-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixture();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-EXR-1 导入→索引→练习集→用户题→编辑→确认→刷新持久', async ({ page }) => {
    await importViaUi(page, path.join(FIXTURES, TXT_NAME));
    await openDetailViaUi(page, TXT_NAME);
    await indexMaterialViaUi(page);

    await createAndSelectSetViaUi(page, SET_TITLE);
    await createExerciseViaUi(page, 'multiple_choice', MC_PROMPT, '0');
    await expect(page.locator('#exercises .exercise-item', { hasText: MC_PROMPT })).toBeVisible({ timeout: 15000 });

    await page.locator('#exercises .exercise-item', { hasText: MC_PROMPT }).click();
    await expect(page.locator('#exercise-detail')).toContainText('题目：', { timeout: 10000 });
    await expect(page.locator('#exercise-detail')).toContainText('选择题');
    // Defect regression: exactly one confirm entry for a draft exercise.
    await expect(page.getByRole('button', { name: '确认题目' })).toHaveCount(1);
    await expect(page.locator('#exercise-detail')).toContainText('选项：');
    await assertNoSensitiveVisibleText(page);

    // Edit the draft, then confirm; editing must be gone once ready.
    await page.locator('[aria-label="题目内容"]').fill(MC_EDITED);
    await page.getByRole('button', { name: '保存题目' }).click();
    await expect(page.locator('#exercise-status')).toHaveText('题目已保存', { timeout: 15000 });
    await expect(page.locator('#exercises .exercise-item', { hasText: MC_EDITED })).toBeVisible({ timeout: 15000 });
    await confirmExerciseViaUi(page, MC_EDITED);
    await expect(page.locator('#exercise-detail').getByRole('button', { name: '保存题目' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '开始作答' })).toBeVisible();

    // Reload: set, edited prompt and ready status persist.
    await page.reload();
    await createAndSelectSetViaUi(page, SET_TITLE);
    await expect(page.locator('#exercises .exercise-item', { hasText: MC_EDITED })).toBeVisible({ timeout: 15000 });
    await page.locator('#exercises .exercise-item', { hasText: MC_EDITED }).click();
    await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-EXR-2 AI 草稿经页面 UI 生成→引用可见→确认', async ({ page }) => {
    await createAndSelectSetViaUi(page, SET_TITLE);
    await page.fill('#exercise-topic', '欧姆定律');
    await page.fill('#exercise-material-ids', materialId);
    await page.click('#exercise-generate-form button[type=submit]');
    await expect(page.locator('#exercise-status')).toHaveText('题目草稿已生成', { timeout: 30000 });

    await page.locator('#exercises .exercise-item', { hasText: GENERATED_HINT }).click();
    await expect(page.locator('#exercise-detail')).toContainText('题目：', { timeout: 10000 });
    await expect(page.locator('#exercise-detail')).toContainText('引用来源');
    await expect(page.getByRole('button', { name: '确认题目' })).toHaveCount(1);
    await assertNoSensitiveVisibleText(page);
    await page.getByRole('button', { name: '确认题目' }).click();
    await expect(page.locator('#exercise-status')).toHaveText('题目已确认', { timeout: 15000 });
    await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
  });

  test('A-E2E-EXR-3 简答题→单题会话→pending_review 结果语义', async ({ page }) => {
    await createAndSelectSetViaUi(page, SET_TITLE);
    await createExerciseViaUi(page, 'short_answer', SA_PROMPT, SA_ANSWER);
    await confirmExerciseViaUi(page, SA_PROMPT);

    await page.getByRole('button', { name: '开始作答' }).click();
    await page.waitForURL(/practice\.html\?exercise_id=/, { timeout: 15000 });
    await expect(page.locator('[data-od-id="practice-exercise-entry"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#exercise-entry')).toContainText(SA_PROMPT, { timeout: 10000 });
    await page.getByRole('button', { name: '为该题目创建练习会话' }).click();
    await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 15000 });
    sessionIdSa = page.url().split('session_id=')[1];

    await page.getByRole('button', { name: '开始练习' }).click();
    await expect(page.locator('.practice-question')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('.practice-question h3')).toHaveText('第 1 题 / 1');
    await page.locator('#answer').fill(SA_ANSWER);
    await page.getByRole('button', { name: '提交答案' }).click();
    await expect(page.locator('#session-status')).toContainText('等待复核', { timeout: 15000 });
    await page.getByRole('button', { name: '完成会话' }).click();
    await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('已评分：0，已提交：1');
    await expect(page.locator('#review-link')).toBeVisible();
    await assertResultPrivacy(page);
  });

  test('A-E2E-EXR-4 选择题→开始作答→答错→结果→复盘链路', async ({ page }) => {
    await page.goto(`${BASE}/app/exercises.html`);
    await page.locator('#sets .set-item', { hasText: SET_TITLE }).click();
    await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
    await page.locator('#exercises .exercise-item', { hasText: MC_EDITED }).click();
    await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
    await page.getByRole('button', { name: '开始作答' }).click();
    await page.waitForURL(/practice\.html\?exercise_id=/, { timeout: 15000 });
    await expect(page.locator('#exercise-entry')).toContainText(MC_EDITED, { timeout: 10000 });
    await page.getByRole('button', { name: '为该题目创建练习会话' }).click();
    await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 15000 });
    sessionIdMc = page.url().split('session_id=')[1];

    await page.getByRole('button', { name: '开始练习' }).click();
    await expect(page.locator('.practice-question')).toBeVisible({ timeout: 15000 });
    await page.locator('#answer').selectOption('1'); // answer_key=0 → wrong on purpose
    await page.getByRole('button', { name: '提交答案' }).click();
    await expect(page.locator('#session-status')).toContainText('答案已提交', { timeout: 15000 });
    await page.getByRole('button', { name: '完成会话' }).click();
    await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('已评分：1，已提交：1');

    await page.reload();
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });
    await assertResultPrivacy(page);

    await page.locator('#review-link').click();
    await page.waitForURL(/review\.html/, { timeout: 15000 });
    await expect(page.locator('#review-list')).toContainText(MC_EDITED, { timeout: 15000 });
    await expect(page.locator('#review-list')).toContainText('待处理');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-EXR-5 服务真重启：练习集/题目/结果持久', async ({ page }) => {
    await stopServer();
    server = startServer();
    await ready();

    await page.goto(`${BASE}/app/exercises.html`);
    await page.locator('#sets .set-item', { hasText: SET_TITLE }).click();
    await expect(page.locator('#set-summary')).toContainText('共 3 道题', { timeout: 15000 });
    await expect(page.locator('#exercises')).toContainText(MC_EDITED, { timeout: 15000 });
    await expect(page.locator('#exercises')).toContainText(GENERATED_HINT);
    await expect(page.locator('#exercises')).toContainText(SA_PROMPT);
    await assertNoSensitiveVisibleText(page);

    await page.goto(`${BASE}/app/practice-result.html?session_id=${encodeURIComponent(sessionIdMc)}`);
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('已评分：1，已提交：1');
    await assertResultPrivacy(page);
  });

  test('A-E2E-EXR-6 列表/详情失败注入：安全文案与真实恢复', async ({ page }) => {
    await page.route('**/api/study/exercise-sets', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.goto(`${BASE}/app/exercises.html`);
    await expect(page.locator('#set-status')).toContainText('请求失败', { timeout: 15000 });
    await assertNoSensitiveVisibleText(page);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#refresh-sets').click();
    await expect(page.locator('#sets .set-item', { hasText: SET_TITLE })).toBeVisible({ timeout: 15000 });

    // Refresh failure must remain visible even after a previously successful load.
    await page.route('**/api/study/exercise-sets', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_refresh_error', traceback: 'hidden-traceback' }),
    }));
    await page.locator('#refresh-sets').click();
    await expect(page.locator('#set-status')).toContainText('请求失败，请重试', { timeout: 15000 });
    await assertNoSensitiveVisibleText(page);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#refresh-sets').click();
    await expect(page.locator('#sets .set-item', { hasText: SET_TITLE })).toBeVisible({ timeout: 15000 });

    // The exercise list has its own failure/retry path, independent of set detail.
    await page.route(/\/api\/study\/exercises\?set_id=/, route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.locator('#sets .set-item', { hasText: SET_TITLE }).click();
    await expect(page.locator('#exercise-status')).toContainText('请求失败，请重试', { timeout: 15000 });
    await expect(page.locator('#retry-exercises')).toBeVisible();
    await assertNoSensitiveVisibleText(page);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-exercises').click();
    await expect(page.locator('#exercises')).toContainText(MC_EDITED, { timeout: 15000 });

    await page.route('**/api/study/exercise-sets/*', route => route.fulfill({
      status: 500, contentType: 'application/json',
      body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden-traceback' }),
    }));
    await page.locator('#sets .set-item', { hasText: SET_TITLE }).click();
    await expect(page.locator('#set-summary')).toContainText('请求失败，请重试', { timeout: 15000 });
    await expect(page.locator('#retry-set-detail')).toBeVisible();
    await assertNoSensitiveVisibleText(page);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-set-detail').click();
    await expect(page.locator('#set-summary')).toContainText('共 3 道题', { timeout: 15000 });
  });

  test('A-E2E-EXR-7 结果页错误/缺失/重试/边界（B 类补充，mock）', async ({ page }) => {
    // Missing session identifier.
    await page.goto(`${BASE}/app/practice-result.html`);
    await expect(page.locator('#result-status')).toContainText('缺少会话标识', { timeout: 10000 });
    await expect(page.locator('#retry-result')).toBeHidden();

    // Unknown session id → safe message, retry available.
    await page.goto(`${BASE}/app/practice-result.html?session_id=does-not-exist`);
    await expect(page.locator('#result-status')).toContainText('请求失败，请重试', { timeout: 10000 });
    await expect(page.locator('#retry-result')).toBeVisible();
    await assertNoSensitiveVisibleText(page);

    // Result endpoint 500 → retry recovers with real data.
    let calls = 0;
    await page.route(/\/api\/study\/practice-sessions\/[^/]+\/result$/, route => {
      calls += 1;
      if (calls === 1) {
        return route.fulfill({ status: 500, contentType: 'application/json',
          body: JSON.stringify({ detail: 'private_backend_error', traceback: 'hidden' }) });
      }
      return route.continue();
    });
    await page.goto(`${BASE}/app/practice-result.html?session_id=${encodeURIComponent(sessionIdSa)}`);
    await expect(page.locator('#result-status')).toContainText('请求失败，请重试', { timeout: 10000 });
    await expect(page.locator('#retry-result')).toBeVisible();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-result').click();
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 1', { timeout: 15000 });
    await expect(page.locator('#result-detail')).toContainText('已评分：0，已提交：1');

    // `id` compat parameter still resolves through the ordinary endpoint.
    await page.route('**/api/study/practice-sessions/compat-session/result', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ session: { id: 'compat-session', status: 'finished' },
        summary: { score_total: 8, total_item_count: 10, scored_count: 8, submitted_count: 8 } }),
    }));
    await page.goto(`${BASE}/app/practice-result.html?id=compat-session`);
    await expect(page.locator('#result-detail')).toContainText('得分：8 / 10', { timeout: 10000 });

    // Zero-score and pending-review summaries render true values.
    await page.route('**/api/study/practice-sessions/empty-session/result', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ session: { id: 'empty-session', status: 'finished' },
        summary: { score_total: 0, total_item_count: 0, scored_count: 0, submitted_count: 0 } }),
    }));
    await page.goto(`${BASE}/app/practice-result.html?session_id=empty-session`);
    await expect(page.locator('#result-detail')).toContainText('得分：0 / 0', { timeout: 10000 });
    await page.route('**/api/study/practice-sessions/pending-session/result', route => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ session: { id: 'pending-session', status: 'finished' },
        summary: { score_total: 0, total_item_count: 2, scored_count: 0, submitted_count: 2 } }),
    }));
    await page.goto(`${BASE}/app/practice-result.html?session_id=pending-session`);
    await expect(page.locator('#result-detail')).toContainText('已评分：0，已提交：2', { timeout: 10000 });

    // cram_goal_id mismatch → backend 404 mapped to a safe user message.
    await page.route(/\/api\/study\/cram-goals\/[^/]+\/sessions\/[^/]+\/result$/, route => route.fulfill({
      status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'cram_goal_not_found' }),
    }));
    await page.goto(`${BASE}/app/practice-result.html?session_id=${encodeURIComponent(sessionIdMc)}&cram_goal_id=cram_wrong`);
    await expect(page.locator('#result-status')).toContainText('冲刺目标不存在或已不可用', { timeout: 10000 });
    await expect(page.locator('#retry-result')).toBeVisible();
    await assertResultPrivacy(page);
  });

  test('A-E2E-EXR-8 响应式/键盘/焦点/截图', async ({ page }) => {
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(`${BASE}/app/exercises.html`);
      await page.locator('#sets .set-item', { hasText: SET_TITLE }).click();
      await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(ART, `exercises-${viewport.name}.png`), fullPage: true });

      await page.goto(`${BASE}/app/practice-result.html?session_id=${encodeURIComponent(sessionIdSa)}`);
      await expect(page.locator('#result-detail')).toBeVisible({ timeout: 15000 });
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: path.join(ART, `result-${viewport.name}.png`), fullPage: true });
    }

    // Keyboard: Enter submits both creation forms natively.
    await page.setViewportSize({ width: 1280, height: 800 });
    await createAndSelectSetViaUi(page, SET_TITLE);
    await page.fill('#new-set-title', '键盘回车练习集');
    await page.press('#new-set-title', 'Enter');
    await expect(page.locator('#exercise-status')).toHaveText('练习集已创建', { timeout: 15000 });
    await page.fill('#new-exercise-prompt', '回车创建的题目');
    await page.fill('#new-exercise-answer', '答案');
    await page.press('#new-exercise-prompt', 'Enter');
    await expect(page.locator('#exercise-status')).toHaveText('题目已创建', { timeout: 15000 });

    await assertFocusStyle(page, '#new-set-title');
    await page.goto(`${BASE}/app/practice-result.html?session_id=${encodeURIComponent(sessionIdSa)}`);
    await expect(page.locator('#result-detail')).toBeVisible({ timeout: 15000 });
    await assertFocusStyle(page, '#review-link');
    await assertNoSensitiveVisibleText(page);
  });
});
