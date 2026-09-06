/**
 * P2-FE-3-8: 正式 /app/review.html 错题复盘（第三批）
 *
 * 覆盖场景 3 第三批：
 * 1. review 页面加载 mistake 列表
 * 2. detail 展开、feedback 保存、redo/archive 操作
 * 3. 空状态与 retry 恢复
 * 4. DOM/URL/storage 隐私保护、390px 窄屏、键盘焦点
 */

const {test, expect} = require('@playwright/test');
const {spawn} = require('child_process');
const fs = require('fs');
const ROOT = 'H:/studybuddy-test/runs/p2-fe3-review';
const PORT = 8799;
const BASE = `http://127.0.0.1:${PORT}`;
function start() { const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: 'fake'}; return spawn('C:/miniconda/py310/python.exe', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], {cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true}); }
async function ready() { for(let i=0;i<100;i++){try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ } await new Promise(r=>setTimeout(r,100))} throw new Error('server_not_ready') }
function stop(server){if(server&&!server.killed)server.kill()}

test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true})});

test('formal app P2-FE-3-8-1: review list loads and displays mistake status', async({page})=>{
  const server=start();
  try{
    await ready();

    // Create exercise and session with wrong answer
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Review Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);

    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Review test question?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);

    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});

    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Review Test',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);

    // Start, submit wrong answer, finish
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});

    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);

    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:false},headers:{'Idempotency-Key':'review-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});

    // Visit review page
    await page.goto(`${BASE}/app/review.html`);

    // Wait for loading to complete
    await page.waitForFunction(() => {
      const status = document.querySelector('#review-status');
      return status && status.hidden;
    }, {timeout:10000});

    // Verify mistake list item displayed
    await expect(page.locator('#review-list article')).toBeVisible();
    await expect(page.locator('#review-list article')).toContainText('待处理');

    // Verify action buttons present
    await expect(page.locator('#review-list button:has-text("查看详情")')).toBeVisible();
    await expect(page.locator('#review-list button:has-text("再次练习")')).toBeVisible();
    await expect(page.locator('#review-list button:has-text("归档")')).toBeVisible();

  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-8-2: detail view expands, feedback saves, archive disables buttons', async({page})=>{
  const server=start();
  try{
    await ready();

    // Setup mistake
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Detail Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);

    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Detail test?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);

    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});

    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Detail',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);

    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});

    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);

    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:false},headers:{'Idempotency-Key':'detail-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});

    // Visit review page
    await page.goto(`${BASE}/app/review.html`);
    await page.waitForTimeout(1500);

    // Click detail button
    await page.click('button:has-text("查看详情")');
    await page.waitForTimeout(500);

    // Verify detail view expanded
    await expect(page.locator('.mistake-detail')).toBeVisible();
    await expect(page.locator('[aria-label="复盘反馈"]')).toBeVisible();

    // Save feedback
    await page.fill('[aria-label="复盘反馈"]', 'Test feedback note');
    await page.click('button:has-text("保存反馈")');
    await page.waitForTimeout(1000);

    // Verify success message
    await expect(page.locator('#review-status')).toContainText('复盘反馈已保存');

    // Click archive
    await page.click('button:has-text("归档")');
    await page.waitForTimeout(1000);

    // Verify archive success
    await expect(page.locator('#review-status')).toContainText('错题已归档');

    // Verify redo/archive buttons disabled
    await expect(page.locator('button:has-text("再次练习")')).toBeDisabled();
    await expect(page.locator('button:has-text("归档")')).toBeDisabled();

  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-8-3: redo creates new session', async({page})=>{
  const server=start();
  try{
    await ready();

    // Setup mistake
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Redo Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);

    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'true_false',prompt:'Redo test?',answer_key:true}});
    const exerciseData = await exerciseRes.json();
    const exerciseId = String(exerciseData.id);

    await page.request.post(`${BASE}/api/study/exercises/${exerciseId}/confirm`,{data:{}});

    const sessionRes = await page.request.post(`${BASE}/api/study/practice-sessions`,{data:{title:'Redo',exercise_ids:[exerciseId]}});
    const sessionData = await sessionRes.json();
    const sessionId = String(sessionData.id);

    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/start`,{data:{}});

    const sessionDetail = await page.request.get(`${BASE}/api/study/practice-sessions/${sessionId}`);
    const sessionInfo = await sessionDetail.json();
    const itemId = String(sessionInfo.items[0].id);

    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:false},headers:{'Idempotency-Key':'redo-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});

    // Visit review page
    await page.goto(`${BASE}/app/review.html`);
    await page.waitForTimeout(1500);

    // Click redo button
    await page.click('button:has-text("再次练习")');
    await page.waitForTimeout(1000);

    // Verify success message
    await expect(page.locator('#review-status')).toContainText('已创建再次练习会话');

  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-8-4: empty state and retry recovery', async({page})=>{
  const server=start();
  try{
    await ready();

    // Visit review page with no mistakes
    await page.goto(`${BASE}/app/review.html`);
    await page.waitForTimeout(1500);

    // Verify empty state
    await expect(page.locator('#review-status')).toContainText('暂无错题记录');
    await expect(page.locator('#review-list article')).toHaveCount(0);

    // Inject failure
    await page.route('**/api/study/mistakes', route => route.abort());
    await page.reload();
    await page.waitForTimeout(1000);

    // Verify error state
    await expect(page.locator('#review-status')).toContainText('请求失败');
    await expect(page.locator('#retry-review')).toBeVisible();

    // Remove route and retry
    await page.unroute('**/api/study/mistakes');
    await page.click('#retry-review');
    await page.waitForTimeout(1000);

    // Verify recovered to empty state
    await expect(page.locator('#review-status')).toContainText('暂无错题记录');

  }finally{
    stop(server);
  }
});

test('formal app P2-FE-3-8-5: privacy, narrow viewport, keyboard focus', async({page})=>{
  const server=start();
  try{
    await ready();

    // Setup mistake
    const setRes = await page.request.post(`${BASE}/api/study/exercise-sets`,{data:{title:'Privacy Test'}});
    const setData = await setRes.json();
    const setId = String(setData.id);

    const exerciseRes = await page.request.post(`${BASE}/api/study/exercise-sets/${setId}/exercises`,{data:{exercise_type:'multiple_choice',prompt:'Privacy test?',options:['Secret A','Wrong B','Wrong C'],answer_key:0}});
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

    // Submit wrong answer
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/items/${itemId}/submit`,{data:{answer:1},headers:{'Idempotency-Key':'privacy-key-1'}});
    await page.request.post(`${BASE}/api/study/practice-sessions/${sessionId}/finish`,{data:{}});

    // Visit review page
    await page.goto(`${BASE}/app/review.html`);
    await page.waitForTimeout(1500);

    // Check URL doesn't contain sensitive data
    const url = page.url();
    expect(url).not.toContain('answer_key');
    expect(url).not.toContain('Secret A');

    // Check DOM doesn't expose answer key
    const htmlContent = await page.content();
    expect(htmlContent).not.toContain('answer_key');
    expect(htmlContent).not.toContain('answer-key');

    // Check localStorage
    const storage = await page.evaluate(() => {
      const items = [];
      for(let i=0; i<localStorage.length; i++) {
        const key = localStorage.key(i);
        items.push({key, value: localStorage.getItem(key)});
      }
      return items;
    });

    storage.forEach(item => {
      expect(item.value).not.toContain('Secret A');
      expect(item.value).not.toContain('answer_key');
    });

    // Test narrow viewport 390x844
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(500);

    // Check no horizontal overflow
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow).toBe(false);

    // Test keyboard focus visibility
    await page.setViewportSize({width:1280,height:720});
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    const focusVisible = await page.evaluate(() => {
      const el = document.activeElement;
      if(!el || el === document.body) return false;
      const style = window.getComputedStyle(el);
      return style.outline !== 'none' || parseFloat(style.outlineWidth) > 0 || style.boxShadow.includes('inset') || style.boxShadow !== 'none';
    });

    expect(focusVisible).toBe(true);

  }finally{
    stop(server);
  }
});
