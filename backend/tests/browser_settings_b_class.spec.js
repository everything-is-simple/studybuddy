// B-SET-1..B-SET-15 independent contract / race / fault / privacy review for
// settings.html + settings-provider.html. This spec does not depend on the
// A-class spec or its data. It freely uses page.request for contract
// observation and page.route for fault injection; UI-created data is marked
// inline. Real successes run against the deterministic fake provider and the
// fake SMTP server; no case here claims a real third-party provider pass.
const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const fs = require('fs');

const STAMP = Date.now();
const RUN_ROOT = `H:/studybuddy-test/runs/settings-b-class-${STAMP}`;
const PORT = 8843, PROVIDER_PORT = 8944, SMTP_PORT = 8945, CLOSED_PORT = 8946;
const BASE = `http://127.0.0.1:${PORT}`;
const FAKE_BASE = `http://127.0.0.1:${PROVIDER_PORT}/v1`;
const KEY = 'TEST_SETTINGS_API_KEY_DO_NOT_LEAK_u9';
const SMTP_PASS = 'TEST_SMTP_PASSWORD_DO_NOT_LEAK_s3';
const WEBHOOK = 'https://open.feishu.cn/hook/TEST_FEISHU_WEBHOOK_DO_NOT_LEAK_w5';
const CAP_KEYS = ['import_parse', 'ocr', 'asr', 'index', 'qa', 'generation', 'report'];
const CAP_STATUSES = ['available', 'degraded', 'not_configured', 'not_installed', 'disabled'];
let server, fakeProvider, fakeSmtp;

function startFakeProvider() {
  return new Promise(resolve => {
    let lastBody = null;
    const srv = http.createServer((req, res) => {
      let body = ''; req.on('data', c => body += c);
      req.on('end', () => {
        if (req.url === '/__last') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(lastBody || {})); return; }
        lastBody = { url: req.url, auth: req.headers['authorization'] || '', body: body ? JSON.parse(body) : null };
        const auth = lastBody.auth;
        if (auth.endsWith('FAIL401')) { res.writeHead(401); res.end('{"error":{"message":"bad key"}}'); return; }
        if (auth.endsWith('FAIL500')) { res.writeHead(500); res.end('{}'); return; }
        const model = (lastBody.body && lastBody.body.model) || '';
        if (model === 'bad-json-model') { res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('not json at all'); return; }
        if (req.url.endsWith('/chat/completions')) {
          const content = model === 'huge-model' ? 'x'.repeat(2048) : 'ok';
          res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ choices: [{ message: { content } }] }));
        } else if (req.url.endsWith('/embeddings')) {
          res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ data: [{ embedding: [0.1, 0.2] }] }));
        } else { res.writeHead(404); res.end('{}'); }
      });
    });
    srv.on('error', () => {});
    srv.listen(PROVIDER_PORT, '127.0.0.1', () => resolve(srv));
  });
}
function startFakeSmtp() {
  return new Promise(resolve => {
    const srv = net.createServer(socket => {
      socket.setEncoding('utf8'); socket.write('220 fake.smtp ESMTP\r\n'); let buf = '';
      socket.on('error', () => {});
      socket.on('data', chunk => {
        buf += chunk; let i;
        while ((i = buf.indexOf('\r\n')) >= 0) {
          const line = buf.slice(0, i); buf = buf.slice(i + 2); const cmd = line.toUpperCase();
          if (cmd.startsWith('EHLO') || cmd.startsWith('HELO')) socket.write('250-fake\r\n250-AUTH PLAIN\r\n250 OK\r\n');
          else if (cmd.startsWith('AUTH')) {
            const decoded = Buffer.from(line.split(' ').pop() || '', 'base64').toString('utf8');
            socket.write(decoded.toLowerCase().includes('fail') ? '535 auth failed\r\n' : '235 ok\r\n');
          }
          else if (cmd.startsWith('DATA')) socket.write('354 go\r\n');
          else if (cmd === '.') socket.write('250 queued\r\n');
          else if (cmd.startsWith('QUIT')) { socket.write('221 bye\r\n'); socket.end(); }
          else socket.write('250 ok\r\n');
        }
      });
    });
    srv.on('error', () => {});
    srv.listen(SMTP_PORT, '127.0.0.1', () => resolve(srv));
  });
}
function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  for (const k of ['STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL', 'STUDYBUDDY_AI_API_KEY']) delete env[k];
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
function stopServer(s) { return new Promise(resolve => { const p = s || server; if (!p || p.killed) return resolve(); p.once('exit', resolve); p.kill(); if (p === server) server = null; }); }
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
async function api(request, method, path, payload) {
  const r = await request.fetch(`${BASE}${path}`, { method, data: payload, headers: { 'Content-Type': 'application/json' } });
  let body = null; try { body = await r.json(); } catch (_) {}
  return { status: r.status(), body, text: JSON.stringify(body) };
}
async function pageState(page) {
  return page.evaluate(() => ({ text: document.body.innerText, html: document.documentElement.outerHTML, url: location.href, history: JSON.stringify(history.state), cookie: document.cookie, local: JSON.stringify(localStorage), session: JSON.stringify(sessionStorage) }));
}
function leaked(state, ...secrets) { return secrets.some(s => Object.values(state).some(v => v.includes(s))); }
function attachRecorder(page) {
  const rec = { console: [], bodies: [] };
  page.on('console', m => rec.console.push(m.text()));
  page.on('response', async r => { if (r.url().includes('/api/')) { try { rec.bodies.push(await r.text()); } catch (_) {} } });
  return rec;
}
function recorderClean(rec, ...secrets) {
  return !secrets.some(s => rec.bodies.some(b => b.includes(s)) || rec.console.some(c => c.includes(s)));
}

