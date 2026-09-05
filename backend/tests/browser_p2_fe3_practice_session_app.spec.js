/**
 * P2-FE-3-6: 正式 /app/practice-session.html 练习会话核心路径（第一批）
 */
const {test, expect} = require('@playwright/test');
const {spawn} = require('child_process');
const fs = require('fs');
const ROOT = 'H:/studybuddy-test/runs/p2-fe3-practice-session';
const PORT = 8794;
const BASE = `http://127.0.0.1:${PORT}`;
function start() { const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'}; return spawn('C:/miniconda/py310/python.exe', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], {cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true}); }
async function ready() { for(let i=0;i<100;i++){try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ } await new Promise(r=>setTimeout(r,100))} throw new Error('server_not_ready') }
function stop(server){if(server&&!server.killed)server.kill()}

test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true})});

test('formal app P2-FE-3-6-1: practice session draft→start→active state transition', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create exercise set and exercise
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Test Set'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Test question?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    // Create session
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Test Session',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    // Visit session page
    await page.goto(`${BASE}/app/practice-session.html?session_id=${sessionId}`);
    
    // Wait for loading to complete
    await page.waitForFunction(() => {
      const status = document.querySelector('#session-status');
      return status && (status.hidden || !status.textContent.includes('正在加载'));
    }, {timeout:10000});
    
    // Verify draft state and start button exists
    await expect(page.locator('#session-detail')).toBeVisible();
    await expect(page.locator('button:has-text("开始")')).toBeVisible();
    
    // Click start
    await page.click('button:has-text("开始")');
    await page.waitForTimeout(1500);
    
    // Verify transition to active (question appears or status updates)
    const hasQuestion = await page.locator('.practice-question').count() > 0;
    const statusText = await page.locator('#session-status').textContent();
    expect(hasQuestion || statusText.includes('已开始')).toBeTruthy();
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-6-2: session not found shows safe error', async({page})=>{
  const server=start();
  try{
    await ready();
    
    await page.goto(`${BASE}/app/practice-session.html?session_id=nonexistent`);
    await page.waitForTimeout(1500);
    
    // Verify safe error message
    const statusText = await page.locator('#session-status').textContent();
    expect(statusText).toBeTruthy();
    expect(statusText).toContain('请');
    
    // Verify no internal info leaked
    expect(statusText).not.toContain('practice_session_not_found');
    expect(statusText).not.toContain('H:/');
    expect(statusText).not.toContain('ValueError');
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-6-3: narrow viewport 390x844 no horizontal overflow', async({page})=>{
  const server=start();
  try{
    await ready();
    
    await page.setViewportSize({width:390,height:844});
    
    // Create minimal session
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Narrow'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'short_answer',prompt:'Long question text to verify wrapping behavior on narrow screens',answer_key:'test'}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Narrow Test',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    await page.goto(`${BASE}/app/practice-session.html?session_id=${sessionId}`);
    await page.waitForTimeout(1500);
    
    // Verify no horizontal scrollbar
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const viewportWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1);
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-6-4: keyboard focus visible on buttons', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create session
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Keyboard'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Keyboard test',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Keyboard',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    await page.goto(`${BASE}/app/practice-session.html?session_id=${sessionId}`);
    await page.waitForTimeout(1500);
    
    // Tab to first button
    await page.keyboard.press('Tab');
    
    // Verify focused element has visible focus indicator
    const hasFocusVisible = await page.evaluate(() => {
      const el = document.activeElement;
      if(!el || el === document.body) return false;
      const computed = window.getComputedStyle(el);
      return computed.outlineWidth !== '0px' || computed.boxShadow !== 'none';
    });
    
    expect(hasFocusVisible).toBeTruthy();
    
  }finally{
    stop(server);
  }
});
