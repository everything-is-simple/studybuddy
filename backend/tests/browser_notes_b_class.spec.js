const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// B-class review spec for notes.html + note-detail.html.
//
// THIS IS NOT A PURE USER-PATH E2E (that is the A-class spec
// browser_notes_userpath.spec.js). This spec deliberately uses:
//   * page.request -> observe real response shapes and drive state-machine
//                     boundaries that the UI correctly refuses to expose;
//   * page.route   -> inject real HTTP status + detail codes that a healthy
//                     server cannot produce on demand.
// Business data below the interface line is still created through the page UI
// unless the boundary itself is the subject of the contract check.
// ---------------------------------------------------------------------------
let RUN_ROOT = 'H:/studybuddy-test/runs/notes-b';
const FIXTURES = 'H:/studybuddy-test/fixtures/notes-b';
const ART = 'H:/studybuddy-test/artifacts/notes-b';
const PORT = 8953;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const TXT_NAME = 'B 类契约材料.txt';

// Stable pattern identity is required by page.unroute(pattern).
const R = {
  list: /\/api\/study\/notes(\?|$)/,
  detail: /\/api\/study\/notes\/note_[^/?]+(\?|$)/,
  generate: /\/api\/study\/notes\/generate$/,
  exportMd: /\/api\/study\/notes\/note_[^/?]+\/export/,
  confirm: /\/api\/study\/notes\/note_[^/?]+\/confirm$/,
  archive: /\/api\/study\/notes\/note_[^/?]+\/archive$/,
  reject: /\/api\/study\/notes\/note_[^/?]+\/reject$/,
};

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

// Inject a real HTTP failure with a real backend detail code.
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
  expect(visible).not.toMatch(/traceback|sqlite|insert into|select .* from|api[_-]?key|password|cpk-|[A-Z]:\\\\/i);
}

async function notesLoaded(page) {
  await expect(page.locator('#note-status')).not.toContainText('正在加载', { timeout: 10000 });
}

async function createNote(page, title, content) {
  await page.fill('#new-title', title);
  await page.fill('#new-content', content);
  await page.click('#create-form button[type=submit]');
  await expect(page.locator('#note-status')).toContainText('用户笔记已创建', { timeout: 10000 });
}

async function selectNote(page, title) {
  await page.locator('#notes .note-item', { hasText: title }).click({ position: { x: 5, y: 5 } });
  await expect(page.locator('#detail-title')).toContainText(title, { timeout: 10000 });
}

function currentNoteId(page) {
  return new URL(page.url()).searchParams.get('note_id');
}

