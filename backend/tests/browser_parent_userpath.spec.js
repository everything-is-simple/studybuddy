const { test, expect } = require('@playwright/test');

const BASE = process.env.STUDYBUDDY_BASE_URL || 'http://127.0.0.1:8787';
function json(body, status = 200) { return { status, contentType: 'application/json', body: JSON.stringify(body) }; }

async function mockCreation(page) {
  await page.route('**/api/materials?limit=100', route => route.fulfill(json({ items: [{ id: 'material-parent', original_name: '五年级语文.txt' }], total: 1, has_more: false })));
  await page.route('**/api/study/goals', route => route.request().method() === 'POST' ? route.fulfill(json({ id: 'goal-parent', title: '语文学习' }, 201)) : route.fulfill(json([])));
  await page.route('**/api/study/plans', route => route.request().method() === 'POST' ? route.fulfill(json({ id: 'plan-parent', title: '语文学习安排', status: 'draft' }, 201)) : route.fulfill(json([])));
  await page.route('**/api/study/plans/plan-parent/items', route => route.fulfill(json({ id: 'item-parent', title: '五年级语文.txt', status: 'pending' }, 201)));
  for (const action of ['confirm', 'activate']) await page.route(`**/api/study/plans/plan-parent/${action}`, route => route.fulfill(json({ id: 'plan-parent', status: action === 'confirm' ? 'confirmed' : 'active' })));
  await page.route('**/api/study/plans/plan-parent/rhythm', route => route.request().method() === 'PUT' ? route.fulfill(json({ status: 'configured', settings: {} })) : route.fulfill(json([])));
  await page.route('**/api/study/plans/plan-parent/rhythm/allocations', route => route.fulfill(json({ id: 'allocation-parent', item_id: 'item-parent' }, 201)));
}

test('parent view exposes three clear entries and completes the three-step arrangement', async ({ page }) => {
  await mockCreation(page);
  await page.goto(`${BASE}/app/parent.html`);
  await expect(page.locator('h1')).toHaveText('学习安排');
  await expect(page.locator('.action-cards')).toContainText('安排学习');
  await expect(page.locator('.action-cards')).toContainText('查看报告');
  await expect(page.locator('.action-cards')).toContainText('调整设置');
  await expect(page.locator('nav, aside')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(/目标|模块|依赖关系|来源链接|向量检索/);

  await page.locator('#parent-start-planning').click();
  await expect(page.locator('#parent-step-material')).toBeVisible();
  await page.locator('#parent-material').selectOption('material-parent');
  await page.locator('#parent-material-next').click();
  await expect(page.locator('#parent-step-time')).toBeVisible();
  await page.locator('#parent-minutes').fill('30');
  await page.locator('#parent-time-next').click();
  await expect(page.locator('#parent-step-review')).toBeVisible();
  await expect(page.locator('#parent-review-material')).toHaveText('五年级语文.txt');
  await expect(page.locator('#parent-review-minutes')).toHaveText('30 分钟');
  await page.locator('#parent-create').click();
  await expect(page.locator('#parent-success')).toBeVisible();
  await expect(page.locator('#parent-success-copy')).toContainText('每天 30 分钟');
});

test('parent view keeps material loading errors safe and retryable', async ({ page }) => {
  let failing = true;
  await page.route('**/api/materials?limit=100', route => failing ? route.fulfill(json({ detail: 'H:/private/traceback' }, 500)) : route.fulfill(json({ items: [{ id: 'material-parent', original_name: '恢复教材.txt' }] })));
  await page.goto(`${BASE}/app/parent.html`);
  await page.locator('#parent-start-planning').click();
  await expect(page.locator('#parent-status')).toContainText('操作没有完成');
  await expect(page.locator('#parent-status')).toContainText('怎么办：请重试');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|private/);
  failing = false;
  await page.locator('#parent-status').getByRole('button', { name: '重新加载' }).click();
  await expect(page.locator('#parent-material')).toContainText('恢复教材.txt');
});
