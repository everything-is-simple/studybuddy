const {test, expect} = require('@playwright/test');
const {spawn} = require('child_process');
const fs = require('fs');
const ROOT = 'H:/studybuddy-test/runs/p2-fe3-qa-threads-errors-app';
const PORT = 8794;
const BASE = `http://127.0.0.1:${PORT}`;
function start(provider = 'fake') { const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: provider}; return spawn('C:/miniconda/py310/python.exe', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], {cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true}); }
async function ready() { for(let i=0;i<100;i++){try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ } await new Promise(r=>setTimeout(r,100))} throw new Error('server_not_ready') }
function stop(server){if(server&&!server.killed)server.kill()}
async function createMaterial(page,name,body){const response=await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name,mimeType:'text/plain',buffer:Buffer.from(body)}}});expect(response.ok()).toBeTruthy();const data=await response.json();return String(data.id||data.material_id)}
async function index(page,id){const response=await page.request.post(`${BASE}/api/materials/${id}/ai-index`);expect(response.ok()).toBeTruthy()}

test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true})});

test('formal app QA thread workspace creates and switches conversations', async({page})=>{
  const server=start();
  try{
    await ready();
    const id=await createMaterial(page,'qa-threads.txt','Thread workspace evidence contains first question answer. Thread workspace evidence contains second question answer.');
    await index(page,id);
    await page.goto(`${BASE}/app/qa.html?material=${id}`);
    
    // First question
    await page.locator('#question').fill('first question answer');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('回答已生成',{timeout:15000});
    await expect(page.locator('#threads .thread-item')).toHaveCount(1);
    
    // Expand first thread
    await page.getByRole('button',{name:'查看对话与引用'}).first().click();
    await expect(page.locator('.thread-detail').first()).toContainText('first question answer');
    
    // Second question
    await page.locator('#question').fill('second question answer');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('回答已生成',{timeout:15000});
    await expect(page.locator('#threads .thread-item')).toHaveCount(2);
    
    // Expand both threads independently
    const openButtons=page.getByRole('button',{name:'查看对话与引用'});
    const openCount=await openButtons.count();
    for(let i=0;i<openCount;i++){
      await openButtons.nth(i).click();
    }
    const details=page.locator('.thread-detail');
    await expect(details).toHaveCount(2);
    await expect(details.nth(0)).toBeVisible();
    await expect(details.nth(1)).toBeVisible();
    
    // Refresh and verify persistence
    await page.reload();
    await expect(page.locator('#threads .thread-item')).toHaveCount(2);
  }finally{
    stop(server);
  }
});

test('formal app QA safely maps rate-limit error without leaking internals', async({page})=>{
  const server=start();
  try{
    await ready();
    const id=await createMaterial(page,'qa-ratelimit.txt','Rate limit evidence content.');
    await index(page,id);
    await page.goto(`${BASE}/app/qa.html?material=${id}`);
    
    await page.route(`${BASE}/api/qa/ask`,route=>route.fulfill({
      status:429,
      contentType:'application/json',
      body:JSON.stringify({detail:'provider_rate_limited',path:'H:/private',traceback:'hidden',api_key:'secret'})
    }));
    
    await page.locator('#question').fill('rate limit test');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    
    await expect(page.locator('#submit-status')).toContainText('请求过于频繁，请稍后重试');
    await expect(page.locator('body')).not.toContainText(/provider_rate_limited|H:\/private|hidden|api_key|secret/);
  }finally{
    stop(server);
  }
});

test('formal app QA safely maps unavailable error without leaking internals', async({page})=>{
  const server=start();
  try{
    await ready();
    const id=await createMaterial(page,'qa-unavailable.txt','Unavailable evidence content.');
    await index(page,id);
    await page.goto(`${BASE}/app/qa.html?material=${id}`);
    
    await page.route(`${BASE}/api/qa/ask`,route=>route.fulfill({
      status:503,
      contentType:'application/json',
      body:JSON.stringify({detail:'provider_unavailable',path:'H:/private',traceback:'hidden',api_key:'secret'})
    }));
    
    await page.locator('#question').fill('unavailable test');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    
    await expect(page.locator('#submit-status')).toContainText('Provider 暂时不可用，请重试');
    await expect(page.locator('body')).not.toContainText(/provider_unavailable|H:\/private|hidden|api_key|secret/);
  }finally{
    stop(server);
  }
});
