# StudyBuddy 产品体验设计指南

> **版本**：v1.0  
> **创建日期**：2026-09-28  
> **适用范围**：StudyBuddy 产品功能设计、用户体验设计、交互流程设计、视觉设计  
> **配套文档**：`docs/[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md`（测试与验证任务执行协议，不涉及产品设计）

---

## ⚠️ 本文件与测试模板的职责边界

**本文件的职责**：
- ✓ 定义什么样的产品体验对用户有价值
- ✓ 指导界面应该如何设计才能让用户愿意每天打开
- ✓ 规范交互流程、视觉风格、文案语气
- ✓ 平衡产品需求与测试需求的冲突

**测试模板的职责**（`AI_AGENT_TASK_DIALOGUE_TEMPLATES.md`）：
- ✓ 指导 AI Agent 如何执行测试、验证、审核任务
- ✓ 确保测试证据可追溯、可复现
- ✗ 不管产品功能设计、用户体验设计

**关键区分**：
- 测试辅助属性（`data-od-id`、详细 `aria-label`、`title="[1] 导入文件夹..."`）**只为测试脚本服务**
- 这些属性不应成为产品界面的主导设计思路
- **产品界面的第一用户 = 真实人类**（家长、孩子），不是 Playwright 和审核 Agent

---

## 第一原则：Buddy 不是后台管理系统

### 什么是 Buddy？

**Buddy = 学习伙伴**，核心特征：
1. **主动性**：不等用户问"今天学什么"，而是主动说"今天继续学五年级语文第3课吗？"
2. **简洁性**：核心流程 ≤ 3 步，用户不需要理解"目标/模块/依赖"等项目管理概念
3. **温暖性**：有鼓励、有反馈、有成就感，不是冷冰冰的数据报表
4. **隐藏复杂度**：后台能力（目标/模块/节奏/来源链接/Provider 配置）默认隐藏，只在"高级设置"入口可见

### 什么不是 Buddy？

**后台管理系统**的特征（StudyBuddy 当前状态）：
- 每个页面都在向陌生人自我介绍："今日任务""你的学习日程""查看今日分配的学习任务和进度"
- 要求用户理解 8+ 项目管理概念：目标/模块/计划草稿/学习项/依赖关系/学习节奏/来源链接/分配
- 串行 loading 让人感觉在等数据库查询
- 状态标签 46 个，用户不知道"来源待复核"是什么意思
- 错误提示是开发者语言：`study_plan_dependency_cycle`、`learning_goal_archived`
- 页面跳转两次全页刷新才能开始学习

---

## 核心设计标准

### 1. 界面语气：对话式，不是演示稿

**❌ 错误示例**（当前 today.html）：
```html
<p class="eyebrow">今日任务</p>
<h1>你的学习日程</h1>
<p class="lead">查看今日分配的学习任务和进度。</p>
```

**✓ 正确示例**：
```html
<h1>今天学什么？</h1>
<!-- 或者直接显示任务 -->
<div class="today-task">
  <h2>五年级语文 · 第3课《草船借箭》</h2>
  <button class="btn-primary btn-large">开始学习</button>
</div>
```

**原则**：
- 用户看到的文本应该像在和朋友对话，不是在读产品说明书
- 标题直接回答用户的问题："今天学什么？""学完了吗？"
- 去掉所有"你的""查看""管理"等第三人称视角的词

### 2. 概念模型：学习任务，不是项目管理

**❌ 用户不应该看到的概念**（除非进入"高级设置"）：
- 目标(Goal)
- 模块(Module)
- 计划草稿(Plan Draft)
- 依赖关系(Predecessor/Successor)
- 学习节奏(Cadence/Timezone/Period)
- 来源链接(Source Link)
- 分配(Allocation)

**✓ 用户应该看到的概念**：
- 今天学什么
- 学习进度（已完成 X 项，还有 Y 项）
- 学习历史（本周学了几天）
- 错题本
- 笔记

**原则**：
- 用户只需要知道"今天学什么""怎么学""学完了吗"
- 所有项目管理概念在后台自动处理或在"家长视图"的"高级设置"中配置

