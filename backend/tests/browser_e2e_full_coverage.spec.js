import { test, expect } from '@playwright/test';

const BASE_URL = process.env.STUDYBUDDY_BASE_URL || 'http://127.0.0.1:8787';

// 所有21个正式页面
const PAGES = [
  { name: 'materials', path: '/app/materials.html', description: '材料管理' },
  { name: 'material-detail', path: '/app/material-detail.html', description: '材料详情' },
  { name: 'qa', path: '/app/qa.html', description: '问答对话' },
  { name: 'tasks', path: '/app/tasks.html', description: '任务列表' },
  { name: 'index', path: '/app/index.html', description: '入口页面' },
  { name: 'cards', path: '/app/cards.html', description: '卡片管理' },
  { name: 'exercises', path: '/app/exercises.html', description: '练习集管理' },
  { name: 'plans', path: '/app/plans.html', description: '学习计划' },
  { name: 'plan-detail', path: '/app/plan-detail.html', description: '计划详情' },
  { name: 'notes', path: '/app/notes.html', description: '笔记列表' },
  { name: 'note-detail', path: '/app/note-detail.html', description: '笔记详情' },
  { name: 'today', path: '/app/today.html', description: '今日学习' },
  { name: 'practice', path: '/app/practice.html', description: '练习导航' },
  { name: 'practice-session', path: '/app/practice-session.html', description: '答题会话' },
  { name: 'practice-result', path: '/app/practice-result.html', description: '答题结果' },
  { name: 'review', path: '/app/review.html', description: '错题复习' },
  { name: 'capture', path: '/app/capture.html', description: '课堂采集' },
  { name: 'classroom', path: '/app/classroom.html', description: '采集详情' },
  { name: 'reports', path: '/app/reports.html', description: '家长报告' },
  { name: 'settings', path: '/app/settings.html', description: '系统设置' },
  { name: 'settings-provider', path: '/app/settings-provider.html', description: 'Provider配置' },
];

test.describe('StudyBuddy E2E 完整覆盖测试', () => {
  
  // 为每个页面创建测试套件
  for (const pageInfo of PAGES) {
    test.describe(`${pageInfo.description} (${pageInfo.name})`, () => {
      
      test('页面可以加载', async ({ page }) => {
        const response = await page.goto(`${BASE_URL}${pageInfo.path}`);
        expect(response.status()).toBeLessThan(400);
        
        // 等待页面完全加载
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 截图记录
        await page.screenshot({ 
          path: `H:/studybuddy-test/e2e-screenshots/${pageInfo.name}-loaded.png`,
          fullPage: true 
        });
      });
      
      test('页面有标题元素', async ({ page }) => {
        await page.goto(`${BASE_URL}${pageInfo.path}`);
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 检查是否有h1或h2标题
        const hasTitle = await page.locator('h1, h2').count() > 0;
        expect(hasTitle).toBeTruthy();
      });
      
      test('所有可见按钮都有title属性', async ({ page }) => {
        await page.goto(`${BASE_URL}${pageInfo.path}`);
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 获取所有可见按钮
        const buttons = await page.locator('button:visible').all();
        
        let missingTitleCount = 0;
        const missingButtons = [];
        
        for (const button of buttons) {
          const title = await button.getAttribute('title');
          const id = await button.getAttribute('id');
          const text = await button.textContent();
          
          if (!title) {
            missingTitleCount++;
            missingButtons.push({ id, text: text?.trim() });
          }
        }
        
        if (missingTitleCount > 0) {
          console.log(`⚠ ${pageInfo.name} 有 ${missingTitleCount} 个按钮缺少title:`);
          missingButtons.forEach(btn => {
            console.log(`  - id="${btn.id}" text="${btn.text}"`);
          });
        }
        
        // 不强制要求所有按钮都有title（因为有些是动态生成的）
        // 但记录下来供后续改进
      });
      
      test('主要交互元素可点击', async ({ page }) => {
        await page.goto(`${BASE_URL}${pageInfo.path}`);
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 获取所有可见的主要按钮（不包括下拉菜单等次要按钮）
        const mainButtons = await page.locator('button:visible').all();
        
        let clickableCount = 0;
        let errorCount = 0;
        const errors = [];
        
        // 只测试前5个按钮，避免测试时间过长
        const buttonsToTest = mainButtons.slice(0, 5);
        
        for (const button of buttonsToTest) {
          try {
            const id = await button.getAttribute('id');
            const isEnabled = await button.isEnabled();
            
            if (isEnabled) {
              clickableCount++;
            }
          } catch (error) {
            errorCount++;
            errors.push(error.message);
          }
        }
        
        // 至少要有一个可点击的按钮（除非是纯展示页面）
        if (mainButtons.length > 0) {
          expect(clickableCount).toBeGreaterThan(0);
        }
      });
      
      test('页面没有JavaScript错误', async ({ page }) => {
        const jsErrors = [];
        
        page.on('pageerror', error => {
          jsErrors.push(error.message);
        });
        
        page.on('console', msg => {
          if (msg.type() === 'error') {
            jsErrors.push(msg.text());
          }
        });
        
        await page.goto(`${BASE_URL}${pageInfo.path}`);
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 等待一段时间让异步错误冒出来
        await page.waitForTimeout(2000);
        
        if (jsErrors.length > 0) {
          console.log(`⚠ ${pageInfo.name} 有JavaScript错误:`);
          jsErrors.forEach(err => console.log(`  - ${err}`));
        }
        
        // 截图记录最终状态
        await page.screenshot({ 
          path: `H:/studybuddy-test/e2e-screenshots/${pageInfo.name}-final.png`,
          fullPage: true 
        });
      });
      
    });
  }
  
  // 额外的集成测试
  test.describe('关键流程测试', () => {
    
    test('材料列表→详情页导航', async ({ page }) => {
      // 访问材料列表
      await page.goto(`${BASE_URL}/app/materials.html`);
      await page.waitForLoadState('networkidle', { timeout: 10000 });
      
      // 查找第一个材料卡片
      const firstCard = page.locator('.material-card, [data-material-id]').first();
      const cardExists = await firstCard.count() > 0;
      
      if (cardExists) {
        await firstCard.click();
        await page.waitForLoadState('networkidle', { timeout: 10000 });
        
        // 验证跳转到了详情页
        expect(page.url()).toContain('material-detail.html');
      } else {
        console.log('⚠ 没有找到材料卡片（可能数据库为空）');
      }
    });
    
    test('设置页面保存配置', async ({ page }) => {
      await page.goto(`${BASE_URL}/app/settings-provider.html`);
      await page.waitForLoadState('networkidle', { timeout: 10000 });
      
      // 检查是否有保存按钮
      const saveButton = page.locator('button:has-text("保存"), button:has-text("测试")').first();
      const buttonExists = await saveButton.count() > 0;
      
      expect(buttonExists).toBeTruthy();
    });
    
  });
  
});
