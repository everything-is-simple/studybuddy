const {test,expect}=require('@playwright/test');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs');

const ROOT='H:/studybuddy-test/runs/p1-4-c3-batch-export';
const PORT=8862;
const BASE=`http://127.0.0.1:${PORT}`;
const PYTHON='C:/miniconda/py310/python.exe';
let server;

function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn(PYTHON,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function stopServer(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
async function upload(request,name,body,type='text/plain'){const response=await request.post(`${BASE}/api/materials`,{multipart:{file:{name,mimeType:type,buffer:Buffer.from(body)}}});expect(response.status()).toBe(201);return response.json()}
async function download(page,selector){const pending=page.waitForEvent('download');await page.locator(selector).click();const result=await pending;expect(result.suggestedFilename()).toBe('studybuddy-materials.zip');return result.path()}
function archive(zipPath){const code=`import json,zipfile\nz=zipfile.ZipFile(r'${zipPath}')\nprint(json.dumps({'n':z.namelist(),'b':{x:z.read(x).decode('utf-8') for x in z.namelist()}},ensure_ascii=False))`;const result=spawnSync(PYTHON,['-c',code],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});expect(result.status,result.stderr).toBe(0);return JSON.parse(result.stdout)}

test.beforeEach(async()=>{await stopServer();fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(async()=>stopServer());

test('C3 /app exports selected originals and text after restart',async({page,request})=>{
  await upload(request,'中文笔记.txt','alpha 中文正文');
  await upload(request,'chapter.md','# Chapter\n\nbeta body','text/markdown');
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('.material-select')).toHaveCount(2);
  await expect(page.locator('#export-all')).toBeDisabled();
  await page.locator('#select-page').check();
  await expect(page.locator('#selection-status')).toHaveText('已选择 2 份');

  const originals=archive(await download(page,'#export-originals'));
  expect(originals.n.sort()).toEqual(['originals/chapter.md','originals/中文笔记.txt'].sort());
  expect(originals.b['originals/中文笔记.txt']).toBe('alpha 中文正文');
  await expect(page.locator('#export-status')).toContainText('原件 ZIP 导出完成（2 份）');

  const texts=archive(await download(page,'#export-texts'));
  expect(texts.n.sort()).toEqual(['text/chapter.md.extracted.txt','text/中文笔记.txt.extracted.txt'].sort());
  expect(texts.b['text/中文笔记.txt.extracted.txt']).toBe('alpha 中文正文');

  await page.locator('#apply-filters').click();
  await expect(page.locator('#selection-status')).toHaveText('已选择 0 份');
  await expect(page.locator('#export-all')).toBeDisabled();
  await page.locator('.material-select').first().check();
  const all=archive(await download(page,'#export-all'));
  expect(all.n).toHaveLength(2);
  expect(all.n.some(name=>name.startsWith('originals/'))).toBeTruthy();
  expect(all.n.some(name=>name.startsWith('text/'))).toBeTruthy();

  await stopServer();server=startServer();await ready();
  await page.goto(`${BASE}/app/materials.html`);
  await page.locator('#select-page').check();
  const restarted=archive(await download(page,'#export-all'));
  expect(restarted.n).toHaveLength(4);
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
});

test('C3 export failure is safe, retryable, and unavailable in recycle bin',async({page,request})=>{
  const material=await upload(request,'retry.txt','retry body');
  await page.goto(`${BASE}/app/materials.html`);
  await page.locator('.material-select').check();
  let calls=0;
  await page.route('**/api/materials/export',route=>{calls++;return route.fulfill({status:413,contentType:'application/json',body:'{"detail":"export_too_large"}'})});
  await page.locator('#export-all').evaluate(button=>{button.click();button.click()});
  await expect(page.locator('#export-status')).toContainText('导出内容过大，请减少选择数量');
  await expect(page.locator('#export-all')).toBeEnabled();
  expect(calls).toBe(1);
  await page.unroute('**/api/materials/export');
  expect(archive(await download(page,'#export-all')).n).toHaveLength(2);

  expect((await request.delete(`${BASE}/api/materials/${material.material_id}`)).status()).toBe(204);
  await page.locator('#view-deleted').click();
  await expect(page.locator('#batch-export')).toBeHidden();
  await expect(page.locator('.material-select')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(/export_too_large|traceback|H:\\|SELECT |api_key|stored_path/i);
});