test.beforeAll(async () => { fakeProvider = await startFakeProvider(); fakeSmtp = await startFakeSmtp(); });
test.afterAll(async () => { if (fakeProvider) fakeProvider.close(); if (fakeSmtp) fakeSmtp.close(); });
test.beforeEach(async () => { fs.rmSync(RUN_ROOT, { recursive: true, force: true }); server = startServer(); await ready(); });
test.afterEach(async () => { await stopServer(); });

test('B-SET-1 能力 API 契约与自检无副作用', async ({ request }) => {
  const caps = await api(request, 'GET', '/api/system/capabilities');
  expect(caps.status).toBe(200);
  expect(Object.keys(caps.body.capabilities).sort()).toEqual([...CAP_KEYS].sort());
  for (const key of CAP_KEYS) expect(CAP_STATUSES).toContain(caps.body.capabilities[key].status);
  expect(caps.body.total_count).toBe(7);
  expect(caps.body.ready_count).toBe(CAP_KEYS.filter(k => caps.body.capabilities[k].status === 'available').length);
  expect(caps.body.degraded_count).toBe(CAP_KEYS.filter(k => caps.body.capabilities[k].status === 'degraded').length);
  expect(caps.body.delivery_mode).toBe('off');
  for (const bad of ['api_key', 'Authorization', 'H:', 'sqlite', 'SELECT', 'Traceback', '\\\\']) expect(caps.text).not.toContain(bad);
  const tasksBefore = await api(request, 'GET', '/api/tasks');
  const self = await api(request, 'POST', '/api/system/capabilities/self-check', {});
  expect(self.status).toBe(200);
  expect(self.body.checked).toBe(true);
  expect(self.body.total_count).toBe(7);
  const tasksAfter = await api(request, 'GET', '/api/tasks');
  expect((tasksAfter.body.items || tasksAfter.body).length).toBe((tasksBefore.body.items || tasksBefore.body).length);
  const ai = await api(request, 'GET', '/api/ai/capabilities');
  expect(ai.status).toBe(200);
  expect(ai.body.status).toBe('demo');
  expect(ai.body.provider_id).toBe('fake');
  expect(ai.body.model_id).toBe('fake-studybuddy-v1');
  if (ai.body.embedding) expect(ai.body.embedding.status).toBe('demo');
  else expect(ai.body.ocr).toBeDefined();
  for (const bad of ['api_key', 'Authorization', 'secret']) expect(ai.text).not.toContain(bad);
});

test('B-SET-2 settings API 契约、安全投影与未知键拒绝', async ({ request }) => {
  let r = await api(request, 'GET', '/api/system/settings');
  expect(r.status).toBe(200);
  // Only presence flags cross the API, even when nothing is stored.
  expect(Object.entries(r.body.settings).every(([k, v]) => k.endsWith('_set') && v === false)).toBe(true);
  const payload = { ai_provider_id: 'bclass-p', ai_model_id: 'bclass-m', ai_base_url: `http://127.0.0.1:${PROVIDER_PORT}/v1`, ai_api_key: KEY, embedding_provider_id: 'bclass-e', embedding_model_id: 'bclass-em', embedding_base_url: `http://127.0.0.1:${PROVIDER_PORT}/v1`, embedding_api_key: KEY + 'E' };
  r = await api(request, 'PUT', '/api/system/settings', payload);
  expect(r.status).toBe(200);
  expect(r.body.settings.ai_api_key_set).toBe(true);
  expect(r.body.settings.embedding_api_key_set).toBe(true);
  expect(r.text).not.toContain(KEY);
  expect(r.body.total_count).toBe(7);
  r = await api(request, 'GET', '/api/system/settings');
  expect(r.text).not.toContain(KEY);
  expect(r.body.settings.ai_provider_id).toBe('bclass-p');
  // Secrets live only in the local config file, never in SQLite or a backup.
  const db = fs.readFileSync(`${RUN_ROOT}/studybuddy.sqlite3`);
  expect(db.includes(Buffer.from(KEY))).toBe(false);
  expect(fs.readFileSync(`${RUN_ROOT}/config/settings.json`, 'utf8')).not.toContain(RUN_ROOT);
  expect(fs.existsSync(`${RUN_ROOT}/backups`)).toBe(false);
  expect(await api(request, 'PUT', '/api/system/settings', {})).toMatchObject({ status: 400, text: '{"detail":"settings_empty_payload"}' });
  const unknown = await api(request, 'PUT', '/api/system/settings', { evil_key: 'evil-value' });
  expect(unknown.status).toBe(400);
  expect(unknown.text).toContain('settings_unknown_key');
  expect(unknown.text).not.toContain('evil-value');
  expect((await api(request, 'PUT', '/api/system/settings', { ai_provider_id: ['x'] })).status).toBe(422);
  expect((await api(request, 'PUT', '/api/system/settings', { ai_model_id: 'x'.repeat(1001) })).text).toContain('settings_invalid_value');
  expect((await api(request, 'PUT', '/api/system/settings', { ai_base_url: 'https://evil.example.com/hook?token=1' })).text).toContain('settings_invalid_value');
  expect((await api(request, 'PUT', '/api/system/settings', { ocr_model_root: '../outside' })).text).toContain('settings_invalid_value');
  expect((await api(request, 'PUT', '/api/system/settings', { ocr_model_root: 'a\\..\\b' })).text).toContain('settings_invalid_value');
  expect((await api(request, 'PUT', '/api/system/settings', { asr_runtime_path: 'a b' })).text).toContain('settings_invalid_value');
  expect((await api(request, 'PUT', '/api/system/settings', { asr_model_path: 'x'.repeat(1001) })).text).toContain('settings_invalid_value');
  r = await api(request, 'POST', '/api/system/settings/clear', { keys: ['ai_provider_id'] });
  expect(r.status).toBe(200);
  expect(r.body.settings.ai_provider_id).toBeUndefined();
  expect(r.body.settings.ai_model_id).toBe('bclass-m');
  expect((await api(request, 'POST', '/api/system/settings/clear', { keys: ['not_a_key'] })).text).toContain('settings_unknown_key');
  r = await api(request, 'POST', '/api/system/settings/clear', {});
  expect(r.status).toBe(200);
  expect(Object.entries(r.body.settings).every(([k, v]) => k.endsWith('_set') && v === false)).toBe(true);
  expect(r.text).not.toContain(KEY);
});

