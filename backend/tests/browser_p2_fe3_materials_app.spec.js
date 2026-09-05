const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const path=require('path');

const ROOT='H:/studybuddy-test/runs/p2-fe3-materials-app';
const FIXTURES='H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT=8897;
const BASE=`http://127.0.0.1:${PORT}`;

function startServer(extra={}){
  const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,...extra};
  return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true});
}
async function ready(){
  for(let i=0;i<100;i++){
    try{if((await fetch(`${BASE}/api/health`)).ok)return}catch(_){ }
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error('server_not_ready');
}
function stop(server){if(server&&!server.killed)server.kill()}

async function openMaterials(page){
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#state')).not.toHaveText('加载中…',{timeout:10000});
}

test.beforeEach(async()=>{
  fs.rmSync(ROOT,{recursive:true,force:true});
});

test('P2-FE-3 formal materials page imports single and batch files with real status',async({page})=>{
  const server=startServer();
  const errors=[];
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text())});
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await ready();
    await openMaterials(page);
    await page.setInputFiles('#file-input',{name:'formal-single.txt',mimeType:'text/plain',buffer:Buffer.from('Formal app single material')});
    await expect(page.locator('#upload-status')).toContainText('已导入 1/1 个文件',{timeout:15000});
    await expect(page.locator('#items li')).toHaveCount(1);
    await expect(page.locator('#items li a')).toHaveAttribute('href',/material-detail\.html\?material=/);

    await page.setInputFiles('#file-input',[
      {name:'formal-batch-a.txt',mimeType:'text/plain',buffer:Buffer.from('Batch A')},
      {name:'formal-batch-b.md',mimeType:'text/markdown',buffer:Buffer.from('# Batch B')},
    ]);
    await expect(page.locator('#upload-status')).toContainText('已导入 2/2 个文件',{timeout:15000});
    await expect(page.locator('#items li')).toHaveCount(3);
    expect(errors).toEqual([]);
  }finally{stop(server)}
});

test('P2-FE-3 formal materials page imports a directory and paginates real records',async({page})=>{
  const source=path.join(ROOT,'folder-source');
  fs.mkdirSync(path.join(source,'nested'),{recursive:true});
  for(let i=0;i<22;i++)fs.writeFileSync(path.join(source,i<11?'nested':'',`folder-${i}.txt`),`Folder material ${i}`);
  const server=startServer();
  try{
    await ready();
    await openMaterials(page);
    await page.locator('#folder-input').setInputFiles(source);
    await expect(page.locator('#upload-status')).toContainText('已导入 22/22 个文件',{timeout:30000});
    await expect(page.locator('#items li')).toHaveCount(20);
    await expect(page.locator('#pagination')).toBeVisible();
    await page.locator('#pagination').getByRole('button',{name:'下一页'}).click();
    await expect(page.locator('#items li')).toHaveCount(2);
    await expect(page.locator('#pagination')).toContainText('第 2 页');
    await page.locator('#search-input').fill('folder-21');
    await page.locator('#apply-filters').click();
    await expect(page.locator('#items li')).toHaveCount(1);
    await expect(page.locator('#items li')).toContainText('folder-21.txt');
  }finally{stop(server)}
});

test('P2-FE-3 formal materials page exposes a retry after list failure',async({page})=>{
  const server=startServer();
  let fail=true;
  await page.route('**/api/materials?*',async route=>{
    if(fail){fail=false;await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_failure',path:'H:/secret'})});return}
    await route.continue();
  });
  try{
    await ready();
    await page.goto(`${BASE}/app/materials.html`);
    await expect(page.locator('#state')).toHaveText('加载失败');
    await expect(page.locator('#error')).toBeVisible();
    await expect(page.locator('#error')).not.toContainText('private_failure');
    await expect(page.locator('#error')).not.toContainText('H:/secret');
    await expect(page.locator('#retry-materials')).toBeVisible();
    await page.locator('#retry-materials').click();
    await expect(page.locator('#retry-materials')).toBeHidden();
    await expect(page.locator('#state')).toHaveText('暂无材料');
    await expect(page.locator('#items .empty')).toContainText('还没有材料');
  }finally{
    fail=false;
    await page.unroute('**/api/materials?*').catch(()=>{});
    stop(server);
  }
});
