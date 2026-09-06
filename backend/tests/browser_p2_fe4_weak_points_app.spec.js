const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/p2-fe4-weak-points';
const PORT=8859;
const BASE=`http://127.0.0.1:${PORT}`;
let server;
function start(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('formal app review renders weak-point summary and restores it after reload',async({page})=>{
 await page.route(`${BASE}/api/study/mistakes`,route=>route.fulfill({status:200,contentType:'application/json',body:'[]'}));
 await page.route(`${BASE}/api/study/weak-points`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify([{exercise_id:'exercise-public',occurrence_count:3,open_count:2,fixed_count:1,reopened_count:0,source_warning_count:1,last_occurrence_at:'2026-09-06T00:00:00Z'}])}));
 await page.goto(`${BASE}/app/review.html`);
 await expect(page.locator('#weak-points')).toContainText('exercise-public');
 await expect(page.locator('#weak-points')).toContainText('出现 3 次');
 await expect(page.locator('#weak-points')).toContainText('部分来源当前不可用');
 await expect(page.locator('#review-status')).toContainText('暂无错题记录');
 await page.reload();
 await expect(page.locator('#weak-points')).toContainText('出现 3 次');
 await expect(page.locator('body')).not.toContainText(/traceback|SELECT |H:\\|answer_key|secret/i);
});

test('formal app weak-point failure is safe and retryable without hiding mistake state',async({page})=>{
 let calls=0;
 await page.route(`${BASE}/api/study/mistakes`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify([{id:'mistake-1',question:'公开错题',status:'open',mistake_fact:'公开原因',occurrences:[]}])}));
 await page.route(`${BASE}/api/study/weak-points`,async route=>{calls++;if(calls===1)return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_failure',traceback:'hidden',path:'H:/secret'})});return route.fulfill({status:200,contentType:'application/json',body:'[]'})});
 await page.goto(`${BASE}/app/review.html`);
 await expect(page.locator('#review-list')).toContainText('公开错题');
 await expect(page.locator('#weak-point-status')).toContainText('请求失败，请重试');
 await expect(page.locator('#retry-weak-points')).toBeVisible();
 await page.locator('#retry-weak-points').click();
 await expect(page.locator('#weak-point-status')).toContainText('暂无薄弱点记录');
 await expect(page.locator('#retry-weak-points')).toBeHidden();
 await expect(page.locator('body')).not.toContainText(/private_failure|traceback|H:\\secret|SELECT /i);
});
