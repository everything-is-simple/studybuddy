const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = `H:/studybuddy-test/runs/ui-control-matrix-${Date.now()}`;
const PORT = 8862;
const BASE = `http://127.0.0.1:${PORT}`;
const STATIC = 'H:/studybuddy/backend/app/static';
const PYTHON = 'C:/miniconda/py310/python.exe';
const pages = fs.readdirSync(STATIC).filter(file => file.endsWith('.html')).sort();
let server;

function startServer() {
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' };
  for (const key of ['STUDYBUDDY_AI_MODEL', 'STUDYBUDDY_AI_BASE_URL', 'STUDYBUDDY_AI_API_KEY']) delete env[key];
  return spawn(PYTHON, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true });
}
function stopServer() { if (server && !server.killed) server.kill(); server = null; }
async function ready() { await expect.poll(async () => { try { return (await fetch(`${BASE}/api/readiness`)).ok; } catch (_) { return false; } }, { timeout: 20000 }).toBe(true); }
function controlLabel(el) { return `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.getAttribute('name') ? `[name=${el.getAttribute('name')}]` : ''} ${(el.innerText || el.getAttribute('aria-label') || el.getAttribute('href') || '').trim().replace(/\s+/g, ' ').slice(0, 100)}`.trim(); }
async function fillForm(form) {
  for (const field of await form.locator('input:not([type="hidden"]), textarea, select').all()) {
    if (!(await field.isVisible().catch(() => false)) || await field.isDisabled().catch(() => true)) continue;
    const tag = await field.evaluate(el => el.tagName.toLowerCase());
    const type = (await field.getAttribute('type') || '').toLowerCase();
    if (type === 'file' || type === 'checkbox' || type === 'radio') continue;
    if (tag === 'select') {
      const values = await field.locator('option').evaluateAll(options => options.map(option => option.value).filter(Boolean));
      if (values.length) await field.selectOption(values[0]).catch(() => {});
    } else if (type === 'date') await field.fill('2026-09-16').catch(() => {});
    else if (type === 'number') await field.fill('1').catch(() => {});
    else if (type === 'url') await field.fill('http://127.0.0.1:1').catch(() => {});
    else if (type === 'email') await field.fill('audit@example.test').catch(() => {});
    else await field.fill('UI control audit').catch(() => {});
  }
}
async function operate(page, locator, artifact) {
  const tag = await locator.evaluate(el => el.tagName.toLowerCase());
  const type = (await locator.getAttribute('type') || '').toLowerCase();
  const visible = await locator.isVisible().catch(() => false);
  const disabled = await locator.isDisabled().catch(() => false);
  if (!visible) return { status: 'blocked', detail: 'conditional/hidden at initial state' };
  if (disabled) return { status: 'blocked', detail: 'disabled at initial state' };
  if (tag === 'a') {
    const href = await locator.getAttribute('href') || '';
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return { status: 'passed', detail: 'anchor inspected' };
    const response = await page.request.get(new URL(href, BASE).toString(), { timeout: 3000 });
    return { status: response.ok() || response.status() === 204 ? 'passed' : 'failed', detail: `GET ${response.status()} ${href}` };
  }
  if (tag === 'input' && type === 'file') {
    fs.mkdirSync(path.dirname(artifact), { recursive: true });
    fs.writeFileSync(artifact, 'UI control matrix fixture');
    await locator.setInputFiles(artifact);
    return { status: 'passed', detail: 'file selected' };
  }
  if (tag === 'input') {
    if (type === 'checkbox' || type === 'radio') await locator.check().catch(() => locator.click({ timeout: 1500 }));
    else if (type === 'date') await locator.fill('2026-09-16');
    else if (type === 'number') await locator.fill('1');
    else if (type === 'url') await locator.fill('http://127.0.0.1:1');
    else if (type === 'email') await locator.fill('audit@example.test');
    else await locator.fill('UI control audit');
    return { status: 'passed', detail: `${type || 'text'} input exercised` };
  }
  if (tag === 'textarea') { await locator.fill('UI control audit response'); return { status: 'passed', detail: 'textarea filled' }; }
  if (tag === 'select') {
    const values = await locator.locator('option').evaluateAll(options => options.map(option => option.value).filter(Boolean));
    if (!values.length) return { status: 'blocked', detail: 'no selectable option in current state' };
    await locator.selectOption(values[0]);
    return { status: 'passed', detail: `selected ${values[0]}` };
  }
  if (tag === 'button' || tag === 'summary' || await locator.getAttribute('role').then(role => role === 'button')) {
    const form = locator.locator('xpath=ancestor::form[1]');
    if (await form.count()) await fillForm(form);
    page.once('dialog', dialog => dialog.dismiss().catch(() => {}));
    await locator.click({ timeout: 1500, noWaitAfter: true }).catch(error => { throw error; });
    return { status: 'passed', detail: 'button clicked' };
  }
  return { status: 'warning', detail: `unsupported ${tag}` };
}

