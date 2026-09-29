# StudyBuddy Buddy 化任务分解

> **版本**：v1.0  
> **创建日期**：2026-09-28  
> **文档类型**：任务分解（HOW）  
> **配套文档**：  
> - `[产品看]BUDDY_EXPERIENCE_DESIGN.md`（设计标准）  
> - `[产品看]BUDDY_化需求说明.md`（需求说明）

---

## 任务分解总览

### 三期推进策略

```
第一期（P0，1天）     第二期（P1，1周）       第三期（P2，按需）
├─ today.html改造    ├─ 学生视图           ├─ SPA改造
├─ 错误提示改造       ├─ 家长视图           ├─ AI对话入口
└─ 状态简化          └─ 进度可视化         ├─ 双视图切换
                                            └─ 移动端适配
```

### 任务编号规则

- **P0-XX**：第一期短期速效任务
- **P1-XX**：第二期中期改造任务
- **P2-XX**：第三期长期重构任务

---

## 第一期：短期速效（1天内，P0）

### P0-01：today.html 去掉演示稿语气

**目标**：让页面标题和文案像在和朋友对话，不是在读产品说明书

**当前问题**：
```html
<p class="eyebrow">今日任务</p>
<h1>你的学习日程</h1>
<p class="lead">查看今日分配的学习任务和进度。</p>
```

**改动清单**：
1. 删除 `<p class="eyebrow">今日任务</p>`
2. 删除 `<p class="lead">查看今日分配的学习任务和进度。</p>`
3. 改标题：`<h1>你的学习日程</h1>` → `<h1>今天学什么？</h1>`

**文件**：`backend/app/static/today.html`

**验收标准**：
- 打开 today.html，看到的第一句话是"今天学什么？"
- 没有"今日任务""你的学习日程""查看今日分配的学习任务和进度"

**工作量**：30 分钟

---

### P0-02：today.html 合并 loading 状态

**目标**：把三个串行 loading 改成一个统一 loading

**当前问题**：
```javascript
<div id="summary-status">正在加载今日概览...</div>
<div id="weekly-status">正在加载近七天趋势…</div>
<div id="task-status">正在加载任务列表...</div>
```

**改动方案**：

**方案 A：统一 loading（推荐）**
```html
<!-- 新增全局 loading，放在 main 开头 -->
<div id="page-loading" class="loading-overlay">
  <div class="spinner"></div>
  <p>正在加载今天的学习任务...</p>
</div>
```

**改动清单**：
1. 新增全局 loading 容器（放在 `<main>` 开头）
2. 修改 JS：三个加载函数开始时显示全局 loading，全部完成后隐藏
3. CSS 添加 `.loading-overlay` 样式（半透明遮罩 + 居中 spinner）

**文件**：
- `backend/app/static/today.html`（HTML 结构 + JS）
- `backend/app/static/css/app.css`（样式）

**验收标准**：
- 打开 today.html，只看到一个 loading 提示"正在加载今天的学习任务..."
- 不再看到三个独立的"正在加载今日概览""正在加载近七天趋势""正在加载任务列表"

**工作量**：1 小时

---

### P0-03：today.html 内联开始与完成学习

**目标**：页面顶部直接显示最近的学习任务，点一下即可开始，并在 Today 内记录完成

**当前问题**：
- 用户要滚动到任务列表，找到某个任务，进入 plan-detail 才能开始
- 没有"继续昨天的学习"这种快捷入口

**改动方案**：

在今日概览下方、任务列表上方，新增一个大按钮区域：

```html
<div class="quick-start">
  <h2>继续学习</h2>
  <button id="continue-btn" class="btn-primary btn-large">
    开始今天的语文课
  </button>
  <p class="subtitle">五年级上册·第3课·预计20分钟</p>
</div>
```

**改动清单**：
1. HTML：新增 `.quick-start` 区域
2. JS：加载时自动获取"最近的待处理任务"，填充按钮文案
3. JS：点击“开始学习”或“记录完成”调用现有 progress API，页面 URL 不变
4. CSS：`.btn-large` 样式（大字体、醒目颜色、圆角）

**文件**：
- `backend/app/static/today.html`（HTML + JS）
- `backend/app/static/css/app.css`（样式）

**API 需求**：
- 新增或复用现有 API，返回"最近的待处理任务"（或今天第一个任务）

**验收标准**：
- 打开 today.html，在任务列表上方看到一个大按钮"开始今天的语文课"
- 点击按钮后 Today 内显示“记录完成”；完成后显示完成摘要，plan-detail 只保留为次级详情入口

**工作量**：2 小时

---

### P0-04：状态简化为 3 种

**目标**：把 46 种状态标签简化为 3 种：可用 / 处理中 / 有问题

