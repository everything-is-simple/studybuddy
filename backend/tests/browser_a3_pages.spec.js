const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/a3-pages';
const PORT = 8830;
const BASE = `http://127.0.0.1:${PORT}`;
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
async function mock(page,url,body,status=200){await page.route(url,route=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)}))}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('A3-PAGES plan and note details render safe source lifecycle and return navigation',async({page})=>{
  await mock(page,'**/api/study/plans/plan-1',{id:'plan-1',title:'本周计划',status:'active',description:'安全计划摘要',items:[{id:'item-1',title:'阅读材料',status:'completed',source_link_status:'source_deleted'}]});
  await page.goto(`${BASE}/app/plan-detail.html?plan_id=plan-1`);
  await expect(page.locator('#plan-detail')).toContainText('本周计划');
  await expect(page.locator('#plan-detail')).toContainText('来源：来源已删除');
  await page.getByRole('link',{name:'返回计划'}).click();
  await expect(page).toHaveURL(/\/app\/plans\.html$/);
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/notes/note-1',{id:'note-1',title:'复习笔记',note_type:'ai_draft',content:'安全的笔记内容',citation_keys:['ctx-safe'],source_citation_status:'source_unavailable'});
  await page.goto(`${BASE}/app/note-detail.html?note_id=note-1`);
  await expect(page.locator('#note-detail')).toContainText('复习笔记');
  await expect(page.locator('#note-detail')).toContainText('来源状态：来源不可用');
  await expect(page.locator('body')).not.toContainText(/H:\\|SELECT|traceback|secret/i);
  await page.getByRole('link',{name:'返回笔记'}).click();
  await expect(page).toHaveURL(/\/app\/notes\.html$/);
});

test('A3-PAGES detail failures expose safe retry controls',async({page})=>{
  let attempts=0;
  await page.route('**/api/study/plans/plan-retry',route=>{attempts+=1;if(attempts===1)return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_error',path:'H:/secret',traceback:'hidden'})});return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'plan-retry',title:'重试成功',items:[]})})});
  await page.goto(`${BASE}/app/plan-detail.html?plan_id=plan-retry`);
  await expect(page.locator('#plan-status')).toContainText('请求失败');
  await expect(page.locator('#plan-status')).not.toContainText(/private_error|H:\/secret|traceback/i);
  await page.locator('#retry-plan').click();
  await expect(page.locator('#plan-detail')).toContainText('重试成功');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/notes/note-fail',{detail:'private_error',path:'H:/secret'},500);
  await page.goto(`${BASE}/app/note-detail.html?note_id=note-fail`);
  await expect(page.locator('#note-status')).toContainText('请求失败');
  await expect(page.locator('#retry-note')).toBeVisible();
});

test('A3-PAGES practice session and result render approved read-only data',async({page})=>{
  await mock(page,'**/api/study/practice-sessions/session-1',{id:'session-1',title:'模拟练习',status:'finished',deadline:'2026-01-01T10:00:00Z'});
  await page.goto(`${BASE}/app/practice-session.html?session_id=session-1`);
  await expect(page.locator('#session-detail')).toContainText('模拟练习');
  await expect(page.locator('#session-detail')).toContainText('已完成');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/practice-sessions/session-1/result',{session:{id:'session-1',status:'finished'},summary:{score_total:8,total_item_count:10,scored_count:8,submitted_count:8,grading_note:'继续复习重点。'}});
  await page.goto(`${BASE}/app/practice-result.html?session_id=session-1`);
  await expect(page.locator('#result-detail')).toContainText('得分：8 / 10');
  await expect(page.locator('body')).not.toContainText(/answer.?key|正确答案/i);
  await page.getByRole('link',{name:'返回练习'}).click();
  await expect(page).toHaveURL(/\/app\/practice\.html$/);
});

test('A3-PAGES review reports and settings retain safe read-only boundaries',async({page})=>{
  await mock(page,'**/api/study/mistakes',[{id:'mistake-1',question:'错题',mistake_fact:'概念混淆',weak_point:'基础概念'}]);
  await page.goto(`${BASE}/app/review.html`);
  await expect(page.locator('#review-list')).toContainText('基础概念');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/study/reports',{items:[{id:'report-1',title:'脱敏周报',created_at:'2026-01-01T00:00:00Z'}]});
  await page.goto(`${BASE}/app/reports.html`);
  await expect(page.locator('#report-list')).toContainText('脱敏周报');
  await expect(page.locator('body')).not.toContainText('已发送');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await mock(page,'**/api/ai/capabilities',{provider_id:'fake'});await mock(page,'**/api/readiness',{status:'ready'});
  await page.goto(`${BASE}/app/settings.html`);
  await expect(page.locator('#settings-content')).toContainText('Provider：fake');
  await expect(page.locator('#settings-content')).toContainText('系统：就绪');
  await expect(page.locator('body')).not.toContainText(/api.?key|secret|保存配置|连接测试/i);
});
