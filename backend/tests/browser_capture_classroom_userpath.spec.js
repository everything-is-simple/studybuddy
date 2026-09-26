// CAP-1..CAP-12 A-class pure user-path E2E for capture.html + classroom.html.
// Pure UI cases use only page interactions; route fault injection cases are marked
// "B-element" and counted separately. Fake ASR (fake-capture-v1) only: this does
// not verify real ASR/OCR quality.
const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const STAMP = Date.now();
const RUN_ROOT = `H:/studybuddy-test/runs/capture-classroom-userpath-${STAMP}`;
const ART_ROOT = `H:/studybuddy-test/artifacts/capture-classroom-userpath-${STAMP}`;
const PORT = 8847;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = process.env.STUDYBUDDY_TEST_PYTHON || 'D:/miniconda/py310/python.exe';
let server;

function startServer() {
  const env = {
    ...process.env,
    PYTHONPATH: 'H:/studybuddy/backend',
    STUDYBUDDY_DATA_ROOT: RUN_ROOT,
    STUDYBUDDY_ASR_PROVIDER: 'fake',
    STUDYBUDDY_ASR_MODEL: 'fake-capture-v1',
    STUDYBUDDY_OCR_ENABLED: 'false',
    STUDYBUDDY_REPORT_DELIVERY_MODE: 'off',
  };
  for (const key of ['STUDYBUDDY_AI_PROVIDER', 'STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL',
                     'STUDYBUDDY_AI_API_KEY', 'STUDYBUDDY_ASR_RUNTIME', 'STUDYBUDDY_ASR_MODEL_PATH',
                     'STUDYBUDDY_OCR_PROVIDER', 'STUDYBUDDY_OCR_MODEL_ROOT',
                     'STUDYBUDDY_REPORT_DELIVERY_TARGETS', 'STUDYBUDDY_REPORT_DELIVERY_ENABLED',
                     'STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED']) delete env[key];
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  await expect.poll(async () => {
    try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; }
  }, { timeout: 20000 }).toBe(true);
}

function stop() {
  return new Promise(resolve => {
    if (!server || server.killed) { server = null; return resolve(); }
    let settled = false;
    const finish = () => { if (!settled) { settled = true; server = null; resolve(); } };
    server.once('exit', finish);
    server.kill();
    setTimeout(finish, 5000);
  });
}

async function assertNoSensitiveText(page) {
  const visible = await page.locator('body').innerText();
  expect(visible).not.toMatch(/H:\\|C:\\|stored_path|sha256|originals[\\/]|sqlite|SELECT |Traceback|api[_-]?key|secret|token/i);
}

function wavBuffer() {
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + 800, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(8000, 24);
  header.writeUInt32LE(16000, 28);
  header.writeUInt16LE(1, 32);
  header.writeUInt16LE(8, 34);
  header.write('data', 36);
  header.writeUInt32LE(800, 40);
  return Buffer.concat([header, Buffer.alloc(800)]);
}

async function createSessionFromUi(page, name, { media = 'audio/wav', kind = 'audio' } = {}) {
  await page.getByRole('button', { name: '新建采集会话' }).click();
  const dialog = page.locator('#new-session-dialog');
  await expect(dialog).toBeVisible();
  await page.locator('#asset-kind').selectOption(kind);
  await page.locator('#media-type').selectOption(media);
  await page.locator('#original-name').fill(name);
  await page.getByRole('button', { name: '创建' }).click();
  await expect(dialog).toBeHidden({ timeout: 10000 });
}

async function uploadFromDetail(page, fileName) {
  const detail = page.locator('#session-detail-dialog');
  if (!(await detail.isVisible())) {
    await page.locator('#sessions .session-card').first().getByRole('button', { name: '查看详情' }).click();
  }
  await expect(detail).toBeVisible();
  const path = `${ART_ROOT}/${fileName}`;
  fs.writeFileSync(path, wavBuffer());
  await detail.locator('#file-input').setInputFiles(path);
  await expect(detail.locator('#session-detail-status')).toContainText('上传成功', { timeout: 15000 });
  await expect(detail).toContainText('发起转写', { timeout: 15000 });
}

