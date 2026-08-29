const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase9c-ui';
const PORT = 8813;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer(provider = 'fake') {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  if (provider === 'fake') env.STUDYBUDDY_AI_PROVIDER = 'fake';
  else delete env.STUDYBUDDY_AI_PROVIDER;
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}
async function ready() {
  for (let i = 0; i < 120; i += 1) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}
function stop() { if (server && !server.killed) server.kill(); server = null; }
async function createExercise(page, type = 'multiple_choice') {
  const set = await page.request.post(`${BASE}/api/study/exercise-sets`, {data: {title: 'Browser 9C'}});
  const payload = type === 'multiple_choice'
    ? {exercise_type: type, prompt: 'Choose the verified answer', options: ['wrong', 'right'], answer_key: 1}
    : {exercise_type: type, prompt: 'Explain the verified answer', answer_key: 'because'};
  const created = await page.request.post(`${BASE}/api/study/exercise-sets/${(await set.json()).id}/exercises`, {data: payload});
  const exercise = await created.json();
  await page.request.post(`${BASE}/api/study/exercises/${exercise.id}/confirm`);
  return exercise.id;
}
async function createGoal(page) {
  const response = await page.request.post(`${BASE}/api/study/cram-goals`, {data: {title: 'Browser exam', target_date: '2026-06-01', target_exercise_count: 1}});
  const goal = await response.json();
  await page.request.post(`${BASE}/api/study/cram-goals/${goal.id}/active`);
  return goal.id;
}

test.beforeEach(async () => { fs.rmSync(RUN_ROOT, {recursive: true, force: true}); server = startServer(); await ready(); });
test.afterEach(stop);

test('Phase 9C S3 workspace starts, submits, results, reloads and preserves privacy', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const exerciseId = await createExercise(page);
  await page.goto(`${BASE}/legacy`);
  await page.getByRole('link', {name: '练习反馈'}).click();
  await expect(page.locator('#phase9c')).toBeVisible();
  await expect(page.locator('#phase9c-session-list')).toContainText('尚无限时练习');
  await page.locator('#phase9c-refresh').click();
  await page.locator('.phase9c-exercise-choice').check();
  await page.locator('#phase9c-session-create').click();
  await expect(page.locator('#phase9c-detail')).toContainText('状态：draft');
  await page.getByRole('button', {name: '开始限时练习'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('状态：active');
  await page.locator('.phase9c-answer').selectOption('0');
  await page.getByRole('button', {name: '提交本题'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('已提交：1');
  await page.getByRole('button', {name: '结束练习'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('状态：finished');
  await page.getByRole('button', {name: '查看结果'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('错误：1');
  await expect(page.locator('body')).not.toContainText('answer_key_json');
  await expect(page.locator('body')).not.toContainText('answer_json');
  await expect(page.locator('body')).not.toContainText('stored_path');
  await page.reload();
  await page.getByRole('link', {name: '练习反馈'}).click();
  await expect(page.locator('#phase9c-session-list')).toContainText('finished');
  await page.getByRole('link', {name: '练习反馈'}).focus(); await page.keyboard.press('Enter');
  await expect(page.locator('#phase9c')).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(errors).toEqual([]);
  expect(exerciseId).toMatch(/^exercise_/);
});

test('Phase 9C S4/S5 workspace exposes feedback and safe failure paths', async ({page}) => {
  const exerciseId = await createExercise(page, 'short_answer');
  const goalId = await createGoal(page);
  await page.goto(`${BASE}/legacy`);
  await page.getByRole('link', {name: '练习反馈'}).click();
  await expect(page.locator('#phase9c')).toBeVisible();
  await page.locator('#phase9c-refresh').click();
  await page.locator('#phase9c-goal-list').getByRole('button').first().click();
  await expect(page.locator('#phase9c-detail')).toContainText('Browser exam');
  await page.locator('.phase9c-cram-choice').check();
  await page.getByRole('button', {name: '创建模拟练习'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('状态：draft');
  await page.getByRole('button', {name: '开始限时练习'}).click();
  await page.locator('.phase9c-answer').fill('private answer');
  await page.getByRole('button', {name: '提交本题'}).click();
  await expect(page.locator('#phase9c-detail')).toContainText('已提交：1');
  await page.route('**/api/study/practice-sessions/**/result', route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'private_backend_error'})}));
  await page.getByRole('button', {name: '查看结果'}).click();
  await expect(page.locator('#phase9c-status')).toContainText('结果加载失败，可重试');
  await expect(page.locator('body')).not.toContainText('private_backend_error');
  await page.unroute('**/api/study/practice-sessions/**/result');
  await expect(page.locator('body')).not.toContainText('private answer');
  expect(goalId).toMatch(/^cram_goal_/);
  expect(exerciseId).toMatch(/^exercise_/);
});

test('Phase 9C default provider remains safe and retryable', async ({page}) => {
  await page.goto(`${BASE}/legacy`);
  await page.getByRole('link', {name: '练习反馈'}).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#phase9c')).toBeVisible();
  await page.route('**/api/study/practice-sessions', route => route.abort());
  await page.locator('#phase9c-refresh').click();
  await expect(page.locator('#phase9c-status')).toContainText('加载失败，可重试');
  await page.unroute('**/api/study/practice-sessions');
  await page.locator('#phase9c-refresh').click();
  await expect(page.locator('#phase9c-status')).toContainText('已加载');
  await expect(page.locator('body')).not.toContainText('traceback');
});
