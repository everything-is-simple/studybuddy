const {test,expect}=require('@playwright/test');
const {spawn,execFileSync}=require('child_process');
const fs=require('fs');
const path=require('path');
const os=require('os');

const ROOT='H:/studybuddy-test/runs/p1-4-c2-explainability';
const FIXTURES='H:/studybuddy-test/runs/p1-4-c2-fixtures';
const FOUNDATION='H:/studybuddy-test/fixtures/kaobuddy-foundation';
const PORT=8861;
const BASE=`http://127.0.0.1:${PORT}`;
const PYTHON='C:/miniconda/py310/python.exe';
let server;

function startServer(){
  const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};
  delete env.STUDYBUDDY_AI_MODEL;delete env.STUDYBUDDY_AI_BASE_URL;delete env.STUDYBUDDY_AI_API_KEY;
  return spawn(PYTHON,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true});
}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:20000}).toBe(true)}
async function stopServer(){if(!server||server.killed){server=null;return}await new Promise(resolve=>{let done=false;const finish=()=>{if(!done){done=true;resolve()}};server.once('exit',finish);server.kill();setTimeout(finish,5000)});server=null}
function chromium(){const base=path.join(process.env.LOCALAPPDATA||os.homedir(),'ms-playwright');for(const dir of fs.existsSync(base)?fs.readdirSync(base):[]){for(const inner of ['chrome-win64','chrome-win']){const candidate=path.join(base,dir,inner,'chrome.exe');if(dir.startsWith('chromium')&&fs.existsSync(candidate))return candidate}}return null}
function buildFixtures(){
  fs.rmSync(FIXTURES,{recursive:true,force:true});fs.mkdirSync(FIXTURES,{recursive:true});
  for(const name of ['sample.doc','sample.ppt','sample.rtf'])fs.copyFileSync(path.join(FOUNDATION,name),path.join(FIXTURES,name));
  fs.writeFileSync(path.join(FIXTURES,'sample.xml'),'<study>unsupported</study>','utf8');
  const browser=chromium();expect(browser,'managed Chromium is required').toBeTruthy();
  fs.copyFileSync(path.join(FOUNDATION,'sample.png'),path.join(FIXTURES,'scan.png'));
  const html=path.join(FIXTURES,'scan.html');fs.writeFileSync(html,'<html><body><img src="scan.png" style="width:500px"></body></html>','utf8');
  execFileSync(browser,['--headless','--disable-gpu','--no-sandbox','--no-pdf-header-footer',`--print-to-pdf=${path.join(FIXTURES,'scanned-page.pdf')}`,`file:///${html.replace(/\\/g,'/')}`],{timeout:180000});
  const script=`from pathlib import Path\nfrom docx import Document\nfrom pptx import Presentation\np=Path(r'${FIXTURES}')\nd=Document();d.add_paragraph('DOCX paragraph text');d.save(p/'complex-note.docx')\nr=Presentation();r.slides.add_slide(r.slide_layouts[6]);r.save(p/'image-slide.pptx')`;
  execFileSync(PYTHON,['-c',script],{timeout:180000});
}
async function post(request,url,data){const response=await request.post(BASE+url,{data});expect(response.ok(),await response.text()).toBeTruthy();return response.json()}
async function upload(request,name,type='text/plain'){const response=await request.post(`${BASE}/api/materials`,{multipart:{file:{name,mimeType:type,buffer:fs.readFileSync(path.join(FIXTURES,name))}}});expect(response.status()).toBe(201);return response.json()}

