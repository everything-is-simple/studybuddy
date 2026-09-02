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
  await page.goto(`${BASE}/app/notes.html`);
  await page.locator('#topic').fill('材料摘要');
  await page.locator('#material-id').fill('missing-material');
  await page.getByRole('button',{name:'生成 AI 草稿'}).click();
  await expect(page.locator('#note-status')).toContainText('笔记操作失败，可重试');
  await expect(page.locator('body')).not.toContainText(/provider_not_configured|traceback|H:\\|SELECT/i);
});
