// SET-1..SET-12 A-class pure user-path E2E for settings.html + settings-provider.html.
// Pure UI cases use only page interactions. Cases marked "B-element" inject faults
// via page.route and are counted separately; no route-mocked success is ever
// reported as a real provider pass. Real successes run against the deterministic
// fake provider / fake SMTP servers started below.
const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const fs = require('fs');

const STAMP = Date.now();
const RUN_ROOT = `H:/studybuddy-test/runs/settings-userpath-${STAMP}`;
const ART_ROOT = `H:/studybuddy-test/artifacts/settings-userpath-${STAMP}`;
const PORT = 8842, PROVIDER_PORT = 8942, SMTP_PORT = 8942 + 1, CLOSED_PORT = 8942 + 2;
const BASE = `http://127.0.0.1:${PORT}`;
const FAKE_BASE = `http://127.0.0.1:${PROVIDER_PORT}/v1`;
const KEY = 'TEST_SETTINGS_API_KEY_DO_NOT_LEAK_u9';
const SMTP_PASS = 'TEST_SMTP_PASSWORD_DO_NOT_LEAK_s3';
fs.mkdirSync(ART_ROOT, { recursive: true });
let server, fakeProvider, fakeSmtp;

function startServer(withFakeAI = true) {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT };
  if (withFakeAI) env.STUDYBUDDY_AI_PROVIDER = 'fake'; else delete env.STUDYBUDDY_AI_PROVIDER;
  for (const k of ['STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL', 'STUDYBUDDY_AI_API_KEY']) delete env[k];
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
function stopServer(s) { return new Promise(resolve => { const p = s || server; if (!p || p.killed) return resolve(); p.once('exit', resolve); p.kill(); if (p === server) server = null; }); }
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
function startFakeProvider() {
  return new Promise(resolve => {
    let lastBody = null;
    const srv = http.createServer((req, res) => {
      let body = ''; req.on('data', c => body += c);
      req.on('end', () => {
        if (req.url === '/__last') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(lastBody || {})); return; }
        setTimeout(() => {
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
        }, 400);
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
            const token = line.split(' ').pop() || '';
            const decoded = Buffer.from(token, 'base64').toString('utf8');
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
function countRequests(page, needle, method) { const urls = []; page.on('request', r => { if (r.url().includes(needle) && (!method || r.method() === method)) urls.push(r.url()); }); return urls; }
async function noLeak(page, secret) {
  const x = await page.evaluate(s => ({ text: document.body.innerText, html: document.documentElement.outerHTML, url: location.href, history: JSON.stringify(history.state), cookie: document.cookie, local: JSON.stringify(localStorage), session: JSON.stringify(sessionStorage) }), secret);
  return Object.values(x).every(v => !v.includes(secret));
}

test.beforeAll(async () => { fakeProvider = await startFakeProvider(); fakeSmtp = await startFakeSmtp(); });
test.afterAll(async () => { if (fakeProvider) fakeProvider.close(); if (fakeSmtp) fakeSmtp.close(); });
test.beforeEach(async () => { fs.rmSync(RUN_ROOT, { recursive: true, force: true }); server = startServer(); await ready(); });
test.afterEach(async () => { await stopServer(); });

test('SET-1 首次访问能力仪表盘：七项状态、安全文案、无自动外呼', async ({ page }) => {
  const connTests = countRequests(page, 'connection-test');
  const external = []; page.on('request', r => { if (!r.url().startsWith(BASE)) external.push(r.url()); });
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  await expect(page.locator('#capability-loading')).toBeHidden();
  await expect(page.locator('#capability-grid')).toBeVisible();
  const titles = await page.locator('#capability-grid h3').allInnerTexts();
  expect(titles).toEqual(['导入解析', '图片 OCR', '录音转写', '索引', '问答', '生成', '报告']);
  for (const badge of await page.locator('#capability-grid .badge').allInnerTexts()) expect(['可用', '降级可用', '未配置', '未安装', '已关闭']).toContain(badge);
  await expect(page.locator('#capability-grid')).toContainText('演示模式');
  await expect(page.locator('body')).not.toContainText(/not_installed|not_configured|available/i);
  await expect(page.locator('body')).not.toContainText(/api[_-]?key|H:\\|H:\//i);
  await expect(page.locator('body')).not.toContainText(/sqlite|SELECT|Traceback|token/i);
  await expect(page.locator('#capability-recheck')).toBeVisible();
  await expect(page.locator('#capability-refresh')).toBeVisible();
  expect(connTests).toEqual([]);
  expect(external).toEqual([]);
});

test('SET-2 settings-provider 首次状态：先测后存边界与就绪状态', async ({ page }) => {
  const connTests = countRequests(page, 'connection-test');
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#provider-form')).toBeVisible();
  await expect(page.locator('#email-form')).toBeVisible();
  await expect(page.locator('#provider-save')).toBeHidden();
  await expect(page.locator('#email-save')).toBeHidden();
  await expect(page.locator('body')).toContainText('先测后存');
  await expect(page.locator('body')).toContainText('测试不改变当前配置');
  await expect(page.locator('body')).toContainText('不发送学习材料');
  await expect(page.locator('body')).toContainText('不等于开启投递');
  await expect(page.locator('#state')).toHaveText('已加载');
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  expect(await page.locator('input[type=password]').evaluateAll(xs => xs.every(x => x.value === ''))).toBe(true);
  expect(connTests).toEqual([]);
});

test('SET-3 fake LLM 测试并保存：busy 防重复、secret 清理、即时生效', async ({ page }) => {
  // Run without the STUDYBUDDY_AI_PROVIDER=fake demo lock so the saved LLM
  // configuration takes effect and the capability card reflects it.
  await stopServer();
  server = startServer(false); await ready();
  const connTests = countRequests(page, 'provider-connection-test');
  const puts = countRequests(page, '/api/system/settings', 'PUT');
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-id').fill('synthetic-llm');
  await page.locator('#provider-model').fill('synthetic-chat');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-test')).toBeDisabled();
  await page.locator('#provider-test').dispatchEvent('click');
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  expect(connTests).toHaveLength(1);
  await expect(page.locator('#provider-save')).toBeVisible();
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-save')).toBeDisabled();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  expect(puts).toHaveLength(1);
  await expect(page.locator('#provider-save')).toBeHidden();
  await expect(page.locator('#provider-key')).toHaveValue('');
  await expect(page.locator('#capabilities')).toContainText('synthetic-llm');
  expect(await noLeak(page, KEY)).toBe(true);
  await page.locator('#provider-model').fill('edited-model');
  await expect(page.locator('#provider-save')).toBeHidden();
});

test('SET-4 fake Embedding 测试并保存：settings 页真实变化、持久化、不进 SQLite', async ({ page }) => {
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-type').selectOption('embedding');
  await page.locator('#provider-id').fill('synthetic-embed');
  await page.locator('#provider-model').fill('synthetic-embedding');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  await expect(page.locator('#provider-key')).toHaveValue('');
  expect(await noLeak(page, KEY)).toBe(true);
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  await expect(page.locator('#capability-grid')).toContainText('可用');
  await page.reload();
  await expect(page.locator('#embedding-key')).toHaveAttribute('placeholder', /已保存/);
  // True restart: config persists, secret stays a presence flag, SQLite stays clean.
  await stopServer();
  server = startServer(); await ready();
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#embedding-provider')).toHaveValue('synthetic-embed');
  await expect(page.locator('#embedding-key')).toHaveAttribute('placeholder', /已保存/);
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  const db = fs.readFileSync(`${RUN_ROOT}/studybuddy.sqlite3`);
  expect(db.includes(Buffer.from(KEY))).toBe(false);
  expect(fs.readFileSync(`${RUN_ROOT}/config/settings.json`, 'utf8')).toContain(KEY);
});

test('SET-5 OCR/ASR 本机覆盖：保存、不回显路径、清除恢复', async ({ page }) => {
  const puts = countRequests(page, '/api/system/settings', 'PUT');
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#ocr-enabled')).toHaveValue('');
  await page.locator('#ocr-enabled').selectOption('false');
  await page.locator('#ocr-root').fill(`${RUN_ROOT}/fixture-ocr`);
  await page.locator('#local-save').click();
  await page.locator('#local-save').dispatchEvent('click');
  await expect(page.locator('#local-result')).toContainText('已保存');
  // The duplicate dispatch must not produce a second PUT.
  expect(puts).toHaveLength(1);
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#ocr-enabled')).toHaveValue('false');
  await expect(page.locator('#ocr-root')).toHaveAttribute('placeholder', /已设置/);
  await expect(page.locator('body')).not.toContainText('fixture-ocr');
  await expect(page.locator('body')).not.toContainText(/H:\\|H:\//i);
  await page.reload();
  await expect(page.locator('#ocr-enabled')).toHaveValue('false');
  await expect(page.locator('#ocr-root')).toHaveAttribute('placeholder', /已设置/);
  for (const badge of await page.locator('#capability-grid .badge').allInnerTexts()) expect(['可用', '降级可用', '未配置', '未安装', '已关闭']).toContain(badge);
  await page.locator('#local-clear').click();
  await expect(page.locator('#local-clear')).toBeDisabled();
  await expect(page.locator('#local-result')).toContainText('已清除');
  await expect(page.locator('#ocr-enabled')).toHaveValue('');
  await expect(page.locator('#ocr-root')).toHaveAttribute('placeholder', /仅当自动探测失败时填写/);
});

test('SET-6 保存/清除后即时生效与刷新恢复', async ({ page }) => {
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-type').selectOption('embedding');
  await page.locator('#provider-id').fill('synthetic-embed');
  await page.locator('#provider-model').fill('synthetic-embedding');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  const taskPosts = countRequests(page, '/api/tasks', 'POST');
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-recheck')).toBeDisabled();
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  await expect(page.locator('#embedding-provider')).toHaveValue('synthetic-embed');
  expect(taskPosts.filter(u => u.includes('/api/tasks'))).toEqual([]);
  await page.locator('#embedding-clear').click();
  await expect(page.locator('#embedding-result')).toContainText('已清除');
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-grid')).not.toContainText('synthetic-embed');
  // Under the demo lock, clearing returns to the deterministic fake embedding.
  await expect(page.locator('#capability-grid')).toContainText('fake-embedding-v1');
});

test('SET-7 Provider/Email 失败恢复（含真实失败与 B 类 route 注入）', async ({ page }) => {
  await page.goto(`${BASE}/app/settings-provider.html`);
  async function fill(providerType, model, key) {
    await page.locator('#provider-type').selectOption(providerType);
    await page.locator('#provider-id').fill('synthetic-p');
    await page.locator('#provider-model').fill(model || 'synthetic-chat');
    await page.locator('#provider-url').fill(FAKE_BASE);
    await page.locator('#provider-key').fill(key || KEY);
  }
  // Real failures through the fake provider.
  for (const [key, code] of [[`${KEY}FAIL401`, 'provider_auth_failed'], [`${KEY}FAIL500`, 'provider_unavailable']]) {
    await fill('llm', 'synthetic-chat', key);
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toBeVisible();
    await expect(page.locator('#provider-result')).not.toContainText(code);
    await expect(page.locator('#provider-result')).not.toContainText(/Traceback|H:\//i);
    await expect(page.locator('#provider-test')).toBeEnabled();
    await expect(page.locator('#provider-save')).toBeHidden();
  }
  await fill('llm', 'huge-model');
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('过大');
  await expect(page.locator('#provider-test')).toBeEnabled();
  await fill('llm', 'bad-json-model');
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('格式无效');
  // Real successes (LLM + Embedding) still reachable after failures.
  await fill('llm');
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await expect(page.locator('#provider-save')).toBeVisible();
  await fill('embedding', 'synthetic-embedding');
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  // Route-injected failures (B-element): safe copy, recoverable buttons, dashboard intact.
  for (const code of ['provider_invalid_config', 'provider_timeout', 'provider_connection_failed', 'provider_protocol_error', 'provider_response_too_large']) {
    await page.route('**/api/system/provider-connection-test', r => r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: code }) }));
    await fill('llm');
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(code);
    await expect(page.locator('#provider-test')).toBeEnabled();
    await expect(page.locator('#provider-save')).toBeHidden();
    await expect(page.locator('#capabilities')).toBeVisible();
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
  // Email: real SMTP success + real auth/connection failures via the fake SMTP server.
  await page.locator('#smtp-host').fill('127.0.0.1');
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#smtp-secure').selectOption('false');
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('连接测试通过');
  await expect(page.locator('#email-save')).toBeVisible();
  await page.locator('#smtp-password').fill(`FAIL-${SMTP_PASS}`);
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('认证失败');
  await page.locator('#smtp-host').fill('');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('无效');
  // Feishu webhook failure via route injection (B-element; no real network).
  await page.route('**/api/system/email-connection-test', r => r.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'delivery_configuration_invalid' }) }));
  await page.locator('#email-channel').selectOption('feishu');
  await page.locator('#feishu-webhook').fill('https://open.feishu.cn/hook/synthetic');
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('无效');
  await expect(page.locator('body')).not.toContainText('delivery_configuration_invalid');
  await expect(page.locator('#email-test')).toBeEnabled();
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('SET-8 SMTP/Feishu 渠道切换、secret 清理与保存边界', async ({ page }) => {
  const connTests = countRequests(page, 'email-connection-test');
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#smtp-host').fill('127.0.0.1');
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-channel').selectOption('feishu');
  await expect(page.locator('#smtp-fields')).toBeHidden();
  await expect(page.locator('#feishu-fields')).toBeVisible();
  await expect(page.locator('#smtp-password')).toHaveValue('');
  await expect(page.locator('#email-save')).toBeHidden();
  await expect(page.locator('#feishu-webhook')).toHaveAttribute('type', 'password');
  await page.locator('#feishu-webhook').fill(`https://open.feishu.cn/hook/${SMTP_PASS}`);
  await page.locator('#email-channel').selectOption('smtp');
  await expect(page.locator('#feishu-webhook')).toHaveValue('');
  await expect(page.locator('#smtp-password')).toHaveValue('');
  await expect(page.locator('#email-save')).toBeHidden();
  // Real SMTP test + save (no learning material in payload; delivery stays off).
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#smtp-port').fill(String(SMTP_PORT));
  await page.locator('#smtp-secure').selectOption('false');
  await page.locator('#email-test').click();
  await expect(page.locator('#email-result')).toContainText('连接测试通过');
  expect(connTests).toHaveLength(1);
  await page.locator('#email-save').click();
  await expect(page.locator('#email-result')).toContainText('已保存凭据');
  await expect(page.locator('#email-result')).toContainText('仍需单次授权');
  await expect(page.locator('#smtp-password')).toHaveValue('');
  expect(await noLeak(page, SMTP_PASS)).toBe(true);
  await page.reload();
  await expect(page.locator('#smtp-password')).toHaveValue('');
  expect(await noLeak(page, SMTP_PASS)).toBe(true);
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-summary')).toContainText('报告投递：已关闭');
});

test('SET-9 剪贴板环境变量：成功/拒绝、不触发测试或保存、secret 清理', async ({ page }) => {
  const connTests = countRequests(page, 'connection-test');
  const puts = countRequests(page, '/api/system/settings');
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, 'clipboard', { configurable: true, get: () => ({ writeText: async t => { window.__clip = t; } }) }); });
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-id').fill('synthetic-llm');
  await page.locator('#provider-model').fill('synthetic-chat');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-copy').click();
  await expect(page.locator('#provider-result')).toContainText('已复制');
  const clip = await page.evaluate(() => window.__clip);
  expect(clip).toContain('STUDYBUDDY_AI_PROVIDER=synthetic-llm');
  expect(clip).toContain(`STUDYBUDDY_AI_API_KEY=${KEY}`);
  expect(connTests).toEqual([]); expect(puts).toEqual([]);
  await expect(page.locator('#provider-key')).toHaveValue('');
  expect(await noLeak(page, KEY)).toBe(true);
  await page.locator('#provider-key').fill(KEY);
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, 'clipboard', { configurable: true, get: () => ({ writeText: async () => { throw new Error('denied'); } }) }); });
  await page.reload();
  await page.locator('#provider-id').fill('synthetic-llm');
  await page.locator('#provider-model').fill('synthetic-chat');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-copy').click();
  await expect(page.locator('#provider-result')).toContainText('无法访问剪贴板');
  await expect(page.locator('body')).not.toContainText('denied');
  await expect(page.locator('#provider-key')).toHaveValue('');
  expect(await noLeak(page, KEY)).toBe(true);
  // Email clipboard: SMTP lines and Feishu webhook line, both success and rejection.
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, 'clipboard', { configurable: true, get: () => ({ writeText: async t => { window.__clip2 = t; } }) }); });
  await page.reload();
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-copy').click();
  await expect(page.locator('#email-result')).toContainText('已复制');
  expect(await page.evaluate(() => window.__clip2)).toContain(`STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD=${SMTP_PASS}`);
  await expect(page.locator('#smtp-password')).toHaveValue('');
  expect(await noLeak(page, SMTP_PASS)).toBe(true);
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, 'clipboard', { configurable: true, get: () => ({ writeText: async () => { throw new Error('denied'); } }) }); });
  await page.reload();
  await page.locator('#smtp-username').fill('user@example.test');
  await page.locator('#smtp-password').fill(SMTP_PASS);
  await page.locator('#smtp-sender').fill('sender@example.test');
  await page.locator('#smtp-recipient').fill('recipient@example.test');
  await page.locator('#email-copy').click();
  await expect(page.locator('#email-result')).toContainText('无法访问剪贴板');
  await expect(page.locator('#smtp-password')).toHaveValue('');
  expect(await noLeak(page, SMTP_PASS)).toBe(true);
});