**当前问题**：
- `sbState.labels` 有 46 个键值对（draft/confirmed/active/paused/completed/archived/pending/...）
- 用户在 materials.html 看到："解析完成""没有可提取的正文""已拒绝""失败"

**改动方案**：

**后端保留所有 46 种状态**（不动），但前端展示时映射为 3 种：

```javascript
// 新建 sb-state-display.js
const displayState = {
  // 可用：能直接使用的
  'ready': ['completed', 'active', 'confirmed', 'succeeded'],
  
  // 处理中：正在运行的
  'processing': ['pending', 'in_progress', 'queued', 'running'],
  
  // 有问题：需要用户介入的
  'problem': ['failed', 'stale', 'source_deleted', 'source_unavailable', 
              'not_linked', 'pending_review', 'review_required', 'rejected']
};
```

**改动清单**：
1. 在 `backend/app/static/js/state.js` 提供 `sourceDisplay(value)`，复用三类映射规则
2. 修改 `materials.html` / `today.html` / `plans.html`，可见正文只调用三类映射
3. 前端显示：
   - ✅ 可用（绿色）
   - ⏳ 处理中（黄色）
   - ⚠️ 有问题（红色 + 可展开详情）

**文件**：
- 新建：`backend/app/static/js/sb-state-display.js`
- 修改：`materials.html` / `today.html` / `plans.html`
- CSS：添加状态颜色样式

**验收标准**：
- 打开 materials.html、today.html、plans.html，只看到“可用 / 处理中 / 有问题”三种来源状态；内部详细状态只用于标题或高级上下文
- 点击 ⚠️ 有问题，展开详情："解析失败：格式不支持"

**工作量**：2 小时

---

### P0-05：错误提示加"怎么办"

**目标**：所有错误提示后面跟一个"怎么办"建议

**当前问题**：
```javascript
"study_plan_dependency_cycle: 检测到依赖环，未保存"
"study_rhythm_allocation_duplicate: 该学习项当天已有分配"
"learning_goal_archived: 目标已归档，不能继续使用"
```

**改动方案**：

修改 `backend/app/static/js/api.js` 的错误映射，并提供 `errorInfo(error)`：

```javascript
_errors = {
  'study_plan_dependency_cycle': {
    message: '这个学习项和另一个冲突了',
    action: '试试调整顺序，或者联系我们帮你看看'
  },
  'study_rhythm_allocation_duplicate': {
    message: '今天已经安排过这门课了',
    action: '要改时间吗？或者删掉其中一个'
  },
  'learning_goal_archived': {
    message: '这个计划已经归档了',
    action: '需要重新激活吗？去"计划"页面找到它'
  }
};
```

**改动清单**：
1. 保留 `safeError()` 兼容现有调用方，同时返回结构化的 `message`、`advice`、`action`
2. 依赖冲突聚焦依赖控件，重复日期聚焦日期控件，归档目标/模块刷新计划
3. Today、Materials、Plans 渲染可点击动作；未知错误至少提供重新加载/重试

**文件**：
- `backend/app/static/js/api.js`
- 所有调用 `api.safeError()` 的页面（materials.html / plans.html / today.html）

**验收标准**：
- 触发任何错误，看到的提示格式是："这个学习项和另一个冲突了。试试调整顺序，或者联系我们帮你看看"
- “调整顺序”或“重新加载”动作可点击，且页面不显示原始错误码、路径或 traceback

**工作量**：2 小时

---

## 第二期：中期改造（1周内，P1）

### P1-01：创建学生视图（student.html）

**目标**：新建一个极简的学生视图，只有大字 + 大按钮

**页面结构**：

```html
<main class="student-view">
  <h1 class="greeting">早上好！</h1>
  
  <div class="today-task">
    <p class="task-title">今天学：五年级语文·第3课</p>
    <p class="task-time">预计 20 分钟</p>
    <button class="btn-huge btn-primary">开始</button>
  </div>
  
  <div class="progress">
    <p>本周已学 3 天</p>
    <div class="progress-bar"></div>
  </div>
  
  <div class="recent-achievements">
    <p>🎉 昨天完成了数学练习！</p>
  </div>
</main>
```

**设计要求**：
- 字体：标题 36px+，正文 24px+
- 按钮：至少 60px 高，圆角 12px
- 颜色：主色鲜艳（蓝色/绿色/橙色），不是灰白
- 无导航栏：学生视图只有这一个页面，其他功能藏在家长视图

**改动清单**：
1. 新建 `backend/app/static/student.html`
2. 新建 `backend/app/static/css/student.css`（独立样式）
3. 新建 `backend/app/static/js/student.js`（逻辑）
4. API：复用现有的"今日任务"接口

