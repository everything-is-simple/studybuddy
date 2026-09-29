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

test('parent requires explicit selection and keeps minute controls aligned without writes', async ({ page }) => {
  await mockCreation(page);
  const writes = [];
  page.on('request', request => {
    if (request.url().includes('/api/') && request.method() !== 'GET') writes.push(request.method());
  });
  await page.goto(`${BASE}/app/parent.html`);
  await page.getByRole('button', { name: '开始安排', exact: true }).click();
  await expect(page.locator('#parent-material')).toBeEnabled();
  await expect(page.locator('#parent-material')).toHaveValue('');
  await page.locator('#parent-material-next').click();
  await expect(page.locator('#parent-status')).toHaveText('请先选择一份教材。');
  await expect(page.locator('#parent-step-material')).toBeVisible();
  await page.locator('#parent-material').selectOption('material-parent');
  await page.locator('#parent-material-next').click();
  for (const value of ['15', '20', '30']) {
    await page.getByRole('button', { name: `${value} 分钟`, exact: true }).click();
    await expect(page.locator('#parent-minutes')).toHaveValue(value);
    await expect(page.locator('.minute-option.selected')).toHaveAttribute('data-minutes', value);
    await expect(page.locator('.minute-option[aria-pressed="true"]')).toHaveAttribute('data-minutes', value);
  }
  await page.locator('#parent-minutes').fill('15');
  await expect(page.locator('.minute-option.selected')).toHaveAttribute('data-minutes', '15');
  await page.locator('#parent-minutes').fill('30');
  await expect(page.locator('.minute-option.selected')).toHaveAttribute('data-minutes', '30');
  await page.locator('#parent-minutes').fill('25');
  await expect(page.locator('.minute-option.selected, .minute-option[aria-pressed="true"]')).toHaveCount(0);
  for (const value of ['4', '241', '5.5', '']) {
    await page.locator('#parent-minutes').fill(value);
    await page.locator('#parent-time-next').click();
    await expect(page.locator('#parent-status')).toHaveText('请输入 5 到 240 之间的学习分钟数。');
    await expect(page.locator('#parent-step-time')).toBeVisible();
  }
  for (const value of ['5', '240']) {
    await page.locator('#parent-minutes').fill(value);
    await page.locator('#parent-time-next').click();
    await expect(page.locator('#parent-review-minutes')).toHaveText(`${value} 分钟`);
    await page.locator('#parent-review-back').click();
    await expect(page.locator('#parent-minutes')).toHaveValue(value);
  }
  await page.locator('#parent-time-back').click();
  await expect(page.locator('#parent-material')).toHaveValue('material-parent');
  await page.getByRole('button', { name: '返回', exact: true }).click();
  await expect(page.locator('#parent-home')).toBeVisible();
  expect(writes).toEqual([]);
});
