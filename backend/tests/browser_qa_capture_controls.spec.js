// UI-created synthetic data only; fake Provider/ASR evidence is browser-pass.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const BASE = process.env.STUDYBUDDY_BASE_URL;
const ART = path.join(process.env.STUDYBUDDY_TEST_ROOT || 'H:/studybuddy-test', 'control-evidence');
test.setTimeout(90000);
test.beforeAll(() => {
  if (!BASE) throw new Error('Use test-browser.ps1 with an isolated service');
  fs.mkdirSync(ART, { recursive: true });
});
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => new URL(route.request().url()).origin === new URL(BASE).origin ? route.continue() : route.abort());
});

async function capture(page, label) {
  await page.screenshot({ path: path.join(ART, label + '.png'), fullPage: true,
    mask: [page.locator('.thread-question, .thread-answer, .transcript-view')] });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator('body').innerText()).not.toMatch(/Traceback|sqlite|stored_path|api[_-]?key|[A-Z]:[\\/]/i);
}

async function createQa(page, label) {
  await page.goto(BASE + '/app/materials.html');
  const content = '# Synthetic 星环\n\n星环知识点一是加法。星环知识点二是减法。星环知识点三是乘法。\n问题：星环包含几个知识点？选择题：一加一是多少？A 一；B 二。正确答案 B。';
  await page.locator('#file-input').setInputFiles({ name: label + '.md', mimeType: 'text/markdown', buffer: Buffer.from(content) });
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1');
  await page.locator('#items li').filter({ hasText: label + '.md' }).getByRole('button', { name: /详情/ }).click();
  await expect(page).toHaveURL(/material-detail\.html\?material=/);
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立');
  await page.locator('#qa').click();
  await expect(page).toHaveURL(/qa\.html\?material=/);
  await page.locator('#retrieval-mode').selectOption('lexical');
  await page.locator('#question').fill('星环知识点');
  await page.locator('#submit-btn').click();
  await expect(page.locator('#submit-status')).toHaveText('回答已生成');
  return page.locator('[data-control=qa-thread]').first();
}

function wav() {
  const buffer = Buffer.alloc(1644);
  buffer.write('RIFF'); buffer.writeUInt32LE(buffer.length - 8, 4);
  buffer.write('WAVE', 8); buffer.write('fmt ', 12); buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(8000, 24); buffer.writeUInt32LE(16000, 28);
  buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36); buffer.writeUInt32LE(1600, 40);
  return buffer;
}

async function reviewedCapture(page, label, action) {
  await page.goto(BASE + '/app/capture.html');
  await page.locator('#new-session-btn').click();
  await page.locator('#asset-kind').selectOption('audio');
  await page.locator('#media-type').selectOption('audio/wav');
  await page.locator('#original-name').fill(label + '.wav');
  await page.locator('#submit-new-session').click();
  await expect(page.locator('#new-session-dialog')).not.toBeVisible();
  const card = page.locator('#sessions .session-card').filter({ hasText: label + '.wav' });
  await card.getByRole('button', { name: '查看详情' }).click();
  const detail = page.locator('#session-detail-dialog');
  await expect(detail.locator('[data-control=capture-archive]')).toHaveCount(0);
  await detail.locator('#file-input').setInputFiles({ name: label + '.wav', mimeType: 'audio/wav', buffer: wav() });
  await expect(detail.locator('#session-detail-status')).toContainText('上传成功');
  await detail.locator('[data-control=capture-transcribe]').click();
  await expect(detail.locator('#session-detail-status')).toContainText('转写完成');
  await expect(detail.locator('[data-control=capture-archive]')).toHaveCount(0);
  await detail.locator('[data-control=capture-' + action + '-draft]').click();
  if (action === 'confirm') {
    await expect(detail.locator('#session-detail-status')).toContainText('草稿已确认');
    await page.locator('#close-detail-btn').click();
  }
  await expect(detail).not.toBeVisible();
  await expect(card).toContainText(action === 'confirm' ? '已确认' : '已拒绝');
  await card.getByRole('button', { name: '查看详情' }).click();
  await expect(detail.locator('[data-control=capture-archive]')).toBeVisible();
  return { card, detail };
}