test.describe.serial('notes/note-detail interface contract + fault injection (B-class)', () => {
  test.beforeAll(async () => {
    RUN_ROOT = `H:/studybuddy-test/runs/notes-b-${Date.now()}`;
    fs.mkdirSync(ART, { recursive: true });
    fs.mkdirSync(FIXTURES, { recursive: true });
    fs.writeFileSync(path.join(FIXTURES, TXT_NAME),
      'B 类契约材料：光合作用是绿色植物利用光能，把二氧化碳和水转化为有机物并释放氧气的过程。' +
      '本材料只用于验证生成接口的契约与失败降级，不用于验证索引质量。\n', 'utf8');
    server = startServer();
    await ready();
  });
  test.afterAll(() => stopServer());

  test('B-ND-1 [接口契约] 创建与编辑的请求/响应形状与页面消费字段一致', async ({ page }) => {
    const creates = [], patches = [];
    await page.route(R.list, async route => {
      if (route.request().method() !== 'POST') return route.fallback();
      creates.push({ body: JSON.parse(route.request().postData()), headers: route.request().headers() });
      return route.continue();
    });
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await createNote(page, '契约笔记', '契约正文');
    expect(creates).toHaveLength(1);
    expect(creates[0].body).toEqual({ title: '契约笔记', blocks: [{ block_kind: 'text', content: '契约正文' }] });
    expect(creates[0].headers['content-type']).toContain('application/json');
    expect(creates[0].headers['idempotency-key']).toBeTruthy();
    await page.unroute(R.list);
    // 页面渲染的状态/类型必须来自真实响应键。
    await expect(page.locator('#note-detail')).toContainText('状态：草稿 · 用户笔记');

    await page.route(R.detail, async route => {
      if (route.request().method() !== 'PATCH') return route.fallback();
      patches.push(JSON.parse(route.request().postData()));
      return route.continue();
    });
    await page.locator('#note-detail input[aria-label="笔记标题"]').fill('契约笔记（改）');
    await page.locator('#note-detail textarea').first().fill('契约正文（改）');
    await page.click('#note-detail form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('笔记编辑已保存', { timeout: 10000 });
    expect(patches).toEqual([{ title: '契约笔记（改）', blocks: [{ block_kind: 'text', content: '契约正文（改）' }] }]);
    await page.unroute(R.detail);

    const noteId = currentNoteId(page);
    expect(noteId).toMatch(/^note_/);
    const response = await page.request.get(`${BASE}/api/study/notes/${noteId}`);
    expect(response.status()).toBe(200);
    const note = await response.json();
    for (const key of ['id', 'title', 'status', 'provenance', 'user_edited', 'blocks', 'modules',
      'source_warning_count', 'archived_module_warning_count']) {
      expect(note, `response must expose ${key}`).toHaveProperty(key);
    }
    expect(note.title).toBe('契约笔记（改）');
    expect(note.status).toBe('draft');
    expect(note.provenance).toBe('user_created');
    expect(note.user_edited).toBe(1);
    expect(note.blocks[0]).toHaveProperty('content');
    expect(note.blocks[0]).toHaveProperty('sources');
    // 页面不得依赖后端不存在的字段（A 轮 3 个缺陷的共同根因）。
    for (const absent of ['content', 'citation_keys', 'source_citation_status', 'material_name', 'note_type']) {
      expect(note, `response must not invent ${absent}`).not.toHaveProperty(absent);
    }
    await assertNoSensitive(page);
  });

  test('B-ND-2 [接口契约] 归档默认隐藏、include_archived 可取，且 UI 必须给得出查看入口', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await createNote(page, '待归档笔记', '待归档正文');
    await page.click('#note-archive');
    await expect(page.locator('#note-status')).toContainText('笔记已归档', { timeout: 10000 });
    await expect(page.locator('#notes .note-item', { hasText: '待归档笔记' })).toHaveCount(0);

    const visible = await (await page.request.get(`${BASE}/api/study/notes`)).json();
    expect(Array.isArray(visible)).toBe(true);
    expect(visible.some(item => item.title === '待归档笔记')).toBe(false);
    const all = await (await page.request.get(`${BASE}/api/study/notes?include_archived=true`)).json();
    const archived = all.find(item => item.title === '待归档笔记');
    expect(archived, 'include_archived=true must return the archived note').toBeTruthy();
    expect(archived.status).toBe('archived');

    // 接口支持不等于用户可达：页面必须提供查看已归档的控件。
    const toggle = page.locator('#show-archived');
    await expect(toggle, 'UI must expose an archived-notes control').toHaveCount(1, { timeout: 5000 });
    await toggle.check();
    await expect(page.locator('#notes .note-item', { hasText: '待归档笔记' })).toHaveCount(1, { timeout: 10000 });
    await expect(page.locator('#notes .note-item', { hasText: '待归档笔记' })).toContainText('已归档');
    await toggle.uncheck();
    await expect(page.locator('#notes .note-item', { hasText: '待归档笔记' })).toHaveCount(0, { timeout: 10000 });
    await assertNoSensitive(page);
  });

  test('B-ND-3 [故障注入] 列表与创建失败的用户可见降级', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    // 500 读取失败
    await inject(page, R.list, 'GET', 500, 'study_note_read_failed');
    await page.click('#refresh');
    await expect(page.locator('#note-status')).toContainText('读取笔记失败，请重试', { timeout: 10000 });
    await assertNoSensitive(page);
    await page.unroute(R.list);
    await page.click('#refresh');
    await notesLoaded(page);
    const baseline = await page.locator('#notes .note-item').count();
    // 409 空内容
    await inject(page, R.list, 'POST', 409, 'study_note_empty');
    await page.fill('#new-title', '空内容笔记');
    await page.fill('#new-content', 'x');
    await page.click('#create-form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('笔记内容不能为空', { timeout: 10000 });
    await page.unroute(R.list);
    // 400 无效负载
    await inject(page, R.list, 'POST', 400, 'study_note_invalid_payload');
    await page.click('#create-form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('笔记内容无效，请检查后重试', { timeout: 10000 });
    await page.unroute(R.list);
    await page.click('#refresh');
    await notesLoaded(page);
    expect(await page.locator('#notes .note-item').count()).toBe(baseline);
    // 真实恢复：表单在失败后仍然可用
    await createNote(page, '恢复后笔记', '恢复后正文');
    await assertNoSensitive(page);
  });

  test('B-ND-4 [故障注入] 编辑/确认/归档失败的用户可见降级且失败不落库', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await selectNote(page, '契约笔记（改）');
    // PATCH 409 已确认不可编辑
    await inject(page, R.detail, 'PATCH', 409, 'study_note_edit_not_allowed');
    await page.locator('#note-detail input[aria-label="笔记标题"]').fill('不应保存的标题');
    await page.click('#note-detail form button[type=submit]');
    await expect(page.locator('#note-status')).toContainText('该笔记已确认、拒绝或归档，不能编辑', { timeout: 10000 });
    await assertNoSensitive(page);
    await page.unroute(R.detail);
    // 失败不落库：刷新后仍是原值
    await page.click('#refresh');
    await notesLoaded(page);
    await selectNote(page, '契约笔记（改）');
    await expect(page.locator('#note-detail input[aria-label="笔记标题"]')).toHaveValue('契约笔记（改）');
    // confirm 409 引用不可用
    await inject(page, R.confirm, 'POST', 409, 'study_note_confirm_source_invalid');
    await page.click('#note-confirm');
    await expect(page.locator('#note-status')).toContainText('AI 草稿引用已不可用，不能确认', { timeout: 10000 });
    await page.unroute(R.confirm);
    // confirm 409 状态已变化
    await inject(page, R.confirm, 'POST', 409, 'study_note_invalid_state');
    await page.click('#note-confirm');
    await expect(page.locator('#note-status')).toContainText('笔记状态已变化，请刷新后重试', { timeout: 10000 });
    await page.unroute(R.confirm);
    // archive 409 状态已变化
    await inject(page, R.archive, 'POST', 409, 'study_note_invalid_state');
    await page.click('#note-archive');
    await expect(page.locator('#note-status')).toContainText('笔记状态已变化，请刷新后重试', { timeout: 10000 });
    await page.unroute(R.archive);
    await assertNoSensitive(page);
  });

  test('B-ND-5 [故障注入+契约] 生成链路失败降级与真实未就绪契约', async ({ page }) => {
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).not.toContainText('加载中', { timeout: 5000 });
    await page.setInputFiles('#file-input', path.join(FIXTURES, TXT_NAME));
    await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await page.click('#reload-materials');
    const option = page.locator('#material-select option', { hasText: TXT_NAME });
    await expect(option).toHaveCount(1, { timeout: 10000 });
    const materialId = await option.getAttribute('value');
    await page.fill('#topic', '光合作用');
    await page.selectOption('#material-select', materialId);

    await inject(page, R.generate, 'POST', 503, 'study_note_provider_not_configured');
    await page.click('#generate');
    await expect(page.locator('#note-status')).toContainText('AI 笔记服务尚未配置', { timeout: 10000 });
    await page.unroute(R.generate);
    await inject(page, R.generate, 'POST', 404, 'study_note_source_deleted');
    await page.click('#generate');
    await expect(page.locator('#note-status')).toContainText('来源已删除，无法生成引用草稿', { timeout: 10000 });
    await page.unroute(R.generate);
    await inject(page, R.generate, 'POST', 503, 'study_note_provider_timeout');
    await page.click('#generate');
    await expect(page.locator('#note-status')).toContainText('AI 笔记服务响应超时，请重试', { timeout: 10000 });
    await page.unroute(R.generate);

    // 真实契约：未建索引的材料不得被伪造为“生成成功”。
    const response = await page.request.post(`${BASE}/api/study/notes/generate`,
      { data: { topic: '光合作用', material_id: materialId, retrieval_mode: 'lexical' } });
    expect([404, 409, 503]).toContain(response.status());
    const body = await response.json();
    expect(String(body.detail)).toMatch(/^study_note_/);
    expect(JSON.stringify(body)).not.toMatch(/traceback|[A-Z]:\\\\|select .* from/i);
    await page.click('#refresh');
    await notesLoaded(page);
    await expect(page.locator('#notes .note-item', { hasText: 'AI 草稿' })).toHaveCount(0);
    await assertNoSensitive(page);
  });

  test('B-ND-6 [接口契约+故障注入] 导出格式契约与导出失败不得脱离页面', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await selectNote(page, '契约笔记（改）');
    const noteId = currentNoteId(page);

    const markdown = await page.request.get(`${BASE}/api/study/notes/${noteId}/export?format=markdown`);
    expect(markdown.status()).toBe(200);
    expect(markdown.headers()['content-type']).toContain('text/markdown');
    expect(markdown.headers()['content-disposition']).toContain('studybuddy-note.md');
    expect(await markdown.text()).toContain('# 契约笔记（改）');

    const jsonExport = await page.request.get(`${BASE}/api/study/notes/${noteId}/export?format=json`);
    expect(jsonExport.status()).toBe(200);
    const payload = await jsonExport.json();
    expect(payload.format_version).toBe('phase9b-note-v1');
    expect(payload.note.id).toBe(noteId);

    const badFormat = await page.request.get(`${BASE}/api/study/notes/${noteId}/export?format=xml`);
    expect(badFormat.status()).toBe(400);
    expect((await badFormat.json()).detail).toBe('study_note_export_failed');
    const missing = await page.request.get(`${BASE}/api/study/notes/note_missing/export?format=markdown`);
    expect(missing.status()).toBe(404);
    expect((await missing.json()).detail).toBe('study_note_not_found');

    // 故障注入：导出失败必须留在页面内看到文案，而不是被导航到裸 JSON 错误页。
    await inject(page, R.exportMd, 'GET', 404, 'study_note_not_found');
    await page.click('#note-export');
    await expect(page.locator('#note-status')).toContainText('笔记不存在或已删除', { timeout: 10000 });
    expect(page.url()).toContain('notes.html');
    await page.unroute(R.exportMd);
    await inject(page, R.exportMd, 'GET', 413, 'study_note_export_failed');
    await page.click('#note-export');
    await expect(page.locator('#note-status')).toContainText('导出失败，请重试', { timeout: 10000 });
    expect(page.url()).toContain('notes.html');
    await page.unroute(R.exportMd);
    await assertNoSensitive(page);

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 15000 }),
      page.click('#note-export'),
    ]);
    expect(download.suggestedFilename()).toBe('studybuddy-note.md');
    await screenshot(page, 'notes-export-success.png');
  });

  test('B-ND-7 [接口契约] 状态机与幂等边界（UI 不提供的路径用 request 观察）', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await selectNote(page, '恢复后笔记');
    await page.click('#note-confirm');
    await expect(page.locator('#note-status')).toContainText('笔记已确认', { timeout: 10000 });
    const noteId = currentNoteId(page);

    const again = await page.request.post(`${BASE}/api/study/notes/${noteId}/confirm`);
    expect(again.status()).toBe(409);
    expect((await again.json()).detail).toBe('study_note_invalid_state');
    const rejected = await page.request.post(`${BASE}/api/study/notes/${noteId}/reject`);
    expect(rejected.status()).toBe(409);
    const patched = await page.request.patch(`${BASE}/api/study/notes/${noteId}`, { data: { title: '篡改标题' } });
    expect(patched.status()).toBe(409);
    expect((await patched.json()).detail).toBe('study_note_edit_not_allowed');
    const archived = await page.request.post(`${BASE}/api/study/notes/${noteId}/archive`);
    expect(archived.status()).toBe(200);
    expect((await archived.json()).status).toBe('archived');
    const archivedAgain = await page.request.post(`${BASE}/api/study/notes/${noteId}/archive`);
    expect(archivedAgain.status()).toBe(409);
    // 归档后仍可读取与导出（归档不是删除）
    expect((await page.request.get(`${BASE}/api/study/notes/${noteId}`)).status()).toBe(200);
    expect((await page.request.get(`${BASE}/api/study/notes/${noteId}/export?format=json`)).status()).toBe(200);
    const missing = await page.request.get(`${BASE}/api/study/notes/note_missing`);
    expect(missing.status()).toBe(404);
    expect((await missing.json()).detail).toBe('study_note_not_found');

    // UI 竞态：双击确认只能产生一次流转。
    await page.click('#refresh');
    await notesLoaded(page);
    await createNote(page, '双击笔记', '双击正文');
    await page.locator('#note-confirm').dblclick();
    await expect(page.locator('#note-status')).toContainText('笔记已确认', { timeout: 10000 });
    await expect(page.locator('#note-status')).not.toContainText('失败');
    await page.click('#refresh');
    await notesLoaded(page);
    await expect(page.locator('#notes .note-item', { hasText: '双击笔记' })).toContainText('已确认');
    await expect(page.locator('#notes .note-item', { hasText: '已确认' })).toHaveCount(1);
    await assertNoSensitive(page);
  });

  test('B-ND-8 [故障注入] 快速切换选中不被迟到响应覆盖，失败不残留旧内容', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await selectNote(page, '契约笔记（改）');
    const slowId = currentNoteId(page);
    await selectNote(page, '双击笔记');
    // A 的详情响应迟到 1200ms，B 立即返回。
    await page.route(R.detail, async route => {
      if (new URL(route.request().url()).pathname.endsWith(slowId)) {
        await new Promise(resolve => setTimeout(resolve, 1200));
      }
      return route.fallback();
    });
    await page.locator('#notes .note-item', { hasText: '契约笔记（改）' }).click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(150);
    await page.locator('#notes .note-item', { hasText: '双击笔记' }).click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#detail-title')).toContainText('双击笔记', { timeout: 10000 });
    await page.waitForTimeout(1600);
    await expect(page.locator('#detail-title')).toContainText('双击笔记');
    await expect(page.locator('#note-detail')).toContainText('已确认');
    await page.unroute(R.detail);

    // 详情加载失败不得把上一篇笔记的内容留在屏幕上。
    await inject(page, R.detail, 'GET', 500, 'study_note_read_failed');
    await page.locator('#notes .note-item', { hasText: '契约笔记（改）' }).click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#detail-status')).toContainText('读取笔记失败，请重试', { timeout: 10000 });
    expect(await page.locator('#note-detail').innerText()).not.toContain('已确认');
    await page.unroute(R.detail);
    await page.locator('#notes .note-item', { hasText: '契约笔记（改）' }).click({ position: { x: 5, y: 5 } });
    await expect(page.locator('#detail-title')).toContainText('契约笔记（改）', { timeout: 10000 });
    await assertNoSensitive(page);
  });

  test('B-ND-9 [故障注入+契约] XSS 转义、输入上限与隐私边界', async ({ page }) => {
    const xssTitle = '<img src=x onerror="window.__xss=1">XSS标题';
    const xssBody = '<script>window.__xss=1</script><b>粗体</b>';
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    await createNote(page, xssTitle, xssBody);
    expect(await page.evaluate(() => window.__xss)).toBeUndefined();
    expect(await page.locator('#notes img, #notes script').count()).toBe(0);
    await expect(page.locator('#notes .note-item', { hasText: 'XSS标题' })).toHaveCount(1);
    await expect(page.locator('#note-detail input[aria-label="笔记标题"]')).toHaveValue(xssTitle);
    const noteId = currentNoteId(page);
    await page.goto(`${BASE}/app/note-detail.html?note_id=${noteId}`);
    await expect(page.locator('#note-detail')).toBeVisible({ timeout: 10000 });
    expect(await page.evaluate(() => window.__xss)).toBeUndefined();
    expect(await page.locator('#note-detail img, #note-detail script').count()).toBe(0);
    await expect(page.locator('#note-detail')).toContainText('<script>window.__xss=1</script>');

    const post = data => page.request.post(`${BASE}/api/study/notes`, { data });
    const longTitle = await post({ title: 'x'.repeat(401), blocks: [{ block_kind: 'text', content: 'ok' }] });
    expect(longTitle.status()).toBe(400);
    expect((await longTitle.json()).detail).toBe('study_note_invalid_payload');
    const emptyBlocks = await post({ title: '空块', blocks: [] });
    expect(emptyBlocks.status()).toBe(409);
    expect((await emptyBlocks.json()).detail).toBe('study_note_empty');
    const hugeBlock = await post({ title: '巨型块', blocks: [{ block_kind: 'text', content: '字'.repeat(12001) }] });
    expect(hugeBlock.status()).toBe(400);
    expect((await hugeBlock.json()).detail).toBe('study_note_block_invalid');
    const badKind = await post({ title: '非法类型', blocks: [{ block_kind: 'raw', content: 'x' }] });
    expect(badKind.status()).toBe(400);
    for (const response of [longTitle, emptyBlocks, hugeBlock, badKind]) {
      expect(JSON.stringify(await response.json())).not.toMatch(/traceback|sqlite|insert into|[A-Z]:\\\\|api[_-]?key/i);
    }
    await assertNoSensitive(page);
  });

  test('B-ND-10 [接口契约] 导出大小上限在受支持内容上限内不可达（防御分支）', async ({ page }) => {
    await page.goto(`${BASE}/app/notes.html`);
    await notesLoaded(page);
    // NOTE_MAX_BLOCK_CONTENT=12000, NOTE_MAX_CONTENT=48000；导出阈值 256 KiB 不可达。
    const blocks = Array.from({ length: 4 }, () => ({ block_kind: 'text', content: '字'.repeat(12000) }));
    const created = await page.request.post(`${BASE}/api/study/notes`, { data: { title: '上限笔记', blocks } });
    expect(created.status()).toBe(201);
    const noteId = (await created.json()).id;
    const exported = await page.request.get(`${BASE}/api/study/notes/${noteId}/export?format=json`);
    expect(exported.status()).toBe(200);
    expect(Buffer.byteLength(await exported.text(), 'utf8')).toBeLessThan(256 * 1024);
    const overBlock = await page.request.post(`${BASE}/api/study/notes`,
      { data: { title: '超限', blocks: [{ block_kind: 'text', content: '字'.repeat(12001) }] } });
    expect(overBlock.status()).toBe(400);
  });
});

async function screenshot(page, name) {
  await page.screenshot({ path: path.join(ART, name), fullPage: true });
}
