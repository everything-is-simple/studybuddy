const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');

const ROOT='H:/studybuddy-test/runs/p1-4-plan-status-race';
const PORT=8863;
const BASE=`http://127.0.0.1:${PORT}`;
let server;

function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function stopServer(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
async function post(request,path,data){const response=await request.post(BASE+path,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json()}

test.beforeEach(async()=>{await stopServer();fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(async()=>stopServer());

test('late plan selection cannot overwrite mutation success status',async({page,request})=>{
  const goal=await post(request,'/api/study/goals',{title:'竞态目标'});
  const first=await post(request,'/api/study/plans',{title:'已选计划',goal_id:goal.id});
  const plan=await post(request,'/api/study/plans',{title:'竞态计划',goal_id:goal.id});
  await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(first.id)}`);
  await expect(page.locator('#plan-status')).toHaveText('计划已加载');

  let firstDetailCalls=0;
  page.on('request',request=>{if(request.url().endsWith(`/api/study/plans/${first.id}`))firstDetailCalls++});
  await page.locator('#plans .plan-item').filter({hasText:'已选计划'}).click();
  await page.waitForTimeout(100);
  expect(firstDetailCalls).toBe(0);

  let releaseOldRhythm;
  const oldRhythmReleased=new Promise(resolve=>{releaseOldRhythm=resolve});
  let rhythmCalls=0;
  await page.route(`**/api/study/plans/${plan.id}/rhythm`,async route=>{
    rhythmCalls++;
    if(rhythmCalls===1)await oldRhythmReleased;
    await route.continue()
  });

  await page.locator('#plans .plan-item').filter({hasText:'竞态计划'}).click();
  await expect.poll(()=>rhythmCalls).toBe(1);
  await page.locator('#plan-item-title').fill('不会被覆盖的学习项');
  await page.locator('#plan-item-add').click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  await expect(page.locator('[aria-label="学习项 不会被覆盖的学习项"]')).toHaveValue('不会被覆盖的学习项');

  releaseOldRhythm();
  await expect.poll(()=>rhythmCalls).toBeGreaterThanOrEqual(2);
  await page.waitForTimeout(300);
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i)
});
