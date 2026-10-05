const {test,expect}=require('@playwright/test');
const BASE=process.env.STUDYBUDDY_BASE_URL;
test.describe.configure({mode:'serial'});
const localDate=(delta=0)=>{const d=new Date();d.setDate(d.getDate()+delta);return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);};

async function makePlan(page,count=1){
  const title='S1 '+Date.now();
  await page.goto(`${BASE}/app/plans.html`);
  await page.locator('#goal-title').fill(title);
  await page.locator('#goal-form button').click();
  await expect(page.locator('#plan-status')).toHaveText('目标已创建');
  await page.locator('#plan-title').fill(title);
  await page.locator('#plan-goal').selectOption({label:title});
  await page.locator('#plan-form button').click();
  await expect(page.locator('#plan-status')).toHaveText('计划草稿已创建');
  for(let i=0;i<count;i++){
    const name=title+' item '+i;
    await page.locator('#plan-item-title').fill(name);
    await page.getByRole('button',{name:'添加学习项',exact:true}).click();
    await expect(page.locator('#plan-status')).toHaveText('学习项已添加');
  }
  await page.locator('#rhythm-period-start').fill(localDate());
  await page.locator('#rhythm-target-minutes').fill('1000');
  await page.getByRole('button',{name:'保存节奏设置',exact:true}).click();
  await expect(page.locator('#plan-status')).toHaveText('学习节奏已保存');
  for(let i=0;i<count;i++){
    await page.locator('#rhythm-item').selectOption({label:title+' item '+i});
    await page.locator('#rhythm-date').fill(localDate(i===count-1&&count>1?1:0));
    await page.getByRole('button',{name:'添加分配',exact:true}).click();
    await expect(page.locator('#plan-status')).toHaveText('学习项已分配');
  }
  await page.getByRole('button',{name:'确认草稿',exact:true}).click();
  await expect(page.locator('#plan-status')).toHaveText('确认草稿成功');
  await page.getByRole('button',{name:'激活计划',exact:true}).click();
  await expect(page.locator('#plan-status')).toHaveText('激活计划成功');
  return title;
}

test('S1 honest empty state and safe failure recovery',async({page})=>{
  await page.route('**/api/today/pending-items',r=>r.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'private_backend',path:'H:/private'})}));
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#more-tasks')).not.toHaveAttribute('open');
  await expect(page.locator('#pending-error')).toContainText('请重试');
  await expect(page.locator('body')).not.toContainText('H:/private');
  await page.unroute('**/api/today/pending-items');
  await page.locator('#refresh-pending').click();
  await expect(page.locator('#pending-status')).toContainText('今天没有紧急待办');
  await expect(page.locator('#pending-items li')).toHaveCount(0);
});

test('S1 UI-only plan -> five-item cap -> inline completion -> reload -> detail link',async({page})=>{
  const title=await makePlan(page,7);
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#pending-items li')).toHaveCount(5);
  await expect(page.locator('#pending-overflow')).toContainText('还有 2 项未显示');
  await expect(page.locator('#more-tasks')).not.toHaveAttribute('open');
  const first=page.locator('#pending-items li').first();
  const id=await first.getAttribute('data-pending-id');
  let requests=0;
  page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/progress'))requests++;});
  await first.getByRole('button',{name:'开始学习',exact:true}).evaluate(b=>{b.click();b.click();});
  await expect(page.locator(`[data-pending-id="${id}"] button`)).toHaveText('记录完成');
  expect(requests).toBe(1);
  await page.locator(`[data-pending-id="${id}"] button`).click();
  await expect(page.locator(`[data-pending-id="${id}"]`)).toHaveCount(0);
  await page.reload();
  await expect(page.locator(`[data-pending-id="${id}"]`)).toHaveCount(0);
  await expect(page.locator('#pending-items li')).toHaveCount(5);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({path:require('path').join(process.env.STUDYBUDDY_TEST_ROOT,'s1-today-mobile.png'),fullPage:true});
  await page.locator('#pending-items li').first().getByRole('link',{name:'查看计划详情'}).click();
  await page.waitForURL(/plan-detail.html/);
  await expect(page.locator('#plan-detail')).toContainText(title);
});

test('S1 material quality item navigates to the actual material workflow',async({page})=>{
  const name='S1 empty '+Date.now()+'.txt';
  await page.goto(`${BASE}/app/materials.html`);
  await page.locator('#file-input').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.alloc(0)});
  await expect(page.locator('#upload-status')).toContainText('已导入 0/1');
  await expect(page.locator('#items li').filter({hasText:name})).toBeVisible();
  // Suspend the plan through its UI so this independent material task is visible.
  await page.goto(`${BASE}/app/plans.html`);
  await page.locator('#plans .plan-item').first().click();
  await page.getByRole('button',{name:'暂停计划',exact:true}).click();
  await expect(page.locator('#plan-status')).toHaveText('暂停计划成功');
  await page.goto(`${BASE}/app/today.html`);
  const item=page.locator('#pending-items li').filter({hasText:name});
  await expect(item).toContainText('正文待核对');
  await item.getByRole('link',{name:'查看材料'}).click();
  await page.waitForURL(/material-detail.html\?material=/);
  await expect(page.locator('#title')).toHaveText(name);
});

test('S1 cited AI draft action opens knowledge workspace directly',async({page})=>{
  const name='S1 draft '+Date.now()+'.txt';
  await page.goto(`${BASE}/app/materials.html`);
  await page.locator('#file-input').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from('Controlled source supports this study module and the generated draft.')});
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1');
  await page.locator('#items li').filter({hasText:name}).getByRole('button',{name:/详情/}).click();
  await page.waitForURL(/material-detail/);
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立');
  await page.locator('#knowledge-tab').click();
  await page.locator('#knowledge-extract').click();
  await page.locator('#knowledge-count').fill('1');
  await page.locator('#knowledge-extract-form button[type=submit]').click();
  await expect(page.locator('#knowledge-list article')).toHaveCount(1);
  await page.goto(`${BASE}/app/today.html`);
  const item=page.locator('#pending-items li').filter({hasText:name});
  await expect(item).toContainText('1 个 AI 草稿');
  await item.getByRole('link',{name:'核对知识草稿'}).click();
  await page.waitForURL(/tab=knowledge/);
  await expect(page.locator('#knowledge-panel')).toBeVisible();
  await page.getByRole('button',{name:'拒绝草稿',exact:true}).click();
  await expect(page.locator('#knowledge-list')).toContainText('已拒绝');
  await page.goto(`${BASE}/app/today.html`);
  await expect(page.locator('#pending-items li').filter({hasText:name})).toHaveCount(0);
});