test('SET-10 五档响应式、键盘与焦点（截图入独立 artifact）', async ({ page }) => {
  await page.goto(`${BASE}/app/settings.html`);
  for (const [w, h] of [[1920, 1080], [1280, 800], [768, 1024], [540, 800], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    for (const box of [await page.locator('#ai-save').boundingBox(), await page.locator('#capability-refresh').boundingBox()]) {
      expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(w);
    }
    await page.screenshot({ path: `${ART_ROOT}/settings-${w}x${h}.png`, fullPage: true });
  }
  await page.goto(`${BASE}/app/settings-provider.html`);
  for (const [w, h] of [[1920, 1080], [1280, 800], [768, 1024], [540, 800], [390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: `${ART_ROOT}/settings-provider-${w}x${h}.png`, fullPage: true });
  }
  // Keyboard: focus-visible, Enter submits the provider form, hidden controls stay out of tab order.
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.locator('#email-channel').selectOption('feishu');
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  for (let i = 0; i < 30; i++) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(() => {
      const el = document.activeElement;
      return el && (el.closest('#smtp-fields') || el.id === 'provider-save' || el.id === 'email-save');
    });
    expect(inside).toBeFalsy();
  }
  const posts = countRequests(page, 'provider-connection-test');
  await page.locator('#provider-id').fill('synthetic-llm');
  await page.locator('#provider-model').fill('synthetic-chat');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-model').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  expect(posts).toHaveLength(1);
});

