// B-class review spec for review.html (错题复盘).
//
// THIS IS NOT A PURE USER-PATH E2E (that is browser_review_userpath.spec.js).
// It is an INDEPENDENT spec that deliberately uses:
//   * page.request -> observe real response shapes, state-machine boundaries
//                     and "no silent truncation / no answer-key leak" contracts
//                     that a pure click-path cannot pin down;
//   * page.route   -> inject real HTTP status + detail codes a healthy server
//                     cannot produce on demand (500/404/409) and real latency
//                     to observe busy-state and the stale-response guard.
// Business data below the interface line is still created by driving the real
// pages (materials -> material-detail -> exercises -> practice -> session),
// never by a business API write. Assertions read only what the browser rendered
// plus the shapes the browser itself consumes.

const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

let RUN_ROOT = 'H:/studybuddy-test/runs/review-b';
const FIXTURES = 'H:/studybuddy-test/fixtures/review-b';
const ART = 'H:/studybuddy-test/artifacts/review-b';
const PORT = 8972;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = 'B 类复盘契约材料.txt';
const AI_HINT = 'Which statement is supported';
const EX_A = 'B类复盘题目A';
const EX_B = 'B类复盘题目B';
const EX_XSS = 'XSS题面<script>window.__xss=1</script>';
const XSS_HINT = 'XSS题面';
const SET_TITLE = 'B类复盘练习集';

// Stable pattern identity so page.unroute(pattern) works reliably.
const R = {
  list: /\/api\/study\/mistakes(\?|$)/,
  detail: /\/api\/study\/mistakes\/mistake_[^/?]+(\?|$)/,
  feedback: /\/api\/study\/mistakes\/[^/?]+\/feedback$/,
  redo: /\/api\/study\/mistakes\/[^/?]+\/redo$/,
  archive: /\/api\/study\/mistakes\/[^/?]+\/archive$/,
  weak: /\/api\/study\/weak-points(\?|$)/,
};

let server;
let materialId = '';

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

async function inject(page, pattern, method, status, code, delayMs = 0) {
  await page.route(pattern, async route => {
    const request = route.request();
    if (method && request.method() !== method) return route.fallback();
    if (delayMs) await new Promise(resolve => setTimeout(resolve, delayMs));
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify({ detail: code }) });
  });
}

async function assertNoSensitive(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/traceback|sqlite|insert into|delete from|api[_-]?key|password|token|private_backend_error|H:\/secret/i);
}

function buildFixture() {
  fs.mkdirSync(FIXTURES, { recursive: true });
  fs.writeFileSync(path.join(FIXTURES, TXT_NAME),
    'B 类复盘契约材料：本材料介绍欧姆定律。欧姆定律指出，通过导体的电流与导体两端的电压成正比，' +
    '与导体的电阻成反比。本材料只用于验证复盘接口的契约、失败降级与竞态守卫。\n', 'utf8');
}

// --- real user-path data builders (identical technique to the A-class spec) ---
async function importViaUi(page, filePath) {
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 15000 });
  await page.setInputFiles('#file-input', filePath);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 40000 });
}

