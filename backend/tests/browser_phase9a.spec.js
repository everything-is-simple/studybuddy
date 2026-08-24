const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase9a-ui';
const PORT = 8810;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  delete env.STUDYBUDDY_AI_PROVIDER;
  delete env.STUDYBUDDY_AI_MODEL;
  delete env.STUDYBUDDY_AI_BASE_URL;
  delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  for (let i = 0; i < 120; i += 1) {
    try {
      if ((await fetch(`${BASE}/api/health`)).ok) return;
    } catch (_) {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

function stop() {
  if (server && !server.killed) server.kill();
  server = null;
}

async function createGoalAndPlan(page) {
  await page.getByRole('link', {name: '学习计划'}).click();
  await page.locator('#plan-goal-title').fill('SQLite 基础');
  await page.locator('#plan-goal-create').click();
  await expect(page.locator('#plan-status')).toHaveText('目标已创建');
  await page.locator('#plan-module-title').fill('事务模块');
  await page.locator('#plan-module-create').click();
  await expect(page.locator('#plan-status')).toHaveText('模块已创建');
  await page.locator('#plan-title').fill('第一周计划');
  await page.locator('#plan-create').click();
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
}

test.beforeEach(async () => {
  fs.rmSync(RUN_ROOT, {recursive: true, force: true});
  server = startServer();
  await ready();
});

test.afterEach(stop);

test('Phase 9A plan workspace completes draft, dependency, activation, progress and refresh path', async ({page}) => {
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(BASE);
  await createGoalAndPlan(page);
  await page.locator('#plan-item-title').fill('读取事务日志');
  await page.locator('#plan-item-add').click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  await page.locator('#plan-item-title').fill('理解 WAL');
  await page.locator('#plan-item-add').click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  await expect(page.locator('#plan-detail')).toContainText('draft');
  await expect(page.locator('#plan-detail')).toContainText('计划项来源：未添加');
  await page.locator('#plan-dependency-predecessor').selectOption({label: '读取事务日志'});
  await page.locator('#plan-dependency-successor').selectOption({label: '理解 WAL'});
  await page.locator('#plan-dependency-add').click();
  await expect(page.locator('#plan-status')).toHaveText('依赖已添加');
  await page.locator('#plan-dependency-predecessor').selectOption({label: '理解 WAL'});
  await page.locator('#plan-dependency-successor').selectOption({label: '读取事务日志'});
  await page.locator('#plan-dependency-add').click();
  await expect(page.locator('#plan-status')).toHaveText('检测到依赖环，未保存');
  await page.locator('#plan-confirm').click();
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已确认');
  await page.locator('#plan-activate').click();
  await expect(page.locator('#plan-status')).toHaveText('计划已激活');
  await expect(page.locator('#plan-detail')).toContainText('active');
  await page.locator('.plan-item-complete').first().click();
  await expect(page.locator('#plan-status')).toHaveText('学习进度已保存');
  await expect(page.locator('#plan-detail')).toContainText('进度：1/2');
  await page.reload();
  await page.getByRole('link', {name: '学习计划'}).click();
  await expect(page.locator('#plan-detail')).toContainText('active');
  await expect(page.locator('#plan-detail')).toContainText('进度：1/2');
  await expect(page.locator('#plan-detail')).toContainText('来源：未添加');
  expect(errors).toEqual([]);
});

test('Phase 9A source lifecycle refresh is explicit and safe', async ({page}) => {
  await page.goto(BASE);
  const upload = await page.request.post(`${BASE}/api/materials`, {
    multipart: {file: {name: 'lifecycle.txt', mimeType: 'text/plain', buffer: Buffer.from('Lifecycle browser source text.')}},
  });
  expect(upload.ok()).toBe(true);
  const material = await upload.json();
  const indexed = await page.request.post(`${BASE}/api/materials/${material.material_id}/ai-index`);
  expect(indexed.ok()).toBe(true);
  const retrieval = await page.request.post(`${BASE}/api/retrieval`, {
    data: {query: 'Lifecycle browser source', material_ids: [material.material_id], mode: 'lexical'},
  });
  expect(retrieval.ok()).toBe(true);
  const hit = (await retrieval.json()).hits[0];
  expect(hit).toBeTruthy();
  const goal = await (await page.request.post(`${BASE}/api/study/goals`, {data: {title: 'Browser lifecycle goal'}})).json();
  const module = await (await page.request.post(`${BASE}/api/study/modules`, {data: {title: 'Browser lifecycle module'}})).json();
  const plan = await (await page.request.post(`${BASE}/api/study/plans`, {data: {goal_id: goal.id, title: 'Browser lifecycle plan'}})).json();
  const item = await (await page.request.post(`${BASE}/api/study/plans/${plan.id}/items`, {data: {title: 'Read lifecycle source', module_id: module.id}})).json();
  const link = await page.request.post(`${BASE}/api/study/modules/${module.id}/sources`, {data: {material_id: material.material_id, revision_id: hit.revision_id, chunk_id: hit.chunk_id}});
  expect(link.ok()).toBe(true);
  await page.request.post(`${BASE}/api/study/plans/${plan.id}/confirm`);
  await page.request.post(`${BASE}/api/study/plans/${plan.id}/activate`);
  await page.request.post(`${BASE}/api/study/plans/${plan.id}/items/${item.id}/progress`, {data: {event_type: 'completed'}});
  await page.request.delete(`${BASE}/api/materials/${material.material_id}`);
  await expect.poll(async () => (await (await page.request.get(`${BASE}/api/study/sources?plan_id=${plan.id}`)).json())[0].status).toBe('source_deleted');
  const restored = await page.request.post(`${BASE}/api/materials/${material.material_id}/restore`);
  expect(restored.ok()).toBe(true);
  expect((await (await page.request.get(`${BASE}/api/study/sources?plan_id=${plan.id}`)).json())[0].status).toBe('source_deleted');
  await page.request.post(`${BASE}/api/study/sources/refresh`);
  expect((await (await page.request.get(`${BASE}/api/study/sources?plan_id=${plan.id}`)).json())[0].status).toBe('valid');
  await page.request.delete(`${BASE}/api/materials/${material.material_id}`);
  await page.request.post(`${BASE}/api/materials/${material.material_id}/purge`);
  await page.request.post(`${BASE}/api/study/sources/refresh`);
  expect((await (await page.request.get(`${BASE}/api/study/sources?plan_id=${plan.id}`)).json())[0].status).toBe('source_unavailable');
  const detail = await (await page.request.get(`${BASE}/api/study/plans/${plan.id}`)).json();
  expect(detail.status).toBe('active');
  expect(detail.progress.completed_count).toBe(1);
  expect(detail.progress.source_warning_count).toBe(1);
  await page.getByRole('link', {name: '学习计划'}).click();
  await page.locator('#plan-list button').filter({hasText: 'Browser lifecycle plan'}).click();
  await expect(page.locator('#plan-detail')).toContainText('来源：source_unavailable');
  await expect(page.locator('#plan-detail')).toContainText('进度：1/1');
  await expect(page.locator('body')).not.toContainText('stored_path');
  await expect(page.locator('body')).not.toContainText('Lifecycle browser source text.');
});

test('Phase 9A plan workspace handles safe failure, retry, keyboard and narrow viewport', async ({page}) => {
  await page.goto(BASE);
  await page.getByRole('link', {name: '学习计划'}).click();
  await page.route('**/api/study/goals', route => route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({detail: 'private_backend_error'})}));
  await page.locator('#plan-refresh').click();
  await expect(page.locator('#plan-status')).toHaveText('计划加载失败，可重试');
  await expect(page.locator('#plan-refresh')).toBeEnabled();
  await page.unroute('**/api/study/goals');
  await page.locator('#plan-refresh').click();
  await expect(page.locator('#plan-status')).toContainText('创建目标后开始计划');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.locator('#nav-plans').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#plans')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('private_backend_error');
});