test('SET-11 刷新、返回、跨页与真重启持久化', async ({ page }) => {
  const connTests = countRequests(page, 'connection-test');
  await page.goto(`${BASE}/app/settings-provider.html`);
  await page.locator('#provider-type').selectOption('embedding');
  await page.locator('#provider-id').fill('synthetic-embed');
  await page.locator('#provider-model').fill('synthetic-embedding');
  await page.locator('#provider-url').fill(FAKE_BASE);
  await page.locator('#provider-key').fill(KEY);
  await page.locator('#provider-test').click();
  await expect(page.locator('#provider-result')).toContainText('连接测试通过');
  await page.locator('#provider-save').click();
  await expect(page.locator('#provider-result')).toContainText('已保存');
  const connTestsAfterSave = connTests.length;
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  await page.reload();
  await expect(page.locator('#embedding-provider')).toHaveValue('synthetic-embed');
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#capabilities')).toContainText('synthetic-embed');
  await page.goBack();
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  await page.goto(`${BASE}/app/tasks.html`);
  await expect(page.locator('#state')).toBeVisible();
  await page.goBack();
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  expect(await noLeak(page, KEY)).toBe(true);
  // True restart: process exit awaited, config persists, nothing auto-fires.
  await stopServer();
  server = startServer(); await ready();
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#capabilities')).toContainText('synthetic-embed');
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  expect(await page.locator('input[type=password]').evaluateAll(xs => xs.every(x => !x.value))).toBe(true);
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-grid')).toContainText('synthetic-embed');
  await expect(page.locator('#capability-summary')).toContainText('报告投递：已关闭');
  // No additional connection test fired by navigation or restart.
  expect(connTests.length).toBe(connTestsAfterSave);
});