**验收标准**：
- 打开 student.html，看到大字"早上好！"+ 大按钮"开始"
- 点击"开始"，直接跳转到学习页面
- 整个页面没有导航栏、没有侧边栏、没有"目标""模块""节奏"等术语

**工作量**：1 天

---

### P1-02：简化家长视图（parent.html）

**目标**：创建一个简化的家长视图，只有"安排学习""查看报告""调整设置"三个入口

**页面结构**：

```html
<main class="parent-view">
  <h1>学习安排</h1>
  
  <div class="action-cards">
    <div class="card">
      <h2>安排学习</h2>
      <p>快速创建学习计划</p>
      <button>开始安排</button>
    </div>
    
    <div class="card">
      <h2>查看报告</h2>
      <p>本周学习情况</p>
      <button>查看报告</button>
    </div>
    
    <div class="card">
      <h2>调整设置</h2>
      <p>学习时间、提醒、AI 配置</p>
      <button>去设置</button>
    </div>
  </div>
  
  <a href="/app/index.html" class="link-subtle">进入完整后台</a>
</main>
```

**"安排学习"流程简化为 3 步**：
1. 选教材（从已导入的材料中选）
2. 设定时间（每天几分钟）
3. 自动生成计划

**改动清单**：
1. 新建 `backend/app/static/parent.html`
2. 新建 `backend/app/static/js/parent.js`（3 步引导流程）
3. 新建 `backend/app/static/css/parent.css`
4. API：可能需要新增"一键生成计划"接口（或在前端调用现有 API 组合）

**验收标准**：
- 打开 parent.html，看到三个大卡片
- 点击"安排学习"，进入 3 步引导（选教材 → 设定时间 → 生成计划）
- 整个流程不需要理解"目标""模块""依赖关系"

**工作量**：2 天

---

### P1-03：添加进度可视化

**目标**：在学生视图和今天页添加进度条、连续天数、本周完成率

**新增元素**：

```html
<div class="progress-visual">
  <div class="streak">
    <span class="number">7</span>
    <span class="label">连续天数</span>
  </div>
  
  <div class="week-progress">
    <p>本周已学 4/7 天</p>
    <div class="progress-bar">
      <div class="progress-fill" style="width: 57%"></div>
    </div>
  </div>
  
  <div class="monthly-complete">
    <span>本月完成率 85%</span>
  </div>
</div>
```

**改动清单**：
1. 修改 `student.html` 和 `today.html`，添加进度元素
2. API：新增"学习统计"接口（连续天数、本周天数、本月完成率）
3. CSS：进度条样式（渐变色 + 动画）

**验收标准**：
- 打开 student.html，看到"连续 7 天"+ 进度条
- 完成一次学习后，刷新页面，看到进度条增长（有动画）

**工作量**：1 天

---

### P1-04：现有页面入口重新组织

**目标**：把现有 21 个页面整理成"后台/高级功能"入口

**改动方案**：

在 `parent.html` 添加一个不显眼的链接，进入独立高级功能目录；在 Buddy 内嵌家长页中点击时切换顶层页面：

```html
<a href="/app/advanced.html" target="_top" data-control="parent-advanced">
  进入完整后台
</a>
```

**首页兼容约定**：

- `/`、`/app`、`/app/index.html` 保留到 Today 的统一跳转，与现行运行基线和旧书签兼容。
- `/app/buddy.html` 为简化体验入口，首次默认学生视图，之后恢复已保存的学生/家长视图。
- Today 和共享后台页面提供“学生视图 / 家长视图 / 高级功能”入口；学生与家长页保持简化布局。
- `advanced.html` 按“资料与课堂 / 学习与复盘 / 报告与设置”组织 15 个工作流入口，保留现有页面；有 ID 的详情页仍从对应列表进入，不提供无上下文的详情深链。
- 高级功能页可返回家长视图，共享页面可返回学生/家长视图；这些链接在内嵌页面中切换顶层页面。

**改动清单**：
1. 新增 `advanced.html` 和独立样式，复用现有共享导航和业务页面。
2. 修改 `parent.html` 的“进入完整后台”链接。
3. 修改 `shell.js`，增加学生/家长视图和高级功能返回入口，保留主导航和 Today 首页契约。
4. 补充入口点击、浏览器返回、刷新、无 JavaScript 和窄屏键盘导航测试。

**验收标准**：
- 新用户打开 Buddy，默认看到学生视图；重新打开 Buddy 恢复已保存视图。
- 旧首页别名仍跳转 Today，且可以直接打开学生/家长视图。
- 家长“进入完整后台”直达高级功能目录，目录中所有工作流入口可打开并返回。
- 在 Buddy 家长视图内点击高级功能后顶层 URL 正确；浏览器返回和刷新恢复家长视图。
- 390px 与桌面宽度无横向溢出，键盘和无 JavaScript 的目录返回路径可用。

