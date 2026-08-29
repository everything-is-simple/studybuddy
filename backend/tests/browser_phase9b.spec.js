const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase9b-ui';
const PORT = 8811;
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
async function uploadAndIndex(page, name = 'rhythm-notes.txt') {
  await page.locator('#file').setInputFiles({name, mimeType: 'text/plain', buffer: Buffer.from('A controlled source establishes a stable rhythm and a cited note.')});
  await page.locator('#file-import').click();
  await expect(page.locator('#status')).toContainText('导入完成');
  await page.locator('#ai-index').click();
  await expect(page.locator('#qa-status')).toContainText('AI 索引已建立');
  return page.evaluate(async () => (await (await fetch('/api/materials')).json())[0].id);
}
async function createActivePlan(page) {
  await page.getByRole('link', {name: '学习计划'}).click();
  await page.locator('#plan-goal-title').fill('节奏目标'); await page.locator('#plan-goal-create').click();
  await page.locator('#plan-title').fill('节奏计划'); await page.locator('#plan-create').click();
  await page.locator('#plan-item-title').fill('阅读材料'); await page.locator('#plan-item-add').click();
  await page.locator('#plan-confirm').click(); await expect(page.locator('#plan-status')).toHaveText('计划草稿已确认');
  await page.locator('#plan-activate').click(); await expect(page.locator('#plan-detail')).toContainText('状态：active');
}

test.beforeEach(async () => { fs.rmSync(RUN_ROOT, {recursive: true, force: true}); server = startServer(); await ready(); });
test.afterEach(stop);