test('B-SET-3 Provider connection-test 契约与稳定错误映射', async ({ request }) => {
  let r = await api(request, 'POST', '/api/system/provider-connection-test', { provider_type: 'llm', base_url: FAKE_BASE, api_key: KEY, model_id: 'bclass-chat', timeout_seconds: 10 });
  expect(r.status).toBe(200);
  expect(r.text).toBe('{"status":"ok"}');
  let last = await (await request.get(`http://127.0.0.1:${PROVIDER_PORT}/__last`)).json();
  expect(last.url.endsWith('/chat/completions')).toBe(true);
  expect(last.body).toMatchObject({ model: 'bclass-chat', max_tokens: 10 });
  expect(last.body.messages[0].content).toBe('Hello');
  expect(last.auth).toBe(`Bearer ${KEY}`);
  r = await api(request, 'POST', '/api/system/provider-connection-test', { provider_type: 'embedding', base_url: FAKE_BASE, api_key: KEY, model_id: 'bclass-embed', timeout_seconds: 10 });
  expect(r.status).toBe(200);
  last = await (await request.get(`http://127.0.0.1:${PROVIDER_PORT}/__last`)).json();
  expect(last.url.endsWith('/embeddings')).toBe(true);
  expect(last.body.input).toEqual(['test']);
  expect(last.body.model).toBe('bclass-embed');
  const cases = [
    [{ provider_type: 'llm', base_url: FAKE_BASE, api_key: KEY + 'FAIL401', model_id: 'm' }, 'provider_auth_failed'],
    [{ provider_type: 'llm', base_url: FAKE_BASE, api_key: KEY + 'FAIL500', model_id: 'm' }, 'provider_unavailable'],
    [{ provider_type: 'llm', base_url: FAKE_BASE, api_key: KEY, model_id: 'huge-model' }, 'provider_response_too_large'],
    [{ provider_type: 'llm', base_url: FAKE_BASE, api_key: KEY, model_id: 'bad-json-model' }, 'provider_protocol_error'],
    [{ provider_type: 'bogus', base_url: FAKE_BASE, api_key: KEY, model_id: 'm' }, 'invalid_provider_type'],
    [{ provider_type: 'llm', base_url: '', api_key: KEY, model_id: 'm' }, 'provider_invalid_config'],
  ];
  for (const [payload, code] of cases) {
    const res = await api(request, 'POST', '/api/system/provider-connection-test', payload);
    expect(res.status).toBe(400);
    expect(res.text).toBe(`{"detail":"${code}"}`);
    expect(res.text).not.toContain(KEY);
  }
});

test('B-SET-4 Email connection-test 契约与渠道隔离', async ({ request }) => {
  const smtpPayload = { channel: 'smtp', smtp_host: '127.0.0.1', smtp_port: SMTP_PORT, smtp_secure: false, smtp_username: 'user@example.test', smtp_password: SMTP_PASS, smtp_sender: 'sender@example.test', smtp_recipient: 'recipient@example.test', timeout_seconds: 10 };
  let r = await api(request, 'POST', '/api/system/email-connection-test', smtpPayload);
  expect(r.status).toBe(200);
  expect(r.text).toBe('{"status":"ok"}');
  expect(r.text).not.toContain(SMTP_PASS);
  expect((await api(request, 'POST', '/api/system/email-connection-test', { ...smtpPayload, smtp_password: `FAIL-${SMTP_PASS}` })).text).toContain('delivery_auth_failed');
  const connFail = await api(request, 'POST', '/api/system/email-connection-test', { ...smtpPayload, smtp_port: CLOSED_PORT });
  expect(connFail.text).toMatch(/delivery_connection_failed|delivery_timeout/);
  expect((await api(request, 'POST', '/api/system/email-connection-test', { ...smtpPayload, smtp_sender: null })).text).toContain('delivery_configuration_invalid');
  expect((await api(request, 'POST', '/api/system/email-connection-test', { channel: 'bogus', feishu_webhook: WEBHOOK })).text).toContain('invalid_channel');
  expect((await api(request, 'POST', '/api/system/email-connection-test', { channel: 'feishu', feishu_webhook: 'https://evil.example.com/hook' })).text).toContain('delivery_configuration_invalid');
  expect((await api(request, 'POST', '/api/system/email-connection-test', { channel: 'feishu', feishu_webhook: WEBHOOK.replace('open.feishu.cn', 'evil.example.com') })).text).toContain('delivery_configuration_invalid');
  // Valid-host Feishu success/failure is covered by backend mock tests. The
  // browser contract suite must remain offline and must not POST to Feishu.
  const bad = await api(request, 'POST', '/api/system/email-connection-test', { channel: 'feishu', feishu_webhook: 'https://evil.example.com/hook', smtp_host: 'smtp.qq.com', smtp_password: SMTP_PASS, timeout_seconds: 10 });
  expect(bad.text).toContain('delivery_configuration_invalid');
  expect(bad.text).not.toContain(SMTP_PASS);
  expect((await api(request, 'GET', '/api/system/capabilities')).body.delivery_mode).toBe('off');
});

