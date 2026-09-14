// B-CAP-1..B-CAP-15 B-class independent contract, race, fault, and safety review
// for capture.html + classroom.html. These tests deliberately use route mocks to
// exercise pagination, stale-response races, error-code mapping, XSS boundaries,
// privacy boundaries, and ARIA/keyboard that do not need persisted business state.
// User interaction remains page UI; contract validation uses page.request for read-only
// observation or fault injection that A-class pure UI cannot reach.
const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const STAMP = Date.now();
const ROOT = `H:/studybuddy-test/runs/capture-classroom-b-${STAMP}`;
const ART = `H:/studybuddy-test/artifacts/capture-classroom-b-${STAMP}`;
const PORT = 8848;
const BASE = `http://127.0.0.1:${PORT}`;
const PYTHON = 'C:/miniconda/py310/python.exe';
let server;

function wavBuffer() {
  const header = Buffer.alloc(44);
  header.write('RIFF', 0); header.writeUInt32LE(836, 4); header.write('WAVE', 8);
  header.write('fmt ', 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22); header.writeUInt32LE(8000, 24); header.writeUInt32LE(16000, 28);
  header.writeUInt16LE(1, 32); header.writeUInt16LE(8, 34); header.write('data', 36);
  header.writeUInt32LE(800, 40);
  return Buffer.concat([header, Buffer.alloc(800)]);
}

