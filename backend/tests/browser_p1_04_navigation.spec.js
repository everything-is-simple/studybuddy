const { test, expect } = require('@playwright/test');
const path = require('path');

const BASE = process.env.STUDYBUDDY_BASE_URL || 'http://127.0.0.1:8787';
const pages = [
  'materials', 'qa', 'capture', 'classroom', 'today', 'plans', 'notes', 'practice',
  'cards', 'exercises', 'review', 'reports', 'tasks', 'settings-provider', 'settings',
];

test('P1-04 A: legacy Today entry exposes both simple views and the advanced directory', async ({ page }) => {
  await page.goto(`${BASE}/app/today.html`);
  await expect(page).toHaveURL(`${BASE}/app/today.html`);
  await page.locator('[data-control="view-student"]').click();
  await expect(page.locator('[data-control="student-view"]')).toBeVisible();
  await page.goBack();
  await page.locator('[data-control="view-parent"]').click();
  await expect(page.locator('[data-control="parent-view"]')).toBeVisible();
  await page.locator('[data-control="parent-advanced"]').click();
  await expect(page).toHaveURL(`${BASE}/app/advanced.html`);
  await expect(page.locator('h1')).toHaveText('高级功能');
  await page.reload();
  await expect(page.locator('[data-control="view-advanced"]')).toHaveAttribute('aria-current', 'page');
  await page.locator('[data-control="advanced-return-parent"]').click();
  await expect(page).toHaveURL(`${BASE}/app/parent.html`);
});

test('P1-04 A: every advanced workflow opens and can return through shared navigation', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const name of pages) {
    await page.goto(`${BASE}/app/advanced.html`);
    await page.locator(`[data-control="advanced-page-link"][href="/app/${name}.html"]`).click();
    await expect(page).toHaveURL(`${BASE}/app/${name}.html`);
    await expect(page.locator('h1')).toBeVisible();
    await page.locator('[data-control="view-advanced"]').click();
    await expect(page.locator('[data-control="advanced-page-link"]')).toHaveCount(pages.length);
  }
  expect(errors).toEqual([]);
});

test('P1-04 A: parent iframe exits to the directory, Back restores Buddy and refresh keeps the view', async ({ page }) => {
  await page.goto(`${BASE}/app/buddy.html?view=parent`);
  await page.frameLocator('#buddy-frame').locator('[data-control="parent-advanced"]').click();
  await expect(page).toHaveURL(`${BASE}/app/advanced.html`);
  await page.goBack();
  await expect(page).toHaveURL(`${BASE}/app/buddy.html?view=parent`);
  await expect(page.frameLocator('#buddy-frame').locator('h1')).toHaveText('学习安排');
  await page.reload();
  await expect(page.locator('#buddy-frame')).toHaveAttribute('src', '/app/parent.html');
});

test('P1-04 A: Buddy defaults to the student view while management links stay hidden', async ({ page }) => {
  await page.goto(`${BASE}/app/buddy.html`);
  await expect(page).toHaveURL(`${BASE}/app/buddy.html?view=student`);
  for (const link of await page.locator('[data-management-link]').all()) await expect(link).toBeHidden();
  await page.locator('[data-switch-view="parent"]').click();
  await page.goto(`${BASE}/app/buddy.html`);
  await expect(page).toHaveURL(`${BASE}/app/buddy.html?view=parent`);
});

test('P1-04 A: parent-directory-return path works with JavaScript disabled', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto(`${BASE}/app/parent.html`);
    await page.locator('[data-control="parent-advanced"]').click();
    await expect(page.locator('[data-control="advanced-page-link"]')).toHaveCount(pages.length);
    await page.locator('[data-control="advanced-return-parent"]').click();
    await expect(page.locator('h1')).toHaveText('学习安排');
  } finally { await context.close(); }
});

for (const width of [390, 1280]) {
  test(`P1-04 A: ${width}px navigation stays usable with keyboard and without horizontal overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`${BASE}/app/advanced.html`);
    const link = page.locator('[data-control="advanced-page-link"][href="/app/plans.html"]');
    await link.focus();
    await expect(link).toBeFocused();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(process.env.STUDYBUDDY_TEST_ROOT || 'H:/studybuddy-test', `p1-04-directory-${width}.png`), fullPage: true });
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(`${BASE}/app/plans.html`);
    await page.locator('[data-control="view-parent"]').click();
    await expect(page.locator('h1')).toHaveText('学习安排');
  });
}