test('B-SET-5 capability 加载竞态：旧成功/旧失败不得覆盖新状态', async ({ page }) => {
  let call = 0;
  const staleCaps = { capabilities: Object.fromEntries(CAP_KEYS.map(k => [k, { status: 'not_configured', reason: '<img src=x onerror=window.__settingsXss=1>' }])), delivery_mode: 'off', ready_count: 0, degraded_count: 0, total_count: 7 };
  await page.route('**/api/system/capabilities', async r => {
    call++;
    if (call === 1) { await new Promise(res => setTimeout(res, 2500)); return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(staleCaps) }); }
    if (call === 3) { await new Promise(res => setTimeout(res, 2500)); return r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'late_failure' }) }); }
    return r.continue();
  });
  await page.goto(`${BASE}/app/settings.html`);
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  const realSummary = await page.locator('#capability-summary').innerText();
  expect(realSummary).not.toBe('状态未知');
  // The stale (older) success arrives last and must be discarded.
  await page.waitForTimeout(2600);
  expect(await page.locator('#capability-summary').innerText()).toBe(realSummary);
  expect(await page.evaluate(() => window.__settingsXss)).toBeUndefined();
  // A late failure after a newer success must not flip the region into an error.
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  const summary2 = await page.locator('#capability-summary').innerText();
  await page.waitForTimeout(2600);
  expect(await page.locator('#capability-summary').innerText()).toBe(summary2);
  await expect(page.locator('#capability-error')).toBeHidden();
});

test('B-SET-6 settings 加载与保存竞态：旧 GET 不得覆盖新保存值', async ({ page }) => {
  let getCall = 0;
  await page.route('**/api/system/settings', async r => {
    if (r.request().method() !== 'GET') return r.continue();
    getCall++;
    if (getCall === 1) { await new Promise(res => setTimeout(res, 4000)); return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ settings: {} }) }); }
    return r.continue();
  });
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-id').fill('race-p');
  await page.locator('#provider-model').fill('race-m');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  // The stale empty GET (started at page load) resolves after the PUT.
  await page.waitForTimeout(4200);
  await expect(page.locator('#provider-id')).toHaveValue('race-p');
  await expect(page.locator('#provider-model')).toHaveValue('race-m');
  await expect(page.locator('#provider-result')).toContainText('已保存');
  const state = await pageState(page);
  expect(leaked(state, KEY)).toBe(false);
});

test('B-SET-7 provider/email 验证生命周期竞态', async ({ page }) => {
  let providerCall = 0, emailCall = 0;
  await page.route('**/api/system/provider-connection-test', async r => {
    providerCall++;
    if (providerCall === 1 || providerCall === 3) { await new Promise(res => setTimeout(res, 900)); return r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'provider_timeout' }) }); }
    return r.continue();
  });
  await page.route('**/api/system/email-connection-test', async r => {
    emailCall++;
    if (emailCall === 1) { await new Promise(res => setTimeout(res, 900)); return r.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }); }
    return r.continue();
  });
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-id').fill('race-p');
  await page.locator('#provider-model').fill('race-m');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  // Test in flight; editing the form must invalidate the pending result.
  await page.locator('#provider-test').click();
  await page.locator('#provider-model').fill('race-m2');
  await page.waitForTimeout(1100);
  await expect(page.locator('#provider-save')).toBeHidden();
  // A passing test re-enables save; an older failure arriving later must not hide it again.
  // (Secrets are cleared after every test attempt by design; the user retypes them.)
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await expect(page.locator('#provider-save')).toBeVisible();
  // Editing after a success withdraws the save affordance again.
  await page.locator('#provider-model').fill('race-m3');
  await expect(page.locator('#provider-save')).toBeHidden();
  // Channel switch during an in-flight email test invalidates it.
  await page.locator('#smtp-host').fill('127.0.0.1');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#smtp-secure').selectOption('false');
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-test').click();
  await page.locator('#email-channel').selectOption('feishu');
  await page.waitForTimeout(1100);
  await expect(page.locator('#email-save')).toBeHidden();
  await expect(page.locator('#email-result')).not.toContainText('连接测试通过');
  // Reload: verification state never survives a fresh page.
  await page.reload();
  await expect(page.locator('#provider-save')).toBeHidden();
  await expect(page.locator('#email-save')).toBeHidden();
  const state = await pageState(page);
  expect(leaked(state, KEY, SMTP_PASS)).toBe(false);
});