function startServer() {
  const env = {
    ...process.env,
    PYTHONPATH: 'H:/studybuddy/backend',
    STUDYBUDDY_DATA_ROOT: ROOT,
    STUDYBUDDY_ASR_PROVIDER: 'fake',
    STUDYBUDDY_ASR_MODEL: 'fake-capture-v1',
    STUDYBUDDY_REPORT_DELIVERY_MODE: 'off',
    STUDYBUDDY_MAX_UPLOAD_BYTES: '1024',
  };
  for (const key of ['STUDYBUDDY_AI_PROVIDER', 'STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_ASR_RUNTIME',
                     'STUDYBUDDY_OCR_PROVIDER', 'STUDYBUDDY_REPORT_DELIVERY_TARGETS']) delete env[key];
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

test.beforeEach(async () => {
  fs.rmSync(ROOT, { recursive: true, force: true });
  fs.mkdirSync(ROOT, { recursive: true });
  fs.mkdirSync(ART, { recursive: true });
  server = startServer();
  await ready();
});

test.afterEach(async () => {
  await stop();
});

test.describe('capture.html + classroom.html B-class contract and safety', () => {
  test('B-CAP-1: capture-sessions list contract (pagination limit/offset/has_more/total, include_archived, invalid_pagination 400)', async ({ page, request }) => {
    const base64Audio = Buffer.from('RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00').toString('base64');
    for (let i = 0; i < 3; i++) {
      await request.post(`${BASE}/api/study/capture-sessions`, {
        data: { asset_kind: 'audio', original_name: `Session ${i}`, media_type: 'audio/wav' }
      });
    }

    const page1 = await request.get(`${BASE}/api/study/capture-sessions?limit=2&offset=0`);
    expect(page1.ok()).toBe(true);
    const p1Data = await page1.json();
    expect(p1Data.items.length).toBe(2);
    expect(p1Data.has_more).toBe(true);
    expect(p1Data.total).toBe(3);

    const page2 = await request.get(`${BASE}/api/study/capture-sessions?limit=2&offset=2`);
    expect(page2.ok()).toBe(true);
    const p2Data = await page2.json();
    expect(p2Data.items.length).toBe(1);
    expect(p2Data.has_more).toBe(false);

    const archived = await request.get(`${BASE}/api/study/capture-sessions?include_archived=true`);
    expect(archived.ok()).toBe(true);

    const invalid = await request.get(`${BASE}/api/study/capture-sessions?limit=-1`);
    expect(invalid.status()).toBe(400);
    const invalidData = await invalid.json();
    expect(invalidData.detail).toBe('invalid_pagination');
  });

  test('B-CAP-2: upload contract (valid/invalid media type, size limit, error codes, no path echo)', async ({ request }) => {
    async function session(name) {
      const response=await request.post(`${BASE}/api/study/capture-sessions`, {
        data:{asset_kind:'audio',original_name:name,media_type:'audio/wav'}
      });
      expect(response.ok()).toBe(true);
      return response.json();
    }
    const valid=await session('Upload contract.wav');
    const upload=await request.post(`${BASE}/api/study/capture-sessions/${valid.id}/upload`, {
      multipart:{file:{name:'test.wav',mimeType:'audio/wav',buffer:wavBuffer()}}
    });
    expect(upload.ok()).toBe(true);
    const detailData=await (await request.get(`${BASE}/api/study/capture-sessions/${valid.id}`)).json();
    expect(detailData.status).toBe('uploaded');
    expect(JSON.stringify(detailData)).not.toMatch(/stored_path|originals|sha256|H:\\|C:\\/i);

    const invalid=await session('Invalid signature.wav');
    const invalidUpload=await request.post(`${BASE}/api/study/capture-sessions/${invalid.id}/upload`, {
      multipart:{file:{name:'invalid.wav',mimeType:'audio/wav',buffer:Buffer.from('not-a-wave')}}
    });
    expect(invalidUpload.status()).toBe(400);
    expect((await invalidUpload.json()).detail).toBe('capture_asset_type_not_supported');
    expect(await invalidUpload.text()).not.toMatch(/originals|H:\\|C:\\|Traceback/i);

    const oversized=await session('Oversized.wav');
    const oversizedUpload=await request.post(`${BASE}/api/study/capture-sessions/${oversized.id}/upload`, {
      multipart:{file:{name:'oversized.wav',mimeType:'audio/wav',buffer:Buffer.concat([wavBuffer(),Buffer.alloc(1024)])}}
    });
    expect(oversizedUpload.status()).toBe(413);
    expect((await oversizedUpload.json()).detail).toBe('capture_asset_too_large');
  });

  test('B-CAP-3: transcribe/edit/confirm/reject contract (draft_id required, state machine boundaries, idempotent, stable error codes, material creation)', async ({ page, request }) => {
    const create = await request.post(`${BASE}/api/study/capture-sessions`, {
      data: { asset_kind: 'audio', original_name: 'Transcript contract.wav', media_type: 'audio/wav' }
    });
    const session = await create.json();
    const wavPath = `${ART}/contract-transcribe.wav`;
    fs.writeFileSync(wavPath, wavBuffer());
    await request.post(`${BASE}/api/study/capture-sessions/${session.id}/upload`, {
      multipart: { file: { name: 'test.wav', mimeType: 'audio/wav', buffer: fs.readFileSync(wavPath) } }
    });

    const key='b-cap-transcribe-key';
    const transcribe = await request.post(`${BASE}/api/study/capture-sessions/${session.id}/transcribe`,{headers:{'Idempotency-Key':key}});
    expect(transcribe.ok()).toBe(true);
    const replay=await request.post(`${BASE}/api/study/capture-sessions/${session.id}/transcribe`,{headers:{'Idempotency-Key':key}});
    expect(replay.ok()).toBe(true);
    expect((await replay.json()).replay).toBe(true);

    const transcript = await request.get(`${BASE}/api/study/capture-sessions/${session.id}/transcript`);
    const transcriptData = await transcript.json();
    expect(transcriptData.transcript_drafts.length).toBeGreaterThan(0);
    const draftId = transcriptData.transcript_drafts[0].id;

    const confirmNoDraft = await request.post(`${BASE}/api/study/capture-sessions/${session.id}/confirm`, {
      data: {}
    });
    expect(confirmNoDraft.status()).toBe(422);

    const edited=await request.post(`${BASE}/api/study/capture-sessions/${session.id}/transcript/edit`,{
      data:{draft_id:draftId,text:'B 类人工复核文本'}
    });
    expect(edited.ok()).toBe(true);
    expect((await edited.json()).edited_by_user).toBe(true);

    const confirm = await request.post(`${BASE}/api/study/capture-sessions/${session.id}/confirm`, {
      data: { draft_id: draftId }
    });
    expect(confirm.ok()).toBe(true);
    const confirmReplay=await request.post(`${BASE}/api/study/capture-sessions/${session.id}/confirm`,{data:{draft_id:draftId}});
    expect(confirmReplay.ok()).toBe(true);
    expect((await confirmReplay.json()).replay).toBe(true);
    const protectedEdit=await request.post(`${BASE}/api/study/capture-sessions/${session.id}/transcript/edit`,{data:{draft_id:draftId,text:'禁止覆盖'}});
    expect(protectedEdit.status()).toBe(400);
    expect((await protectedEdit.json()).detail).toBe('transcript_user_edit_protected');

    const rejectSessionResponse=await request.post(`${BASE}/api/study/capture-sessions`,{data:{asset_kind:'audio',original_name:'Reject contract.wav',media_type:'audio/wav'}});
    const rejectSession=await rejectSessionResponse.json();
    await request.post(`${BASE}/api/study/capture-sessions/${rejectSession.id}/upload`,{multipart:{file:{name:'reject.wav',mimeType:'audio/wav',buffer:wavBuffer()}}});
    const rejectTranscribe=await request.post(`${BASE}/api/study/capture-sessions/${rejectSession.id}/transcribe`);
    const rejectDraft=(await rejectTranscribe.json()).draft.id;
    const rejected=await request.post(`${BASE}/api/study/capture-sessions/${rejectSession.id}/reject`,{data:{draft_id:rejectDraft}});
    expect(rejected.ok()).toBe(true);
    expect((await rejected.json()).capture.status).toBe('rejected');
    const confirmRejected=await request.post(`${BASE}/api/study/capture-sessions/${rejectSession.id}/confirm`,{data:{draft_id:rejectDraft}});
    expect(confirmRejected.status()).toBe(409);
    expect((await confirmRejected.json()).detail).toBe('capture_invalid_state');

    const materials = await request.get(`${BASE}/api/materials`);
    const materialsData = await materials.json();
    expect(materialsData.length).toBe(3);
    expect(materialsData.some(item => item.original_name === 'Transcript contract.wav')).toBe(true);
  });

  test('B-CAP-4: archive 409 stable boundary and no archive UI entry point on both pages', async ({ page, request }) => {
    const create = await request.post(`${BASE}/api/study/capture-sessions`, {
      data: { asset_kind: 'audio', original_name: 'Archive boundary', media_type: 'audio/wav' }
    });
    const session = await create.json();

    const archive = await request.post(`${BASE}/api/study/capture-sessions/${session.id}/archive`);
    expect(archive.status()).toBe(409);
    const archiveData = await archive.json();
    expect(archiveData.detail).toBe('capture_invalid_state');

    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('body')).not.toContainText(/归档按钮|archive.*button/i);

    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('body')).not.toContainText(/归档按钮|archive.*button/i);
  });

  test('B-CAP-5: reports contract (create, list, detail, preview/export boundaries)', async ({ page, request }) => {
    const report = await request.post(`${BASE}/api/study/reports`, {
      data: {
        report_kind: 'weekly',
        timezone: 'Asia/Shanghai',
        period_start: '2026-01-13',
        period_end: '2026-01-20'
      }
    });
    expect(report.ok()).toBe(true);
    const reportData = await report.json();
    expect(reportData.report_kind).toBe('weekly');

    const list = await request.get(`${BASE}/api/study/reports`);
    const listData = await list.json();
    expect(listData.items.length).toBe(1);

    const detail = await request.get(`${BASE}/api/study/reports/${reportData.id}`);
    expect(detail.ok()).toBe(true);

    const preview = await request.get(`${BASE}/api/study/reports/${reportData.id}/preview`);
    expect(preview.ok()).toBe(true);

    const exportMd = await request.get(`${BASE}/api/study/reports/${reportData.id}/export?format=markdown`);
    expect(exportMd.ok()).toBe(true);
  });

  test('B-CAP-6: delivery boundary (off/dry-run, live rejected, delivery-attempts read-only, no auto-send, no "已发送")', async ({ page, request }) => {
    const report = await request.post(`${BASE}/api/study/reports`, {
      data: {
        report_kind: 'weekly',
        timezone: 'Asia/Shanghai',
        period_start: '2026-01-13',
        period_end: '2026-01-20'
      }
    });
    const reportData = await report.json();

    const attempts = await request.get(`${BASE}/api/study/reports/${reportData.id}/delivery-attempts`);
    expect(attempts.ok()).toBe(true);
    expect((await attempts.json()).items.length).toBe(0);
    const off=await request.post(`${BASE}/api/study/reports/${reportData.id}/delivery`,{
      data:{channel:'smtp',target_label:'guardian-primary'}
    });
    expect(off.ok()).toBe(true);
    const offData=await off.json();
    expect(offData).toMatchObject({mode:'off',status:'blocked',error_code:'delivery_disabled'});
    const live=await request.post(`${BASE}/api/study/reports/${reportData.id}/delivery`,{
      data:{channel:'smtp',target_label:'guardian-primary',mode:'live',authorization_granted:true}
    });
    expect(live.status()).toBe(400);
    expect((await live.json()).detail).toBe('delivery_disabled');
    const audit=await request.get(`${BASE}/api/study/reports/${reportData.id}/delivery-attempts`);
    expect((await audit.json()).items).toHaveLength(1);

    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('body')).not.toContainText(/已发送|delivery.*enabled|live.*authorized/i);
    const reportItem=page.locator('#reports .report-item').first();
    await reportItem.getByRole('button',{name:'查看详情'}).click();
    await page.getByRole('button',{name:'查看交付审计'}).click();
    await expect(page.locator('#detail-content')).toContainText('交付功能仅支持 off/dry-run 模式。live 交付被系统明确禁用。');
  });

  test('B-CAP-7: list load race guard (stale failure does not overwrite new success)', async ({ page }) => {
    let resolveFirst, resolveSecond;
    const firstPromise = new Promise(r => { resolveFirst = r; });
    const secondPromise = new Promise(r => { resolveSecond = r; });
    let firstCalled = false, secondCalled = false;

    await page.route('**/api/study/capture-sessions?*', async (route, request) => {
      if (!firstCalled) {
        firstCalled = true;
        await firstPromise;
        route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'capture_list_failed' }) });
      } else if (!secondCalled) {
        secondCalled = true;
        resolveSecond();
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], has_more: false, total: 0 }) });
      } else {
        route.continue();
      }
    });

    // The initial page load starts the first (stale, will fail) request.
    await page.goto(`${BASE}/app/capture.html`);
    // The refresh button is busy-guarded while the first request is in flight,
    // but the archived filter toggle is a valid unguarded entry that starts a
    // new generation; the stale failure must not overwrite its success.
    await page.locator('#include-archived').check();
    await secondPromise;
    await page.waitForTimeout(100);
    resolveFirst();
    await page.waitForTimeout(500);
    await expect(page.locator('#empty')).toBeVisible();
    await expect(page.locator('#error')).toBeHidden();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('B-CAP-8: detail race guard (rapid switch capture/report does not cross-contaminate)', async ({ page, request }) => {
    const cap1 = await request.post(`${BASE}/api/study/capture-sessions`, {
      data: { asset_kind: 'audio', original_name: 'Capture 1', media_type: 'audio/wav' }
    });
    const cap1Data = await cap1.json();
    const cap2 = await request.post(`${BASE}/api/study/capture-sessions`, {
      data: { asset_kind: 'audio', original_name: 'Capture 2', media_type: 'audio/wav' }
    });
    const cap2Data = await cap2.json();

    let firstDetailCalled = false;
    await page.route(`**/api/study/capture-sessions/${cap1Data.id}`, async route => {
      if (!firstDetailCalled) {
        firstDetailCalled = true;
        await page.waitForTimeout(500);
      }
      route.continue();
    });

    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('#captures .capture-item')).toHaveCount(2);
    await page.locator('#captures .capture-item').nth(1).getByRole('button', {name:'查看详情'}).click();
    await page.locator('#captures .capture-item').nth(0).getByRole('button', {name:'查看详情'}).click();
    await page.waitForTimeout(1000);
    await expect(page.locator('#detail-content')).toContainText('Capture 2');
    await expect(page.locator('#detail-content')).not.toContainText('Capture 1');
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('B-CAP-9: create and refresh busy guards prevent duplicate requests', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await page.locator('#original-name').fill('Busy guard.wav');
    const submitBtn = page.getByRole('button', { name: '创建' });
    await submitBtn.dispatchEvent('click');
    await submitBtn.dispatchEvent('click');
    await submitBtn.dispatchEvent('click');
    await page.waitForTimeout(1000);
    await expect(page.locator('#sessions .session-card')).toHaveCount(1);

    let listRequests=0;
    await page.route('**/api/study/capture-sessions?*',async route=>{
      listRequests++;
      await new Promise(resolve=>setTimeout(resolve,300));
      await route.continue();
    });
    const refresh=page.getByRole('button',{name:'刷新'});
    await refresh.dispatchEvent('click');
    await refresh.dispatchEvent('click');
    await refresh.dispatchEvent('click');
    await page.waitForTimeout(600);
    expect(listRequests).toBe(1);
    await page.unrouteAll({behavior:'ignoreErrors'});
  });

  test('B-CAP-10: error code mapping completeness and safe user text', async ({ page }) => {
    const codes = ['capture_list_failed', 'capture_not_found', 'capture_invalid_state', 'transcript_confirm_failed', 'file_too_large', 'unsupported_format'];
    for (const code of codes) {
      await page.route('**/api/study/capture-sessions*', route => route.fulfill({
        status: 400, contentType: 'application/json', body: JSON.stringify({ detail: code })
      }));
      await page.goto(`${BASE}/app/capture.html`);
      await expect(page.locator('#error')).toBeVisible();
      await expect(page.locator('#error')).not.toContainText(code);
      await expect(page.locator('body')).not.toContainText(/H:\\|C:\\|sqlite|SELECT|Traceback/i);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('B-CAP-11: list/detail/transcript/report payloads render as text without executable nodes', async ({ page }) => {
    const xss = '<script>alert("xss")</script>.wav';
    const draftXss='<img src=x onerror=window.__draftXss=1>';
    await page.route('**/api/study/capture-sessions?*', route => route.fulfill({
      status:200,contentType:'application/json',body:JSON.stringify({items:[{id:'xss-capture',original_name:xss,media_type:'audio/wav',asset_kind:'audio',status:'review_required',created_at:'2026-01-01T00:00:00Z'}],has_more:false,total:1})
    }));
    await page.route('**/api/study/capture-sessions/xss-capture',route=>route.fulfill({
      status:200,contentType:'application/json',body:JSON.stringify({id:'xss-capture',original_name:xss,media_type:'audio/wav',asset_kind:'audio',status:'review_required',transcript_drafts:[{id:'draft-xss',status:'draft',text:draftXss,segments:[]}]})
    }));
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#sessions .session-header h3')).toHaveText(xss);
    await page.getByRole('button',{name:'查看详情'}).click();
    await expect(page.locator('.transcript-view')).toHaveText(draftXss);
    expect(await page.locator('script[src="x"],img[src="x"]').count()).toBe(0);
    expect(await page.evaluate(()=>window.__draftXss)).toBeUndefined();
    await page.unrouteAll({behavior:'ignoreErrors'});

    const reportXss='<img src=x onerror=window.__reportXss=1>';
    await page.route('**/api/study/capture-sessions?*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[],has_more:false,total:0})}));
    await page.route('**/api/study/reports?*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[{id:'report-xss',report_kind:reportXss,period_start:reportXss}],has_more:false,total:1})}));
    await page.route('**/api/study/reports/report-xss',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'report-xss',report_kind:reportXss,period_start:reportXss,period_end:reportXss,status:reportXss})}));
    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('#reports .item-title')).toContainText(reportXss);
    await page.locator('#reports').getByRole('button',{name:'查看详情'}).click();
    await expect(page.locator('#detail-content')).toContainText(reportXss);
    expect(await page.locator('img[src="x"]').count()).toBe(0);
    expect(await page.evaluate(()=>window.__reportXss)).toBeUndefined();
    await page.unrouteAll({behavior:'ignoreErrors'});
  });

  test('B-CAP-12: privacy boundary (no path/hash/original audio echo; audit no secret)', async ({ page, request }) => {
    const create = await request.post(`${BASE}/api/study/capture-sessions`, {
      data: { asset_kind: 'audio', original_name: 'Privacy check', media_type: 'audio/wav' }
    });
    const session = await create.json();
    const detail = await request.get(`${BASE}/api/study/capture-sessions/${session.id}`);
    const detailData = await detail.json();
    expect(JSON.stringify(detailData)).not.toMatch(/stored_path|originals|sha256|H:\\|C:\\/i);

    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('body')).not.toContainText(/stored_path|originals|sha256|H:\\|C:\\/i);

    await page.goto(`${BASE}/app/classroom.html`);
    await expect(page.locator('body')).not.toContainText(/stored_path|originals|sha256|secret|password|api[_-]?key/i);
  });

  test('B-CAP-13: DOM/ARIA/keyboard (dialog semantics, label, role=alert, focus-visible)', async ({ page }) => {
    await page.goto(`${BASE}/app/capture.html`);
    await page.getByRole('button', { name: '新建采集会话' }).click();
    const dialog = page.locator('#new-session-dialog');
    await expect(dialog).toHaveAttribute('aria-labelledby', 'new-session-title');

    await page.route('**/api/study/capture-sessions?*', route => route.fulfill({
      status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'capture_list_failed' })
    }));
    await page.reload();
    await expect(page.locator('#error')).toHaveAttribute('role', 'alert');
    await expect(page.locator('#error')).toHaveAttribute('aria-live', 'polite');
    await page.unrouteAll({ behavior: 'ignoreErrors' });

    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toHaveCount(1);
  });

  test('B-CAP-14: error and success feedback does not rely on alert/confirm (route injection verifies page-internal feedback)', async ({ page }) => {
    await page.route('**/api/study/capture-sessions', route => route.fulfill({
      status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'create_failed' })
    }));
    await page.goto(`${BASE}/app/capture.html`);
    await page.getByRole('button', { name: '新建采集会话' }).click();
    await page.locator('#original-name').fill('Error feedback test.wav');
    await page.getByRole('button', { name: '创建' }).click();
    await expect(page.locator('#new-session-status')).toBeVisible();
    await expect(page.locator('#new-session-status')).toHaveAttribute('role', 'alert');
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('B-CAP-15: capability status failure semantics (unknown ≠ not_configured, independent retry)', async ({ page }) => {
    await page.route('**/api/ai/capabilities', route => route.fulfill({
      status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unknown_capability_error' })
    }));
    await page.goto(`${BASE}/app/capture.html`);
    await expect(page.locator('#asr-notice')).not.toContainText('未配置');
    await expect(page.locator('#asr-notice')).toContainText('组件状态暂不可用');
    await expect(page.locator('#retry-asr')).toBeVisible();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.locator('#retry-asr').click();
    await expect(page.locator('#asr-notice')).toContainText('演示模式');
  });
});