### 3. Loading 状态：统一反馈，不是串行等待

**❌ 错误示例**（当前 today.html）：
```javascript
正在加载今日概览...
正在加载近七天趋势…  
正在加载任务列表...
```

**✓ 正确示例**：
```html
<!-- 方案1：统一 loading -->
<div class="loading-overlay">
  <div class="spinner"></div>
  <p>正在加载今天的学习任务...</p>
</div>

<!-- 方案2：骨架屏 -->
<div class="skeleton">
  <div class="skeleton-title"></div>
  <div class="skeleton-button"></div>
  <div class="skeleton-list"></div>
</div>
```

**原则**：
- 三个独立 loading 改成一个统一 loading
- 或者使用骨架屏，让用户感觉页面在"逐渐显示"而不是"逐个查询数据库"
- Loading 文案简洁："正在加载..."，不要"正在加载今日概览..."+"正在加载任务列表..."

### 4. 状态标签：简化为 3 种，不是 46 种

**❌ 当前问题**（46 个状态标签）：
```javascript
// backend/app/static/js/state.js
draft / confirmed / active / paused / completed / archived /
pending / in_progress / skipped / finished / expired /
queued / running / succeeded / failed / cancelled / stale /
source_deleted / source_unavailable / not_linked / ...
```

**✓ 正确示例**：
- **可用**：材料可以使用，点击"开始学习"
- **处理中**：正在解析/转写/生成，请稍候
- **有问题**：点击查看详情（展开显示具体错误和解决方案）

**原则**：
- 用户只需要知道三种状态：能用/不能用/处理中
- "有问题"状态必须提供下一步动作建议，不能只显示错误码
- 所有 46 个内部状态标签保留在后台，但前端显示时映射到这 3 种

### 5. 错误提示：人话，不是错误码

**❌ 错误示例**（当前 plans.html）：
```javascript
study_plan_dependency_cycle: '检测到依赖环，未保存'
learning_goal_archived: '目标已归档，不能继续使用'
study_rhythm_allocation_duplicate: '该学习项当天已有分配'
```

**✓ 正确示例**：
```html
<div class="error-card">
  <div class="error-message">
    这个学习项和另一个学习项的顺序冲突了
  </div>
  <div class="error-action">
    <button>调整学习顺序</button>
  </div>
</div>

<div class="error-card">
  <div class="error-message">
    这个计划已经归档，不能继续使用
  </div>
  <div class="error-action">
    <button>重新激活计划</button>
  </div>
</div>

<div class="error-card">
  <div class="error-message">
    今天已经安排过这门课了
  </div>
  <div class="error-action">
    <button>改到明天</button>
    <button>调整今天的时间</button>
  </div>
</div>
```

**原则**：
- 错误提示必须用人话，不要技术术语
- 每个错误必须提供至少一个可点击的解决方案
- 错误码保留在日志和开发者工具中，不显示给用户

### 6. 页面跳转：平滑过渡，不是全页刷新

**❌ 当前问题**：
- today.html → plan-detail.html（全页刷新）
- plan-detail.html 内完成学习操作（全页刷新）
- 共两次全页刷新才能完成一次学习

**✓ 正确方案**：

**方案 1：卡片展开**（推荐，改动最小）
```html
<!-- today.html -->
<div class="today-task-card" data-task-id="123">
  <h3>五年级语文 · 第3课</h3>
  <button class="btn-start">开始学习</button>
  
  <!-- 点击后展开，不跳转 -->
  <div class="task-detail" hidden>
    <div class="learning-progress">
      <!-- 学习进度内容 -->
    </div>
    <button class="btn-complete">完成</button>
  </div>
</div>
```

**方案 2：SPA 改造**（长期方案）
- 使用 Vue/React 单页应用
- 页面切换不刷新，使用路由和状态管理

**原则**：
- 核心路径（今天学什么 → 开始学习 → 完成）应该在同一个页面内完成
- 如果必须跳转，使用 URL hash 而不是全页刷新
- 保留后退按钮的正常行为