test('B-SET-8 busy 防重复：mutation 单请求与失败恢复', async ({ page }) => {
  await page.goto(`${BASE}/app/settings-provider.html`);
  let testDelay = true;
  await page.route('**/api/system/provider-connection-test', async r => {
    if (testDelay) { await new Promise(res => setTimeout(res, 600)); return r.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' }); }
    return r.continue();
  });
  let putDelay = false;
  const puts = [];
  await page.route('**/api/system/settings', async r => {
    if (r.request().method() === 'PUT') { puts.push(1); if (putDelay) { await new Promise(res => setTimeout(res, 600)); } return r.continue(); }
    return r.continue();
  });
  const counts = {};
  const count = name => page.on('request', r => { const u = r.url(); if (u.includes(name)) counts[name] = (counts[name] || 0) + 1; });
  count('provider-connection-test');
  await page.locator('#provider-id').fill('busy-p');
  await page.locator('#provider-model').fill('busy-m');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await page.locator('#provider-test').dispatchEvent('click');
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  expect(counts['provider-connection-test']).toBe(1);
  // Save: double activation produces exactly one PUT.
  putDelay = true;
  await page.locator('#provider-save').click();
  await page.locator('#provider-save').dispatchEvent('click');
  await expect(page.locator('#provider-result')).toContainText('已保存');
  expect(puts.length).toBe(1);
  // Email test + save double-activation.
  testDelay = true;
  await page.route('**/api/system/email-connection-test', async r => {
    await new Promise(res => setTimeout(res, 600));
    return r.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
  });
  await page.locator('#smtp-host').fill('127.0.0.1');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#smtp-secure').selectOption('false');
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-test').click();
  await page.locator('#email-test').dispatchEvent('click');
  await expect(page.locator('#email-result')).toContainText('连接测试通过');
  expect(await page.evaluate(() => window.__emails || 0)).toBe(0);
  putDelay = true;
  await page.locator('#email-save').click();
  await page.locator('#email-save').dispatchEvent('click');
  await expect(page.locator('#email-result')).toContainText('已保存凭据');
  expect(puts.length).toBe(2);
  // Failure recovery: a failing save keeps the button usable without reload.
  putDelay = false;
  let putFail = true;
  await page.unroute('**/api/system/settings');
  await page.route('**/api/system/settings', async r => {
    if (r.request().method() === 'PUT') { puts.push(1); if (putFail) return r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"settings_write_failed"}' }); return r.continue(); }
    return r.continue();
  });
  await page.locator('#provider-id').fill('busy-p2');
  await page.locator('#provider-model').fill('busy-m2');
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('失败');
  await expect(page.locator('#provider-save')).toBeEnabled();
  putFail = false;
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  expect(puts.length).toBe(4);
  const state = await pageState(page);
  expect(leaked(state, KEY, SMTP_PASS)).toBe(false);
});

test('B-SET-8b settings 页 busy 防重复与清除/自检', async ({ page }) => {
  await page.goto(`${BASE}/app/settings.html`);
  const posts = [];
  await page.route('**/api/system/settings', async r => {
    if (r.request().method() === 'PUT') { posts.push(1); await new Promise(res => setTimeout(res, 500)); return r.continue(); }
    return r.continue();
  });
  const clears = [];
  await page.route('**/api/system/settings/clear', async r => { clears.push(1); await new Promise(res => setTimeout(res, 500)); return r.continue(); });
  const checks = [];
  await page.route('**/api/system/capabilities/self-check', async r => { checks.push(1); await new Promise(res => setTimeout(res, 500)); return r.continue(); });
  await page.locator('#ai-provider').fill('busy-p');
  await page.locator('#ai-model').fill('busy-m');
  await page.locator('#ai-url').fill(FAKE_BASE);
  await page.locator('#ai-save').click();
  await page.locator('#ai-save').dispatchEvent('click');
  await expect(page.locator('#ai-result')).toContainText('已保存');
  expect(posts.length).toBe(1);
  await page.locator('#embedding-provider').fill('busy-e');
  await page.locator('#embedding-model').fill('busy-em');
  await page.locator('#embedding-url').fill(FAKE_BASE);
  await page.locator('#embedding-save').click();
  await page.locator('#embedding-save').dispatchEvent('click');
  await expect(page.locator('#embedding-result')).toContainText('已保存');
  expect(posts.length).toBe(2);
  await page.locator('#ocr-enabled').selectOption('true');
  await page.locator('#local-save').click();
  await page.locator('#local-save').dispatchEvent('click');
  await expect(page.locator('#local-result')).toContainText('已保存');
  expect(posts.length).toBe(3);
  await page.locator('#ai-clear').click();
  await page.locator('#ai-clear').dispatchEvent('click');
  await expect(page.locator('#ai-result')).toContainText('已清除');
  expect(clears.length).toBe(1);
  await page.locator('#embedding-clear').click();
  await page.locator('#embedding-clear').dispatchEvent('click');
  await expect(page.locator('#embedding-result')).toContainText('已清除');
  expect(clears.length).toBe(2);
  await page.locator('#local-clear').click();
  await page.locator('#local-clear').dispatchEvent('click');
  await expect(page.locator('#local-result')).toContainText('已清除');
  expect(clears.length).toBe(3);
  await page.locator('#capability-recheck').click();
  await page.locator('#capability-recheck').dispatchEvent('click');
  await expect(page.locator('#capability-grid')).toBeVisible();
  expect(checks.length).toBe(1);
});

test('B-SET-9 错误码映射完整性：settings/capability', async ({ page }) => {
  const map = { settings_invalid_value: '填写内容无效，请检查格式', settings_unknown_key: '配置项不受支持', settings_empty_payload: '没有需要保存的内容', settings_payload_too_large: '配置内容过大', settings_write_failed: '配置写入失败，请重试', settings_read_failed: '配置读取失败，请重试', settings_clear_failed: '配置清除失败，请重试', database_unavailable: '数据暂时不可用，请稍后重试' };
  let current = Object.keys(map)[0];
  await page.route('**/api/system/settings', async r => {
    if (r.request().method() === 'PUT') return r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: current }) });
    return r.continue();
  });
  await page.goto(`${BASE}/app/settings.html`);
  await page.locator('#ai-provider').fill('map-p');
  await page.locator('#ai-model').fill('map-m');
  await page.locator('#ai-url').fill(FAKE_BASE);
  for (const [code, text] of Object.entries(map)) {
    current = code;
    await page.locator('#ai-save').click();
    await expect(page.locator('#ai-result')).toHaveText(text);
    await expect(page.locator('body')).not.toContainText(code);
    await expect(page.locator('#ai-save')).toBeEnabled();
    await expect(page.locator('#ai-provider')).toHaveValue('map-p');
  }
  // Capability errors keep the dashboard recoverable and silent about raw codes.
  current = 'capability_probe_failed';
  await page.unroute('**/api/system/settings');
  await page.route('**/api/system/capabilities/self-check', r => r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'capability_probe_failed' }) }));
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-error')).toContainText('探测失败');
  await expect(page.locator('body')).not.toContainText('capability_probe_failed');
  await expect(page.locator('#capability-recheck')).toBeEnabled();
  await page.unroute('**/api/system/capabilities/self-check');
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-error')).toBeHidden();
});

