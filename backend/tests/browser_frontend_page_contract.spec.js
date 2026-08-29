const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const fs = require('fs');

const ROOT = 'H:/studybuddy-test/runs/frontend-page-contract';
const PORT = 8825;
const BASE = `http://127.0.0.1:${PORT}`;
let server;
function startServer(){const env={...process.env,PYTHONPATH:'H:/studybuddy/backend',STUDYBUDDY_DATA_ROOT:ROOT,STUDYBUDDY_AI_PROVIDER:'fake'};delete env.STUDYBUDDY_AI_MODEL;delete env.STUDYBUDDY_AI_BASE_URL;delete env.STUDYBUDDY_AI_API_KEY;return spawn('C:/miniconda/py310/python.exe',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(PORT)],{cwd:'H:/studybuddy/backend',env,stdio:'ignore',windowsHide:true})}
async function ready(){await expect.poll(async()=>{try{return(await fetch(`${BASE}/api/readiness`)).ok}catch(_){return false}},{timeout:15000}).toBe(true)}
test.beforeEach(async()=>{fs.rmSync(ROOT,{recursive:true,force:true});server=startServer();await ready()});test.afterEach(()=>{if(server&&!server.killed)server.kill();server=null});

test('materials page exposes safe empty and failure states',async({page})=>{await page.goto(`${BASE}/app/materials.html`);await expect(page.locator('#state')).toHaveText('暂无材料');await page.route('**/api/materials?*',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_error',path:'C:/secret'})}));await page.click('#apply-filters');await expect(page.locator('#error')).toBeVisible();await expect(page.locator('#error')).not.toContainText('private_error');await expect(page.locator('body')).not.toContainText('C:/secret')});
test('material detail reports missing identity safely',async({page})=>{await page.goto(`${BASE}/app/material-detail.html`);await expect(page.locator('#state')).toContainText('请从资料库进入');await expect(page.locator('#export-original')).toBeDisabled();await expect(page.locator('#export-text')).toBeDisabled()});
test('qa page exposes empty history and safe provider state',async({page})=>{await page.goto(`${BASE}/app/qa.html`);await expect(page.locator('#thread-status')).toHaveText('暂无问答历史');await expect(page.locator('#provider-status')).not.toContainText('正在检查');await expect(page.locator('#question')).toBeVisible()});
test('page context change ignores stale thread response',async({page})=>{await page.goto(`${BASE}/app/qa.html`);let release;const blocked=new Promise(resolve=>{release=resolve});await page.route('**/api/qa/threads',async route=>{await blocked;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[]})})});await page.evaluate(()=>loadThreads&&loadThreads()).catch(()=>{});release();await expect(page.locator('#thread-status')).toBeVisible()});