---

## 三层产品架构

StudyBuddy 需要建立**三层架构**，把不同用户群体的需求分开：

### 层级 1：学生视图（主航道，新建）

**目标用户**：小学生
**核心路径**：今天学什么 → 开始学习 → 获得反馈

**页面清单**（新建）：
- `student.html` - 学生主页
  - 显示：今天要学的内容（1-3 项）
  - 一键开始按钮
  - 学习历史（本周学了几天）
  - 错题本入口

**设计要求**：
- 极简界面，只有大按钮和大字
- 有颜色、有动画、有鼓励反馈
- 完成任务后显示"今天真棒！已经学了 X 分钟"
- 不显示任何项目管理概念（目标/模块/计划/节奏）

### 层级 2：家长视图（简化版）

**目标用户**：家长
**核心路径**：安排学习 → 查看报告 → 调整设置

**页面清单**（简化现有页面）：
- `parent.html` - 家长主页
  - 快速安排：3 步建计划（上传教材 → 选择学习时间 → 开始）
  - 学习报告：本周学习天数、完成率、错题数
  - 设置入口：学习时间、提醒、高级设置

**设计要求**：
- 引导流程清晰，每步有示例和说明
- 隐藏复杂概念，使用自动化和智能推荐
- 高级设置链接到层级 3

### 层级 3：后台/高级功能（现有 21 个页面）

**目标用户**：需要精细控制的高级用户、开发者
**核心路径**：完整的项目管理能力

**页面清单**（保留现有）：
- plans.html（完整计划管理）
- materials.html（资料库）
- practice.html（练习管理）
- qa.html（问答）
- notes.html（笔记）
- settings.html（系统设置）
- 其他 15 个页面

**设计要求**：
- 保持现有功能和测试覆盖
- 只在"高级设置"入口可见
- 不作为主要用户路径

---

## 测试属性与产品属性分离

### 双层属性标准

前端元素需要**同时满足测试需求和产品需求**：

```html
<!-- 测试层属性（只给 Playwright 看，不影响视觉） -->
<button 
  data-od-id="today-start-learning"
  data-testid="start-btn"
  aria-label="开始学习按钮 - 点击开始今天的学习任务"
  
  <!-- 产品层属性（用户看到的） -->
  class="btn-primary btn-large"
  title="开始学习">
  
  开始学习
</button>
```

**原则**：
1. **测试属性**（`data-od-id`、`data-testid`、详细 `aria-label`）必须保留，但不影响视觉
2. **产品属性**（`class`、`title`、可见文本）面向用户，简洁温暖
3. 用户可见的文本 ≠ 测试用的 aria-label
   - 用户看到："开始学习"
   - 测试脚本看到："开始学习按钮 - 点击开始今天的学习任务"

### 禁止的做法

**❌ 不要为了测试污染产品界面**：
```html
<!-- 错误：把测试标识暴露给用户 -->
<button title="[1] 导入文件夹 - 点击此按钮导入教材文件夹">
  导入文件夹
</button>

<!-- 错误：把内部状态标签直接显示给用户 -->
<span class="status-badge">来源待复核</span>
```

**✓ 正确做法**：
```html
<!-- 正确：测试标识在 data-* 和 aria-label 里 -->
<button 
  data-od-id="import-folder"
  aria-label="导入文件夹按钮 - 点击此按钮导入教材文件夹"
  title="导入教材">
  导入文件夹
</button>

<!-- 正确：内部状态映射到用户友好的文本 -->
<span class="status-badge status-processing">处理中</span>
```

---

## 短期速效改进方案（1 天内可完成）

### 1. today.html 改造

**目标**：从"报表系统"变成"学习伙伴"

**改动清单**：
1. **去掉演示稿语气**
   - 删除：`<p class="eyebrow">今日任务</p>`
   - 删除：`<p class="lead">查看今日分配的学习任务和进度。</p>`
   - 改标题：`<h1>你的学习日程</h1>` → `<h1>今天学什么？</h1>`

