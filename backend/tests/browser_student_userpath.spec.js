const { test, expect } = require('@playwright/test');

const BASE = process.env.STUDYBUDDY_BASE_URL || 'http://127.0.0.1:8787';
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

function json(body, status = 200) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

async function mockTask(page, state = 'pending') {
  const date = today();
  await page.route('**/api/study/plans', route => route.fulfill(json([{ id: 'student-plan', title: '学习计划', status: 'active' }])));
  await page.route('**/api/study/plans/student-plan', route => route.fulfill(json({ id: 'student-plan', title: '学习计划', items: [{ id: 'student-item', title: '五年级语文 · 第三课', status: state }] })));
  await page.route('**/api/study/plans/student-plan/rhythm', route => route.fulfill(json({ settings: { timezone: 'UTC' } })));
  await page.route('**/api/study/plans/student-plan/rhythm/allocations', route => route.fulfill(json([{ item_id: 'student-item', local_date: date, planned_minutes: 20 }])));
  await page.route('**/api/study/plans/student-plan/rhythm/weekly-trend', route => route.fulfill(json({ days: [{ local_date: date, completed_count: state === 'completed' ? 1 : 0 }] })));
}

test('student view shows a focused task and starts the learning path', async ({ page }) => {
  await mockTask(page);
  await page.goto(`${BASE}/app/student.html`);
  await expect(page.locator('#student-greeting')).toHaveText('早上好！');
  await expect(page.locator('#student-task-title')).toHaveText('五年级语文 · 第三课');
  await expect(page.locator('#student-task-time')).toHaveText('预计 20 分钟');
  await expect(page.locator('#student-start')).toHaveText('开始');
  await expect(page.locator('nav, aside')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(/目标|模块|节奏/);
  await page.locator('#student-start').click();
  await expect(page).toHaveURL(/\/app\/plan-detail\.html\?plan_id=student-plan&item_id=student-item/);
});

test('student view handles no task and safe retryable failures', async ({ page }) => {
  await page.route('**/api/study/plans', route => route.fulfill(json([])));
  await page.goto(`${BASE}/app/student.html`);
  await expect(page.locator('#student-empty')).toBeVisible();
  await expect(page.locator('#student-empty')).toContainText('今天还没有学习安排');

  let failing = true;
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/study/plans', route => failing
    ? route.fulfill(json({ detail: 'H:/private/traceback' }, 500))
    : route.fulfill(json([{ id: 'student-plan', title: '学习计划', status: 'active' }])));
  await page.goto(`${BASE}/app/student.html`);
  await expect(page.locator('#student-error')).toContainText('操作没有完成');
  await expect(page.locator('#student-error')).toContainText('怎么办：请重试');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|private/);
  failing = false;
  await mockTask(page);
  await page.locator('#student-retry').click();
  await expect(page.locator('#student-task')).toBeVisible();
  await expect(page.locator('#student-start')).toHaveText('开始');
});
