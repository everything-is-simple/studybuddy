/**
 * P2-FE-3-7: 正式 /app/practice-result.html 练习结果与跨页导航（第二批）
 * 
 * 覆盖场景 3 第二批：
 * 1. result 读取成功路径
 * 2. result → review 跨页导航
 * 3. 刷新恢复非敏感上下文
 * 4. DOM/URL 不含答案 key
 */

const {test, expect} = require('@playwright/test');
const {spawn} = require('child_process');
const fs = require('fs');
const ROOT = 'H:/studybuddy-test/runs/p2-fe3-practice-result';
const PORT = 8795;
const BASE = `http://127.0.0.1:${PORT}`;
function start() { const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'}; return spawn('C:/miniconda/py310/python.exe', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], {cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true}); }
async function ready() { for(let i=0;i<100;i++){try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ } await new Promise(r=>setTimeout(r,100))} throw new Error('server_not_ready') }
function stop(server){if(server&&!server.killed)server.kill()}

test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true})});

test('formal app P2-FE-3-7-1: result page loads and displays safe summary', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create exercise and session
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Result Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Result test question?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Result Test',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    // Start and submit
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});
    
    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:true},headers:{'Idempotency-Key':'test-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});
    
    // Visit result page
    await page.goto(`${BASE}/app/practice-result.html?session_id=${sessionId}`);
    
    // Wait for loading to complete
    await page.waitForFunction(() => {
      const status = document.querySelector('#result-status');
      return status && (status.hidden || !status.textContent.includes('正在加载'));
    }, {timeout:10000});
    
    // Verify result displayed
    await expect(page.locator('#result-detail')).toBeVisible();
    await expect(page.locator('#result-detail')).toContainText('得分');
    
    // Verify review link exists
    await expect(page.locator('#review-link')).toBeVisible();
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-7-2: result → review cross-page navigation', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create and complete session
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Nav Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Navigation test?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Nav',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});
    
    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);
    
    // Submit wrong answer to create mistake
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:false},headers:{'Idempotency-Key':'nav-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});
    
    // Visit result page
    await page.goto(`${BASE}/app/practice-result.html?session_id=${sessionId}`);
    await page.waitForTimeout(1500);
    
    // Click review link
    await page.click('#review-link');
    
    // Verify navigated to review page
    await expect(page).toHaveURL(/review\.html/,{timeout:5000});
    await expect(page.locator('h1')).toContainText('错题');
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-7-3: page reload recovers non-sensitive context', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create completed session
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Reload Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Reload test?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Reload',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});
    
    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:true},headers:{'Idempotency-Key':'reload-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});
    
    // Visit result page
    await page.goto(`${BASE}/app/practice-result.html?session_id=${sessionId}`);
    await page.waitForTimeout(1500);
    
    // Verify initial load
    await expect(page.locator('#result-detail')).toBeVisible();
    
    // Reload page
    await page.reload();
    await page.waitForTimeout(1500);
    
    // Verify result still displayed after reload
    await expect(page.locator('#result-detail')).toBeVisible();
    await expect(page.locator('#result-detail')).toContainText('得分');
    
  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-7-4: DOM and URL do not contain answer keys', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Create session with known answer
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Privacy Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);
    
    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'multiple_choice',prompt:'Privacy test?',options:['Secret Answer A','Wrong B','Wrong C'],answer_key:0}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);
    
    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});
    
    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Privacy',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});
    
    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);
    
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:0},headers:{'Idempotency-Key':'privacy-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});
    
    // Visit result page
    await page.goto(`${BASE}/app/practice-result.html?session_id=${sessionId}`);
    await page.waitForTimeout(1500);
    
    // Check URL does not contain sensitive data
    const url = page.url();
    expect(url).not.toContain('answer_key');
    expect(url).not.toContain('Secret Answer');
    expect(url).not.toContain('correct_option');
    
    // Check DOM does not expose answer key in data attributes or text
    const htmlContent = await page.content();
    expect(htmlContent).not.toContain('answer_key');
    expect(htmlContent).not.toContain('answer-key');
    expect(htmlContent).not.toContain('correct_option');
    
    // Check localStorage does not contain answer keys
    const storage = await page.evaluate(() => {
      const items = [];
      for(let i=0; i<localStorage.length; i++) {
        const key = localStorage.key(i);
        items.push({key, value: localStorage.getItem(key)});
      }
      return items;
    });
    
    storage.forEach(item => {
      expect(item.value).not.toContain('Secret Answer');
      expect(item.value).not.toContain('answer_key');
    });
    
  }finally{
    stop(server);
  }
});
