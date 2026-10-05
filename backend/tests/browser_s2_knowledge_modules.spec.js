const {test, expect} = require('@playwright/test');
const BASE = process.env.STUDYBUDDY_BASE_URL;

async function material(page) {
  const name = `s2-${Date.now()}-${Math.random().toString(16).slice(2)}.txt`;
  await page.goto(`${BASE}/app/materials.html`);
  await page.locator('#file-input').setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from('Newton force mass acceleration is established by this controlled study.')});
  await expect(page.locator('#upload-status')).toContainText('已导入 1/1');
  await page.locator('#items li').filter({hasText:name}).getByRole('button',{name:/详情/}).click();
  await page.waitForURL(/material-detail/);
  await page.locator('#index').click();
  await expect(page.locator('#index-status')).toContainText('AI 索引已建立');
  await page.locator('#knowledge-tab').click();
  await expect(page.locator('#knowledge-save')).toBeEnabled();
  return page.url();
}

test('S2 manual module -> selected evidence exercise -> scored session -> mastery after reload', async ({page}) => {
  const url = await material(page);
  await page.locator('#knowledge-title').fill('Newton force module');
  await page.locator('#knowledge-description').fill('Force and acceleration');
  await page.locator('#knowledge-save').click();
  const module = page.locator('#knowledge-list article').filter({hasText:'Newton force module'});
  await expect(module).toContainText('已确认');
  await module.getByRole('link',{name:'按此模块练习'}).click();
  await page.waitForURL(/exercises/);
  await expect(page.locator('#exercise-module-status')).toContainText('已加载');
  await page.locator('#new-set-title').fill('S2 practice '+Date.now());
  await page.locator('#set-create-form button').click();
  await page.locator('#sets li').filter({hasText:'S2 practice'}).last().click();
  await page.locator('#exercise-generate-form button').click();
  await expect(page.locator('#exercise-status')).toContainText('题目草稿已生成');
  await page.locator('#exercises li').first().click();
  await page.getByRole('button',{name:'确认题目',exact:true}).click();
  await expect(page.getByRole('button',{name:'开始作答',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'开始作答',exact:true}).click();
  await page.getByRole('button',{name:'为该题目创建练习会话'}).click();
  await page.waitForURL(/practice-session/);
  await page.getByRole('button',{name:'开始练习',exact:true}).click();
  await page.locator('#answer').selectOption('0');
  await page.getByRole('button',{name:'提交答案',exact:true}).click();
  await expect(page.locator('#session-status')).toContainText('答案已提交');
  await page.getByRole('button',{name:'完成会话',exact:true}).click();
  await page.waitForURL(/practice-result/);
  await page.goto(url);
  await page.locator('#knowledge-tab').click();
  await expect(page.locator('#knowledge-list')).toContainText('10%');
  await page.reload();
  await page.locator('#knowledge-tab').click();
  await expect(page.locator('#knowledge-list')).toContainText('10%');
});

test('S2 AI drafts can be edited, confirmed or rejected, searched and deleted', async ({page}) => {
  await material(page);
  await page.locator('#knowledge-extract').click();
  await page.locator('#knowledge-count').fill('2');
  await page.locator('#knowledge-extract-form button[type=submit]').click();
  await expect(page.locator('#knowledge-list article')).toHaveCount(2);
  const first=page.locator('#knowledge-list article').filter({hasText:'知识要点 1'});
  await expect(first).toContainText('AI 草稿，待确认');
  await expect(first.getByRole('link',{name:'按此模块练习'})).toHaveCount(0);
  await first.getByRole('button',{name:'编辑模块'}).click();
  await page.locator('#knowledge-title').fill('Edited Newton');
  await page.locator('#knowledge-save').click();
  const edited=page.locator('#knowledge-list article').filter({hasText:'Edited Newton'});
  await edited.getByRole('button',{name:'确认模块'}).click();
  await expect(edited).toContainText('已确认');
  await page.locator('#knowledge-list article').filter({hasText:'知识要点 2'}).getByRole('button',{name:'拒绝草稿'}).click();
  await expect(page.locator('#knowledge-list')).toContainText('已拒绝');
  await page.locator('#knowledge-query').fill('Edited');
  await page.locator('#knowledge-query').press('Enter');
  await expect(page.locator('#knowledge-list article')).toHaveCount(1);
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'删除模块'}).click();
  await expect(page.locator('#knowledge-list')).toContainText('暂无知识模块');
});

test('S2 narrow viewport, keyboard and failure retry keep manual work available', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await material(page);
  await page.route('**/api/knowledge-modules/extract', route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'provider_not_configured'})}));
  await page.locator('#knowledge-extract').click();
  await page.locator('#knowledge-extract-form button[type=submit]').click();
  await expect(page.locator('#knowledge-panel [role=status]').first()).toContainText('可使用手动添加');
  await page.locator('#knowledge-title').fill('Keyboard module');
  await page.locator('#knowledge-title').press('Enter');
  await expect(page.locator('#knowledge-list')).toContainText('Keyboard module');
  await page.unroute('**/api/knowledge-modules/extract');
  await page.locator('#knowledge-extract').click();
  await page.locator('#knowledge-count').fill('1');
  await page.locator('#knowledge-extract-form button[type=submit]').click();
  await expect(page.locator('#knowledge-list article')).toHaveCount(2);
  expect(await page.locator('body').innerText()).not.toMatch(/Traceback|api_key|answer_key|INSERT INTO/);
});