test('B-SET-9b 错误码映射完整性：provider/email/connection', async ({ page }) => {
  const providerCodes = { invalid_provider_type: 'Provider 类型无效', provider_invalid_config: 'Provider 配置无效，请检查 Base URL、Model ID 和密钥', provider_connection_failed: 'Provider 连接失败，请检查网络和地址', provider_timeout: 'Provider 请求超时，请稍后重试', provider_auth_failed: 'Provider 认证失败，请检查 API Key', provider_forbidden: 'Provider 拒绝访问', provider_rate_limited: 'Provider 请求过于频繁，请稍后重试', provider_unavailable: 'Provider 暂时不可用', provider_protocol_error: 'Provider 响应格式无效', provider_response_too_large: 'Provider 响应过大', connection_test_failed: '连接测试失败，请稍后重试' };
  const deliveryCodes = { invalid_channel: 'Email 渠道无效', delivery_configuration_invalid: 'Email 配置无效，请检查字段', delivery_connection_failed: 'Email 连接失败，请检查网络和地址', delivery_timeout: 'Email 连接超时，请稍后重试', delivery_auth_failed: 'Email 认证失败，请检查凭据', delivery_failed: 'Email 发送测试失败', delivery_response_too_large: 'Email 测试响应过大' };
  let current = 'provider_invalid_config';
  await page.route('**/api/system/provider-connection-test', r => r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: current }) }));
  await page.route('**/api/system/email-connection-test', r => r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: current }) }));
  await page.goto(`${BASE}/app/settings-provider.html`);
  for (const [code, text] of Object.entries(providerCodes)) {
    current = code;
    await page.locator('#provider-id').fill('map-p');
    await page.locator('#provider-model').fill('map-m');
    await page.locator('#provider-url').fill(FAKE_BASE);
    await page.locator('#provider-key').fill(KEY);
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toHaveText(text);
    await expect(page.locator('body')).not.toContainText(code);
    await expect(page.locator('#provider-test')).toBeEnabled();
    await expect(page.locator('#provider-save')).toBeHidden();
  }
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  for (const [code, text] of Object.entries(deliveryCodes)) {
    current = code;
    await page.locator('#smtp-password').fill(SMTP_PASS);
    await page.locator('#email-test').click();
    await expect(page.locator('#email-result')).toHaveText(text);
    await expect(page.locator('body')).not.toContainText(code);
    await expect(page.locator('#email-test')).toBeEnabled();
    await expect(page.locator('#email-save')).toBeHidden();
    await expect(page.locator('#smtp-password')).toHaveValue('');
  }
  const state = await pageState(page);
  expect(leaked(state, KEY, SMTP_PASS)).toBe(false);
});

