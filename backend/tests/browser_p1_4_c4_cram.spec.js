const {test,expect}=require('@playwright/test');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs');

const ROOT='H:/studybuddy-test/runs/p1-4-c4-cram';
const PORT=8863;
const BASE=`http://127.0.0.1:${PORT}`;
const PYTHON='C:/miniconda/py310/python.exe';
let server;

function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn(PYTHON,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function stopServer(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
async function post(request,path,data){const response=await request.post(BASE+path,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json()}
async function readyExercise(request,prompt='C4 冲刺题'){const set=await post(request,'/api/study/exercise-sets',{title:'C4 题库'});const exercise=await post(request,`/api/study/exercise-sets/${set.id}/exercises`,{exercise_type:'multiple_choice',prompt,options:['错误','正确'],answer_key:1});await post(request,`/api/study/exercises/${exercise.id}/confirm`);return exercise}
async function citedExercise(request){const materialResponse=await request.post(`${BASE}/api/materials`,{multipart:{file:{name:'cram-source.txt',mimeType:'text/plain',buffer:Buffer.from('A verified source for the C4 cram lifecycle.')}}});expect(materialResponse.status()).toBe(201);const material=await materialResponse.json();const indexed=await post(request,`/api/materials/${material.material_id}/ai-index`);const script="import json,sqlite3; c=sqlite3.connect(r'"+ROOT+"/studybuddy.sqlite3'); r=c.execute('select id,text from chunks where material_id=?',(\""+material.material_id+"\",)).fetchone(); print(json.dumps(r))";const result=spawnSync(PYTHON,['-c',script],{encoding:'utf8'});expect(result.status,result.stderr).toBe(0);const [chunkId,quote]=JSON.parse(result.stdout);const set=await post(request,'/api/study/exercise-sets',{title:'C4 来源题库'});const exercise=await post(request,`/api/study/exercise-sets/${set.id}/exercises`,{exercise_type:'true_false',prompt:'来源当前有效吗？',answer_key:true,exercise_kind:'ai_generated',source_revision:indexed.revision_id,citations:[{citation_key:'c4-source',chunk_id:chunkId,quote}]});await post(request,`/api/study/exercises/${exercise.id}/confirm`);return{material,exercise}}

test.beforeEach(async()=>{await stopServer();fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(async()=>stopServer());

test('C4-1 /app completes a cram workflow and rereads it after restart',async({page,request})=>{
  await readyExercise(request);
  await page.goto(`${BASE}/app/practice.html`);
  await expect(page.locator('#create-cram-goal')).toBeEnabled();
  await page.locator('#cram-title').fill('C4 期末冲刺');
  await page.locator('#cram-date').fill('2099-12-31');
  await page.locator('#cram-count').fill('1');
  await page.getByRole('button',{name:'创建冲刺目标'}).click();
  await expect(page.locator('#cram-status')).toContainText('冲刺目标已创建');
  await page.locator('#cram-goals .session-item').first().click();
  const goalId=await page.locator('#cram-goals .session-item').first().evaluate(async()=>{const rows=await(await fetch('/api/study/cram-goals')).json();return rows[0].id});
  await page.getByRole('button',{name:'激活目标'}).click();
  await expect(page.locator('#cram-status')).toContainText('冲刺目标已激活');
  await page.locator('#cram-goals .session-item').first().click();
  await page.locator('.cram-exercise-choice').check();
  await page.getByRole('button',{name:'创建冲刺练习'}).click();
  await expect(page).toHaveURL(/practice-session\.html.*cram_goal_id=/);
  const sessionId=new URL(page.url()).searchParams.get('session_id');
  await page.getByRole('button',{name:'开始练习'}).click();
  await page.locator('#answer').selectOption('1');
  await page.getByRole('button',{name:'提交答案'}).click();
  await page.getByRole('button',{name:'完成会话'}).click();
  await expect(page).toHaveURL(/practice-result\.html.*cram_goal_id=/);
  await expect(page.locator('#result-detail')).toContainText('冲刺目标：C4 期末冲刺');
  await expect(page.locator('#result-detail')).toContainText('得分：1 / 1');
  await page.goto(`${BASE}/app/practice.html`);await page.locator('#cram-goals .session-item').first().click();
  await page.getByRole('button',{name:'完成目标'}).click();
  await expect(page.locator('#cram-status')).toContainText('冲刺目标已完成');

  await stopServer();server=startServer();await ready();
  await page.goto(`${BASE}/app/practice.html`);
  await expect(page.locator('#cram-goals')).toContainText('C4 期末冲刺');
  await expect(page.locator('#cram-goals')).toContainText('已完成');
  await expect(page.locator('#sessions')).toContainText('冲刺练习');
  await page.locator('#sessions .session-item').filter({hasText:'冲刺练习'}).getByRole('link',{name:'打开会话'}).click();
  await expect(page).toHaveURL(new RegExp(`practice-session\\.html.*session_id=${sessionId}.*cram_goal_id=${goalId}`));
  await page.getByRole('link',{name:'查看结果'}).click();
  await expect(page.locator('#result-detail')).toContainText('得分：1 / 1');
  await expect(page.locator('body')).not.toContainText(/answer_key|answer_json|traceback|stored_path|H:\\/i);

  const ordinary=await post(request,'/api/study/practice-sessions',{title:'普通练习回归',exercise_ids:[(await (await request.get(`${BASE}/api/study/exercises`)).json())[0].id],duration_seconds:600,timezone:'UTC',local_date:'2099-12-31'});
  await post(request,`/api/study/practice-sessions/${ordinary.id}/start`);await post(request,`/api/study/practice-sessions/${ordinary.id}/finish`);
  await page.goto(`${BASE}/app/practice-result.html?session_id=${ordinary.id}`);
  await expect(page.locator('#result-detail')).toContainText('得分：0 / 1');
});

test('C4-1 handles empty, expired, invalid-source, duplicate and retry boundaries',async({page,request})=>{
  await post(request,'/api/study/exercise-sets',{title:'空题库'});
  await page.goto(`${BASE}/app/practice.html`);
  await expect(page.locator('#create-cram-goal')).toBeEnabled();
  await page.locator('#cram-title').fill('空题目标');await page.locator('#cram-date').fill('2099-12-31');
  const createdResponse=page.waitForResponse(response=>response.url().endsWith('/api/study/cram-goals')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'创建冲刺目标'}).click();expect((await createdResponse).status()).toBe(201);await expect(page.locator('#cram-status')).toContainText('冲刺目标已创建');await page.locator('#cram-goals .session-item').first().click();await page.getByRole('button',{name:'激活目标'}).click();await page.locator('#cram-goals .session-item').first().click();
  await expect(page.locator('#cram-detail')).toContainText('暂无已确认且来源有效的题目');
  await expect(page.getByRole('button',{name:'创建冲刺练习'})).toBeDisabled();

  await post(request,'/api/study/cram-goals',{title:'过期目标',target_date:'2000-01-01',target_exercise_count:1});
  await page.locator('#refresh-cram').click();await page.locator('#cram-goals .session-item').filter({hasText:'过期目标'}).click();
  await expect(page.locator('#cram-detail')).toContainText('目标日期已过');
  await expect(page.getByRole('button',{name:'激活目标'})).toHaveCount(0);

  const sourced=await citedExercise(request);await request.delete(`${BASE}/api/materials/${sourced.material.material_id}`);
  await page.locator('#refresh-cram').click();await page.locator('#cram-goals .session-item').filter({hasText:'空题目标'}).click();
  await expect(page.locator('#cram-detail')).toContainText('暂无已确认且来源有效的题目');

  await readyExercise(request,'双击与重试题');await page.locator('#refresh-cram').click();await page.locator('#cram-goals .session-item').filter({hasText:'空题目标'}).click();
  let calls=0;await page.route('**/api/study/cram-goals/*/sessions',async route=>{calls++;if(calls===1)return route.fulfill({status:500,contentType:'application/json',body:'{"detail":"private_backend_error","traceback":"hidden"}'});return route.continue()});
  await page.locator('.cram-exercise-choice').check();await page.getByRole('button',{name:'创建冲刺练习'}).evaluate(button=>{button.click();button.click()});
  await expect(page.locator('#cram-status')).toContainText('请求失败，请重试');expect(calls).toBe(1);await expect(page.getByRole('button',{name:'创建冲刺练习'})).toBeEnabled();
  await page.getByRole('button',{name:'创建冲刺练习'}).click();await expect(page).toHaveURL(/practice-session\.html/);expect(calls).toBe(2);
  await expect(page.locator('body')).not.toContainText(/private_backend_error|traceback|answer_key|stored_path|H:\\/i);
});