for (const width of [1280, 390]) {
  test.describe('control follow-up ' + width, () => {
    test.use({ viewport: { width, height: width === 1280 ? 800 : 844 } });
    test('QA close, keyboard, reload, citation and return', async ({ page }) => {
      const thread = await createQa(page, 'qa-controls-' + width);
      const threadId = await thread.getAttribute('data-thread-id');
      const item = page.locator('[data-control=qa-thread]').filter({ has: page.locator('[data-thread-id="' + threadId + '"]') });
      const open = item.locator('[data-control=qa-thread-open]');
      const detail = item.locator('.thread-detail');
      const close = item.locator('[data-control=qa-thread-close]');
      const originalUrl = page.url();
      await open.click();
      await expect(detail.locator('.thread-answer')).toContainText('Fake answer');
      await capture(page, 'qa-' + width + '-before-close');
      await close.click();
      await expect(detail).toBeHidden();
      await expect(open).toBeFocused();
      await expect(open).toHaveAttribute('aria-expanded', 'false');
      await expect(page).toHaveURL(originalUrl);
      await open.press('Enter');
      await expect(detail).toBeVisible();
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      await expect(close).toBeFocused();
      await page.keyboard.press('Space');
      await expect(detail).toBeHidden();
      await expect(open).toBeFocused();
      await open.click();
      await open.click();
      await expect(detail).toBeHidden();
      await page.reload();
      await open.click();
      await expect(detail.locator('.thread-answer')).toContainText('Fake answer');
      await detail.locator('.citation-link').first().click();
      await expect(page).toHaveURL(/material-detail\.html\?material=.+&citation=.+/);
      await expect(page.locator('#body-location')).toContainText('已定位引用来源');
      await page.goBack();
      await expect(page).toHaveURL(originalUrl);
      await open.click();
      await expect(close).toBeVisible();
      await close.click();
      await capture(page, 'qa-' + width + '-closed-after-return');
    });

    for (const action of ['confirm', 'reject']) {
      test('capture archive ' + action + ': cancel, persist, filter and preserve materials', async ({ page }) => {
        const label = 'archive-' + action + '-' + width;
        const { card, detail } = await reviewedCapture(page, label, action);
        const archive = detail.locator('[data-control=capture-archive]');
        let posts = 0;
        page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/archive')) posts++; });
        await capture(page, label + '-before');
        page.once('dialog', d => d.dismiss());
        await archive.click();
        await expect(archive).toBeEnabled();
        expect(posts).toBe(0);
        await expect(detail).toContainText(action === 'confirm' ? '已确认' : '已拒绝');
        page.once('dialog', d => d.accept());
        await archive.click();
        await expect(detail.locator('#session-detail-status')).toContainText('归档成功');
        await expect(detail).toContainText('此会话已归档');
        await expect(archive).toHaveCount(0);
        expect(posts).toBe(1);
        await capture(page, label + '-archived');
        await page.locator('#close-detail-btn').click();
        await expect(card).toHaveCount(0);
        await page.locator('#include-archived').click();
        await expect(card).toContainText('已归档');
        await page.reload();
        await expect(card).toHaveCount(0);
        await page.locator('#include-archived').click();
        await expect(card).toContainText('已归档');
        await card.getByRole('button', { name: '查看详情' }).click();
        await expect(detail.locator('.transcript-view')).not.toBeEmpty();
        await expect(archive).toHaveCount(0);
        await capture(page, label + '-reloaded');
        if (action === 'confirm') {
          await page.goto(BASE + '/app/materials.html');
          await page.locator('#items li').filter({ hasText: label + '.wav' }).filter({ hasText: '解析完成' }).getByRole('button', { name: /详情/ }).click();
          await expect(page.locator('#state')).toHaveText('材料已加载');
          await expect(page.locator('#body')).not.toBeEmpty();
        }
      });
    }
  });
}

