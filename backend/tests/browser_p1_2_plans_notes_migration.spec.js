const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/p1-2-plans-notes';
const PORT = 8846;
const BASE = `http://127.0.0.1:${PORT}`;
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};delete env.STUDYBUDDY_AI_MODEL;delete env.STUDYBUDDY_AI_BASE_URL;delete env.STUDYBUDDY_AI_API_KEY;return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
async function stopServer(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let settled=false;const finish=()=>{if(!settled){settled=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
test.beforeEach(async()=>{await stopServer();fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});test.afterEach(async()=>{await stopServer()});

async function createMaterial(page){const response=await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'p1-2-source.txt',mimeType:'text/plain',buffer:Buffer.from('P1-2 source text for learning notes and plan context.')}}});expect(response.ok()).toBe(true);const result=await response.json();return String(result.id||result.material_id)}

test('P1-2 plans page creates a goal, plan draft, item and rhythm settings',async({page})=>{
  await page.goto(`${BASE}/app/plans.html`);
  await page.locator('#goal-title').fill('完成 P1-2 学习目标');
  await page.getByRole('button',{name:'新建目标'}).click();
  await expect(page.locator('#plan-status')).toHaveText('目标已创建');
  await expect(page.locator('#goals')).toContainText('完成 P1-2 学习目标');
  await page.locator('#plan-title').fill('P1-2 迁移计划');
  await page.locator('#plan-goal').selectOption({label:'完成 P1-2 学习目标'});
  await page.getByRole('button',{name:'新建计划草稿'}).click();
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
  await expect(page.locator('#plans')).toContainText('P1-2 迁移计划');
  await page.locator('#plans .plan-item').click();
  await expect(page.locator('#plan-detail')).toContainText('草稿');
  await page.locator('#plan-item-title').fill('验证学习节奏');
  await page.getByRole('button',{name:'添加学习项'}).click();
  await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  await expect(page.locator('[aria-label="学习项 验证学习节奏"]')).toHaveValue('验证学习节奏');
  await page.locator('#rhythm-period-start').fill('2026-09-01');
  await page.locator('#rhythm-target-minutes').fill('90');
  await page.getByRole('button',{name:'保存节奏设置'}).click();
  await expect(page.locator('#plan-status')).toContainText('学习节奏已保存');
  await page.locator('#rhythm-date').fill('2026-09-02');
  await page.locator('#rhythm-minutes').fill('45');
  await page.getByRole('button',{name:'添加分配'}).click();
  await expect(page.locator('#plan-status')).toContainText('学习项已分配');
  await expect(page.getByRole('button',{name:'调整'})).toHaveCount(1);
});


