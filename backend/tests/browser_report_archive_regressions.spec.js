// All entities are created through the rendered UI. Injected failures are browser-pass only.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const BASE = process.env.STUDYBUDDY_BASE_URL;
const ART = path.join(process.env.STUDYBUDDY_TEST_ROOT || 'H:/studybuddy-test', 'regression-evidence');
test.setTimeout(60000);
test.beforeAll(async () => {
  if (!BASE) throw new Error('Use the isolated test-browser.ps1 runner');
  fs.mkdirSync(ART, { recursive: true });
  const health = [];
  for (const endpoint of ['liveness', 'health', 'readiness']) {
    const response = await fetch(BASE + '/api/' + endpoint);
    expect(response.status).toBe(200);
    health.push({ endpoint, status: response.status });
  }
  fs.writeFileSync(path.join(ART, 'health.json'), JSON.stringify(health, null, 2));
});
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => new URL(route.request().url()).origin === new URL(BASE).origin
    ? route.continue() : route.abort());
});
async function shot(page, label) {
  await page.screenshot({ path: path.join(ART, label + '.png'), fullPage: true,
    mask: [page.locator('textarea, #new-content, .note-content')] });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator('body').innerText()).not.toMatch(/Traceback|sqlite|stored_path|api[_-]?key|[A-Z]:[\\/]/i);
}
async function report(page, start, end) {
  await page.locator('#report-create-kind').selectOption('daily');
  await page.locator('#report-create-start').fill(start);
  await page.locator('#report-create-end').fill(end);
  await page.locator('#report-create-timezone').fill('UTC');
  await page.locator('#report-create-submit').click();
  await expect(page.locator('#report-create-status')).toHaveText('报告已生成');
  const item = page.locator('.report-item').filter({ hasText: start });
  await expect(item).toHaveCount(1);
  await item.click();
  await expect(page.locator('#report-actions')).toBeVisible();
  return item.getAttribute('data-report-id');
}
async function note(page, label, confirmed) {
  await page.goto(BASE + '/app/notes.html');
  await page.locator('#new-title').fill(label);
  await page.locator('#new-content').fill('Synthetic note for archive confirmation.');
  await page.locator('#create-form button[type=submit]').click();
  await expect(page.locator('#note-status')).toHaveText('用户笔记已创建');
  if (confirmed) {
    await page.locator('#note-confirm').click();
    await expect(page.locator('#note-status')).toHaveText('笔记已确认');
  }
  return new URL(page.url()).searchParams.get('note_id');
}
async function plan(page, label, active) {
  await page.goto(BASE + '/app/plans.html');
  await page.locator('#goal-title').fill(label + ' goal');
  await page.locator('#goal-form button[type=submit]').click();
  await expect(page.locator('#goals .goal-item').filter({ hasText: label + ' goal' })).toBeVisible();
  await page.locator('#plan-title').fill(label);
  await page.locator('#plan-goal').selectOption({ label: label + ' goal' });
  await page.locator('#plan-form button[type=submit]').click();
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
  await page.locator('#plan-item-title').fill(label + ' item');
  await page.getByRole('button', { name: '添加学习项', exact: true }).click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  if (active) {
    await page.getByRole('button', { name: '确认草稿', exact: true }).click();
    await expect(page.locator('#plan-status')).toHaveText('确认草稿成功');
    await page.getByRole('button', { name: '激活计划', exact: true }).click();
    await expect(page.locator('#plan-status')).toHaveText('激活计划成功');
  }
  return new URL(page.url()).searchParams.get('plan_id');
}
for (const width of [1280, 390]) {
  test.describe('historical failures ' + width, () => {
    test.use({ viewport: { width, height: width === 1280 ? 800 : 844 } });
    test('UI-REPORT-RETRY-001 keeps the exact selected report and return chain', async ({ page }) => {
      await page.goto(BASE + '/app/reports.html');
      const start = width === 1280 ? '2026-02-01' : '2026-03-01';
      const end = width === 1280 ? '2026-02-02' : '2026-03-02';
      const first = await report(page, start, end);
      const otherStart = width === 1280 ? '2026-02-03' : '2026-03-03';
      const otherEnd = width === 1280 ? '2026-02-04' : '2026-03-04';
      const second = await report(page, otherStart, otherEnd);
      expect(first).not.toBe(second);
      await page.locator('.report-item[data-report-id="' + first + '"]').click();
      const selectedUrl = page.url();
      await expect(page.locator('#report-detail')).toContainText(start);
      await shot(page, 'report-' + width + '-before');
      let faults = 2;
      await page.route('**/api/study/reports?*', async route => {
        if (faults-- > 0) return route.fulfill({ status: 503, contentType: 'application/json',
          body: JSON.stringify({ detail: 'report_list_unavailable' }) });
        return route.continue();
      });
      await page.reload();
      const retry = page.locator('#retry-reports');
      await expect(retry).toBeVisible();
      await retry.click();
      await expect(retry).toBeVisible();
      await expect(page.locator('#report-status')).not.toContainText('正在加载');
      await shot(page, 'report-' + width + '-injected-failure');
      await retry.focus();
      await page.keyboard.press('Enter');
      await expect(page.locator('#report-detail')).toContainText(start);
      await expect(page.locator('#report-detail')).not.toContainText(otherStart);
      await expect(page.locator('.report-item.selected')).toHaveAttribute('data-report-id', first);
      await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报');
      await expect(page.locator('#report-actions')).toBeVisible();
      await expect(retry).toBeHidden();
      await expect(page).toHaveURL(selectedUrl);
      await page.locator('#preview-report').click();
      await expect(page.locator('#report-detail')).toContainText(start);
      for (const format of ['json', 'markdown']) {
        const downloaded = page.waitForEvent('download');
        await page.locator('#export-' + format).click();
        const file = await downloaded;
        expect(file.suggestedFilename()).toBe('studybuddy-report.' + (format === 'json' ? 'json' : 'md'));
        const target = path.join(ART, 'report-' + width + '-' + file.suggestedFilename());
        await file.saveAs(target);
        expect(fs.statSync(target).size).toBeGreaterThan(0);
        expect(await file.failure()).toBeNull();
      }
      await page.getByRole('link', { name: '返回课堂', exact: true }).click();
      await expect(page).toHaveURL(BASE + '/app/classroom.html');
      await page.goBack();
      await expect(page).toHaveURL(selectedUrl);
      await expect(page.locator('#report-detail')).toContainText(start);
      await page.reload();
      await expect(page.locator('.report-item.selected')).toHaveAttribute('data-report-id', first);
      await expect(page.locator('#report-detail')).toContainText(start);
      await shot(page, 'report-' + width + '-recovered');
    });
    for (const kind of ['note', 'plan']) {
      test((kind === 'note' ? 'UI-ARCHIVE-CONFIRM-887' : 'UI-ARCHIVE-CONFIRM-908') +
        ' cancel, failure, single submit and persisted archive', async ({ page }) => {
        const label = 'Synthetic ' + kind + ' archive ' + width;
        const id = await (kind === 'note' ? note(page, label, width === 390) : plan(page, label, width === 390));
        expect(id).toBeTruthy();
        const originalUrl = page.url();
        let planDetailHref;
        if (kind === 'plan') {
          const link = page.locator('#plans .plan-item[data-plan-id="' + id + '"]').getByRole('link', { name: '打开详情' });
          planDetailHref = await link.getAttribute('href');
          await link.click();
          await expect(page.locator('#plan-detail h2')).toContainText(label);
          await page.goBack();
          await expect(page.locator('#plan-detail')).toBeVisible();
        }
        const detail = page.locator(kind === 'note' ? '#note-detail' : '#plan-detail');
        const archive = kind === 'note' ? page.locator('#note-archive') : detail.getByRole('button', { name: '归档计划', exact: true });
        const status = page.locator(kind === 'note' ? '#note-status' : '#plan-status');
        const endpoint = '/api/study/' + (kind === 'note' ? 'notes' : 'plans') + '/' + id + '/archive';
        const decisions = [false, true, true], dialogs = [];
        page.on('dialog', async dialog => {
          dialogs.push({ type: dialog.type(), message: dialog.message() });
          if (decisions.shift()) await dialog.accept(); else await dialog.dismiss();
        });
        let writes = 0;
        page.on('request', request => {
          if (new URL(request.url()).pathname === endpoint && request.method() === 'POST') writes++;
        });
        await shot(page, kind + '-' + width + '-before');
        await archive.click();
        await expect.poll(() => dialogs.length, { timeout: 2000 }).toBe(1);
        expect(dialogs[0].type).toBe('confirm');
        expect(dialogs[0].message).toContain('归档');
        expect(writes).toBe(0);
        await expect(archive).toBeEnabled();
        await expect(page).toHaveURL(originalUrl);
        await page.reload();
        await expect(archive).toBeEnabled();
        await expect(detail).not.toContainText('状态：已归档');
        let failed = false, release;
        const gate = new Promise(resolve => { release = resolve; });
        await page.route('**' + endpoint, async route => {
          if (!failed) {
            failed = true;
            return route.fulfill({ status: 503, contentType: 'application/json',
              body: JSON.stringify({ detail: 'archive_temporarily_unavailable' }) });
          }
          await gate;
          return route.continue();
        });
        await archive.focus();
        await page.keyboard.press('Space');
        await expect(status).toContainText('可重试');
        expect(writes).toBe(1);
        await expect(archive).toBeEnabled();
        await expect(detail).not.toContainText('状态：已归档');
        await shot(page, kind + '-' + width + '-injected-failure');
        try {
          await archive.click();
          await expect.poll(() => writes).toBe(2);
          await expect(archive).toBeDisabled();
          const bounds = await archive.boundingBox();
          await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2, { clickCount: 2 });
          expect(writes).toBe(2);
          expect(dialogs).toHaveLength(3);
        } finally { release(); }
        await expect(status).toHaveText(kind === 'note' ? '笔记已归档' : '计划已归档');
        await expect(archive).toHaveCount(0);
        if (kind === 'note') {
          await expect(page.locator('#notes .note-item').filter({ hasText: label })).toHaveCount(0);
          await page.locator('#show-archived').check();
          await expect(page.locator('#notes .note-item').filter({ hasText: label })).toContainText('已归档');
          await page.reload();
          await expect(detail.locator('textarea')).toHaveValue('Synthetic note for archive confirmation.');
          await expect(detail.locator('textarea')).toBeDisabled();
          await page.getByRole('button', { name: '打开笔记详情页：' + label, exact: true }).click();
          await expect(page).toHaveURL(BASE + '/app/note-detail.html?note_id=' + id);
        } else {
          await expect(page.locator('#plans .plan-item[data-plan-id="' + id + '"]')).toHaveCount(0);
          await expect(detail).toBeHidden();
          await page.reload();
          await expect(page.locator('#plan-status')).not.toContainText('正在加载');
          await expect(page.locator('#plans .plan-item[data-plan-id="' + id + '"]')).toHaveCount(0);
          await page.goto(BASE + planDetailHref);
          await expect(page).toHaveURL(BASE + '/app/plan-detail.html?plan_id=' + id);
        }
        await expect(page.locator(kind === 'note' ? '#note-detail' : '#plan-detail')).toContainText('已归档');
        await shot(page, kind + '-' + width + '-persisted-detail');
        await page.goBack();
        if (kind === 'note') await expect(detail).toContainText('状态：已归档');
        else await expect(detail).toBeHidden();
        await expect(archive).toHaveCount(0);
        await shot(page, kind + '-' + width + '-archived');
      });
    }
  });
}