// Scenario B2-4~B2-6, B3-3, B4-2 and B5-5: source truth must survive restart.
test.beforeAll(()=>buildFixtures());
test.beforeEach(async()=>{await stopServer();fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(async()=>stopServer());

test('C2 source links drive plans and today without false valid fallback',async({page,request})=>{
  const goal=await post(request,'/api/study/goals',{title:'C2 来源目标'});
  const plan=await post(request,'/api/study/plans',{title:'C2 来源计划',goal_id:goal.id});
  const item=await post(request,`/api/study/plans/${plan.id}/items`,{title:'阅读来源材料'});
  const material=await upload(request,'sample.xml','application/xml');
  expect(material.status).toBe('rejected');
  const source=await upload(request,'complex-note.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document');
  const indexed=await post(request,`/api/materials/${source.material_id}/ai-index`,{});
  const retrieval=await post(request,'/api/retrieval',{query:'DOCX',material_ids:[source.material_id],mode:'lexical',top_k:3});
  await post(request,`/api/study/plans/${plan.id}/items/${item.id}/sources`,{material_id:source.material_id,revision_id:indexed.revision_id,chunk_id:retrieval.hits[0].chunk_id});
  const localDate=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  await post(request,`/api/study/plans/${plan.id}/confirm`,{});
  await post(request,`/api/study/plans/${plan.id}/activate`,{});
  const rhythmResponse=await request.put(`${BASE}/api/study/plans/${plan.id}/rhythm`,{data:{cadence:'daily',timezone:'Asia/Shanghai',period_start:localDate,target_minutes:60}});
  expect(rhythmResponse.ok(),await rhythmResponse.text()).toBeTruthy();
  await post(request,`/api/study/plans/${plan.id}/rhythm/allocations`,{item_id:item.id,local_date:localDate,planned_minutes:30});

  await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(plan.id)}`);
  await expect(page.locator('#plan-detail')).toContainText('来源: 来源有效');
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#tasks')).toContainText('来源状态: 来源有效');
  const task=page.locator('#tasks .task-item').filter({hasText:'阅读来源材料'});
  const action=task.getByRole('link',{name:'查看资料'});
  await expect(action).not.toHaveAttribute('aria-disabled','true');
  await expect(action).toHaveAttribute('href',new RegExp(encodeURIComponent(source.material_id)));

  expect((await request.delete(`${BASE}/api/materials/${source.material_id}`)).status()).toBe(204);
  await stopServer();server=startServer();await ready();
  await page.goto(`${BASE}/app/plans.html?plan_id=${encodeURIComponent(plan.id)}`);
  await expect(page.locator('#plan-detail')).toContainText('来源: 来源已删除');
  await page.goto(`${BASE}/app/today.html`);
  const deleted=page.locator('#tasks .task-item').filter({hasText:'阅读来源材料'});
  await expect(deleted).toContainText('来源状态: 来源已删除');
  await expect(deleted.getByRole('link',{name:'查看资料'})).toHaveAttribute('aria-disabled','true');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
});

// Scenario B1-1/B1-3 and B2-1~B2-6: real parser outcomes remain honest and actionable.
test('C2 real files show actionable parse and rejection guidance',async({page,request})=>{
  await page.goto(`${BASE}/app/materials.html`);
  await expect(page.locator('#file-input')).toHaveAttribute('accept','.pdf,.txt,.md,.docx,.pptx');
  await expect(page.locator('#upload-area')).toContainText('DOC、PPT、RTF 请先转换');
  await page.setInputFiles('#file-input',['sample.doc','sample.ppt','sample.rtf','sample.xml'].map(name=>path.join(FIXTURES,name)));
  await expect(page.locator('#upload-status')).toContainText('已导入 0/4',{timeout:30000});
  const failures=page.locator('.upload-failures');
  await expect(failures).toContainText('请转换为 PDF 或 DOCX');
  await expect(failures).toContainText('不支持 RTF 格式');
  await expect(failures).toContainText('不支持该文件格式');
  await expect(failures).not.toContainText(/requires_converter|unsupported_rtf|unsupported_format/);

  const pdf=await upload(request,'scanned-page.pdf','application/pdf');
  const docx=await upload(request,'complex-note.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document');
  const pptx=await upload(request,'image-slide.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation');
  expect(pdf.status).toBe('empty');expect(docx.status).toBe('success');expect(pptx.status).toBe('empty');

  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(pdf.material_id)}`);
  await expect(page.locator('#content')).toContainText('解析器');
  await expect(page.locator('#content')).toContainText('没有可提取的文字层');
  await expect(page.locator('#content')).toContainText('请先使用 OCR 生成可搜索 PDF');
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(docx.material_id)}`);
  await expect(page.locator('#content')).toContainText('复杂样式、文本框和嵌入对象未纳入');
  await page.goto(`${BASE}/app/material-detail.html?material=${encodeURIComponent(pptx.material_id)}`);
  await expect(page.locator('#content')).toContainText('没有可提取的正文');
  await expect(page.locator('#content')).toContainText('请确认内容不是仅图片');
  await expect(page.locator('body')).not.toContainText(/traceback|H:\\|SELECT |api_key|stored_path/i);
});
