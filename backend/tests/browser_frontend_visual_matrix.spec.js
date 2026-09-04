const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-visual-matrix';
const PORT = 8831;
const BASE = `http://127.0.0.1:${PORT}`;
const PAGES = ['today.html','materials.html','material-detail.html','qa.html','plans.html','plan-detail.html','notes.html','note-detail.html','cards.html','exercises.html','practice.html','practice-session.html','practice-result.html','review.html','capture.html','classroom.html','reports.html','tasks.html','settings-provider.html','settings.html'];
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});
test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('Neutral Modern shared visual system applies to every static page at mobile and desktop widths',async({page})=>{
  for(const name of PAGES){for(const width of [360,1920]){
    await page.setViewportSize({width,height:844});await page.goto(`${BASE}/app/${name}`);
    const visual=await page.evaluate(()=>{const root=getComputedStyle(document.documentElement),card=document.querySelector('.card'),main=document.querySelector('main');return {styles:document.querySelectorAll('style').length,tokens:document.querySelectorAll('link[href="/app/css/tokens.css"]').length,shared:document.querySelectorAll('link[href="/app/css/app.css"]').length,accent:root.getPropertyValue('--accent').trim(),radius:root.getPropertyValue('--radius-lg').trim(),cardRadius:card?getComputedStyle(card).borderRadius:null,mainWidth:main.getBoundingClientRect().width,viewport:document.documentElement.clientWidth}});
    expect(visual.styles,name).toBe(0);expect(visual.tokens,name).toBe(1);expect(visual.shared,name).toBe(1);expect(visual.accent,name).toBe('#2f6feb');expect(visual.radius,name).toBe('12px');expect(visual.cardRadius,name).toBe('12px');expect(visual.mainWidth,name).toBeLessThanOrEqual(visual.viewport);
  }}
});

test('Neutral Modern focus and mobile controls remain visible and touch-sized',async({page})=>{
  await page.setViewportSize({width:360,height:844});await page.goto(`${BASE}/app/materials.html`);
  const toggle=page.getByRole('button',{name:'更多'});await expect(toggle).toBeVisible();
  const sizes=await page.evaluate(()=>['#apply-filters','.nav-toggle'].map(selector=>document.querySelector(selector).getBoundingClientRect().height));
  sizes.forEach(size=>expect(size).toBeGreaterThanOrEqual(44));
  await page.locator('#apply-filters').focus();await expect(page.locator('#apply-filters')).toHaveCSS('box-shadow',/47, 111, 235/);
  await toggle.press('Enter');await expect(page.locator('#primary-navigation')).toHaveClass(/is-open/);
});