test('Phase 9B S1 rhythm workspace saves, adjusts, completes and recovers server state', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${BASE}/legacy`); await createActivePlan(page);
  await expect(page.locator('#rhythm-workspace')).toContainText('尚未设置节奏');
  await page.locator('#rhythm-cadence').selectOption('weekly');
  await page.locator('#rhythm-timezone').fill('Asia/Shanghai');
  await page.locator('#rhythm-period-start').fill('2026-01-05');
  await page.locator('#rhythm-target-minutes').fill('120');
  await page.locator('#rhythm-save').click();
  await expect(page.locator('#plan-status')).toHaveText('学习节奏已保存');
  await page.locator('#rhythm-date').fill('2026-01-06');
  await page.locator('#rhythm-minutes').fill('30');
  await page.locator('#rhythm-allocation-add').click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已分配');
  await expect(page.locator('#rhythm-workspace')).toContainText('30/120 分钟');
  await page.getByLabel('调整分配分钟').fill('45');
  await page.getByRole('button', {name: '调整'}).click();
  await expect(page.locator('#plan-status')).toHaveText('学习项分配已调整');
  await expect(page.locator('#rhythm-workspace')).toContainText('45/120 分钟');
  await page.locator('.plan-item-complete').first().click();
  await expect(page.locator('#plan-detail')).toContainText('进度：1/1');
  await page.reload(); await page.getByRole('link', {name: '学习计划'}).click();
  await expect(page.locator('#rhythm-workspace')).toContainText('45/120 分钟');
  await expect(page.locator('#plan-detail')).toContainText('进度：1/1');
  expect(errors).toEqual([]);
});

test('Phase 9B S2 workspace generates a cited draft, edits, confirms, archives and reloads', async ({page}) => {
  await page.goto(`${BASE}/legacy`); const materialId = await uploadAndIndex(page);
  await page.getByRole('link', {name: '资料笔记'}).click();
  await page.locator('#note-title').fill('用户观察'); await page.locator('#note-content').fill('这是用户笔记。'); await page.locator('#note-create').click();
  await expect(page.locator('#notes-status')).toHaveText('用户笔记已创建');
  await page.locator('#note-module-title').fill('资料模块'); await page.locator('#note-module-link').click();
  await expect(page.locator('#notes-status')).toHaveText('知识模块已关联');
  await expect(page.locator('#note-detail')).toContainText('资料模块');
  await page.locator('#note-topic').fill('controlled source'); await page.locator('#note-generate').click();
  await expect(page.locator('#notes-status')).toHaveText('已生成引用草稿');
  await expect(page.locator('#note-detail')).toContainText('AI 引用草稿');
  const citation = page.getByRole('button', {name: /查看引用 ctx-/}).first();
  await expect(citation).toBeVisible();
  await citation.click();
  await expect(page.getByRole('dialog')).toContainText('引用详情');
  await page.keyboard.press('Escape');
  await page.locator('#note-edit-title').fill('已编辑的引用笔记'); await page.locator('#note-save').click();
  await expect(page.locator('#notes-status')).toHaveText('笔记编辑已保存');
  await expect(page.locator('#note-detail')).toContainText('已由用户编辑');
  await page.locator('#note-confirm').click(); await expect(page.locator('#notes-status')).toHaveText('笔记已确认');
  await expect(page.locator('#note-detail')).toContainText('状态：confirmed');
  await page.locator('#note-archive').click(); await expect(page.locator('#notes-status')).toHaveText('笔记已归档');
  await page.reload(); await page.getByRole('link', {name: '资料笔记'}).click();
  await expect(page.locator('#note-list')).toContainText('已编辑的引用笔记');
  await expect(page.locator('body')).not.toContainText('stored_path');
  await expect(page.locator('body')).not.toContainText(materialId.replace('material_', 'H:'));
});

test('Phase 9B workspace keeps failure, stale citation, malformed response, duplicate and narrow paths safe', async ({page}) => {
  await page.goto(`${BASE}/legacy`); const materialId = await uploadAndIndex(page, 'failure-notes.txt');
  await page.getByRole('link', {name: '资料笔记'}).click();
  await page.route('**/api/study/notes/generate', route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'study_note_provider_not_configured'})}));
  await page.locator('#note-topic').fill('controlled'); await page.locator('#note-generate').click();
  await expect(page.locator('#notes-status')).toHaveText('AI 笔记服务尚未配置');
  await expect(page.locator('#note-generate')).toBeEnabled(); await page.unroute('**/api/study/notes/generate');
  await page.locator('#note-topic').fill('controlled source'); await page.locator('#note-generate').click();
  await expect(page.locator('#notes-status')).toHaveText('已生成引用草稿');
  await page.request.delete(`${BASE}/api/materials/${materialId}`);
  await page.locator('#notes-refresh').click();
  await expect.poll(async () => page.locator('#note-detail').textContent()).toContain('来源警告');
  await expect(page.getByRole('button', {name: '来源不可用'}).first()).toBeDisabled();
  await expect(page.locator('#note-detail')).toContainText('来源警告');
  const refreshRoute = '**/api/study/notes/sources/refresh';
  await page.route(refreshRoute, route => route.fulfill({status: 200, contentType: 'application/json', body: '{bad'}));
  await page.locator('#notes-refresh').click(); await expect(page.locator('#notes-status')).toHaveText('笔记来源状态刷新失败，可重试');
  await page.unroute(refreshRoute);
  await page.route(refreshRoute, route => route.abort());
  await page.locator('#notes-refresh').click(); await expect(page.locator('#notes-status')).toHaveText('笔记来源状态刷新失败，可重试');
  await page.unroute(refreshRoute);
  let creates = 0;
  await page.route('**/api/study/notes', async route => { if (route.request().method() === 'POST') { creates += 1; await new Promise(resolve => setTimeout(resolve, 100)); } await route.continue(); });
  await page.locator('#note-title').fill('重复点击'); await page.locator('#note-content').fill('内容');
  await Promise.all([page.locator('#note-create').click(), page.locator('#note-create').click()]);
  await expect(page.locator('#notes-status')).toHaveText('用户笔记已创建'); expect(creates).toBe(1); await page.unroute('**/api/study/notes');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole('link', {name: '资料笔记'}).focus(); await page.keyboard.press('Enter'); await expect(page.locator('#notes')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('traceback');
  await expect(page.locator('body')).not.toContainText('private_backend_error');
});
