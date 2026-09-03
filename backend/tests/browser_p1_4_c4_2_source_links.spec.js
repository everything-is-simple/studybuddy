const {test,expect}=require('@playwright/test');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/p1-4-c4-2-source-links';const PORT=8864;const BASE=`http://127.0.0.1:${PORT}`;const PYTHON='C:/miniconda/py310/python.exe';let server;
function start(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn(PYTHON,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function stop(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
async function post(request,path,data){const response=await request.post(BASE+path,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json()}
async function fixture(request){const uploaded=await request.post(`${BASE}/api/materials`,{multipart:{file:{name:'C4-2 实验资料.txt',mimeType:'text/plain',buffer:Buffer.from('C4-2 source-link verification body.')}}});expect(uploaded.status()).toBe(201);const material=await uploaded.json();const indexed=await post(request,`/api/materials/${material.material_id}/ai-index`);const script=`import sqlite3,json;c=sqlite3.connect(r'${ROOT}/studybuddy.sqlite3');print(json.dumps(c.execute("select id,extraction_id from chunks where material_id=?",('${material.material_id}',)).fetchone()))`;const query=spawnSync(PYTHON,['-c',script],{encoding:'utf8'});expect(query.status,query.stderr).toBe(0);const [chunkId,extractionId]=JSON.parse(query.stdout);const goal=await post(request,'/api/study/goals',{title:'C4-2 goal'});const plan=await post(request,'/api/study/plans',{goal_id:goal.id,title:'C4-2 plan'});const item=await post(request,`/api/study/plans/${plan.id}/items`,{title:'C4-2 item'});const module=await post(request,'/api/study/modules',{title:'C4-2 module'});return{material,revision_id:indexed.revision_id,extraction_id:extractionId,chunk_id:chunkId,goal,plan,item,module}}

test.beforeEach(async()=>{await stop();fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});test.afterEach(async()=>stop());

test('C4-2 /app source workspace adds, refreshes and deletes scoped links',async({page,request})=>{
  const f=await fixture(request);page.on('dialog',dialog=>dialog.accept());await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(f.plan.id)}`);
  await expect(page.locator('#source-owner')).toContainText('学习项：C4-2 item');await expect(page.locator('#source-candidate')).toContainText('C4-2 实验资料.txt');
  await page.locator('#source-owner').selectOption(`item:${f.plan.id}:${f.item.id}`);await page.locator('#source-candidate').selectOption(f.chunk_id);await page.getByRole('button',{name:'添加来源链接'}).click();
  await expect(page.locator('#source-status')).toContainText('来源链接已添加');await expect(page.locator('#source-links')).toContainText('来源有效');
  const linkId=await page.locator('#source-links li').first().evaluate(row=>row.querySelector('button').dataset.linkId||'');
  expect(linkId).toBe('');
  await page.locator('#source-links li').first().getByRole('button',{name:'删除'}).click();await expect(page.locator('#source-links li')).toHaveCount(0);
  await page.locator('#source-owner').selectOption(`module:${f.module.id}`);await page.locator('#source-candidate').selectOption(f.chunk_id);await page.getByRole('button',{name:'添加来源链接'}).click();await expect(page.locator('#source-links')).toContainText('来源有效');
  await page.getByRole('button',{name:'刷新来源'}).click();await expect(page.locator('#source-links')).toContainText('来源有效');
  await request.delete(`${BASE}/api/materials/${f.material.material_id}`);await page.getByRole('button',{name:'刷新来源'}).click();await expect(page.locator('#source-links')).toContainText('来源已删除');
  await request.post(`${BASE}/api/materials/${f.material.material_id}/restore`);await page.getByRole('button',{name:'刷新来源'}).click();await expect(page.locator('#source-links')).toContainText('来源有效');
  await expect(page.locator('body')).not.toContainText(/stored_path|traceback|SELECT |H:\\|C4-2 source-link verification body/i);
});

test('C4-2 source failures are safe and retryable, archived plans remain protected',async({page,request})=>{
  const f=await fixture(request);page.on('dialog',dialog=>dialog.accept());await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(f.plan.id)}`);await page.locator('#source-owner').selectOption(`item:${f.plan.id}:${f.item.id}`);await page.locator('#source-candidate').selectOption(f.chunk_id);
  let calls=0;await page.route('**/api/study/plans/*/items/*/sources',route=>{calls++;return route.fulfill({status:500,contentType:'application/json',body:'{"detail":"private_backend_error","traceback":"hidden"}'})});await page.getByRole('button',{name:'添加来源链接'}).click();await expect(page.locator('#source-status')).toContainText('请求失败，请重试');expect(calls).toBe(1);await expect(page.getByRole('button',{name:'添加来源链接'})).toBeEnabled();await page.unrouteAll({behavior:'ignoreErrors'});
  const link=await post(request,`/api/study/plans/${f.plan.id}/items/${f.item.id}/sources`,{material_id:f.material.material_id,revision_id:f.revision_id,extraction_id:f.extraction_id,chunk_id:f.chunk_id});expect((await request.post(`${BASE}/api/study/plans/${f.plan.id}/archive`)).status()).toBe(200);const deleted=await request.delete(`${BASE}/api/study/plans/${f.plan.id}/items/${f.item.id}/sources/${link.id}`);expect(deleted.status()).toBe(409);expect((await deleted.json()).detail).toBe('study_plan_edit_not_allowed');await expect(page.locator('body')).not.toContainText(/private_backend_error|traceback|stored_path|SELECT |H:\\/i);
});
