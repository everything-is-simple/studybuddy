const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = `H:/studybuddy-test/runs/python-fixture-ui-${Date.now()}`;
const FIXTURES = `H:/studybuddy-test/fixtures/python-fixture-ui`;
const BASE_PORT = 8861;
const PROVIDER_OK_PORT = 8957;
const PROVIDER_FAIL_PORT = 8958;
const SMTP_PORT = 8959;
const BASE = `http://127.0.0.1:${BASE_PORT}`;
const PROVIDER_OK_BASE = `http://127.0.0.1:${PROVIDER_OK_PORT}/v1`;
const PROVIDER_FAIL_BASE = `http://127.0.0.1:${PROVIDER_FAIL_PORT}/v1`;
const PYTHON = 'C:/miniconda/py310/python.exe';
const providerCode = String.raw`
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import sys
fail = len(sys.argv) > 2 and sys.argv[2] == 'fail'
class H(BaseHTTPRequestHandler):
    def _send(self, code, body=b'', content_type='application/json'):
        self.send_response(code); self.send_header('Content-Type', content_type); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0')); self.rfile.read(length)
        if fail:
            self._send(500, b'{"error":"synthetic unavailable"}'); return
        if self.path.endswith('/chat/completions'):
            self._send(200, b'{"choices":[{"message":{"content":"ok"}}]}'); return
        if self.path.endswith('/embeddings'):
            self._send(200, b'{"data":[{"embedding":[0.1,0.2]}]}'); return
        self._send(404, b'{}')
    def log_message(self, *args): pass
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
`;
const smtpCode = `
import socketserver, sys
class H(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 studybuddy-test ESMTP\\r\\n')
        while True:
            line = self.rfile.readline()
            if not line: return
            cmd = line.decode('ascii', 'ignore').strip().upper()
            if cmd.startswith(('EHLO', 'HELO')): self.wfile.write(b'250-studybuddy\\r\\n250 AUTH PLAIN\\r\\n')
            elif cmd.startswith('MAIL FROM') or cmd.startswith('RCPT TO'): self.wfile.write(b'250 OK\\r\\n')
            elif cmd.startswith('DATA'):
                self.wfile.write(b'354 End data with <CR><LF>.<CR><LF>\\r\\n')
                while self.rfile.readline().strip() != b'.': pass
                self.wfile.write(b'250 queued\\r\\n')
            elif cmd.startswith('QUIT'): self.wfile.write(b'221 bye\\r\\n'); return
            else: self.wfile.write(b'250 OK\\r\\n')
class S(socketserver.ThreadingTCPServer): allow_reuse_address = True
S(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
`;
let app, provider, failProvider, smtp;

function startApp(extra = {}) {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, ...extra };
  for (const key of ['STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL', 'STUDYBUDDY_AI_API_KEY']) delete env[key];
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BASE_PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
function startPython(code, port, ...args) { return spawn(PYTHON, ['-u', '-c', code, String(port), ...args], { stdio: 'ignore', windowsHide: true }); }
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
function stop(child) { return new Promise(resolve => { if (!child || child.killed) return resolve(); child.once('exit', resolve); child.kill(); setTimeout(resolve, 3000); }); }
async function runTasks(envExtra) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake', ...envExtra };
    const child = spawn(PYTHON, ['-m', 'app', 'run-tasks', '--data-root', ROOT, '--once'], { cwd: 'H:/studybuddy/backend', env, windowsHide: true });
    let stdout = '', stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; }); child.stderr.on('data', chunk => { stderr += chunk; });
    child.once('error', reject); child.once('exit', code => { if (code) reject(new Error(stderr || stdout)); else resolve(JSON.parse(stdout)); });
  });
}
async function importText(page, name) {
  fs.mkdirSync(FIXTURES, { recursive: true });
  const file = path.join(FIXTURES, name);
  fs.writeFileSync(file, 'StudyBuddy Python fixture material for indexing.');
  await page.goto(`${BASE}/app/materials.html`);
  await page.setInputFiles('#file-input', file);
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1', { timeout: 30000 });
  await page.locator('#items li', { hasText: name }).getByRole('button', { name: /详情/ }).click();
  await page.waitForURL(/material-detail\.html\?material=/);
  await expect(page.locator('#state')).toHaveText('材料已加载');
}

