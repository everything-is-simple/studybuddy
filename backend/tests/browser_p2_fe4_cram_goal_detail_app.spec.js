const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/p2-fe4-cram-detail';
const PORT=8861;
const BASE=`http://127.0.0.1:${PORT}`;
let server;
function start(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
async function createGoal(page){const seeded=await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'cram-scope.txt',mimeType:'text/plain',buffer:Buffer.from('P2 FE4 cram goal detail scope')}}});expect(seeded.ok()).toBe(true);const response=await page.request.post(`${BASE}/api/study/cram-goals`,{data:{title:'正式冲刺详情',target_date:'2099-01-01',target_exercise_count:5,timezone:'UTC'}});expect(response.ok()).toBe(true);return response.json()}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('formal app reads cram-goal detail and restores it after reload',async({page})=>{
 const goal=await createGoal(page);let calls=0;
 await page.route(`${BASE}/api/study/cram-goals/${goal.id}`,route=>{calls++;return route.continue()});
 await page.goto(`${BASE}/app/practice.html`);
 await page.locator('#cram-goals .session-item').click();
 await expect(page.locator('#cram-detail')).toContainText('正式冲刺详情');
 await expect(page.locator('#cram-detail')).toContainText('最多 5 题');
 await expect.poll(()=>calls).toBe(1);
 await page.reload();
 await page.locator('#cram-goals .session-item').click();
 await expect(page.locator('#cram-detail')).toContainText('正式冲刺详情');
 await expect(page.locator('body')).not.toContainText(/answer_key|traceback|SELECT |H:\\|secret/i);
});

test('formal app cram-goal detail failure is safe and retryable',async({page})=>{
 const goal=await createGoal(page);let calls=0;
 await page.route(`${BASE}/api/study/cram-goals/${goal.id}`,route=>{calls++;return calls===1?route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_failure',traceback:'hidden',path:'H:/secret'})}):route.continue()});
 await page.goto(`${BASE}/app/practice.html`);
 await page.locator('#cram-goals .session-item').click();
 await expect(page.locator('#cram-detail')).toContainText('请求失败，请重试');
 await expect(page.locator('#cram-detail button')).toBeVisible();
 await page.locator('#cram-detail button').click();
 await expect(page.locator('#cram-detail')).toContainText('正式冲刺详情');
 await expect.poll(()=>calls).toBe(2);
 await expect(page.locator('body')).not.toContainText(/private_failure|traceback|H:\\secret|SELECT /i);
});