2. **合并 loading 状态**
   - 三个独立 loading 改成一个统一 loading
   - 或者使用骨架屏

3. **添加"一键继续"大按钮**
   - 页面顶部显示："继续昨天的学习"
   - 点击直接进入上次未完成的任务

4. **任务卡片改为可展开**
   - 点击任务卡片展开详情，不跳转页面
   - 在卡片内完成"开始学习"操作

### 2. 错误提示改造

**目标**：所有错误提示加"怎么办"

**改动清单**：
1. 修改 `backend/app/static/js/api.js` 的 `safeError` 函数
2. 每个错误码映射到：错误描述 + 解决方案
3. 前端显示错误时，同时显示可点击的操作按钮

### 3. 状态简化

**目标**：前端只显示 3 种状态

**改动清单**：
1. 修改 `backend/app/static/js/state.js`
2. 添加 `simplifyStatus` 函数，把 46 种状态映射到 3 种
3. 所有页面调用这个函数显示状态

---

## 中期改造方案（1 周内）

### 1. 创建学生视图

**新建文件**：
- `backend/app/static/student.html`
- `backend/app/static/css/student.css`
- `backend/app/static/js/student.js`

**功能**：
- 极简界面：今天学什么 + 大按钮
- 学习反馈：完成后显示鼓励
- 学习历史：本周学了几天

### 2. 简化家长视图

**新建文件**：
- `backend/app/static/parent.html`
- `backend/app/static/css/parent.css`
- `backend/app/static/js/parent.js`

**功能**：
- 3 步建计划：上传教材 → 选择时间 → 开始
- 学习报告：完成率、错题数
- 高级设置入口

### 3. 添加进度可视化

**改动文件**：
- `backend/app/static/css/app.css`
- 各页面添加进度条、连续天数、完成动画

---

## 长期重构方案（如果想做成产品）

### 1. 架构改 SPA

**技术栈**：React/Vue + Vite
**原因**：页面切换不刷新，用户体验更流畅

### 2. 加 AI 对话入口

**位置**：右下角悬浮球
**功能**：用户可以问"今天学什么""这道题怎么做"

### 3. 加家长/学生双视图切换

**实现**：登录后根据角色显示不同界面
- 学生看到：极简学习界面
- 家长看到：统计和设置界面

### 4. 移动端适配

**原因**：现在这个在手机上基本没法用
**方案**：响应式设计 + PWA

---

## 附录：现有页面诊断清单

| 页面 | 核心问题 | 改进优先级 |
|---|---|---|
| today.html | 演示稿语气、串行 loading、无一键开始 | P0（最高）|
| plans.html | 概念过于复杂（8+ 项目管理概念）| P1 |
| materials.html | 状态标签 46 个，用户不理解 | P1 |
| practice.html | 要填表才能开始练习 | P1 |
| qa.html | 要选择检索方式、建立索引 | P2 |
| notes.html | 功能正常，优先级不高 | P3 |
| settings.html | 太多技术细节暴露给用户 | P2 |
| 其他 14 个页面 | 功能完整，但都是后台风格 | P3 |

---

## 总结

**StudyBuddy 要变成真正的 Buddy，需要做的最核心的事**：

1. **分离测试需求和产品需求**
   - 测试属性藏在 `data-*` 和 `aria-label`
   - 产品界面面向真实人类，简洁温暖

2. **建立三层架构**
   - 学生视图（新建，主航道）
   - 家长视图（简化）
   - 后台/高级功能（保留现有 21 个页面）

3. **改造核心路径**
   - today.html 改成"学习伙伴"风格
   - 一键开始，不要跳转两次页面
   - 错误提示加"怎么办"

4. **不要急于重构**
   - 现有 21 个页面保留，作为"高级功能"
   - 637 个后端测试、551 个浏览器测试全部保留
   - 先建新入口，再逐步迁移用户

**记住**：好的产品 = 用户愿意每天打开；通过测试的产品 ≠ 好的产品。

---

**文档版本**：v1.0  
**维护原则**：只增加产品体验标准和用户需求；不新增测试执行协议（那是 `AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` 的职责）。