test('QA pending and failed detail requests remain closable and recover', async ({ page }) => {
  const item = await createQa(page, 'qa-race');
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/api/qa/threads/*', async route => { await pending; await route.continue(); });
  await item.locator('[data-control=qa-thread-open]').click();
  await expect(item.locator('.thread-detail')).toContainText('正在加载对话');
  await item.locator('[data-control=qa-thread-close]').click();
  release();
  await page.unrouteAll({ behavior: 'wait' });
  await expect(item.locator('.thread-detail')).toBeHidden();
  await page.route('**/api/qa/threads/*', route => route.fulfill({ status: 503, json: { detail: 'request_failed' } }));
  await item.locator('[data-control=qa-thread-open]').click();
  await expect(item.locator('.thread-detail')).toContainText('请求失败');
  await item.locator('[data-control=qa-thread-close]').click();
  await page.unroute('**/api/qa/threads/*');
  await item.locator('[data-control=qa-thread-open]').click();
  await expect(item.locator('.thread-answer')).toContainText('Fake answer');
  await capture(page, 'qa-injected-failure-recovery');
});

test('capture archive injected failure recovers; repeated activation sends once', async ({ page }) => {
  const { detail } = await reviewedCapture(page, 'archive-failure', 'confirm');
  const archive = detail.locator('[data-control=capture-archive]');
  await page.route('**/api/study/capture-sessions/*/archive', route => route.fulfill({ status: 503, json: { detail: 'capture_archive_failed' } }));
  page.once('dialog', d => d.accept());
  await archive.click();
  await expect(detail.locator('#session-detail-status')).toHaveText('归档失败，请重试');
  await expect(archive).toBeEnabled();
  await expect(detail).toContainText('已确认');
  await capture(page, 'archive-injected-failure');
  await page.unroute('**/api/study/capture-sessions/*/archive');
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  let posts = 0;
  await page.route('**/api/study/capture-sessions/*/archive', async route => { posts++; await pending; await route.continue(); });
  page.once('dialog', d => d.accept());
  await archive.press('Enter');
  await expect(archive).toBeDisabled();
  const box = await archive.boundingBox();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { clickCount: 2 });
  expect(posts).toBe(1);
  release();
  await expect(detail.locator('#session-detail-status')).toContainText('归档成功');
  expect(posts).toBe(1);
  await capture(page, 'archive-recovered-once');
});

test('pending archive cannot overwrite or disable another session detail', async ({ page }) => {
  await reviewedCapture(page, 'archive-switch-first', 'confirm');
  await page.locator('#close-detail-btn').click();
  const { card: second, detail } = await reviewedCapture(page, 'archive-switch-second', 'reject');
  await page.locator('#close-detail-btn').click();
  const first = page.locator('#sessions .session-card').filter({ hasText: 'archive-switch-first.wav' });
  await first.getByRole('button', { name: '查看详情' }).click();
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/api/study/capture-sessions/*/archive', async route => { await pending; await route.continue(); });
  page.once('dialog', d => d.accept());
  await detail.locator('[data-control=capture-archive]').click();
  await expect(detail.locator('[data-control=capture-archive]')).toBeDisabled();
  await page.locator('#close-detail-btn').click();
  await second.getByRole('button', { name: '查看详情' }).click();
  await expect(detail).toContainText('archive-switch-second.wav');
  await expect(detail.locator('[data-control=capture-archive]')).toBeDisabled();
  release();
  await expect(first).toHaveCount(0);
  await expect(detail.locator('[data-control=capture-archive]')).toBeEnabled();
  await expect(detail).toContainText('archive-switch-second.wav');
  await expect(detail).toContainText('已拒绝');
  await expect(detail).not.toContainText('归档成功');
  await capture(page, 'archive-switch-preserves-current-detail');
});
