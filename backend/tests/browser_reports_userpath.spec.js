const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// A-class pure user-path E2E for reports.html.
// Rule: all user-visible behavior is driven through the page UI only. The
// page itself offers no report-creation control (reports are snapshots
// produced by the backend domain), so the two fixture reports in RP-2+ are
// seeded through the report API once per run — that setup-only request is a
// B-class element and is labeled as such; no assertion below reads API
// state directly. Fault injections (RP-7/8/9) use page.route and are also
// B-class elements per the review protocol.
// Chain: empty state -> seeded list with user-readable kind labels and
//        selection highlight -> redacted detail -> preview refresh ->
//        JSON/Markdown exports -> URL deep link + reload persistence ->
//        list failure retry -> detail failure retry -> rapid-switch race
//        guard -> narrow viewport + keyboard + cross-page nav-toggle.
let RUN_ROOT = 'H:/studybuddy-test/runs/reports-userpath';
const ART = 'H:/studybuddy-test/artifacts/reports-userpath';
const PORT = 8967;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 20000 }).toBe(true);
}

function stopServer() {
  return new Promise(resolve => {
    if (!server || server.killed) { server = null; return resolve(); }
    let settled = false;
    const finish = () => { if (!settled) { settled = true; server = null; resolve(); } };
    server.once('exit', finish);
    server.kill();
    setTimeout(finish, 5000);
  });
}

// B-class setup element: creates one deterministic report snapshot. The
// tests never read this response directly — they obtain ids from the
// rendered list UI.
async function seedReport(request, kind, start, end) {
  const response = await request.post(`${BASE}/api/study/reports`, {
    data: { report_kind: kind, timezone: 'UTC', period_start: start, period_end: end },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()).id;
}

async function assertNoSensitiveVisibleText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|cpk-|safe_payload_json|answer_key|[A-Z]:\\\\/i);
}

async function assertFocusStyle(page, selector) {
  const style = await page.evaluate(sel => {
    const node = document.querySelector(sel);
    node.focus();
    const computed = getComputedStyle(node);
    return { outline: computed.outlineStyle, shadow: computed.boxShadow };
  }, selector);
  expect(style.outline === 'none' || style.shadow !== 'none').toBeTruthy();
}

