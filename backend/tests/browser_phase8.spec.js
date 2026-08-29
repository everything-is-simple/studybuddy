const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const RUN_ROOT = 'H:/studybuddy-test/runs/formal-phase8-ui';
const PORT = 8804;
const BASE = `http://127.0.0.1:${PORT}`;
let server;

function startServer(provider = 'fake') {
  const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: RUN_ROOT};
  if (provider === 'fake') env.STUDYBUDDY_AI_PROVIDER = 'fake';
  else delete env.STUDYBUDDY_AI_PROVIDER;
  delete env.STUDYBUDDY_AI_MODEL; delete env.STUDYBUDDY_AI_BASE_URL; delete env.STUDYBUDDY_AI_API_KEY;
  return spawn('C:/miniconda/py310/python.exe', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {cwd: 'H:/studybuddy/backend', env, stdio: 'ignore', windowsHide: true});
}
async function ready() { for (let i=0;i<100;i++) { try { if ((await fetch(`${BASE}/api/health`)).ok) return; } catch (_) {} await new Promise(r=>setTimeout(r,100)); } throw Error('server_not_ready'); }
function stop() { if (server && !server.killed) server.kill(); server = null; }
async function uploadAndIndex(page, name='phase8.txt') { await page.locator('#file').setInputFiles({name, mimeType:'text/plain', buffer:Buffer.from('A controlled study establishes a stable learning result.')}); await page.locator('#file-import').click(); await expect(page.locator('#status')).toContainText('导入完成'); await page.locator('#ai-index').click(); await expect(page.locator('#qa-status')).toContainText('AI 索引已建立'); }
async function createDeck(page, title='Cards') { await page.locator('#nav-study').click(); await page.locator('#deck-title').fill(title); await page.locator('#deck-create').click(); await expect(page.locator('#study-status')).toContainText('已加载学习内容'); }
async function generate(page, topic='controlled study') { await page.locator('#study-topic').fill(topic); await page.locator('#study-generate').click(); await expect(page.locator('#study-status')).toContainText('已生成'); }

test.beforeEach(async () => { fs.rmSync(RUN_ROOT,{recursive:true,force:true}); server=startServer(); await ready(); });
test.afterEach(stop);

test('Phase 8 fake path generates, edits, confirms and reviews cited card across refresh', async ({page}) => {
  await page.goto(`${BASE}/legacy`); await uploadAndIndex(page); await createDeck(page); await generate(page);
  await expect(page.locator('#study-detail')).toContainText('草稿');
  await expect(page.locator('#study-detail')).toContainText('查看引用');
  await expect(page.locator('body')).not.toContainText('answer_key');
  await page.locator('#study-card-front').fill('Edited generated question'); await page.locator('#study-save').click(); await expect(page.locator('#study-status')).toContainText('草稿已保存');
  await page.locator('#study-confirm').click(); await expect(page.locator('#study-status')).toContainText('内容已确认就绪');
  await expect(page.locator('#study-detail')).toContainText('已就绪');
  await page.getByRole('button',{name:'good'}).click(); await expect(page.locator('#study-status')).toContainText('复习记录已保存');
  await page.reload(); await page.locator('#nav-study').click(); await page.getByRole('button',{name:/Cards/}).click(); await expect(page.locator('#study-workspace')).toContainText('Edited generated question');
});

test('Phase 8 exercise UI drafts, confirms, grades and keeps answer key private', async ({page}) => {
  await page.goto(`${BASE}/legacy`); await uploadAndIndex(page,'exercise.txt'); await page.locator('#nav-study').click();
  await page.locator('#exercise-set-title').fill('Exercises'); await page.locator('#exercise-set-create').click();
  await page.locator('#study-topic').fill('stable learning result'); await page.locator('#study-exercise-type').selectOption('multiple_choice'); await page.locator('#study-generate').click();
  await expect(page.locator('#study-status')).toContainText('已生成'); await expect(page.locator('body')).not.toContainText('answer_key');
  await page.locator('#study-confirm').click(); await expect(page.locator('#study-detail')).toContainText('已就绪');
  await page.locator('input[name="study-answer"]').first().check(); await page.locator('#study-attempt').click(); await expect(page.locator('#study-status')).toContainText('回答正确');
});

test('Phase 8 handles provider, stale generation and citation-unavailable failures safely', async ({page}) => {
  await page.goto(`${BASE}/legacy`); await uploadAndIndex(page,'failure.txt'); await createDeck(page,'Failures');
  await page.route('**/api/study/decks/*/generate', route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"provider_not_configured"}'}));
  await page.locator('#study-topic').fill('controlled'); await page.locator('#study-generate').click(); await expect(page.locator('#study-status')).toContainText('生成草稿失败'); await expect(page.locator('#study-generate')).toBeEnabled(); await page.unroute('**/api/study/decks/*/generate');
  await generate(page); const cite=page.getByRole('button',{name:'查看引用'}); await cite.click(); await expect(page.locator('#study-status')).toContainText('已定位引用来源');
  const materialId = await page.evaluate(async () => (await (await fetch('/api/materials')).json())[0].id);
  await page.request.delete(`${BASE}/api/materials/${materialId}`);
  await page.getByRole('button',{name:/Failures/}).click();
  await page.locator('#study-workspace .study-list button').first().click();
  await expect(page.locator('#study-detail')).toContainText('来源不可用');
  await expect(page.getByRole('button',{name:'来源不可用'})).toBeDisabled();
  await page.setViewportSize({width:390,height:844}); await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  await page.locator('#nav-study').focus(); await page.keyboard.press('Enter'); await expect(page.locator('#study')).toBeVisible();
});