test.describe.serial('Python fixture settings and task user paths', () => {
  test.beforeAll(async () => {
    fs.rmSync(ROOT, { recursive: true, force: true });
    fs.mkdirSync(ROOT, { recursive: true });
    provider = startPython(providerCode, PROVIDER_OK_PORT);
    failProvider = startPython(providerCode, PROVIDER_FAIL_PORT, 'fail');
    smtp = startPython(smtpCode, SMTP_PORT);
    app = startApp({ STUDYBUDDY_AI_PROVIDER: 'fake' });
    await ready();
  });
  test.afterAll(async () => { await stop(app); await stop(provider); await stop(failProvider); await stop(smtp); });

  test('settings: provider LLM and embedding success, save, secret clearing', async ({ page }) => {
    await page.goto(`${BASE}/app/settings-provider.html`);
    await page.locator('#provider-id').fill('python-llm');
    await page.locator('#provider-model').fill('python-chat');
    await page.locator('#provider-url').fill(PROVIDER_OK_BASE);
    await page.locator('#provider-key').fill('PYTHON_FIXTURE_SECRET');
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toContainText('连接测试通过', { timeout: 10000 });
    await expect(page.locator('#provider-save')).toBeVisible();
    await page.locator('#provider-save').click();
    await expect(page.locator('#provider-result')).toContainText('已保存', { timeout: 10000 });
    await expect(page.locator('#provider-key')).toHaveValue('');
    await expect(page.locator('body')).not.toContainText('PYTHON_FIXTURE_SECRET');

    await page.locator('#provider-type').selectOption('embedding');
    await page.locator('#provider-id').fill('python-embedding');
    await page.locator('#provider-model').fill('python-embedding-v1');
    await page.locator('#provider-url').fill(PROVIDER_OK_BASE);
    await page.locator('#provider-key').fill('PYTHON_EMBED_SECRET');
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toContainText('连接测试通过', { timeout: 10000 });
    await page.locator('#provider-save').click();
    await expect(page.locator('#provider-result')).toContainText('已保存', { timeout: 10000 });
    await expect(page.locator('#provider-key')).toHaveValue('');
  });

  test('settings: SMTP success and provider failure recovery', async ({ page }) => {
    await page.goto(`${BASE}/app/settings-provider.html`);
    await page.locator('#smtp-host').fill('127.0.0.1');
    await page.locator('#smtp-port').fill(String(SMTP_PORT));
    await page.locator('#smtp-secure').selectOption('false');
    await page.locator('#smtp-sender').fill('sender@example.test');
    await page.locator('#smtp-recipient').fill('recipient@example.test');
    await page.locator('#email-test').click();
    await expect(page.locator('#email-result')).toContainText('连接测试通过', { timeout: 10000 });
    await page.locator('#email-save').click();
    await expect(page.locator('#email-result')).toContainText('已保存凭据', { timeout: 10000 });

    await page.locator('#provider-type').selectOption('llm');
    await page.locator('#provider-id').fill('python-fail');
    await page.locator('#provider-model').fill('python-chat');
    await page.locator('#provider-url').fill(PROVIDER_FAIL_BASE);
    await page.locator('#provider-key').fill('PYTHON_FAIL_SECRET');
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toContainText('Provider 暂时不可用', { timeout: 10000 });
    await page.locator('#provider-url').fill(PROVIDER_OK_BASE);
    await page.locator('#provider-key').fill('PYTHON_FAIL_SECRET');
    await page.locator('#provider-test').click();
    await expect(page.locator('#provider-result')).toContainText('连接测试通过', { timeout: 10000 });
  });

  test('tasks: failed embedding task shows safe message and retries to success', async ({ page }) => {
    const embeddingEnv = { STUDYBUDDY_EMBEDDING_PROVIDER: 'python-embedding', STUDYBUDDY_EMBEDDING_MODEL: 'python-embedding-v1', STUDYBUDDY_EMBEDDING_BASE_URL: PROVIDER_FAIL_BASE, STUDYBUDDY_EMBEDDING_API_KEY: 'PYTHON_TASK_SECRET' };
    await stop(app); app = startApp({ STUDYBUDDY_AI_PROVIDER: 'fake', ...embeddingEnv }); await ready();
    await importText(page, 'python-task.txt');
    await page.getByRole('button', { name: '加入索引任务' }).click();
    await expect(page.locator('#index-status')).toContainText('索引任务已加入队列', { timeout: 10000 });
    const taskLink = await page.getByRole('link', { name: '查看索引任务' }).getAttribute('href');
    await stop(app); await runTasks(embeddingEnv); app = startApp({ STUDYBUDDY_AI_PROVIDER: 'fake', ...embeddingEnv }); await ready();
    await page.goto(`${BASE}${taskLink}`);
    await expect(page.locator('#task-detail')).toContainText('失败', { timeout: 10000 });
    await expect(page.locator('#task-detail')).toContainText('索引服务暂不可用，请重试');
    page.once('dialog', dialog => dialog.accept());
    await page.locator('[data-action="retry"]').click();
    await expect(page.locator('#detail-notice')).toContainText('已加入重试队列', { timeout: 10000 });
    const successEmbeddingEnv = { ...embeddingEnv, STUDYBUDDY_EMBEDDING_BASE_URL: PROVIDER_OK_BASE };
    await stop(app); await runTasks(successEmbeddingEnv); app = startApp({ STUDYBUDDY_AI_PROVIDER: 'fake', ...successEmbeddingEnv }); await ready();
    await page.goto(`${BASE}${taskLink}`);
    await expect(page.locator('#task-detail')).toContainText('已成功', { timeout: 10000 });
  });
});