async function openDetailViaUi(page, itemName) {
  const row = page.locator('#items li', { hasText: itemName });
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  materialId = decodeURIComponent(page.url().split('material=')[1]);
  await expect(page.locator('#title')).toContainText(itemName, { timeout: 15000 });
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

async function indexMaterialViaUi(page) {
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(materialId)}`);
  await expect(page.locator('#index')).toBeEnabled({ timeout: 15000 });
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立', { timeout: 40000 });
}

async function createAndSelectSetViaUi(page, title) {
  await page.goto(`${BASE}/app/exercises.html`);
  await expect.poll(async () => {
    if (await page.locator('#sets .set-item').count() > 0) return true;
    const text = (await page.locator('#set-status').innerText()).trim();
    return text !== '' && !text.includes('正在加载');
  }, { timeout: 15000 }).toBe(true);
  const existing = page.locator('#sets .set-item', { hasText: title });
  if (await existing.count() === 0) {
    await page.fill('#new-set-title', title);
    await page.click('#set-create-form button');
    await expect(page.locator('#exercise-status')).toHaveText('练习集已创建', { timeout: 15000 });
  }
  await existing.first().click();
  await expect(page.locator('#set-actions')).toBeVisible({ timeout: 10000 });
}

async function confirmExerciseViaUi(page, promptText) {
  await expect(page.locator('#exercises .exercise-item', { hasText: promptText })).toBeVisible({ timeout: 15000 });
  await page.locator('#exercises .exercise-item', { hasText: promptText }).click();
  await expect(page.locator('#exercise-detail')).toContainText('状态：', { timeout: 10000 });
  await page.getByRole('button', { name: '确认题目' }).last().click();
  await expect(page.locator('#exercise-status')).toHaveText('题目已确认', { timeout: 15000 });
  await expect(page.locator('#exercise-detail')).toContainText('可用', { timeout: 10000 });
}

async function createUserExerciseViaUi(page, prompt) {
  await createAndSelectSetViaUi(page, SET_TITLE);
  await page.locator('#new-exercise-type').selectOption('multiple_choice');
  await page.fill('#new-exercise-prompt', prompt);
  await page.fill('#new-exercise-answer', '0');
  await page.click('#exercise-create-form button');
  await expect(page.locator('#exercise-status')).toHaveText('题目已创建', { timeout: 15000 });
  await confirmExerciseViaUi(page, prompt);
}

async function generateAiExerciseViaUi(page) {
  await createAndSelectSetViaUi(page, SET_TITLE);
  await page.fill('#exercise-topic', '欧姆定律');
  await page.fill('#exercise-material-ids', materialId);
  await page.click('#exercise-generate-form button[type=submit]');
  await expect(page.locator('#exercise-status')).toHaveText('题目草稿已生成', { timeout: 40000 });
  await confirmExerciseViaUi(page, AI_HINT);
}

async function runWrongSessionViaUi(page, prompts) {
  await page.goto(`${BASE}/app/practice.html`);
  for (const prompt of prompts) {
    const item = page.locator('#recommendations .recommendation-item', { hasText: prompt });
    await expect(item).toBeVisible({ timeout: 20000 });
    await item.locator('input').check();
  }
  await page.getByRole('button', { name: '创建练习会话' }).click();
  await page.waitForURL(/practice-session\.html\?session_id=/, { timeout: 20000 });
  await page.getByRole('button', { name: '开始练习' }).click();
  await expect(page.locator('.practice-question')).toBeVisible({ timeout: 20000 });
  for (let i = 0; i < prompts.length; i++) {
    await expect(page.locator('.practice-question h3')).toHaveText(new RegExp(`第 ${i + 1} 题 / ${prompts.length}`), { timeout: 20000 });
    await page.locator('#answer').selectOption('1');
    await page.getByRole('button', { name: '提交答案' }).click();
    if (i < prompts.length - 1) {
      await expect(page.locator('.practice-question h3')).toHaveText(`第 ${i + 2} 题 / ${prompts.length}`, { timeout: 20000 });
    } else {
      await expect(page.locator('#session-status')).toContainText('答案已提交', { timeout: 20000 });
    }
  }
  await page.getByRole('button', { name: '完成会话' }).click();
  await page.waitForURL(/practice-result\.html\?session_id=/, { timeout: 20000 });
}

async function buildChainViaUi(page) {
  await importViaUi(page, path.join(FIXTURES, TXT_NAME));
  await openDetailViaUi(page, TXT_NAME);
  await indexMaterialViaUi(page);
  await generateAiExerciseViaUi(page);
  await createUserExerciseViaUi(page, EX_A);
  await runWrongSessionViaUi(page, [AI_HINT, EX_A]);
}

async function rowByTitle(page, title) {
  const row = page.locator('#review-list article', { hasText: title });
  await expect(row).toBeVisible({ timeout: 20000 });
  return row;
}

async function apiMistakes(page, query = 'limit=20&offset=0') {
  const response = await page.request.get(`${BASE}/api/study/mistakes?${query}`);
  expect(response.status()).toBe(200);
  return response.json();
}

test.describe.serial('review.html interface contract + fault injection (B-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/review-b-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    buildFixture();
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('B-RV-1 [分页契约] 遵循 limit/offset/has_more，加载更多只追加下一页且不重复', async ({ page }) => {
    await buildChainViaUi(page);
    const first = await apiMistakes(page);
    expect(first).toMatchObject({ limit: 20, offset: 0, has_more: false });
    expect(first.total).toBe(2);
    expect(first.items).toHaveLength(2);
    for (const item of first.items) {
      for (const key of ['id', 'exercise_id', 'status', 'question', 'occurrences', 'feedback_events']) {
        expect(item, `list item must expose ${key}`).toHaveProperty(key);
      }
      expect(item.id).toMatch(/^mistake_/);
      expect(typeof item.question).toBe('string');
      expect(item.question.length).toBeGreaterThan(0);
      expect(Array.isArray(item.occurrences)).toBe(true);
      expect(item.occurrences.length).toBeGreaterThan(0);
      expect(item.occurrences[0]).toHaveProperty('attempt_id');
      expect(Array.isArray(item.feedback_events)).toBe(true);
      for (const absent of ['answer_key', 'answer', 'correct_option', 'correct_answer', 'is_correct', 'selected_option']) {
        expect(item, `response must not leak ${absent}`).not.toHaveProperty(absent);
      }
    }

    const second = first.items[1];
    await page.route(R.list, async route => {
      const url = new URL(route.request().url());
      const offset = Number(url.searchParams.get('offset'));
      const limit = Number(url.searchParams.get('limit'));
      expect(limit).toBe(20);
      if (offset === 0) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          items: [first.items[0]], total: 2, limit, offset: 0, has_more: true,
        }) });
      }
      expect(offset).toBe(1);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        items: [second], total: 2, limit, offset: 1, has_more: false,
      }) });
    });
    const requests = [];
    page.on('request', request => {
      if (R.list.test(request.url())) requests.push(new URL(request.url()).search);
    });
    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list article')).toHaveCount(1, { timeout: 20000 });
    await expect(page.getByRole('button', { name: '加载更多' })).toBeVisible();
    await page.getByRole('button', { name: '加载更多' }).click();
    await expect(page.locator('#review-list article')).toHaveCount(2, { timeout: 20000 });
    await expect(page.getByRole('button', { name: '加载更多' })).toBeHidden();
    const renderedIds = await page.locator('#review-list article').evaluateAll(nodes => nodes.map(n => n.dataset.mistakeId));
    expect(new Set(renderedIds).size).toBe(2);
    expect(renderedIds.sort()).toEqual(first.items.map(i => i.id).sort());
    expect(requests).toEqual(['?limit=20&offset=0', '?limit=20&offset=1']);
    await assertNoSensitive(page);
  });

  test('B-RV-2 [竞态] 迟到旧详情响应被 generation 守卫丢弃，不留残影', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    const idAi = await (await rowByTitle(page, AI_HINT)).getAttribute('data-mistake-id');
    const idA = await (await rowByTitle(page, EX_A)).getAttribute('data-mistake-id');
    expect(idAi).not.toBe(idA);

    // AI 题的详情迟到 1200ms；EX_A 立即返回。
    await page.route(R.detail, async route => {
      if (new URL(route.request().url()).pathname.endsWith(idAi)) {
        await new Promise(resolve => setTimeout(resolve, 1200));
      }
      return route.fallback();
    });
    await page.goto(`${BASE}/app/review.html`);
    await rowByTitle(page, AI_HINT);
    await (await rowByTitle(page, AI_HINT)).getByRole('button', { name: '查看详情' }).click();
    await page.waitForTimeout(150);
    await (await rowByTitle(page, EX_A)).getByRole('button', { name: '查看详情' }).click();

    await expect(page.locator('#review-list .mistake-detail')).toHaveCount(1, { timeout: 20000 });
    await expect(page.locator('#review-list .mistake-detail')).toContainText(EX_A, { timeout: 20000 });

    // 迟到响应到达后不得追加第二个详情，也不得把旧题面复活到屏幕上。
    await page.waitForTimeout(1500);
    await expect(page.locator('#review-list .mistake-detail')).toHaveCount(1);
    await expect(page.locator('#review-list .mistake-detail')).toContainText(EX_A);
    await expect(page.locator('#review-list .mistake-detail')).not.toContainText(AI_HINT);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await assertNoSensitive(page);
  });

  test('B-RV-3 [故障注入+契约] XSS 以 textContent 渲染不执行，反馈契约拒绝非法负载', async ({ page }) => {
    await createUserExerciseViaUi(page, EX_XSS);
    await runWrongSessionViaUi(page, [XSS_HINT]);

    await page.goto(`${BASE}/app/review.html`);
    await expect(page.locator('#review-list article', { hasText: XSS_HINT })).toBeVisible({ timeout: 20000 });
    expect(await page.evaluate(() => window.__xss)).toBeUndefined();
    expect(await page.locator('#review-list img, #review-list script').count()).toBe(0);
    await expect(page.locator('#review-list')).toContainText('<script>window.__xss=1</script>');

    const row = await rowByTitle(page, XSS_HINT);
    await row.getByRole('button', { name: '查看详情' }).click();
    const detail = row.locator('.mistake-detail');
    await expect(detail).toContainText('题面：', { timeout: 20000 });
    await expect(detail).toContainText('<script>window.__xss=1</script>');
    expect(await detail.locator('img, script').count()).toBe(0);

    // 反馈里的注入同样只作文本渲染。
    const xssFeedback = 'XSS反馈<img src=x onerror="window.__xss=1">';
    await detail.getByLabel('复盘反馈').fill(xssFeedback);
    await detail.getByRole('button', { name: '保存反馈' }).click();
    await expect(page.locator('#review-status')).toContainText('复盘反馈已保存', { timeout: 20000 });
    const refreshed = await rowByTitle(page, XSS_HINT);
    await refreshed.getByRole('button', { name: '查看详情' }).click();
    await expect(refreshed.locator('.mistake-detail')).toContainText(xssFeedback, { timeout: 20000 });
    expect(await page.evaluate(() => window.__xss)).toBeUndefined();
    expect(await page.locator('#review-list img, #review-list script').count()).toBe(0);

    // 契约：非法 event_kind / 超长内容 / 不存在的错题都必须给出真实错误码。
    const xssMistakeId = await refreshed.getAttribute('data-mistake-id');
    const detailData = await (await page.request.get(`${BASE}/api/study/mistakes/${xssMistakeId}`)).json();
    const mistakeId = detailData.id;
    expect(mistakeId).toBe(xssMistakeId);
    const badKind = await page.request.post(`${BASE}/api/study/mistakes/${mistakeId}/feedback`, { data: { event_kind: 'bogus', content: 'x' } });
    expect(badKind.status()).toBe(400);
    expect((await badKind.json()).detail).toBe('mistake_feedback_invalid');
    const tooLong = await page.request.post(`${BASE}/api/study/mistakes/${mistakeId}/feedback`, { data: { event_kind: 'user_note', content: '字'.repeat(12001) } });
    expect(tooLong.status()).toBe(400);
    expect((await tooLong.json()).detail).toBe('mistake_feedback_invalid');
    const missing = await page.request.post(`${BASE}/api/study/mistakes/mistake_missing/feedback`, { data: { event_kind: 'user_note', content: 'x' } });
    expect(missing.status()).toBe(404);
    expect((await missing.json()).detail).toBe('mistake_not_found');
    for (const response of [badKind, tooLong, missing]) {
      expect(JSON.stringify(await response.json())).not.toMatch(/traceback|sqlite|insert into|[A-Z]:\\\\|api[_-]?key/i);
    }
    await assertNoSensitive(page);
  });

  test('B-RV-4 [busy 契约] 提交反馈期间按钮禁用，重复点击不发第二个请求', async ({ page }) => {
    await createUserExerciseViaUi(page, EX_B);
    await runWrongSessionViaUi(page, [EX_B]);

    let feedbackCalls = 0;
    await page.route(R.feedback, async route => {
      feedbackCalls += 1;
      await new Promise(resolve => setTimeout(resolve, 1200));
      return route.fallback();
    });
    await page.goto(`${BASE}/app/review.html`);
    const row = await rowByTitle(page, EX_B);
    await row.getByRole('button', { name: '查看详情' }).click();
    const detail = row.locator('.mistake-detail');
    await expect(detail).toContainText('题面：', { timeout: 20000 });
    await detail.getByLabel('复盘反馈').fill('只应保存一次');
    const saveButton = detail.getByRole('button', { name: '保存反馈' });
    await saveButton.click();
    await expect(saveButton).toBeDisabled({ timeout: 5000 });
    await saveButton.dispatchEvent('click');
    await expect(page.locator('#review-status')).toContainText('复盘反馈已保存', { timeout: 25000 });
    expect(feedbackCalls).toBe(1);
    await page.unroute(R.feedback);
    await assertNoSensitive(page);
  });

  test('B-RV-5 [故障注入] 标记/归档失败映射安全文案并保留重试能力', async ({ page }) => {
    await page.goto(`${BASE}/app/review.html`);
    let row = await rowByTitle(page, EX_A);
    await row.getByRole('button', { name: '查看详情' }).click();
    let detail = row.locator('.mistake-detail');
    await expect(detail).toContainText('题面：', { timeout: 20000 });

    // 业务错误码必须映射为用户文案，不能显示原始 detail、SQL 或 traceback。
    await inject(page, R.feedback, 'POST', 409, 'mistake_invalid_state');
    await detail.getByRole('button', { name: '标记已掌握' }).click();
    await expect(page.locator('#review-status')).toContainText('当前错题状态不允许此操作', { timeout: 20000 });
    await expect(page.locator('#review-status')).not.toContainText('mistake_invalid_state');
    await page.unroute(R.feedback);

    // 取消注入后重试同一操作，真实状态应更新。
    await detail.getByRole('button', { name: '标记已掌握' }).click();
    await expect(page.locator('#review-status')).toContainText('已标记为已掌握', { timeout: 20000 });
    await expect(page.locator('#review-list article', { hasText: EX_A })).toContainText('状态：已修正');

    await inject(page, R.archive, 'POST', 500, 'mistake_archive_failed');
    row = await rowByTitle(page, EX_A);
    await row.getByRole('button', { name: '归档' }).click();
    await expect(page.locator('#review-status')).toContainText('归档失败，请重试', { timeout: 20000 });
    await expect(page.locator('#review-status')).not.toContainText('mistake_archive_failed');
    await page.unroute(R.archive);

    // 归档失败后按钮仍可用，重试真实成功并从默认列表移除。
    await row.getByRole('button', { name: '归档' }).click();
    await expect(page.locator('#review-status')).toContainText('错题已归档', { timeout: 20000 });
    await expect(page.locator('#review-list article', { hasText: EX_A })).toHaveCount(0);
    await assertNoSensitive(page);
  });
});