test.describe.serial('reports.html pure user path (A-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/reports-userpath-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('A-E2E-RP-1 空数据根：报告空态且无重试按钮残留', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    await expect(page.locator('#report-status')).toHaveText('暂无报告', { timeout: 10000 });
    await expect(page.locator('#report-list .report-item')).toHaveCount(0);
    await expect(page.locator('#retry-reports')).toBeHidden();
    await expect(page.locator('#report-detail-title')).toHaveText('选择报告');
    await expect(page.locator('#report-actions')).toBeHidden();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-2 列表渲染用户可读报告类型标签与选中高亮', async ({ page }) => {
    await seedReport(page.request, 'daily', '2026-01-15', '2026-01-16');
    await page.goto(`${BASE}/app/reports.html`);
    const item = page.locator('#report-list .report-item').first();
    await expect(item).toContainText('日报', { timeout: 10000 });
    await expect(item).toContainText('2026-01-15');
    // Raw enum values must not be the only visible wording.
    await expect(page.locator('#report-list')).not.toContainText('· daily');
    await item.click();
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报');
    await expect(item).toHaveClass(/selected/);
    await expect(page).toHaveURL(/report_id=/);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-3 详情展示脱敏统计且绝不出现原始载荷字段', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    const item = page.locator('#report-list .report-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    await item.click();
    const detail = page.locator('#report-detail');
    await expect(detail).toContainText('范围：2026-01-15 至 2026-01-16');
    await expect(detail).toContainText('时区：UTC');
    await expect(detail).toContainText('有效来源：0');
    await expect(detail).toContainText('交付：未发送');
    await expect(page.locator('#report-actions')).toBeVisible();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-4 刷新报告预览真实走 preview 端点并保持详情', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    await page.locator('#report-list .report-item').first().click();
    await expect(page.locator('#report-detail')).toContainText('范围：', { timeout: 10000 });
    await page.locator('#preview-report').click();
    await expect(page.locator('#preview-report')).toBeDisabled();
    await expect(page.locator('#report-detail')).toContainText('范围：2026-01-15 至 2026-01-16');
    await expect(page.locator('#preview-report')).toBeEnabled();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-5 导出 JSON 与 Markdown 真实下载文件名', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    await page.locator('#report-list .report-item').first().click();
    await expect(page.locator('#report-actions')).toBeVisible({ timeout: 10000 });
    const jsonDownload = page.waitForEvent('download');
    await page.locator('#export-json').click();
    expect((await jsonDownload).suggestedFilename()).toBe('studybuddy-report.json');
    const mdDownload = page.waitForEvent('download');
    await page.locator('#export-markdown').click();
    expect((await mdDownload).suggestedFilename()).toBe('studybuddy-report.md');
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-6 URL report_id 直达与刷新后持久化', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    const item = page.locator('#report-list .report-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    await item.click();
    const url = page.url();
    await page.reload();
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报', { timeout: 10000 });
    await expect(page.locator('#report-list .report-item').first()).toHaveClass(/selected/);
    expect(page.url()).toBe(url);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-7 列表失败注入：安全文案 + #retry-reports 真实恢复', async ({ page }) => {
    let failing = true;
    await page.route('**/api/study/reports', route => failing
      ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"private_backend_error","path":"H:/secret","traceback":"hidden"}' })
      : route.continue());
    await page.goto(`${BASE}/app/reports.html`);
    await expect(page.locator('#report-status')).toContainText('请求失败，请重试');
    await expect(page.locator('#retry-reports')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/private_backend_error|H:\/secret|traceback/i);
    failing = false;
    await page.unroute('**/api/study/reports');
    await page.locator('#retry-reports').click();
    await expect(page.locator('#report-list .report-item').first()).toContainText('日报', { timeout: 10000 });
    await expect(page.locator('#retry-reports')).toBeHidden();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-8 详情失败：独立重试控件真实恢复', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    const item = page.locator('#report-list .report-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    const reportId = await item.getAttribute('data-report-id');
    expect(reportId).toBeTruthy();
    await page.route(`**/api/study/reports/${reportId}`, route => route.fulfill({
      status: 500, contentType: 'application/json', body: '{"detail":"private_backend_error","path":"H:/secret","traceback":"hidden"}',
    }));
    await item.click();
    await expect(page.locator('#report-detail-title')).toHaveText('报告不可用');
    await expect(page.locator('#retry-detail')).toBeVisible();
    await page.unroute(`**/api/study/reports/${reportId}`);
    await page.locator('#retry-detail').click();
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报', { timeout: 10000 });
    await expect(page.locator('#retry-detail')).toBeHidden();
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-9 快速切换报告：迟到旧响应不得覆盖新选择', async ({ page }) => {
    await seedReport(page.request, 'weekly', '2026-02-01', '2026-02-08');
    await page.goto(`${BASE}/app/reports.html`);
    const items = page.locator('#report-list .report-item');
    await expect(items).toHaveCount(2, { timeout: 10000 });
    // Newest first: weekly (2026-02) then daily (2026-01).
    const weekly = items.nth(0);
    const daily = items.nth(1);
    const weeklyId = await weekly.getAttribute('data-report-id');
    await page.route(`**/api/study/reports/${weeklyId}`, async route => {
      await new Promise(resolve => setTimeout(resolve, 400));
      await route.continue();
    });
    // Click the slow weekly report, then immediately the fast daily one.
    await weekly.click();
    await daily.click();
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报', { timeout: 10000 });
    await page.waitForTimeout(700);
    // The delayed weekly response must be discarded; the daily detail stays.
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 日报');
    await expect(page.locator('#report-detail')).toContainText('范围：2026-01-15 至 2026-01-16');
    await expect(page.locator('#report-list .report-item').nth(1)).toHaveClass(/selected/);
    await page.unroute(`**/api/study/reports/${weeklyId}`);
    await assertNoSensitiveVisibleText(page);
  });

  test('A-E2E-RP-10 窄屏响应式、键盘焦点与跨页导航（nav-toggle 需重新展开）', async ({ page }) => {
    // Desktop keyboard path: focus the list item and activate it with Enter.
    await page.goto(`${BASE}/app/reports.html`);
    const item = page.locator('#report-list .report-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    await assertFocusStyle(page, '#report-list .report-item');
    await item.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#report-detail-title')).toHaveText('报告 · 周报', { timeout: 10000 });

    // Narrow viewport without horizontal overflow + screenshot artifact.
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: `${ART}/reports-390.png`, fullPage: true });

    // Cross-page: from today, the mobile nav must be re-expanded before the
    // reports link is reachable, and it collapses again after navigation.
    await page.goto(`${BASE}/app/today.html`);
    const toggle = page.locator('.nav-toggle');
    await expect(toggle).toBeVisible();
    await expect(page.locator('#primary-navigation')).toBeHidden();
    await toggle.click();
    await page.locator('#primary-navigation').getByRole('link', { name: '报告' }).click();
    await expect(page).toHaveURL(/reports\.html/);
    await expect(page.locator('#primary-navigation')).toBeHidden();
    await toggle.click();
    await expect(page.locator('#primary-navigation')).toBeVisible();
    await toggle.click();
    await expect(page.locator('#report-list .report-item').first()).toContainText('周报', { timeout: 10000 });

    await page.setViewportSize({ width: 1280, height: 800 });
    await expect(page.locator('#report-list .report-item')).toHaveCount(2);
    await assertNoSensitiveVisibleText(page);
  });
});