**工作量**：半天

---

## 第三期：长期重构（按需，P2）

### P2-01：架构改 SPA（React/Vue）

**目标**：把 MPA（多页应用）改成 SPA（单页应用），页面切换不刷新

**方案选择**：
- **方案 A：React + React Router**（生态好，学习成本高）
- **方案 B：Vue 3 + Vue Router**（上手快，中文文档好）
- **方案 C：原生 JS + History API**（不引入框架，适合简单场景）

**改动清单**：
1. 选定框架（推荐 Vue 3）
2. 重构现有 HTML 为组件
3. 路由配置：`/student` / `/parent` / `/today` / ...
4. API 层改为统一的 `fetch` 或 `axios` 封装
5. 状态管理：Pinia（Vue）或 Redux（React）

**工作量**：2-3 周

**优先级**：P2（不急，等前两期完成后再考虑）

---

### P2-02：添加 AI 对话入口

**目标**：右下角悬浮球，用户可以随时问"今天学什么""这道题怎么做"

**实现方案**：

```html
<div class="chat-bubble">
  <button class="chat-btn">💬</button>
  
  <div class="chat-panel">
    <div class="chat-messages">
      <p class="bot-msg">你好！今天想学什么？</p>
    </div>
    <input type="text" placeholder="问我任何问题..." />
  </div>
</div>
```

**改动清单**：
1. 新建 `backend/app/static/js/chat-widget.js`（悬浮球逻辑）
2. CSS：悬浮球样式 + 展开动画
3. API：新增"对话式查询"接口（调用现有 LLM provider）
4. 集成到所有页面（在 `shell.js` 中全局加载）

**工作量**：1 周

**优先级**：P2

---

### P2-03：双视图切换（家长/学生）

**目标**：同一账号可以在"家长模式"和"学生模式"之间切换

**实现方案**：

在右上角添加切换按钮：

```html
<div class="view-switcher">
  <button class="switch-btn" data-view="student">学生视图</button>
  <button class="switch-btn" data-view="parent">家长视图</button>
</div>
```

**改动清单**：
1. 新增"当前视图"状态（存 localStorage）
2. 根据当前视图，显示不同的首页（student.html / parent.html）
3. 学生视图下，隐藏所有"管理后台"入口

**工作量**：3 天

**优先级**：P2

---

### P2-04：移动端适配

**目标**：在手机/平板上也能正常使用

**改动清单**：
1. CSS 添加响应式断点（`@media (max-width: 768px)`）
2. 按钮、字体、间距在小屏幕上放大
3. 导航栏改为汉堡菜单
4. 测试 iOS Safari / Android Chrome

**工作量**：1 周

**优先级**：P2

---

## 任务优先级总结

| 任务编号 | 任务名称 | 工作量 | 优先级 | 依赖 |
|---|---|---|---|---|
| P0-01 | 去掉演示稿语气 | 30分钟 | P0 | 无 |
| P0-02 | 合并 loading 状态 | 1小时 | P0 | 无 |
| P0-03 | Today 内联开始与完成学习 | 2小时 | P0 | 无 |
| P0-04 | 状态简化为 3 种 | 2小时 | P0 | 无 |
| P0-05 | 错误提示加"怎么办" | 2小时 | P0 | 无 |
| P1-01 | 创建学生视图 | 1天 | P1 | P0 全部完成 |
| P1-02 | 简化家长视图 | 2天 | P1 | P0 全部完成 |
| P1-03 | 添加进度可视化 | 1天 | P1 | P1-01 |
| P1-04 | 现有页面入口重组 | 半天 | P1 | P1-01, P1-02 |
| P2-01 | 架构改 SPA | 2-3周 | P2 | P1 全部完成 |
| P2-02 | 添加 AI 对话入口 | 1周 | P2 | 无 |
| P2-03 | 双视图切换 | 3天 | P2 | P1-01, P1-02 |
| P2-04 | 移动端适配 | 1周 | P2 | 无 |

---

## 下一步建议

**立即可做**（今天/明天）：
1. 从 P0-01 开始，按顺序完成 P0 全部 5 个任务
2. 每完成一个任务，浏览器打开 today.html 实际体验一下
3. P0 全部完成后，再考虑是否进入 P1

**关键里程碑**：
- **第 1 天结束**：P0 全部完成，today.html 已经有 Buddy 的感觉
- **第 7 天结束**：P1 全部完成，学生视图和家长视图可用
- **1 个月后**：根据用户反馈，决定是否启动 P2

---

**配套文档**：
- 设计标准：`[产品看]BUDDY_EXPERIENCE_DESIGN.md`
- 需求说明：`[产品看]BUDDY_化需求说明.md`
