const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-state-matrix';
const PORT = 8827;
const BASE = `http://127.0.0.1:${PORT}`;
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});
async function mock(page, url, body){await page.route(url, route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)}))}

test('learning lists render shared labels for lifecycle and source states',async({page})=>{
  await mock(page,'**/api/study/plans',[{id:'plan-1',title:'计划',status:'confirmed',item_count:0}]);
  await mock(page,'**/api/study/goals',[]);await mock(page,'**/api/study/modules',[]);
  await page.goto(`${BASE}/app/plans.html`);await expect(page.locator('#plans')).toContainText('已确认');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/notes',[{id:'note-1',title:'草稿笔记',note_type:'ai_draft'}]);
  await page.goto(`${BASE}/app/notes.html`);await expect(page.locator('#notes')).toContainText('AI 草稿');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/decks',[{id:'deck-1',title:'卡组',status:'archived',card_count:1}]);
  await page.goto(`${BASE}/app/cards.html`);await expect(page.locator('#decks')).toContainText('已归档');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/exercise-sets',[{id:'set-1',title:'练习集',status:'rejected',exercise_count:1}]);
  await page.goto(`${BASE}/app/exercises.html`);await expect(page.locator('#sets')).toContainText('已拒绝');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/practice-sessions',[{id:'session-1',title:'练习',status:'expired'}]);
  await mock(page,'**/api/study/mistakes',[]);
  await page.goto(`${BASE}/app/practice.html`);await expect(page.locator('#sessions')).toContainText('已过期');
});

test('card and exercise source degradation does not expose raw status as the only label',async({page})=>{
  await mock(page,'**/api/study/decks',[{id:'deck-1',title:'卡组',status:'draft',card_count:1}]);
  await mock(page,'**/api/study/decks/deck-1/cards',[{id:'card-1',front:'问题',status:'draft',source_status:'source_unavailable'}]);
  await page.goto(`${BASE}/app/cards.html`);await page.locator('#decks .deck-item').click();await expect(page.locator('#cards')).toContainText('来源: 来源不可用');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/exercise-sets',[{id:'set-1',title:'练习集',status:'draft',exercise_count:1}]);
  await mock(page,'**/api/study/exercise-sets/set-1/exercises',[{id:'exercise-1',prompt:'题目',exercise_type:'short_answer',status:'draft',source_status:'stale'}]);
  await page.goto(`${BASE}/app/exercises.html`);await page.locator('#sets .set-item').click();await expect(page.locator('#exercises')).toContainText('来源: 已过期');
});

test('plan and note detail display source degradation as user labels',async({page})=>{
  await mock(page,'**/api/study/goals',[]);await mock(page,'**/api/study/modules',[]);
  await mock(page,'**/api/study/plans',[{id:'plan-1',title:'计划',status:'active',item_count:1}]);
  await mock(page,'**/api/study/plans/plan-1',{id:'plan-1',title:'计划',items:[{id:'item-1',title:'学习项',source_link_status:'source_deleted'}]});
  await page.goto(`${BASE}/app/plans.html`);await page.locator('#plans .plan-item').click();await expect(page.locator('#plan-detail')).toContainText('来源: 来源已删除');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/notes',[{id:'note-1',title:'笔记',note_type:'ai_draft'}]);
  await mock(page,'**/api/study/notes/note-1',{id:'note-1',title:'笔记',note_type:'ai_draft',source_citation_status:'source_unavailable'});
  await page.goto(`${BASE}/app/notes.html`);await page.locator('#notes .note-item').click();await expect(page.locator('#note-detail')).toContainText('来源状态: 来源不可用');
});