test('P2-FE-4 plans page exposes goal/module management and dependency removal across Today and detail',async({page})=>{
  const goal=await (await page.request.post(`${BASE}/api/study/goals`,{data:{title:'归档前目标'}})).json();
  const module=await (await page.request.post(`${BASE}/api/study/modules`,{data:{title:'归档前模块'}})).json();
  const plan=await (await page.request.post(`${BASE}/api/study/plans`,{data:{goal_id:goal.id,title:'跨页计划'}})).json();
  const first=await (await page.request.post(`${BASE}/api/study/plans/${plan.id}/items`,{data:{title:'前置学习项',module_id:module.id}})).json();
  const second=await (await page.request.post(`${BASE}/api/study/plans/${plan.id}/items`,{data:{title:'后置学习项',module_id:module.id}})).json();
  const dependency=await (await page.request.post(`${BASE}/api/study/plans/${plan.id}/dependencies`,{data:{predecessor_item_id:first.id,successor_item_id:second.id}})).json();
  const localDate=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  expect((await page.request.put(`${BASE}/api/study/plans/${plan.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:localDate,target_minutes:30}})).ok()).toBe(true);
  expect((await page.request.post(`${BASE}/api/study/plans/${plan.id}/rhythm/allocations`,{data:{item_id:second.id,local_date:localDate,planned_minutes:30}})).ok()).toBe(true);

  await page.goto(`${BASE}/app/plans.html?plan_id=${plan.id}`);
  await expect(page.locator('#plan-detail')).toContainText('前置学习项 → 后置学习项');
  await page.getByRole('button',{name:'查看目标'}).click();
  await expect(page.locator('#goal-detail')).toContainText('归档前目标');
  let renameAttempts=0;
  await page.route('**/api/study/goals/*',route=>{if(route.request().method()==='PATCH'&&renameAttempts++===0)return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_backend_error'})});return route.continue()});
  page.once('dialog',dialog=>dialog.accept('已重命名目标'));
  await page.getByRole('button',{name:'重命名目标'}).click();
  await expect(page.locator('#plan-status')).toHaveText('计划操作失败，可重试');
  await expect(page.locator('#goals')).toContainText('归档前目标');
  page.once('dialog',dialog=>dialog.accept('已重命名目标'));
  await page.getByRole('button',{name:'重命名目标'}).click();
  await page.unroute('**/api/study/goals/*');
  await expect(page.locator('#plan-status')).toHaveText('目标已重命名');
  await expect(page.locator('#goals')).toContainText('已重命名目标');
  await page.getByRole('button',{name:'查看模块'}).click();
  await expect(page.locator('#module-detail')).toContainText('归档前模块');
  page.once('dialog',dialog=>dialog.accept('已重命名模块'));
  await page.getByRole('button',{name:'重命名模块'}).click();
  await expect(page.locator('#plan-status')).toHaveText('模块已重命名');
  await expect(page.locator('#modules')).toContainText('已重命名模块');
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'删除依赖'}).click();
  await expect(page.locator('#plan-status')).toHaveText('依赖已删除');
  await expect(page.locator('#plan-detail')).not.toContainText('前置学习项 → 后置学习项');
  expect((await (await page.request.get(`${BASE}/api/study/plans/${plan.id}`)).json()).dependencies.find(row=>row.id===dependency.id)).toBeFalsy();
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'归档目标'}).click();
  await expect(page.locator('#plan-status')).toHaveText('目标已归档');
  await expect(page.locator('#plan-goal option',{hasText:'已重命名目标'})).toHaveCount(0);
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'归档模块'}).click();
  await expect(page.locator('#plan-status')).toHaveText('模块已归档');
  await expect(page.locator('#modules')).not.toContainText('已重命名模块');
  await page.getByRole('button',{name:'确认草稿'}).click();
  await expect(page.locator('#plan-status')).toContainText('确认草稿成功');
  await page.getByRole('button',{name:'激活计划'}).click();
  await expect(page.locator('#plan-status')).toContainText('激活计划成功');

  await page.goto(`${BASE}/app/plan-detail.html?plan_id=${plan.id}`);
  await expect(page.locator('#plan-detail')).toContainText('跨页计划');
  await expect(page.locator('#plan-detail')).toContainText('暂无学习项依赖');
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#summary')).toContainText('跨页计划');
  await expect(page.locator('body')).not.toContainText(/traceback|private_backend|H:\\|SELECT/i);
});

test('P2-FE-4 formal plans exports local rhythm JSON and recovers from failure',async({page})=>{
  const goal=await (await page.request.post(`${BASE}/api/study/goals`,{data:{title:'导出目标'}})).json();
  const plan=await (await page.request.post(`${BASE}/api/study/plans`,{data:{goal_id:goal.id,title:'可导出节奏计划'}})).json();
  const item=await (await page.request.post(`${BASE}/api/study/plans/${plan.id}/items`,{data:{title:'导出学习项'}})).json();
  const date='2026-09-01';
  expect((await page.request.put(`${BASE}/api/study/plans/${plan.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:date,target_minutes:60}})).ok()).toBe(true);
  expect((await page.request.post(`${BASE}/api/study/plans/${plan.id}/rhythm/allocations`,{data:{item_id:item.id,local_date:date,planned_minutes:30}})).ok()).toBe(true);
  await page.goto(`${BASE}/app/plans.html?plan_id=${plan.id}`);
  const exportButton=page.locator('#rhythm-export');
  await expect(exportButton).toBeVisible();
  let exportAttempts=0;
  await page.route(`**/api/study/plans/${plan.id}/rhythm/export?format=json`,route=>{
    if(exportAttempts++===0)return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'private_backend_error'})});
    return route.continue();
  });
  await exportButton.click();
  await expect(page.locator('#plan-status')).toHaveText('节奏导出失败，请重试');
  await expect(exportButton).toBeEnabled();
  const downloadPromise=page.waitForEvent('download');
  await exportButton.click();
  const download=await downloadPromise;
  expect(download.suggestedFilename()).toBe('studybuddy-rhythm.json');
  const payload=JSON.parse(await download.createReadStream().then(async stream=>{let body='';for await(const chunk of stream)body+=chunk;return body}));
  expect(payload.plan.id).toBe(plan.id);
  expect(payload.allocations[0].planned_minutes).toBe(30);
  await expect(page.locator('#plan-status')).toHaveText('节奏导出已开始');
  await page.reload();
  await expect(page.locator('#rhythm-export')).toBeEnabled();
  await expect(page.locator('#plan-detail')).toContainText('导出学习项');
  await expect(page.locator('body')).not.toContainText(/traceback|private_backend|H:\\|SELECT/i);
});

