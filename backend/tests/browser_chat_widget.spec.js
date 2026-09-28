const { test, expect } = require('@playwright/test');

const BASE = process.env.STUDYBUDDY_BASE_URL || 'http://127.0.0.1:8787';
const json = body => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

test('全站 Buddy 对话入口可打开并安全提交问题', async ({ page }) => {
  await page.route('**/api/readiness', route => route.fulfill(json({ status: 'ready' })));
  await page.route('**/api/materials?limit=20', route => route.fulfill(json({ items: [{ id: 'chat-material', status: 'valid', source_status: 'valid' }] })));
  await page.route('**/api/qa/ask', route => route.fulfill(json({ answer_text: '今天先复习第三课，再做两道练习。' })));
  await page.goto(`${BASE}/app/today.html`);
  const toggle = page.locator('.chat-toggle');
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.locator('#chat-panel')).toBeVisible();
  await page.locator('.chat-input').fill('今天学什么？');
  await page.locator('.chat-send').click();
  await expect(page.locator('.chat-messages')).toContainText('今天先复习第三课，再做两道练习。');
  await expect(page).toHaveURL(/today\.html/);
  await page.locator('.chat-close').click();
  await expect(page.locator('#chat-panel')).toBeHidden();
});
