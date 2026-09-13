const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

// Independent B-class contract review. Route faults and page.request are
// intentionally used here; they are not A-class user-path evidence.
let ROOT = `H:/studybuddy-test/runs/tasks-b-${Date.now()}`;
const PORT = 8978, BASE = `http://127.0.0.1:${PORT}`, PYTHON = 'C:/miniconda/py310/python.exe';
let server;
function start() { const env = { ...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake' }; return spawn(PYTHON, ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], { cwd:'H:/studybuddy/backend', env, stdio:'ignore', windowsHide:true }); }
async function ready() { await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false;}},{timeout:20000}).toBe(true); }
function stop(){return new Promise(resolve=>{if(!server||server.killed){server=null;return resolve();}let done=false;const finish=()=>{if(!done){done=true;server=null;resolve();}};server.once('exit',finish);server.kill();setTimeout(finish,5000);});}
async function safe(page){const body=await page.locator('body').innerText();expect(body).not.toMatch(/traceback|sqlite|select .* from|input_fingerprint|stored_path|api[_-]?key|password|token|H:\\|C:\//i);}
const task=(id,status='queued',extra={})=>({task_id:id,operation_id:'op-'+id,status,task_kind:'embedding_index',operation_type:'embedding_index',progress_percent:extra.progress_percent??20,stage_code:extra.stage_code||'indexing',retry_count:extra.retry_count||0,attempt_count:extra.attempt_count||0,max_retries:1,created_at:'2026-01-01T00:00:00Z',started_at:null,finished_at:null,error_code:extra.error_code||null});

test.describe.serial('tasks.html independent B-class review',()=>{
 test.beforeAll(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready();});test.afterAll(()=>stop());
 test('B-TK-1 API pagination shape, page query and invalid filters are bounded',async({page})=>{
  const calls=[];await page.route('**/api/tasks?*',route=>{calls.push(new URL(route.request().url()).searchParams);const offset=new URL(route.request().url()).searchParams.get('offset');return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[task('t-'+offset)],total:26,limit:25,offset:Number(offset),has_more:offset==='0'})});});
  await page.goto(`${BASE}/app/tasks.html`);await expect(page.locator('#tasks')).toContainText('等待中');expect(calls[0].get('limit')).toBe('25');expect(calls[0].get('offset')).toBe('0');await page.getByRole('button',{name:'下一页'}).click();await expect(calls[1].get('offset')).toBe('25');await expect(page.locator('#tasks')).toContainText('t-25');await expect(page.getByRole('button',{name:'下一页'})).toBeDisabled();
  for(const query of ['status=success','limit=101','offset=-1','task_kind=']){const response=await page.request.get(`${BASE}/api/tasks?${query}`);expect(response.status()).toBe(400);expect(JSON.stringify(await response.json())).not.toMatch(/traceback|sqlite|select/i);}await safe(page);
 });
 test('B-TK-2 delayed old detail success/failure cannot overwrite new task and polling stops terminal',async({page})=>{
  let release;const wait=new Promise(resolve=>release=resolve);let aCalls=0;
  await page.route('**/api/tasks?*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[task('a'),task('b')],total:2,limit:25,offset:0,has_more:false})}));
  await page.route('**/api/tasks/a',async route=>{aCalls++;await wait;return route.fulfill({status:500,contentType:'application/json',body:'{"detail":"database_unavailable"}'});});
  await page.route('**/api/tasks/b',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(task('b','succeeded',{progress_percent:100,stage_code:'finalizing'}))}));
  await page.goto(`${BASE}/app/tasks.html`);await page.locator('#tasks a').nth(0).click();await page.goto(`${BASE}/app/tasks.html?task_id=b`);await expect(page.locator('#task-detail')).toContainText('已成功');release();await page.waitForTimeout(100);await expect(page.locator('#task-detail')).toContainText('已成功');await expect(page.locator('#retry-detail')).toBeHidden();const before=aCalls;await page.waitForTimeout(3200);expect(aCalls).toBe(before);await safe(page);
 });
 test('B-TK-3 malicious task fields render only text and never execute',async({page})=>{
  const payload='<img src=x onerror="window.__taskXss=1"><script>window.__taskXss=1</script>';await page.route('**/api/tasks?*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[task(payload,'failed',{error_code:payload,stage_code:payload})],total:1,limit:25,offset:0,has_more:false})}));await page.goto(`${BASE}/app/tasks.html`);expect(await page.evaluate(()=>window.__taskXss)).toBeUndefined();expect(await page.locator('#tasks img, #tasks script').count()).toBe(0);await expect(page.locator('#tasks')).toContainText('失败');await safe(page);
 });
 test('B-TK-4 cancel mutation is busy-safe, idempotent and restores after failure',async({page})=>{
  let posts=0,release;const hold=new Promise(resolve=>release=resolve);await page.route('**/api/tasks/**',async route=>{if(route.request().method()==='GET')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(task('t-cancel','running'))});posts++;await hold;return route.fulfill({status:500,contentType:'application/json',body:'{"detail":"task_cancel_failed"}'});});await page.goto(`${BASE}/app/tasks.html?task_id=t-cancel`);const button=page.locator('[data-action="cancel"]');page.once('dialog',d=>d.accept());await button.click();await expect(button).toBeDisabled();await expect.poll(()=>posts).toBe(1);await button.dispatchEvent('click');expect(posts).toBe(1);release();await expect(page.locator('#detail-notice')).toContainText('取消任务失败');await expect(button).toBeEnabled();await safe(page);
 });
 test('B-TK-5 error code mapping is safe and invalid actions have no entry point',async({page})=>{
  for(const [code,label] of [['task_not_found','任务不存在'],['task_cancel_not_allowed','当前任务不可取消'],['task_retry_not_allowed','当前任务不可重试'],['task_retry_limit_reached','已达到最大重试次数'],['task_retry_failed','重试任务失败']]){await page.route('**/api/tasks/t-code',route=>route.fulfill({status:code==='task_not_found'?404:409,contentType:'application/json',body:JSON.stringify({detail:code,traceback:'hidden',path:'C:/secret'})}));await page.goto(`${BASE}/app/tasks.html?task_id=t-code`);await expect(page.locator('#detail-error')).toContainText(label);await expect(page.locator('#detail-error')).not.toContainText(code);await page.unroute('**/api/tasks/t-code');}await safe(page);
 });
});
