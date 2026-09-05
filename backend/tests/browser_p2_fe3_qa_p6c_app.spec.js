const {test, expect} = require('@playwright/test');
const {spawn} = require('child_process');
const fs = require('fs');
const ROOT = 'H:/studybuddy-test/runs/p2-fe3-qa-p6c-app';
const PORT = 8795;
const BASE = `http://127.0.0.1:${PORT}`;
function start(provider = 'fake') { const env = {...process.env, PYTHONPATH: 'H:/studybuddy/backend', STUDYBUDDY_DATA_ROOT: ROOT, STUDYBUDDY_AI_PROVIDER: provider}; return spawn('C:/miniconda/py310/python.exe', ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)], {cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true}); }
async function ready() { for(let i=0;i<100;i++){try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ } await new Promise(r=>setTimeout(r,100))} throw new Error('server_not_ready') }
function stop(server){if(server&&!server.killed)server.kill()}

test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true})});

test('formal app P6-C: materials → QA scope → citation → detail → export → back to QA', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Upload 2 materials with longer content for citation
    const response1 = await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'context-alpha.txt',mimeType:'text/plain',buffer:Buffer.from('Context alpha contains the citation export evidence for P6-C cross-page verification. This material provides sufficient text length to support lexical retrieval and citation generation. The citation export evidence phrase appears multiple times to ensure reliable matching.')}}});
    expect(response1.ok()).toBeTruthy();
    const data1=await response1.json();
    const id1=String(data1.id||data1.material_id);
    
    const response2 = await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'context-beta.txt',mimeType:'text/plain',buffer:Buffer.from('Context beta is a second selectable material for multi-material scope testing. This material also contains enough text to support retrieval operations. The second material ensures multi-material scope is preserved across page navigation.')}}});
    expect(response2.ok()).toBeTruthy();
    const data2=await response2.json();
    const id2=String(data2.id||data2.material_id);
    
    // Index both materials
    await page.request.post(`${BASE}/api/materials/${id1}/ai-index`);
    await page.request.post(`${BASE}/api/materials/${id2}/ai-index`);
    
    // Materials list: select 2 materials and goto QA
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#items li')).toHaveCount(2);
    await page.locator('.material-select').nth(0).check();
    await page.locator('.material-select').nth(1).check();
    await expect(page.locator('#goto-qa')).toBeEnabled();
    await page.locator('#goto-qa').click();
    
    // QA: verify pre-selected scope
    await expect(page).toHaveURL(/material=/);
    await expect(page.locator('#material-picker .material-choice')).toHaveCount(2);
    await expect(page.locator('#material-picker input').nth(0)).toBeChecked();
    await expect(page.locator('#material-picker input').nth(1)).toBeChecked();
    
    // Ask question and wait for citations
    await page.locator('#question').fill('P6-C citation export evidence');
    await page.locator('#retrieval-mode').selectOption('lexical');
    await page.locator('#submit-btn').click();
    await expect(page.locator('#submit-status')).toContainText('回答已生成',{timeout:15000});
    
    // Wait for thread to appear and expand all threads
    await expect(page.locator('#threads .thread-item')).toHaveCount(1,{timeout:5000});
    const openButtons=page.getByRole('button',{name:'查看对话与引用'});
    await expect(openButtons).toHaveCount(1);
    await openButtons.first().click();
    
    // Wait for citation link to appear
    await expect(page.locator('.thread-detail')).toBeVisible();
    const citations=page.locator('.thread-detail .citation-link');
    await expect(citations).toHaveCount(1,{timeout:3000});
    await citations.first().click();
    
    // Material detail: verify citation highlight
    await expect(page).toHaveURL(/material-detail\.html\?material=.*&citation=/);
    await expect(page.locator('#body mark.citation-highlight')).toContainText('Context alpha');
    
    // Export original
    const downloadOriginal=page.waitForEvent('download');
    await page.locator('#export-original').click();
    const original=await downloadOriginal;
    expect(original.suggestedFilename()).toBe('context-alpha.txt');
    
    // Export text
    const downloadText=page.waitForEvent('download');
    await page.locator('#export-text').click();
    const text=await downloadText;
    expect(text.suggestedFilename()).toMatch(/context-alpha.*\.txt$/);
    
    // Return to QA via "进入问答" button
    await page.locator('#qa').click();
    await expect(page).toHaveURL(/qa\.html/);
    await expect(page.locator('#threads .thread-item')).toHaveCount(1);
    
  }finally{
    stop(server);
  }
});

test('formal app P6-C: deleted material disables export buttons', async({page})=>{
  const server=start();
  try{
    await ready();
    
    // Upload 1 material
    const response = await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'delete-test.txt',mimeType:'text/plain',buffer:Buffer.from('Delete test material for export button state verification after deletion. This material contains sufficient text to be indexed and displayed in the detail page.')}}});
    expect(response.ok()).toBeTruthy();
    const data=await response.json();
    const id=String(data.id||data.material_id);
    
    // Go to material detail page
    await page.goto(`${BASE}/app/material-detail.html?material=${id}`);
    await expect(page.locator('#state')).toContainText('材料已加载',{timeout:5000});
    
    // Verify export buttons are enabled
    await expect(page.locator('#export-original')).toBeEnabled();
    await expect(page.locator('#export-text')).toBeEnabled();
    
    // Delete material
    await page.request.delete(`${BASE}/api/materials/${id}`);
    
    // Reload detail page
    await page.reload();
    await expect(page.locator('#state')).toContainText('材料不存在或已删除',{timeout:5000});
    await expect(page.locator('#export-original')).toBeDisabled();
    await expect(page.locator('#export-text')).toBeDisabled();
    
  }finally{
    stop(server);
  }
});
