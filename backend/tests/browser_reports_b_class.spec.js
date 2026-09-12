const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// B-class independent review for reports.html. These tests deliberately use
// route mocks to exercise pagination and stale-response boundaries that do
// not need persisted business fixtures. User interaction remains page UI.
let ROOT = 'H:/studybuddy-test/runs/reports-b-class';
const PORT = 8968;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT };
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

function report(id, title, start) {
  return { id, title, report_kind: 'daily', period_start: start, period_end: '2026-01-02' };
}

function detail(id, start) {
  return {
    id, report_kind: 'daily', safe_payload: {
      period: { report_kind: 'daily', period_start: start, period_end: '2026-01-02', timezone: 'UTC', generated_at: '2026-01-02T00:00:00Z' },
      plan: { active_goal_count: 0, active_plan_count: 0, planned_item_count: 0, completed_item_count: 0, started_item_count: 0, skipped_item_count: 0, planned_minutes_total: 0 },
      rhythm: { allocated_day_count: 0, allocated_minutes_total: 0, unallocated_eligible_item_count: 0, overload_day_count: 0 },
      practice: { practice_session_count: 0, cram_session_count: 0, attempt_count: 0, deterministic_correct_count: 0, deterministic_incorrect_count: 0, pending_review_count: 0, completed_session_count: 0 },
      feedback: { open_mistake_count: 0, in_review_count: 0, fixed_count: 0, reopened_count: 0, archived_count: 0, weak_point_count: 0 },
      source_quality: { valid_source_count: 0, stale_count: 0, source_deleted_count: 0, source_unavailable_count: 0, uncertain_transcript_segment_count: 0 },
      quality_flags: { has_pending_review: false, has_source_warnings: false, has_uncertain_capture: false },
      exam_alert: { days_remaining_bucket: null, is_imminent: false },
    },
  };
}

test.describe.serial('reports.html B-class independent review', () => {
  test.beforeAll(async () => {
    ROOT = `H:/studybuddy-test/runs/reports-b-class-${Date.now()}`;
    fs.mkdirSync(ROOT, { recursive: true });
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('B-RP-1 分页请求遵循 limit/offset/has_more，加载更多只追加下一页', async ({ page }) => {
    const firstPage = Array.from({ length: 100 }, (_, index) => report(`r-${index}`, `快照 ${index}`, '2026-01-01'));
    await page.route('**/api/study/reports?*', route => {
      const offset = new URL(route.request().url()).searchParams.get('offset');
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(
        offset === '100' ? { items: [report('r-100', '最后一页', '2026-01-03')], has_more: false } : { items: firstPage, has_more: true },
      ) });
    });
    await page.goto(`${BASE}/app/reports.html`);
    await expect(page.locator('#report-list .report-item')).toHaveCount(100);
    await expect(page.locator('#load-more-reports')).toBeVisible();
    await page.getByRole('button', { name: '加载更多报告' }).click();
    await expect(page.locator('#report-list .report-item')).toHaveCount(101);
    await expect(page.locator('#report-list .report-item[data-report-id="r-100"]')).toHaveText('最后一页');
    await expect(page.locator('#load-more-reports')).toBeHidden();
  });

  test('B-RP-2 迟到预览响应不会恢复旧提示或覆盖新选择', async ({ page }) => {
    let releasePreview;
    const previewReady = new Promise(resolve => { releasePreview = resolve; });
    await page.route('**/api/study/reports?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      items: [report('r-1', '第一份', '2026-01-01'), report('r-2', '第二份', '2026-02-01')], has_more: false,
    }) }));
    await page.route('**/api/study/reports/r-1/preview', async route => { await previewReady; return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail('r-1', '2026-01-01')) }); });
    await page.route('**/api/study/reports/r-1', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail('r-1', '2026-01-01')) }));
    await page.route('**/api/study/reports/r-2', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail('r-2', '2026-02-01')) }));
    await page.goto(`${BASE}/app/reports.html`);
    await page.locator('#report-list .report-item[data-report-id="r-1"]').click();
    await expect(page.locator('#report-detail')).toContainText('范围：2026-01-01 至 2026-01-02');
    await page.getByRole('button', { name: '刷新报告预览' }).click();
    await page.locator('#report-list .report-item[data-report-id="r-2"]').click();
    await expect(page.locator('#report-detail')).toContainText('范围：2026-02-01 至 2026-01-02');
    releasePreview();
    await page.waitForTimeout(100);
    await expect(page.locator('#report-detail')).toContainText('范围：2026-02-01 至 2026-01-02');
    await expect(page.locator('#report-status')).toBeHidden();
  });

  test('B-RP-3 迟到导出响应不触发已切换报告的下载', async ({ page }) => {
    let releaseExport;
    let downloads = 0;
    const exportReady = new Promise(resolve => { releaseExport = resolve; });
    page.on('download', () => { downloads += 1; });
    await page.route('**/api/study/reports?*', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      items: [report('r-1', '第一份', '2026-01-01'), report('r-2', '第二份', '2026-02-01')], has_more: false,
    }) }));
    await page.route('**/api/study/reports/r-1/export?format=json', async route => { await exportReady; return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }); });
    await page.route('**/api/study/reports/r-1', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail('r-1', '2026-01-01')) }));
    await page.route('**/api/study/reports/r-2', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(detail('r-2', '2026-02-01')) }));
    await page.goto(`${BASE}/app/reports.html`);
    await page.locator('#report-list .report-item[data-report-id="r-1"]').click();
    await expect(page.locator('#report-actions')).toBeVisible();
    await page.getByRole('button', { name: '导出 JSON' }).click();
    await page.locator('#report-list .report-item[data-report-id="r-2"]').click();
    await expect(page.locator('#report-detail')).toContainText('范围：2026-02-01 至 2026-01-02');
    releaseExport();
    await page.waitForTimeout(100);
    expect(downloads).toBe(0);
    await expect(page.locator('#report-status')).toBeHidden();
  });
});
