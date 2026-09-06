const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/p2-fe4-exercise-set';
const PORT=8860;
const BASE=`http://127.0.0.1:${PORT}`;
let server;
function start(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
async function setId(page){const created=await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'正式详情练习集'}});expect(created.ok()).toBe(true);return(created.json()).then(item=>item.id)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('formal app reads exercise-set detail and restores it after reload',async({page})=>{
 const id=await setId(page);
 await page.request.post(`${BASE}/api/study/exercise-sets/${id}/exercises`,{data:{exercise_type:'true_false',prompt:'公开详情题',answer_key:true}});
 await page.goto(`${BASE}/app/exercises.html`);
 await page.locator('#sets .set-item').click();
 await expect(page.locator('#set-summary')).toContainText('共 1 道题');
 await expect(page.locator('#exercises')).toContainText('公开详情题');
 await page.reload();
 await page.locator('#sets .set-item').click();
 await expect(page.locator('#set-summary')).toContainText('共 1 道题');
 await expect(page.locator('body')).not.toContainText(/answer_key|traceback|SELECT |H:\\|secret/i);
});

test('formal app exercise-set detail failure is safe and retryable',async({page})=>{
 const id=await setId(page);let calls=0;
 await page.route(`${BASE}/api/study/exercise-sets/${id}`,route=>{calls++;return calls===1?route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_failure',traceback:'hidden',path:'H:/secret'})}):route.continue()});
 await page.goto(`${BASE}/app/exercises.html`);
 await page.locator('#sets .set-item').click();
 await expect(page.locator('#set-summary')).toContainText('请求失败，请重试');
 await expect(page.locator('#retry-set-detail')).toBeVisible();
 await page.locator('#retry-set-detail').click();
 await expect(page.locator('#set-summary')).toContainText('共 0 道题');
 await expect(page.locator('#retry-set-detail')).toBeHidden();
 await expect(page.locator('body')).not.toContainText(/private_failure|traceback|H:\\secret|SELECT /i);
});