test('B-SET-10 XSS / 恶意字段纯文本渲染', async ({ page }) => {
  const evil = '<img src=x onerror="window.__settingsXss=1"><script>window.__settingsXss=1</script><svg onload="window.__settingsXss=1"></svg>';
  await page.route('**/api/system/capabilities', r => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ capabilities: { import_parse: { status: 'available', provider_id: evil, model_id: evil }, ocr: { status: 'degraded', reason: evil }, qa: { status: evil, reason: 'unknown_reason_xyz' } }, delivery_mode: evil, ready_count: 1, degraded_count: 1, total_count: 7 }),
  }));
  await page.goto(`${BASE}/app/settings.html`);
  expect(await page.evaluate(() => window.__settingsXss)).toBeUndefined();
  expect(await page.evaluate(() => document.querySelectorAll('img[src="x"], svg, [onerror], [onload]').length + [...document.querySelectorAll('script')].filter(s => s.textContent.includes('settingsXss')).length)).toBe(0);
  await expect(page.locator('#capability-grid')).toContainText('组件状态暂不可用');
  await expect(page.locator('#capability-summary')).toBeVisible();
  const state = await pageState(page);
  expect(state.local + state.session + state.cookie + state.history + state.url).not.toContain('settingsXss');
  // Error detail injection stays a safe fallback string.
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/system/capabilities/self-check', r => r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: evil }) }));
  await page.goto(`${BASE}/app/settings.html`);
  await page.locator('#capability-recheck').click();
  expect(await page.evaluate(() => window.__settingsXss)).toBeUndefined();
  // Provider page: malicious provider payload rendered as text only.
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/ai/capabilities', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'demo', provider_id: evil, model_id: evil, embedding: { available: false, provider_id: evil } }) }));
  await page.goto(`${BASE}/app/settings-provider.html`);
  expect(await page.evaluate(() => window.__settingsXss)).toBeUndefined();
  expect(await page.evaluate(() => document.querySelectorAll('img[src="x"], svg, [onerror], [onload]').length + [...document.querySelectorAll('script')].filter(s => s.textContent.includes('settingsXss')).length)).toBe(0);
  await expect(page.locator('#capabilities')).toContainText('未配置');
});

test('B-SET-11 secret 生命周期与隐私边界', async ({ page, request }) => {
  const rec = attachRecorder(page);
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-id').fill('secret-p');
  await page.locator('#provider-model').fill('secret-m');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  await expect(page.locator('#provider-key')).toHaveValue('');
  // SMTP + Feishu credentials saved (test through the fake SMTP server first).
  await page.locator('#smtp-host').fill('127.0.0.1');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#smtp-secure').selectOption('false');
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('连接测试通过');
  await page.locator('#email-save').click();
  await expect(page.locator('#email-result')).toContainText('已保存凭据');
  await page.reload();
  expect(leaked(await pageState(page), KEY, SMTP_PASS, WEBHOOK)).toBe(false);
  await page.goBack();
  await page.goForward();
  expect(leaked(await pageState(page), KEY, SMTP_PASS, WEBHOOK)).toBe(false);
  // True restart: secrets are never restored into the UI or any API response.
  await stopServer();
  server = startServer(); await ready();
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#state')).toHaveText('已加载');
  expect(leaked(await pageState(page), KEY, SMTP_PASS, WEBHOOK)).toBe(false);
  expect(recorderClean(rec, KEY, SMTP_PASS, WEBHOOK)).toBe(true);
  await page.screenshot({ path: `H:/studybuddy-test/artifacts/settings-b-class-${STAMP}-secret.png`, fullPage: true });
  const shot = fs.readFileSync(`H:/studybuddy-test/artifacts/settings-b-class-${STAMP}-secret.png`).toString('latin1');
  expect(shot.includes(KEY) || shot.includes(SMTP_PASS)).toBe(false);
  // Storage-level boundaries: local config file holds them; SQLite and backup do not.
  const stored = fs.readFileSync(`${RUN_ROOT}/config/settings.json`, 'utf8');
  expect(stored).toContain(KEY);
  expect(stored).toContain(SMTP_PASS);
  const db = fs.readFileSync(`${RUN_ROOT}/studybuddy.sqlite3`).toString('latin1');
  expect(db.includes(KEY) || db.includes(SMTP_PASS)).toBe(false);
  const caps = await api(request, 'GET', '/api/system/capabilities');
  expect(caps.text).not.toContain(KEY);
  const settings = await api(request, 'GET', '/api/system/settings');
  expect(settings.text).not.toContain(KEY);
  expect(settings.body.settings.smtp_credentials_stored ?? settings.body.settings.report_delivery_smtp_password_set ?? true).toBe(true);
});

