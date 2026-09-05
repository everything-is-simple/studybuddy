const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/plans-today-progress';
const PORT=8852;
const BASE=`http://127.0.0.1:${PORT}`;
let server;
function start(){return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env:{...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'},stdio:'ignore',windowsHide:true})}
async function stop(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
async function ready(){await expect.poll(async()=>{try{return(await fetch(BASE+'/api/readiness')).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function post(request,path,data){const response=await request.post(BASE+path,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json()}
function today(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
test.beforeEach(async()=>{await stop();fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});
test.afterEach(stop);

test('plans to today to progress keeps the allocated task, event state, and return context connected',async({page,request})=>{
  const goal=await post(request,'/api/study/goals',{title:'跨页学习目标'});
  const plan=await post(request,'/api/study/plans',{title:'跨页学习计划',goal_id:goal.id});
  const item=await post(request,`/api/study/plans/${plan.id}/items`,{title:'当天分配的学习项'});
  await post(request,`/api/study/plans/${plan.id}/confirm`,{});
  await post(request,`/api/study/plans/${plan.id}/activate`,{});
  const localDate=today();
  await request.put(`${BASE}/api/study/plans/${plan.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:localDate,target_minutes:60}});
  await post(request,`/api/study/plans/${plan.id}/rhythm/allocations`,{item_id:item.id,local_date:localDate,planned_minutes:30});

  await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(plan.id)}`);
  await expect(page.getByRole('link',{name:'打开详情'})).toHaveAttribute('href',new RegExp(`plan_id=${encodeURIComponent(plan.id)}`));
  await page.goto(`${BASE}/app/today.html`);
  const task=page.locator('#tasks .task-item').filter({hasText:'当天分配的学习项'});
  await expect(task).toContainText(`计划 30 分钟 · ${localDate}`);
  await expect(task.getByRole('link',{name:'开始学习'})).toHaveAttribute('href',new RegExp(`plan_id=${encodeURIComponent(plan.id)}.*item_id=${encodeURIComponent(item.id)}.*return_to=today`));
  await task.getByRole('link',{name:'开始学习'}).click();
  await expect(page).toHaveURL(/plan-detail\.html.*return_to=today/);
  await page.getByRole('button',{name:'开始学习'}).click();
  await expect(page.locator('#progress-status')).toHaveText('已开始学习');
  await page.getByRole('button',{name:'记录完成'}).click();
  await expect(page.locator('#progress-status')).toHaveText('已完成学习');
  await page.getByRole('link',{name:'返回计划'}).click();
  await expect(page).toHaveURL(`${BASE}/app/today.html`);
  await expect(task).toContainText('当天分配的学习项');
  await expect(task.getByRole('link',{name:'查看进度'})).toBeVisible();

  const progress=await (await request.get(`${BASE}/api/study/plans/${plan.id}/progress?item_id=${item.id}`)).json();
  expect(progress.events.map(event=>event.event_type)).toEqual(['started','completed']);
  expect(progress.events.every(event=>event.metadata.local_date===localDate)).toBe(true);
  expect(progress.summary.completed_count).toBe(1);
  await page.reload();
  await expect(page.locator('#tasks .task-item').filter({hasText:'当天分配的学习项'})).toContainText('查看进度');
});

test('today excludes unallocated, inactive, and foreign-plan items',async({page,request})=>{
  const goal=await post(request,'/api/study/goals',{title:'筛选目标'});
  const active=await post(request,'/api/study/plans',{title:'激活计划',goal_id:goal.id});
  const allocated=await post(request,`/api/study/plans/${active.id}/items`,{title:'应该显示'});
  const unallocated=await post(request,`/api/study/plans/${active.id}/items`,{title:'未分配项目'});
  const paused=await post(request,'/api/study/plans',{title:'暂停计划',goal_id:goal.id});
  const pausedItem=await post(request,`/api/study/plans/${paused.id}/items`,{title:'暂停项目'});
  for(const plan of [active,paused])await post(request,`/api/study/plans/${plan.id}/confirm`,{});
  await post(request,`/api/study/plans/${active.id}/activate`,{});
  const localDate=today();
  await request.put(`${BASE}/api/study/plans/${active.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:localDate,target_minutes:60}});
  await post(request,`/api/study/plans/${active.id}/rhythm/allocations`,{item_id:allocated.id,local_date:localDate,planned_minutes:20});
  expect(unallocated.id).toBeTruthy();expect(pausedItem.id).toBeTruthy();
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#tasks')).toContainText('应该显示');
  await expect(page.locator('#tasks')).not.toContainText('未分配项目');
  await expect(page.locator('#tasks')).not.toContainText('暂停项目');
});

test('today surfaces a retry control that recovers every section after a failed load',async({page,request})=>{
  const goal=await post(request,'/api/study/goals',{title:'重试目标'});
  const plan=await post(request,'/api/study/plans',{title:'重试计划',goal_id:goal.id});
  const item=await post(request,`/api/study/plans/${plan.id}/items`,{title:'重试学习项'});
  await post(request,`/api/study/plans/${plan.id}/confirm`,{});
  await post(request,`/api/study/plans/${plan.id}/activate`,{});
  const localDate=today();
  await request.put(`${BASE}/api/study/plans/${plan.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:localDate,target_minutes:60}});
  await post(request,`/api/study/plans/${plan.id}/rhythm/allocations`,{item_id:item.id,local_date:localDate,planned_minutes:25});

  let failing=true;
  await page.route('**/api/study/plans',route=>failing
    ?route.fulfill({status:500,contentType:'application/json',body:'{"detail":"H:/studybuddy/secret_traceback"}'})
    :route.continue());
  await page.goto(`${BASE}/app/today.html`);
  const retry=page.getByRole('button',{name:'重新加载'});
  await expect(retry).toBeVisible();
  for(const id of ['#summary-status','#weekly-status','#task-status'])await expect(page.locator(id)).toContainText('请求失败');
  await expect(page.locator('body')).not.toContainText(/secret_traceback|Traceback|SELECT |H:\\|H:\//);

  failing=false;
  await retry.click();
  await expect(page.locator('#tasks .task-item').filter({hasText:'重试学习项'})).toContainText(`计划 25 分钟 · ${localDate}`);
  await expect(page.locator('#summary')).toContainText('重试计划');
  await expect(page.locator('#weekly-trend .rhythm-card')).toHaveCount(7);
  await expect(retry).toBeHidden();
  for(const id of ['#summary-status','#weekly-status','#task-status'])await expect(page.locator(id)).toBeHidden();
});