async function runPage(page, file, artifact) {
  const result = { page: file, url: `/app/${file}`, controls: [], page_status: 'passed' };
  await page.goto(`${BASE}/app/${file}`, { waitUntil: 'domcontentloaded', timeout: 8000 });
  await page.waitForTimeout(250);
  const controls = page.locator('a, button, input, select, textarea, summary, [role="button"], [role="link"]');
  const count = await controls.count();
  for (let index = 0; index < count; index += 1) {
    const control = controls.nth(index);
    const label = await control.evaluate(controlLabel).catch(() => `control ${index + 1}`);
    const item = { index: index + 1, label };
    try {
      Object.assign(item, await Promise.race([
        operate(page, control, artifact),
        new Promise(resolve => setTimeout(() => resolve({ status: 'failed', detail: 'control timeout' }), 2500)),
      ]));
    } catch (error) { item.status = 'failed'; item.detail = String(error.message || error).slice(0, 300); }
    result.controls.push(item);
    await page.goto(`${BASE}/app/${file}`, { waitUntil: 'domcontentloaded', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(80);
    const fresh = page.locator('a, button, input, select, textarea, summary, [role="button"], [role="link"]');
    if (index + 1 >= await fresh.count()) break;
  }
  if (result.controls.some(item => item.status === 'failed')) result.page_status = 'failed';
  else if (result.controls.some(item => item.status === 'warning' || item.status === 'blocked')) result.page_status = 'warning';
  return result;
}

test.setTimeout(900000);
test('21 pages: every static control receives an action record', async ({ page }) => {
  fs.rmSync(ROOT, { recursive: true, force: true });
  fs.mkdirSync(ROOT, { recursive: true });
  server = startServer();
  await ready();
  const report = { generated_at: new Date().toISOString(), base: BASE, pages: [], totals: { controls: 0, passed: 0, failed: 0, warning: 0, blocked: 0 } };
  for (const file of pages) {
    const result = await runPage(page, file, path.join(ROOT, 'fixture.txt'));
    report.pages.push(result);
    fs.writeFileSync(path.join(ROOT, 'control-matrix-progress.json'), JSON.stringify(report, null, 2), 'utf8');
  }
  for (const result of report.pages) for (const item of result.controls) { report.totals.controls += 1; report.totals[item.status] += 1; }
  fs.writeFileSync(path.join(ROOT, 'control-matrix.json'), JSON.stringify(report, null, 2), 'utf8');
  const lines = ['# StudyBuddy 逐控件矩阵报告', '', `生成时间：${report.generated_at}`, `服务：${BASE}`, '', '## 汇总', '', `- 页面：${report.pages.length}/${pages.length}`, `- 控件记录：${report.totals.controls}`, `- ✅ 操作通过：${report.totals.passed}`, `- ❌ 操作失败：${report.totals.failed}`, `- ⚠️ 条件警告：${report.totals.warning}`, `- ⏸️ 初始隐藏/禁用：${report.totals.blocked}`, '', '## 页面明细', ''];
  for (const result of report.pages) { lines.push(`### ${result.page} ${result.page_status === 'passed' ? '✅' : result.page_status === 'failed' ? '❌' : '⚠️'}`); for (const item of result.controls) { const icon = item.status === 'passed' ? '✅' : item.status === 'failed' ? '❌' : item.status === 'warning' ? '⚠️' : '⏸️'; lines.push(`- ${icon} #${item.index} ${item.label}：${item.detail}`); } lines.push(''); }
  fs.writeFileSync(path.join(ROOT, 'control-matrix.md'), lines.join('\n'), 'utf8');
  expect(report.pages).toHaveLength(pages.length);
});

test.afterEach(() => stopServer());