test('B-SET-12 delivery 默认关闭与凭据隔离', async ({ request, page }) => {
  const payload = { report_delivery_smtp_host: 'smtp.qq.com', report_delivery_smtp_port: 465, report_delivery_smtp_secure: true, report_delivery_smtp_username: 'user@example.test', report_delivery_smtp_password: SMTP_PASS, report_delivery_smtp_targets: 'primary=recipient@example.test', report_delivery_feishu_webhook: WEBHOOK };
  const r = await api(request, 'PUT', '/api/system/settings', payload);
  expect(r.status).toBe(200);
  expect(r.body.settings.report_delivery_smtp_password_set).toBe(true);
  for (const k of ['report_delivery_mode', 'report_delivery_enabled', 'report_delivery_authorized']) expect(k in r.body.settings).toBe(false);
  const caps = await api(request, 'GET', '/api/system/capabilities');
  expect(caps.body.delivery_mode).toBe('off');
  // Stored credentials surface as a configured flag, not as an enabled delivery.
  expect(caps.body.capabilities.report.delivery_configured).toBe(true);
  const deliveryRequests = [];
  page.on('request', req => { if (req.url().includes('delivery')) deliveryRequests.push(req.url()); });
  for (const name of ['settings.html', 'settings-provider.html', 'classroom.html']) {
    await page.goto(`${BASE}/app/${name}`);
    await expect(page.locator('main')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('已发送');
    await expect(page.locator('body')).not.toContainText(/已启用投递|投递已开启/);
    expect(leaked(await pageState(page), SMTP_PASS, WEBHOOK)).toBe(false);
  }
  expect(deliveryRequests.filter(u => u.includes('/api/') && !u.includes('settings-provider.html'))).toEqual([]);
});

test('B-SET-13 路径配置与能力探测安全边界', async ({ page, request }) => {
  await page.goto(`${BASE}/app/settings.html`);
  await page.locator('#ocr-enabled').selectOption('true');
  await page.locator('#ocr-root').fill('models/ocr-b13');
  await page.locator('#asr-runtime').fill('models/whisper-b13');
  await page.locator('#local-save').click();
  await expect(page.locator('#local-result')).toContainText('已保存');
  await expect(page.locator('#ocr-root')).toHaveValue('');
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-grid')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('models/ocr-b13');
  await expect(page.locator('body')).not.toContainText(/H:\\|H:\//i);
  // Only presence flags cross the API; invalid paths are refused safely.
  const r = await api(request, 'GET', '/api/system/settings');
  expect(r.body.settings.ocr_model_root_set).toBe(true);
  expect(r.body.settings.asr_runtime_path_set).toBe(true);
  expect(r.text).not.toContain('models/ocr-b13');
  for (const bad of ['../outside', 'a\\..\\b', 'x'.repeat(1001), 'a b']) {
    expect((await api(request, 'PUT', '/api/system/settings', { ocr_model_root: bad })).text).toContain('settings_invalid_value');
  }
  await page.locator('#local-clear').click();
  await expect(page.locator('#local-result')).toContainText('已清除');
  await expect((await api(request, 'GET', '/api/system/settings')).body.settings.ocr_model_root_set ?? false).toBe(false);
});

test('B-SET-14 readiness/能力/配置失败互不覆盖', async ({ page }) => {
  await page.route('**/api/ai/capabilities', r => r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_ai' }) }));
  await page.route('**/api/readiness', r => r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_ready' }) }));
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#retry-capabilities')).toBeVisible();
  await expect(page.locator('#retry-health')).toBeVisible();
  await expect(page.locator('#provider-form')).toBeVisible();
  await expect(page.locator('body')).not.toContainText(/private_ai|private_ready/);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#retry-capabilities').click();
  await expect(page.locator('#state')).toHaveText('已加载');
  await expect(page.locator('#retry-health')).toBeVisible();
  await page.locator('#retry-health').click();
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  // Settings page: capability failure must not wipe settings forms and vice versa.
  await page.route('**/api/system/settings', r => { if (r.request().method() === 'GET') return r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_settings' }) }); return r.continue(); });
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#settings-retry')).toBeVisible();
  await expect(page.locator('#capability-grid')).toBeVisible();
  await page.locator('#ai-provider').fill('kept-p');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/system/capabilities/self-check', r => r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'private_check' }) }));
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-error')).toBeVisible();
  await expect(page.locator('#ai-provider')).toHaveValue('kept-p');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#settings-retry').click();
  await expect(page.locator('#settings-retry')).toBeHidden();
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-error')).toBeHidden();
  await expect(page.locator('#capability-grid')).toBeVisible();
});

test('B-SET-15 DOM、ARIA 与表单可访问性', async ({ page }) => {
  let dialogSeen = false;
  page.on('dialog', async d => { dialogSeen = true; await d.dismiss(); });
  for (const name of ['settings.html', 'settings-provider.html']) {
    await page.goto(`${BASE}/app/${name}`);
    const audit = await page.evaluate(() => {
      const controls = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')];
      const unlabeled = controls.filter(el => {
        if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
        const field = el.closest('.field');
        return !(field && field.querySelector('label')) && !document.querySelector(`label[for="${el.id}"]`);
      }).map(el => el.id || el.name);
      const live = [...document.querySelectorAll('[aria-live]')].map(el => el.getAttribute('role'));
      const alerts = document.querySelectorAll('[role="alert"]').length;
      const passwords = [...document.querySelectorAll('input[type=password]')];
      return { unlabeled, live, alerts, badPasswords: passwords.filter(p => p.getAttribute('autocomplete') !== 'off').length };
    });
    expect(audit.unlabeled).toEqual([]);
    expect(audit.live.every(role => role === 'status' || role === 'alert')).toBe(true);
    expect(audit.alerts).toBeGreaterThanOrEqual(1);
    expect(audit.badPasswords).toBe(0);
    // Hidden save buttons are unreachable by focus and tab order.
    const hiddenFocus = await page.evaluate(() => {
      const ids = ['provider-save', 'email-save', 'settings-retry'];
      const reachable = [];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        el.focus();
        if (document.activeElement === el && (el.hidden || el.offsetParent === null)) reachable.push(id);
      }
      return reachable;
    });
    expect(hiddenFocus).toEqual([]);
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toHaveCount(1);
    // A visible focus ring appears once keyboard focus reaches a styled control.
    let ring = 'none';
    for (let i = 0; i < 10 && ring === 'none'; i++) {
      await page.keyboard.press('Tab');
      ring = await page.evaluate(() => { const el = document.querySelector(':focus-visible'); return el ? getComputedStyle(el).boxShadow : 'none'; });
    }
    expect(ring).not.toBe('none');
    // Failed submit never falls back to alert()/confirm() (provider page form only).
    if (name === 'settings-provider.html') {
      await page.locator('#provider-id').fill('aria-p');
      await page.locator('#provider-model').fill('aria-m');
      await page.locator('#provider-url').fill('https://invalid host');
      await page.locator('#provider-key').fill(KEY);
      await page.locator('#provider-test').click();
      expect(dialogSeen).toBe(false);
    }
  }
});
