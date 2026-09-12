const {test,expect}=require('@playwright/test');
const {spawn}=require('child_process');
const fs=require('fs');
const ROOT='H:/studybuddy-test/runs/p2-fe4-report-preview';
const PORT=8858;
const BASE=`http://127.0.0.1:${PORT}`;
let server;
function start(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
async function createReport(page){const seeded=await page.request.post(`${BASE}/api/materials`,{multipart:{file:{name:'preview-scope.txt',mimeType:'text/plain',buffer:Buffer.from('P2 FE4 report preview scope')}}});expect(seeded.ok()).toBe(true);const response=await page.request.post(`${BASE}/api/study/reports`,{data:{report_kind:'daily',timezone:'UTC',period_start:'2026-01-15',period_end:'2026-01-16'}});expect(response.ok()).toBe(true);return response.json()}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=start();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('formal app report preview reads the preview endpoint and restores after reload',async({page})=>{
 const report=await createReport(page);let previewCalls=0;
 await page.route(`${BASE}/api/study/reports/${report.id}/preview`,async route=>{previewCalls++;return route.continue()});
 await page.goto(`${BASE}/app/reports.html?report_id=${encodeURIComponent(report.id)}`);
 await expect(page.locator('#report-detail-title')).toContainText('报告 · 日报');
 await expect(page.locator('#preview-report')).toBeVisible();
 await page.locator('#preview-report').click();
 await expect.poll(()=>previewCalls).toBe(1);
 await expect(page.locator('#report-detail')).toContainText('交付：未发送');
 await page.reload();
 await expect(page.locator('#report-detail-title')).toContainText('报告 · 日报');
 await expect(page.locator('body')).not.toContainText(/traceback|SELECT |H:\\|stored_path|secret/i);
});

test('formal app report preview failure is safe, retryable, and protected from duplicate clicks',async({page})=>{
 const report=await createReport(page);let calls=0;let release;
 await page.route(`${BASE}/api/study/reports/${report.id}/preview`,async route=>{calls++;if(calls===1){await new Promise(resolve=>{release=resolve});return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_report_failure',traceback:'hidden',path:'H:/secret'})})}return route.continue()});
 await page.goto(`${BASE}/app/reports.html?report_id=${encodeURIComponent(report.id)}`);
 await expect(page.locator('#preview-report')).toBeVisible();
 await page.locator('#preview-report').click();
 await expect(page.locator('#preview-report')).toBeDisabled();
 await page.locator('#preview-report').dispatchEvent('click');
 expect(calls).toBe(1);release();
 await expect(page.locator('#report-status')).toContainText('请求失败，请重试');
 await expect(page.locator('#preview-report')).toBeEnabled();
 await page.locator('#preview-report').click();
 await expect.poll(()=>calls).toBe(2);
 await expect(page.locator('#report-detail')).toContainText('交付：未发送');
 await expect(page.locator('body')).not.toContainText(/private_report_failure|traceback|H:\\secret|SELECT /i);
});