test('P1-2 notes page creates, edits, confirms and archives a user note',async({page})=>{
  await createMaterial(page);
  await page.goto(`${BASE}/app/notes.html`);
  await page.locator('#new-title').fill('P1-2 用户笔记');
  await page.locator('#new-content').fill('初始笔记内容');
  await page.getByRole('button',{name:'新建用户笔记'}).click();
  await expect(page.locator('#notes')).toContainText('P1-2 用户笔记');
  await expect(page.locator('#note-detail')).toContainText('用户笔记');
  await page.locator('[aria-label="笔记标题"]').fill('P1-2 已编辑笔记');
  await page.locator('[aria-label="笔记区块 1"]').fill('编辑后的笔记内容');
  await page.getByRole('button',{name:'保存笔记编辑'}).click();
  await expect(page.locator('#note-status')).toContainText('笔记编辑已保存');
  await expect(page.locator('[aria-label="笔记区块 1"]')).toHaveValue('编辑后的笔记内容');
  await page.locator('#module-title').fill('P1-2 知识模块');
  await page.getByRole('button',{name:'关联到当前笔记'}).click();
  await expect(page.locator('#note-detail')).toContainText('P1-2 知识模块');
  await page.getByRole('button',{name:'刷新来源状态'}).click();
  await expect(page.locator('#note-status')).toContainText('笔记来源状态已刷新');
  await page.getByRole('button',{name:'归档笔记'}).click();
  await expect(page.locator('#note-status')).toContainText('笔记已归档');
  await expect(page.locator('#note-detail')).toContainText('已归档');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT|api_key|private_backend/i);
});

test('P1-2 note generation keeps provider and source failures user-facing',async({page})=>{
  const materialId=await createMaterial(page);
  await page.goto(`${BASE}/app/notes.html`);
  const option=page.locator('#material-select option',{hasText:'p1-2-source.txt'});
  await expect(option).toHaveCount(1,{timeout:10000});
  await page.locator('#topic').fill('材料摘要');
  await page.selectOption('#material-select',materialId);
  await page.getByRole('button',{name:'生成 AI 草稿'}).click();
  await expect(page.locator('#note-status')).toContainText('笔记操作失败，可重试',{timeout:15000});
  await expect(page.locator('body')).not.toContainText(/provider_not_configured|traceback|H:\\|SELECT/i);
});