test.beforeAll(async () => {
  fs.rmSync(RUN_ROOT, { recursive: true, force: true });
  fs.mkdirSync(ART_ROOT, { recursive: true });
  server = startServer();
  await ready();
});

test.afterAll(async () => {
  await stop();
});

test.describe.serial('capture.html + classroom.html A-class user-path E2E', () => {
  test('CAP-1 首页：demo 能力语义、OCR 未配置、空列表、控件可见', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#asr-notice')).toContainText('fake 转写');
    await expect(page.locator('#asr-notice')).toContainText('演示模式');
    await expect(page.locator('#asr-notice')).toContainText('不是真实语音识别');
    await expect(page.locator('#asr-notice')).not.toContainText(/H:\\|C:\\|runtime|model_path|\.exe/i);
    await expect(page.locator('#asr-notice')).toContainText('必须人工确认');
    await expect(page.locator('#asr-notice')).toContainText('Provider：fake');
    await expect(page.locator('#retry-asr')).toBeHidden();
    await expect(page.locator('#state')).toHaveText('暂无会话');
    await expect(page.locator('#empty')).toBeVisible();
    await expect(page.locator('#new-session-btn')).toBeVisible();
    await expect(page.locator('#refresh-btn')).toBeVisible();
    await expect(page.locator('#include-archived')).not.toBeChecked();
    // No terminal session exists yet, so there is no archive action.
    await expect(page.locator('body')).not.toContainText('归档采集');
    await assertNoSensitiveText(page);
  });

  test('CAP-2 新建会话：后缀校验、真实创建、busy 防重、取消', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#empty')).toBeVisible();

    // Name without a media suffix must be rejected in-page before any request.
    let posts = 0;
    page.on('request', r => { if (r.url().endsWith('/api/study/capture-sessions') && r.method() === 'POST') posts += 1; });
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await page.locator('#media-type').selectOption('audio/wav');
    await page.locator('#original-name').fill('没有后缀的名称');
    await page.getByRole('button', { name: '创建' }).click();
    await expect(page.locator('#new-session-status')).toContainText('名称需以');
    await expect(page.locator('#new-session-status')).toHaveAttribute('role', 'alert');
    expect(posts).toBe(0);
    await expect(page.locator('#new-session-dialog')).toBeVisible();

    // Real creation through the form.
    await page.locator('#original-name').fill('2026-01-15 课堂讲解.wav');
    await page.getByRole('button', { name: '创建' }).click();
    await expect(page.locator('#new-session-dialog')).toBeHidden({ timeout: 10000 });
    await expect(page.locator('#sessions .session-card')).toHaveCount(1);
    await expect(page.locator('#sessions .session-header h3')).toHaveText('2026-01-15 课堂讲解.wav');
    await expect(page.locator('#sessions .session-card')).toContainText('草稿');
    await expect(page.locator('#sessions .session-card')).toContainText('音频');
    expect(posts).toBe(1);

    // Duplicate submission guard under a delayed response: the disabled button
    // and the in-flight guard must collapse re-clicks into one request.
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await page.locator('#original-name').fill('busy 防重.wav');
    await page.route('**/api/study/capture-sessions', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      await new Promise(resolve => setTimeout(resolve, 400));
      return route.continue();
    });
    const submit = page.getByRole('button', { name: '创建' });
    await submit.click();
    await expect(submit).toBeDisabled();
    // A second click while busy must not enqueue another request.
    await submit.dispatchEvent('click');
    await submit.dispatchEvent('click');
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await expect(page.locator('#sessions .session-card')).toHaveCount(2, { timeout: 10000 });
    expect(posts).toBe(2);

    // Cancel keeps the list unchanged.
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await page.locator('#original-name').fill('取消测试.wav');
    await page.getByRole('button', { name: '取消' }).click();
    await expect(page.locator('#new-session-dialog')).toBeHidden();
    await expect(page.locator('#sessions .session-card')).toHaveCount(2);
    await assertNoSensitiveText(page);
  });

  test('CAP-3 上传真实音频 → uploaded 状态；文案不承诺拖放', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '上传链路测试.wav');
    // The upload area must not promise drag-and-drop it does not implement.
    const detail = page.locator('#session-detail-dialog');
    if (!(await detail.isVisible())) {
      await page.locator('#sessions .session-card').first().getByRole('button', { name: '查看详情' }).click();
    }
    await expect(detail).toContainText('上传文件');
    await expect(detail).not.toContainText('拖放');
    await uploadFromDetail(page, 'lesson.wav');
    await expect(page.locator('#sessions .session-card').filter({hasText:'上传链路测试.wav'})).toContainText('已上传', { timeout: 10000 });
    await assertNoSensitiveText(page);
  });

  test('CAP-4 fake 转写 → 草稿 → 确认 → materials.html 材料真实出现', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '完整链路测试.wav');
    await uploadFromDetail(page, 'chain.wav');

    const detail = page.locator('#session-detail-dialog');
    await detail.getByRole('button', { name: '开始转写（ASR）' }).click();
    await expect(detail.locator('#session-detail-status')).toContainText('转写完成', { timeout: 15000 });
    await expect(detail).toContainText('转写草稿');
    await expect(detail).toContainText('低置信度片段');

    const reviewedText='人工复核后的课堂转写内容';
    await detail.getByRole('textbox',{name:'编辑转写内容'}).fill(reviewedText);
    await detail.getByRole('button',{name:'保存编辑'}).click();
    await expect(detail.locator('#session-detail-status')).toContainText('草稿已保存', {timeout:15000});
    await expect(detail.getByRole('textbox',{name:'编辑转写内容'})).toHaveValue(reviewedText);

    await detail.getByRole('button', { name: '确认转为学习材料' }).click();
    await expect(detail.locator('#session-detail-status')).toContainText('草稿已确认', { timeout: 15000 });
    const confirmedCard=page.locator('#sessions .session-card').filter({hasText:'完整链路测试.wav'});
    await expect(confirmedCard).toContainText('已确认', { timeout: 10000 });
    await expect(confirmedCard).toContainText('来源有效', { timeout: 10000 });

    // The confirmed transcript must be visible as a real material in materials.html.
    await page.goto(`${BASE}/app/materials.html`);
    const item = page.locator('#items li').filter({ hasText: '完整链路测试.wav' });
    await expect(item.first()).toBeVisible({ timeout: 15000 });
    await assertNoSensitiveText(page);
  });

  test('CAP-5 拒绝草稿与状态标签、已归档过滤边界', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '拒绝流程测试.wav');
    await uploadFromDetail(page, 'reject.wav');
    const detail = page.locator('#session-detail-dialog');
    await detail.getByRole('button', { name: '开始转写（ASR）' }).click();
    await expect(detail).toContainText('转写草稿', { timeout: 15000 });

    await detail.getByRole('button', { name: '拒绝草稿' }).click();
    await expect(detail.locator('#session-detail-status')).toContainText('草稿已拒绝', { timeout: 15000 });
    await expect(page.locator('#sessions .session-card').filter({hasText:'拒绝流程测试.wav'})).toContainText('已拒绝', { timeout: 10000 });

    // Archived filter includes reviewed sessions; archive is available in detail.
    await page.locator('#include-archived').check();
    await expect(page.locator('#sessions .session-card').filter({hasText:'拒绝流程测试.wav'})).toHaveCount(1, { timeout: 10000 });
    await page.locator('#sessions .session-card').filter({hasText:'拒绝流程测试.wav'}).getByRole('button', {name:'查看详情'}).click();
    await expect(detail.locator('[data-control=capture-archive]')).toBeVisible();
    await page.locator('#close-detail-btn').click();
    await page.locator('#include-archived').uncheck();
    await assertNoSensitiveText(page);
  });

  test('CAP-6 classroom 列表与详情：真实字段渲染（original_name/asset_kind）', async ({ page }) => {
    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('#captures .capture-item')).not.toHaveCount(0);
    await expect(page.locator('#report-status')).toHaveText('暂无学习报告');

    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '课堂工作区字段测试.wav');

    await page.goto(`${BASE}/app/classroom.html`);
    const item = page.locator('#captures .capture-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    await expect(item.locator('.item-title')).toHaveText('课堂工作区字段测试.wav');
    await expect(item).toContainText('音频');
    await expect(item).toContainText('草稿');
    // The broken capture_type label must be gone.
    await expect(page.locator('#captures')).not.toContainText('确定性转写');
    await expect(page.locator('#captures')).not.toContainText('未命名会话');

    await item.getByRole('button', { name: '查看详情' }).click();
    await expect(page.locator('#detail-content')).toContainText('课堂工作区字段测试.wav', { timeout: 10000 });
    await expect(page.locator('#detail-content')).toContainText('状态：');
    await expect(page.locator('#detail-content')).toContainText('草稿');
    await assertNoSensitiveText(page);
  });

  test('CAP-7 classroom 报告详情与交付边界（报告经 reports.html UI 创建）', async ({ page }) => {
    await page.goto(`${BASE}/app/reports.html`);
    await page.selectOption('#report-create-kind', 'weekly');
    await page.fill('#report-create-start', '2026-01-12');
    await page.fill('#report-create-end', '2026-01-19');
    await page.fill('#report-create-timezone', 'UTC');
    await page.getByRole('button', { name: '生成报告' }).click();
    await expect(page.locator('#report-create-status')).toHaveText('报告已生成', { timeout: 15000 });

    await page.goto(`${BASE}/app/classroom.html`);
    const item = page.locator('#reports .report-item').first();
    await expect(item).toBeVisible({ timeout: 10000 });
    await expect(item).toContainText('周报');
    await item.getByRole('button', { name: '查看详情' }).click();
    await expect(page.locator('#detail-content')).toContainText('报告', { timeout: 10000 });
    await expect(page.locator('#detail-content')).toContainText('范围：2026-01-12 至 2026-01-19');
    // Delivery boundary: off/dry-run only, never "已发送", never live.
    await item.getByRole('button', { name: '查看详情' }).click();
    await page.getByRole('button', { name: '查看交付审计' }).click();
    await expect(page.locator('#detail-content')).toContainText('交付审计', { timeout: 10000 });
    await expect(page.locator('#detail-content')).toContainText('暂无交付记录');
    await expect(page.locator('#detail-content')).toContainText('live 交付被系统明确禁用');
    await expect(page.locator('body')).not.toContainText('已发送');
    await assertNoSensitiveText(page);
  });

  test('CAP-8（含 B 类 route 注入）列表/能力状态失败 → 页面内错误 + 独立重试，无 alert', async ({ page }) => {
    let dialogSeen = false;
    page.on('dialog', async dialog => { dialogSeen = true; await dialog.dismiss(); });
    await page.route('**/api/study/capture-sessions?*', route => route.fulfill({
      status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'private_list_error', path: 'H:/secret' }),
    }));
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#error')).toContainText('请求失败，请重试');
    await expect(page.locator('#error')).toBeVisible();
    await expect(page.locator('#retry-list')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/private_list_error|H:\/secret/);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-list').click();
    await expect(page.locator('#error')).toBeHidden({ timeout: 10000 });
    await expect(page.locator('#retry-list')).toBeHidden();
    await expect(page.locator('#sessions .session-card')).not.toHaveCount(0);

    // Capability failure is distinct from not_configured and independently retriable.
    await page.route('**/api/ai/capabilities', route => route.fulfill({
      status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_cap_error', path: 'H:/secret' }),
    }));
    await page.reload();
    await expect(page.locator('#asr-notice')).toContainText('转写能力状态加载失败');
    await expect(page.locator('#asr-notice')).not.toContainText('未配置');
    await expect(page.locator('#retry-asr')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(/private_cap_error|H:\/secret/);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-asr').click();
    await expect(page.locator('#asr-notice')).toContainText('fake 转写', { timeout: 10000 });
    await expect(page.locator('#retry-asr')).toBeHidden();
    expect(dialogSeen).toBe(false);
    await assertNoSensitiveText(page);
  });

  test('CAP-9 五档响应式 + 键盘 + dialog Escape + 焦点', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '响应式测试.wav');
    for (const [w, h] of [[1920, 1080], [1280, 800], [768, 1024], [540, 800], [390, 844]]) {
      await page.setViewportSize({ width: w, height: h });
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      await page.screenshot({ path: `${ART_ROOT}/capture-${w}x${h}.png`, fullPage: true });
    }
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toHaveCount(1);
    // Escape closes the new-session dialog without side effects.
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await expect(page.locator('#new-session-dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#new-session-dialog')).toBeHidden();
    await expect(page.locator('#sessions .session-card').filter({hasText:'响应式测试.wav'})).toHaveCount(1);
    // Detail dialog Escape closes it too.
    await page.locator('#sessions .session-card').first().getByRole('button', { name: '查看详情' }).click();
    await expect(page.locator('#session-detail-dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#session-detail-dialog')).toBeHidden();
    await assertNoSensitiveText(page);
  });

  test('CAP-10 刷新、返回、跨页与真重启持久化', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '持久化测试.wav');
    const persistedCard=page.locator('#sessions .session-card').filter({hasText:'持久化测试.wav'});
    await expect(persistedCard).toHaveCount(1);

    await page.reload();
    await expect(page.locator('#sessions .session-card').filter({hasText:'持久化测试.wav'})).toHaveCount(1);
    await expect(page.locator('#sessions .session-card').filter({hasText:'持久化测试.wav'}).locator('.session-header h3')).toHaveText('持久化测试.wav');

    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('#captures .capture-item .item-title').filter({hasText:'持久化测试.wav'})).toHaveText('持久化测试.wav', { timeout: 10000 });
    await page.goBack();
    await expect(page).toHaveURL(/capture\.html/);
    await expect(page.locator('#sessions .session-card').filter({hasText:'持久化测试.wav'})).toHaveCount(1);

    // Real process restart: the session survives via SQLite/data_root.
    await stop();
    server = startServer();
    await ready();
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#sessions .session-card').filter({hasText:'持久化测试.wav'}).locator('.session-header h3')).toHaveText('持久化测试.wav', { timeout: 15000 });
    await assertNoSensitiveText(page);
  });

  test('CAP-11 无效 ID 深链与空数据边界（classroom URL 参数）', async ({ page }) => {
    await page.goto(`${BASE}/app/classroom.html?capture_id=invalid-capture-xyz`);
    await expect(page.locator('#detail-status')).toContainText('采集会话不存在或已删除', { timeout: 10000 });
    await expect(page.locator('#retry-detail')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('invalid-capture-xyz');

    await page.goto(`${BASE}/app/classroom.html?report_id=invalid-report-xyz`);
    await expect(page.locator('#detail-status')).toContainText('报告不存在或已删除', { timeout: 10000 });
    await expect(page.locator('#retry-detail')).toBeVisible();
    await assertNoSensitiveText(page);
  });

  test('CAP-12（含 B 类 route 注入）超大/非法上传的安全拒绝与重试', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await createSessionFromUi(page, '上传边界测试.wav');
    const detail = page.locator('#session-detail-dialog');
    if (!(await detail.isVisible())) {
      await page.locator('#sessions .session-card').first().getByRole('button', { name: '查看详情' }).click();
    }
    await expect(detail).toBeVisible();
    await page.route('**/upload', route => route.fulfill({
      status: 413, contentType: 'application/json', body: JSON.stringify({ detail: 'file_too_large' }),
    }));
    const path = `${ART_ROOT}/big.wav`;
    fs.writeFileSync(path, wavBuffer());
    await detail.locator('#file-input').setInputFiles(path);
    await expect(detail.locator('#session-detail-status')).toContainText('文件过大', { timeout: 10000 });
    await expect(detail.locator('#session-detail-status')).toHaveAttribute('role', 'alert');
    await expect(detail.locator('#file-input')).toBeEnabled();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    // Retry with the real backend succeeds.
    await detail.locator('#file-input').setInputFiles(path);
    await expect(detail.locator('#session-detail-status')).toContainText('上传成功', { timeout: 15000 });
    await assertNoSensitiveText(page);
  });
});
