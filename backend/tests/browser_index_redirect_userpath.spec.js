// index.html 兼容跳转页 A/B 边界审查（Prompt 1 任务 B，A/B 收尾定稿 v2）。
// 口径：index.html 是 510 字节纯兼容跳转页（meta refresh + canonical +
// location.replace + 兜底链接），不是业务工作区。本 spec 只验证
// 「兼容跳转页边界」：三入口统一落到 today、无 JS 时 meta refresh 仍可达、
// 兜底锚点存在且目标可达、query/hash 与开放重定向边界、响应式跳转、
// 静态结构无样式/脚本依赖、不进入 /legacy、不暴露内部路径。
// 分类：IDX-1/2/4/5 为纯用户路径 A 类（页面导航与断言，无 API 直调、无数据创建）；
// IDX-3/6 使用 page.request 读取静态 HTML 源码做结构断言，属 B 类要素，
// 其结论不计入纯 A 类通过。真实业务链路不适用（页面无业务面）；
// 跨浏览器、屏幕阅读器保持 not_verified。
const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const STAMP = Date.now();
// Timestamped fresh data root; never rmSync (safe-delete guard + EPERM history).
const RUN_ROOT = `H:/studybuddy-test/runs/index-redirect-${STAMP}`;
const PORT = 8848;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer() {
  fs.mkdirSync(RUN_ROOT, { recursive: true });
  const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT };
  env.STUDYBUDDY_AI_PROVIDER = 'fake';
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(process.env.STUDYBUDDY_TEST_PYTHON || 'D:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true,
  });
}

async function ready() {
  for (let i = 0; i < 120; i += 1) {
    try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) { }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('server_not_ready');
}

async function stop() {
  if (server && !server.killed) {
    const dying = server;
    await new Promise(resolve => {
      let settled = false;
      const finish = () => { if (!settled) { settled = true; resolve(); } };
      dying.once('exit', finish);
      dying.kill();
      setTimeout(finish, 5000);
    });
  }
  server = null;
}

test.beforeAll(async () => { server = startServer(); await ready(); });
test.afterAll(stop);

test('IDX-1 三入口统一落到 /app/today.html（A 类）', async ({ page }) => {
  for (const path of ['/', '/app/', '/app/index.html']) {
    await page.goto(`${BASE}${path}`);
    await expect(page).toHaveURL(`${BASE}/app/today.html`);
    await expect(page.locator('h1')).toContainText('你的学习日程');
  }
});

test('IDX-2 无 JavaScript 时 meta refresh 仍可达 today（降级路径，A 类）', async ({ page }) => {
  const context = page.context();
  const noJsPage = await context.browser().newContext({ javaScriptEnabled: false }).then(c => c.newPage());
  try {
    await noJsPage.goto(`${BASE}/app/index.html`);
    await expect(noJsPage).toHaveURL(`${BASE}/app/today.html`);
    await expect(noJsPage.locator('h1')).toContainText('你的学习日程');
  } finally {
    await noJsPage.context().close();
  }
});

test('IDX-3 兜底锚点存在且目标可达（B 类要素：page.request 读静态源码）', async ({ page }) => {
  // meta refresh content="0" 使 index 自身无法稳定停留渲染，因此锚点存在性
  // 通过静态源码断言；其 href 目标的可达性由 IDX-1 的真实导航覆盖。
  const response = await page.request.get(`${BASE}/app/index.html`);
  expect(response.status()).toBe(200);
  const src = await response.text();
  expect(src).toContain('href="/app/today.html"');
  expect(src).toContain('如果没有自动跳转，请点击这里');
});

test('IDX-4 query/hash 边界且无开放重定向（A 类）', async ({ page }) => {
  await page.goto(`${BASE}/app/index.html?x=1#y`);
  await expect(page).toHaveURL(`${BASE}/app/today.html`);
  await expect(page.locator('h1')).toContainText('你的学习日程');
  // index.html 的跳转目标是硬编码的 today，query 不得改变落点（防开放重定向）。
  await page.goto(`${BASE}/app/index.html?next=${encodeURIComponent('/app/qa.html')}`);
  await expect(page).toHaveURL(`${BASE}/app/today.html`);
});

test('IDX-5 390 与 1920 两档视口跳转均正常（A 类）', async ({ page }) => {
  // index 自身为瞬时跳转页且仅一段文本，无自身溢出面；本用例验证两档视口下
  // 跳转链路完整、落点 today 正常渲染（today 自身响应式由其 A 类 spec 覆盖）。
  for (const viewport of [{ width: 390, height: 844 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await page.goto(`${BASE}/app/index.html`);
    await expect(page).toHaveURL(`${BASE}/app/today.html`);
    await expect(page.locator('h1')).toContainText('你的学习日程');
  }
});

test('IDX-6 静态结构与依赖边界（B 类要素：page.request 读静态源码）', async ({ page }) => {
  const response = await page.request.get(`${BASE}/app/index.html`);
  expect(response.status()).toBe(200);
  const src = await response.text();
  // 结构：meta refresh + canonical + 脚本跳转，目标全部为 /app/today.html。
  expect(src).toContain('http-equiv="refresh"');
  expect(src).toContain('url=/app/today.html');
  expect(src).toContain('rel="canonical"');
  expect(src).toContain('href="/app/today.html"');
  expect(src).toContain("location.replace('/app/today.html')");
  // 依赖边界：无内联样式、不加载共享 CSS/JS（页面必须零依赖可达）。
  expect(src).not.toContain('<style');
  expect(src).not.toMatch(/css\/(tokens|app)\.css/);
  expect(src).not.toMatch(/<script[^>]+src=/);
  // 边界：不把用户带去 /legacy；不暴露内部路径/traceback。
  expect(src).not.toContain('/legacy');
  expect(src).not.toMatch(/Traceback|Exception|H:\\|C:\\/i);
});
