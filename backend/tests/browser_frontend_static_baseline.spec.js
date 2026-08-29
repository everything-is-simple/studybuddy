const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-static-baseline';
const PORT = 8829;
const BASE = `http://127.0.0.1:${PORT}`;
const PAGES = [
  ['index.html', null], ['today.html', '#summary-status'], ['materials.html', '#state'],
  ['material-detail.html', '#state'], ['qa.html', '#thread-status'], ['plans.html', '#plan-status'],
  ['notes.html', '#note-status'], ['cards.html', '#deck-status'], ['exercises.html', '#set-status'],
  ['practice.html', '#session-status'], ['capture.html', '#state'], ['classroom.html', '#capture-status'],
  ['tasks.html', '#state'], ['settings-provider.html', '#state'],
];
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};delete env.STUDYBUDDY_AI_MODEL;delete env.STUDYBUDDY_AI_BASE_URL;delete env.STUDYBUDDY_AI_API_KEY;return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('all static pages have safe initial states at mobile and desktop widths',async({page})=>{for(const [name,status] of PAGES){for(const width of [360,390,430,600,768,820,1024,1366,1440,1920]){await page.setViewportSize({width,height:844});await page.goto(`${BASE}/app/${name}`);await expect(page.locator('main')).toBeVisible();await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);if(status)await expect(page.locator(status)).not.toContainText(/正在加载|加载中|正在检查|检查中/,{timeout:5000});if(width===360){const toggle=page.getByRole('button',{name:'更多'});await expect(toggle).toBeVisible();await toggle.press('Enter');await expect(page.locator('#primary-navigation')).toHaveClass(/is-open/)}await expect(page.locator('body')).not.toContainText(/H:\\|SELECT\s|Traceback|api[_-]?key|secret|stored_path/i)}}});