test('SET-12 缺失/失败状态边界（含 B 类 route 注入）', async ({ page }) => {
  // Capabilities failure: error state + retry, forms untouched.
  await page.route('**/api/system/capabilities', r => r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'private_cap_error', path: 'H:/secret' }) }));
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#capability-summary')).toHaveText('状态未知');
  await expect(page.locator('#capability-error')).toContainText('能力状态加载失败');
  await expect(page.locator('body')).not.toContainText('private_cap_error');
  await expect(page.locator('body')).not.toContainText('H:/secret');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#capability-refresh').click();
  await expect(page.locator('#capability-grid')).toBeVisible();
  // Settings read failure: independent retry button; capability area unaffected.
  await page.route('**/api/system/settings', r => { if (r.request().method() === 'GET') return r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'settings_read_failed' }) }); return r.continue(); });
  await page.reload();
  await expect(page.locator('#settings-retry')).toBeVisible();
  await expect(page.locator('#capability-grid')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('settings_read_failed');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#settings-retry').click();
  await expect(page.locator('#settings-retry')).toBeHidden();
  await expect(page.locator('#ai-result')).toBeHidden();
  // Capability failure must not wipe filled forms; self-check failure recovers.
  await page.locator('#ai-provider').fill('form-kept');
  await page.route('**/api/system/capabilities/self-check', r => r.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'capability_probe_failed' }) }));
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-error')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('capability_probe_failed');
  await expect(page.locator('#ai-provider')).toHaveValue('form-kept');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#capability-recheck').click();
  await expect(page.locator('#capability-grid')).toBeVisible();
  // Unknown status/reason and missing items: safe fallback text, no XSS, no crash.
  await page.route('**/api/system/capabilities', r => r.fulfill({
    status: 200, contentType: 'application/json',
    body: JSON.stringify({ capabilities: { import_parse: { status: 'weird', reason: '<img src=x onerror="window.__settingsXss=1">' }, ocr: { status: 'available' }, qa: { status: 'available', provider_id: 'fake', model_id: 'fake-studybuddy-v1', source: 'demo' } }, delivery_mode: 'off', ready_count: 2, degraded_count: 0, total_count: 7 }),
  }));
  await page.reload();
  await expect(page.locator('#capability-summary')).not.toContainText(/正在探测/);
  await expect(page.locator('#capability-grid')).toContainText('组件状态暂不可用');
  const badges = await page.locator('#capability-grid .badge').allInnerTexts();
  for (const badge of badges) expect(['可用', '降级可用', '未配置', '未安装', '已关闭']).toContain(badge);
  expect(await page.evaluate(() => window.__settingsXss)).toBeUndefined();
  expect(await page.locator('#capability-grid img').count()).toBe(0);
  // Provider page: readiness failure gets its own retry without touching capabilities.
  await page.route('**/api/readiness', r => r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_ready' }) }));
  await page.goto(`${BASE}/app/settings-provider.html`);
  await expect(page.locator('#retry-health')).toBeVisible();
  await expect(page.locator('#health-status')).toContainText('暂不可用');
  await expect(page.locator('body')).not.toContainText('private_ready');
  await expect(page.locator('#state')).toHaveText('已加载');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#retry-health').click();
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  // Provider capability failure gets its own retry; health area independent.
  await page.route('**/api/ai/capabilities', r => r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'private_ai' }) }));
  await page.reload();
  await expect(page.locator('#retry-capabilities')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('private_ai');
  await expect(page.locator('#health-status')).toContainText('系统就绪');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.locator('#retry-capabilities').click();
  await expect(page.locator('#state')).toHaveText('已加载');
  await expect(page.locator('#retry-capabilities')).toBeHidden();
});
