# StudyBuddy 用户手册浏览器验证任务模板

> **文档性质**: 任务执行模板  
> **适用角色**: AI Agent、测试工程师  
> **最后更新**: 2026-09-27  
> **任务编号**: `TASK-BROWSER-VERIFICATION-001`

---

## 任务目标

按照 `H:\studybuddy\docs\[用户看]StudyBuddy新手用户使用手册.html` 和 `H:\studybuddy\docs\[用户看]StudyBuddy使用手册.html` 中定义的所有用户场景，使用**真实浏览器自动化**，模拟真实用户的操作行为，逐一验证每个场景、每个页面、每个按钮、每个链接。

---

## 执行要求

### 1. 环境准备

#### 1.1 服务启动
```powershell
# 使用测试数据目录启动服务
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787
```

#### 1.2 验证服务运行
```bash
curl http://127.0.0.1:8787/api/health
# 期望: {"status":"ok"}
```

#### 1.3 工具准备
- 使用项目已有的 Playwright（`backend/tests/browser/` 中的配置）
- 浏览器: Chromium
- 测试数据: `H:\studybuddy-test/fixtures/`

---

### 2. 验证方式

**必须使用真实浏览器操作**，不是 curl、不是 API 测试：

- ✓ 在 Chromium 浏览器中打开页面
- ✓ 自动化点击每个按钮
- ✓ 自动化点击每个链接
- ✓ 自动化填写每个表单
- ✓ 自动化验证页面跳转
- ✓ 截图记录每个关键步骤

**验证层次**:
1. **页面加载验证** - URL、标题、关键元素
2. **按钮交互验证** - 点击、响应、状态变化
3. **链接导航验证** - 跳转、目标页面加载
4. **表单提交验证** - 输入、提交、结果反馈
5. **异步操作验证** - 加载状态、完成状态、错误处理

---

### 3. 验证场景清单

#### 场景组 A: 新手用户使用手册的完整流程

按照新手手册的章节顺序，逐一执行：

| 场景编号 | 场景名称 | 起始页面 | 关键操作 | 验证点 |
|---------|---------|---------|---------|-------|
| A-01 | 快速开始 | `/` | 访问首页 | 重定向到 `/app/today.html` |
| A-02 | 上传学习资料 | `/app/materials.html` | 点击上传，选择文件 | 材料出现在列表 |
| A-03 | 查看材料详情 | `/app/materials.html` | 点击材料项 | 跳转到 `/app/material-detail.html` |
| A-04 | 建立AI索引 | `/app/material-detail.html` | 点击"建立索引" | 任务创建，状态更新 |
| A-05 | 提问 | `/app/qa.html` | 输入问题，点击提交 | 显示回答 |
| A-06 | 查看引用 | `/app/qa.html` | 点击引用链接 | 定位到材料位置 |
| A-07 | 复习卡片 | `/app/cards.html` | 查看卡片，标记掌握 | 卡片状态更新 |
| A-08 | 练习 | `/app/practice.html` | 创建练习，完成练习 | 显示结果 |

#### 场景组 B: 完整使用手册的所有功能点

按照完整手册的章节，验证：

| 场景编号 | 功能模块 | 页面路径 | 操作步骤 |
|---------|---------|---------|---------|
| B-01 | 材料管理 | `/app/materials.html` | 上传、删除、恢复、导出、搜索 |
| B-02 | 学习目标 | `/app/plans.html` | 创建目标、查看列表 |
| B-03 | 学习计划 | `/app/plans.html`, `/app/plan-detail.html` | 创建计划、激活、查看详情 |
| B-04 | 问答功能 | `/app/qa.html` | 提问、查看历史、引用定位 |
| B-05 | 笔记生成 | `/app/notes.html`, `/app/note-detail.html` | 生成、查看、确认、归档 |
| B-06 | 卡片复习 | `/app/cards.html` | 查看卡片、复习、标记掌握 |
| B-07 | 练习 | `/app/practice.html`, `/app/exercises.html` | 创建练习集、完成练习、查看错题 |
| B-08 | 学习报告 | `/app/reports.html` | 生成报告、查看、导出 |
| B-09 | 课堂采集 | `/app/capture.html` | 创建会话、上传音频、转录、确认 |
| B-10 | 设置 | `/app/settings.html`, `/app/settings-provider.html` | 查看能力、配置 Provider、测试连接 |

#### 场景组 C: 每个页面的所有交互元素

对于以下每个页面，验证**所有按钮**和**所有链接**：

| 页面路径 | 页面名称 | 预期按钮数 | 预期链接数 |
|---------|---------|-----------|-----------|
| `/app/today.html` | 今日任务 | 2+ | 4+ |
| `/app/materials.html` | 材料管理 | 8+ | 3+ |
| `/app/material-detail.html` | 材料详情 | 5+ | 2+ |
| `/app/plans.html` | 学习计划 | 3+ | 3+ |
| `/app/plan-detail.html` | 计划详情 | 5+ | 2+ |
| `/app/qa.html` | 问答 | 3+ | 3+ |
| `/app/notes.html` | 笔记 | 5+ | 3+ |
| `/app/note-detail.html` | 笔记详情 | 4+ | 2+ |
| `/app/cards.html` | 卡片 | 3+ | 3+ |
| `/app/practice.html` | 练习 | 6+ | 3+ |
| `/app/practice-session.html` | 练习会话 | 4+ | 1+ |
| `/app/exercises.html` | 练习管理 | 4+ | 3+ |
| `/app/reports.html` | 报告 | 7+ | 3+ |
| `/app/capture.html` | 课堂采集 | 6+ | 3+ |
| `/app/settings.html` | 设置 | 9+ | 4+ |
| `/app/settings-provider.html` | Provider配置 | 5+ | 2+ |
| `/app/review.html` | 复习 | 4+ | 2+ |
| `/app/tasks.html` | 任务监控 | 3+ | 3+ |

---

### 4. 每个页面的验证步骤

对于每个页面，按以下标准化步骤验证：

#### 步骤 1: 打开页面
```javascript
await page.goto('http://127.0.0.1:8787/app/{page}.html');
await page.waitForLoadState('networkidle');
```
- 验证 URL 正确
- 验证页面标题（`<title>` 标签）
- 截图：`{场景编号}_001_initial.png`

#### 步骤 2: 识别所有按钮
```javascript
const buttons = await page.locator('button, .btn, [role="button"]').all();
```
- 列出所有按钮元素
- 记录 ID、class、文本、状态（enabled/disabled）
- 输出到清单文件

#### 步骤 3: 逐个点击按钮
```javascript
for (const button of buttons) {
  const btnId = await button.getAttribute('id');
  await button.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `{场景编号}_btn_{btnId}.png` });
}
```
- 点击前记录状态
- 点击并等待响应
- 验证点击效果（页面变化、API 请求、弹窗等）
- 截图记录
- 记录结果（成功/失败/禁用/无响应）

#### 步骤 4: 识别所有链接
```javascript
const links = await page.locator('a[href^="/app/"]').all();
```
- 列出所有内部链接（`/app/` 开头）
- 记录 href、文本

#### 步骤 5: 逐个点击链接
```javascript
for (const link of links) {
  const href = await link.getAttribute('href');
  await link.click();
  await page.waitForURL(`**${href}`);
  await page.screenshot({ path: `{场景编号}_link_{name}.png` });
  await page.goBack();
}
```
- 点击链接
- 验证页面跳转
- 验证目标页面加载
- 截图目标页面
- 返回原页面

#### 步骤 6: 识别所有表单
```javascript
const inputs = await page.locator('input, textarea, select').all();
```
- 列出所有表单字段
- 记录 name、type、placeholder、required

#### 步骤 7: 测试表单交互
```javascript
await page.fill('input[name="question"]', '测试问题');
await page.click('button[type="submit"]');
await page.waitForResponse(resp => resp.url().includes('/api/'));
```
- 填写表单（使用合理的测试数据）
- 点击提交
- 验证提交结果（成功响应、错误提示）
- 截图结果

---

### 5. 输出要求

#### 5.1 执行日志
**路径**: `H:\studybuddy-test\verification\browser_execution_log_{YYYYMMDD_HHMMSS}.md`

**格式**:
```markdown
# 浏览器验证执行日志

**任务编号**: TASK-BROWSER-VERIFICATION-001  
**执行时间**: 2026-09-27 10:30:00  
**执行者**: Claude / 测试工程师姓名  
**服务地址**: http://127.0.0.1:8787  

---

## 场景 A-01: 快速开始

**执行时间**: 2026-09-27 10:30:15  
**页面**: `/`  

### 操作步骤
1. ✓ 打开根路径 `/`
2. ✓ 验证自动重定向到 `/app/today.html`
3. ✓ 验证页面标题 "StudyBuddy · 今天"
4. ✓ 验证导航栏显示 4 个链接

### 截图
- `A01_001_initial.png` - 首页重定向后
- `A01_002_navigation.png` - 导航栏特写

### 验证结果
**状态**: PASS  
**耗时**: 2.3s  
**备注**: 无异常

---

## 场景 A-02: 上传学习资料

**执行时间**: 2026-09-27 10:30:30  
**页面**: `/app/materials.html`  

### 操作步骤
1. ✓ 打开材料页面
2. ✓ 点击上传按钮 `#folder-btn`
3. ✓ 选择测试文件 `H:\studybuddy-test\fixtures\test_material.pdf`
4. ✓ 等待上传完成（API: POST /api/materials）
5. ✓ 验证材料出现在列表中

### 截图
- `A02_001_materials_initial.png`
- `A02_002_upload_button_clicked.png`
- `A02_003_upload_success.png`

### 验证结果
**状态**: PASS  
**耗时**: 3.5s  
**Material ID**: material_abc123...  
**备注**: 上传成功，文件大小 1.2 MB

---

## 场景 A-03: 查看材料详情

...
```

#### 5.2 UI 元素清单
**路径**: `H:\studybuddy-test\verification\ui_elements_inventory.md`

**格式**:
```markdown
# UI 元素清单

**生成时间**: 2026-09-27 10:45:00  
**任务编号**: TASK-BROWSER-VERIFICATION-001  

---

## /app/today.html - 今日任务

### 页面信息
- **URL**: http://127.0.0.1:8787/app/today.html
- **标题**: StudyBuddy · 今天
- **加载时间**: 0.8s

### 按钮 (2个)
| ID | 文本 | 类型 | 状态 | 点击效果 | 验证结果 |
|----|------|------|------|---------|---------|
| retry-today | 重新加载 | button | enabled | 刷新页面数据 | PASS |
| - | 管理计划 | link-button | enabled | 跳转到 /app/plans.html | PASS |

### 链接 (4个)
| href | 文本 | 位置 | 验证结果 |
|------|------|------|---------|
| /app/materials.html | 学习材料 | 导航栏 | PASS |
| /app/plans.html | 学习计划 | 导航栏 | PASS |
| /app/practice.html | 练习 | 导航栏 | PASS |
| /app/reports.html | 报告 | 导航栏 | PASS |

### 表单 (0个)
无表单元素

---

## /app/materials.html - 材料管理

### 页面信息
- **URL**: http://127.0.0.1:8787/app/materials.html
- **标题**: StudyBuddy · 资料
- **加载时间**: 1.2s

### 按钮 (8个)
| ID | 文本 | 类型 | 状态 | 点击效果 | API | 验证结果 |
|----|------|------|------|---------|-----|---------|
| folder-btn | 上传 | button | enabled | 打开文件选择器 | POST /api/materials | PASS |
| apply-filters | 应用筛选 | button | enabled | 刷新列表 | GET /api/materials | PASS |
| view-deleted | 查看已删除 | button | enabled | 显示已删除材料 | GET /api/materials/deleted | PASS |
| retry-materials | 重试 | button | hidden | 失败后重新加载 | GET /api/materials | SKIP (隐藏) |
| goto-qa | 提问 | button | disabled | 跳转到问答页 | - | PASS (禁用状态正确) |
| export-originals | 导出原文件 | button | enabled | 下载 ZIP | GET /api/materials/export | PASS |
| export-texts | 导出文本 | button | enabled | 下载文本 ZIP | GET /api/materials/export | PASS |
| export-all | 导出全部 | button | enabled | 下载所有 | GET /api/materials/export | PASS |

### 链接 (3个)
| href | 文本 | 验证结果 |
|------|------|---------|
| /app/today.html | 今天 | PASS |
| /app/plans.html | 计划 | PASS |
| /app/practice.html | 练习 | PASS |

### 表单 (2个)
| name | type | placeholder | 验证结果 |
|------|------|-------------|---------|
| search | text | 搜索材料... | PASS |
| - | file | - | PASS (上传功能) |

---

## 页面统计

| 页面 | 按钮数 | 链接数 | 表单数 | 验证状态 |
|------|-------|--------|--------|---------|
| today.html | 2 | 4 | 0 | PASS |
| materials.html | 8 | 3 | 2 | PASS |
| material-detail.html | 5 | 2 | 0 | PASS |
| plans.html | 3 | 3 | 1 | PASS |
| qa.html | 3 | 3 | 1 | PASS |
| ... | ... | ... | ... | ... |
| **总计** | **65** | **48** | **12** | - |
```

#### 5.3 截图
**路径**: `H:\studybuddy-test\verification\screenshots\`

**命名规则**: `{场景编号}_{步骤序号}_{描述}_{时间戳}.png`

**示例**:
- `A01_001_initial_20260927103015.png` - 场景 A-01，步骤 1，初始状态
- `A02_003_upload_success_20260927103045.png` - 场景 A-02，步骤 3，上传成功
- `B04_002_qa_answer_20260927104512.png` - 场景 B-04，步骤 2，问答回答

**截图要求**:
- 格式: PNG
- 分辨率: 1920x1080 (全屏) 或实际浏览器窗口大小
- 包含完整页面（必要时滚动截图）
- 关键元素需要高亮标注

#### 5.4 最终验证报告
**路径**: `H:\studybuddy-test\verification\browser_verification_report_{YYYYMMDD}.md`

**必须包含章节**:

```markdown
# StudyBuddy 用户手册浏览器验证报告

**任务编号**: TASK-BROWSER-VERIFICATION-001  
**执行时间**: 2026-09-27  
**执行者**: [姓名]  

---

## 执行摘要

### 统计数据
- **场景总数**: 28 个
- **通过**: 25 个 (89%)
- **失败**: 2 个 (7%)
- **跳过**: 1 个 (4%)
- **总耗时**: 45 分钟

### 快速结论
- ✓ 核心用户路径（导入→索引→问答→引用）完全通过
- ✗ 发现 2 个 P1 级别问题
- ⚠️ 3 个功能需要配置后才能使用

---

## 场景详细结果

### 场景组 A: 新手用户流程 (8/8 PASS)
| 场景 | 名称 | 结果 | 耗时 | 问题 |
|------|------|------|------|------|
| A-01 | 快速开始 | PASS | 2s | - |
| A-02 | 上传材料 | PASS | 4s | - |
| A-03 | 查看详情 | PASS | 3s | - |
| A-04 | 建立索引 | PASS | 5s | - |
| A-05 | 提问 | PASS | 6s | - |
| A-06 | 查看引用 | PASS | 2s | - |
| A-07 | 复习卡片 | PASS | 4s | - |
| A-08 | 练习 | PASS | 5s | - |

### 场景组 B: 完整功能 (17/20 PASS, 2 FAIL, 1 SKIP)
| 场景 | 功能模块 | 结果 | 问题 |
|------|---------|------|------|
| B-01 | 材料管理 | PASS | - |
| B-02 | 学习目标 | PASS | - |
| B-03 | 学习计划 | PASS | - |
| B-04 | 问答功能 | FAIL | P1-001: 未配置提示不明显 |
| B-05 | 笔记生成 | PASS | - |
| B-06 | 卡片复习 | PASS | - |
| B-07 | 练习 | PASS | - |
| B-08 | 学习报告 | FAIL | P1-002: 导出按钮失效 |
| B-09 | 课堂采集 | SKIP | 需要 ASR 配置 |
| B-10 | 设置 | PASS | - |

### 场景组 C: UI 元素 (65/68 按钮, 48/48 链接)
- ✓ 所有导航链接正常
- ✓ 绝大多数按钮响应正常
- ✗ 3 个按钮存在问题（见问题清单）

---

## 问题清单

### P0 问题 (0个)
无

### P1 问题 (2个)

#### P1-001: 问答页面 AI 未配置提示不够明显
- **页面**: `/app/qa.html`
- **场景**: B-04
- **描述**: 当 AI Provider 未配置时，提问按钮虽然禁用，但没有明显的提示告诉用户原因
- **截图**: `B04_issue_001.png`
- **期望**: 在页面顶部显示醒目提示："需要先配置 AI Provider 才能使用问答功能"
- **代码位置**: `backend/app/static/qa.html` (推测)
- **建议**: 添加提示横幅，链接到设置页面

#### P1-002: 报告导出按钮在某些情况下失效
- **页面**: `/app/reports.html`
- **场景**: B-08
- **描述**: 点击"导出 Markdown"按钮时，如果报告内容过大，按钮无响应
- **截图**: `B08_issue_001.png`
- **复现步骤**: 生成包含大量内容的报告 → 点击导出 → 无响应
- **期望**: 显示加载状态或错误提示
- **建议**: 添加导出进度提示

### P2 问题 (3个)

#### P2-001: 材料搜索框占位符文字不够清晰
- **页面**: `/app/materials.html`
- **描述**: 搜索框 placeholder "搜索材料..." 不够具体
- **建议**: 改为 "搜索材料名称或内容..."

#### P2-002: 练习页面的"重试"按钮位置不明显
- **页面**: `/app/practice.html`
- **描述**: 重试按钮在失败后才显示，但位置在底部不易发现
- **建议**: 移到更显眼的位置

#### P2-003: 设置页面的自检按钮缺少加载状态
- **页面**: `/app/settings.html`
- **描述**: 点击"重新自检"按钮后，按钮无加载状态，用户不知道是否在执行
- **建议**: 添加 loading 状态

### P3 问题 (1个)

#### P3-001: 部分页面标题与导航不一致
- **描述**: 某些页面的 `<title>` 标签与顶部导航显示的名称不完全一致
- **建议**: 统一命名规范

---

## 与用户手册的不一致点

### 不一致 1: 课堂采集入口描述
- **手册位置**: 完整使用手册 > 课堂采集章节
- **手册描述**: "点击顶部导航的'课堂'进入采集页面"
- **实际情况**: 导航栏中没有"课堂"链接，需要直接访问 `/app/capture.html`
- **严重程度**: P1
- **建议修正**: 更新手册，说明需要通过直接访问 URL 或其他入口

### 不一致 2: 索引建立的描述
- **手册位置**: 新手使用手册 > 建立 AI 索引
- **手册描述**: "点击'建立混合索引'按钮"
- **实际情况**: 按钮文本为"建立 AI 索引"，没有"混合"二字
- **严重程度**: P2
- **建议修正**: 统一按钮文本描述

### 不一致 3: 报告生成时间描述
- **手册位置**: 完整使用手册 > 学习报告
- **手册描述**: "报告生成通常需要 10-30 秒"
- **实际情况**: 测试中报告生成平均耗时 3-5 秒（fake provider）
- **严重程度**: P3
- **建议修正**: 说明时间取决于 Provider 配置和报告复杂度

---

## 建议修复的内容

### 优先级 1 (必须修复)
1. P1-001: 问答页面添加 AI 未配置提示
2. P1-002: 报告导出添加进度提示
3. 手册不一致 1: 更新课堂采集入口说明

### 优先级 2 (建议修复)
1. P2-001: 改进搜索框占位符
2. P2-002: 调整重试按钮位置
3. 手册不一致 2: 统一按钮文本描述

### 优先级 3 (可选优化)
1. P2-003: 添加自检按钮加载状态
2. P3-001: 统一页面标题
3. 手册不一致 3: 更新报告生成时间说明

---

## 附录

### A. 测试环境
- **操作系统**: Windows 11
- **浏览器**: Chromium 120.0
- **Python**: 3.10
- **服务地址**: http://127.0.0.1:8787
- **数据目录**: H:\studybuddy-test\data_root
- **测试数据**: H:\studybuddy-test\fixtures

### B. 执行工具
- **Playwright**: 1.40.0
- **测试脚本**: H:\studybuddy-test\verification\scripts\run_verification.js

### C. 截图清单
- 总截图数: 127 张
- 存放路径: H:\studybuddy-test\verification\screenshots\
- 总大小: 45.2 MB

### D. 配置状态
- AI Provider: ✗ 未配置 (使用 fake provider)
- Embedding: ✗ 未配置
- OCR: ✓ 已配置 (PaddleOCR)
- ASR: ✓ 已配置 (Whisper)
- SMTP: ✗ 未配置

---

**报告生成时间**: 2026-09-27 11:30:00  
**签名**: [执行者签名]
```

---

### 6. 特殊处理

#### 6.1 需要配置的功能

**处理原则**: 验证未配置时的提示和降级行为

| 功能 | 配置要求 | 未配置时行为 | 验证点 |
|------|---------|-------------|--------|
| 问答 | AI Provider | 按钮禁用 + 提示 | 提示是否清晰 |
| 索引 | Embedding (可选) | 降级到词法检索 | 是否有降级提示 |
| 笔记生成 | AI Provider | 按钮禁用 + 提示 | 提示是否清晰 |
| 练习生成 | AI Provider | 按钮禁用 + 提示 | 提示是否清晰 |
| 课堂采集 | OCR/ASR | 功能可用但质量未验证 | 是否显示配置状态 |
| 报告投递 | SMTP/飞书 | 功能隐藏或禁用 | 是否有配置入口 |

**验证要求**:
- ✓ 验证未配置时的 UI 提示
- ✓ 验证配置入口的可达性
- ✓ 验证降级功能的可用性
- ✗ 不要求验证真实 Provider 的质量

#### 6.2 异步操作

**处理原则**: 验证加载状态和完成状态的 UI 反馈

| 操作 | 预期耗时 | 超时时间 | 验证点 |
|------|---------|---------|--------|
| 材料上传 | 1-5s | 30s | 进度条、成功提示 |
| 索引任务 | 3-10s | 60s | 任务状态、完成提示 |
| 问答请求 | 2-8s | 30s | 加载动画、回答显示 |
| 笔记生成 | 5-15s | 60s | 生成进度、草稿确认 |
| 报告生成 | 3-10s | 60s | 生成状态、预览加载 |
| 转录 | 10-30s | 120s | 转录进度、结果显示 |

**验证要求**:
- ✓ 操作开始时显示加载状态
- ✓ 操作完成时有明确反馈
- ✓ 操作失败时显示错误信息和重试按钮
- ✓ 长时操作有进度指示

#### 6.3 错误处理

**处理原则**: 故意触发错误，验证错误提示和恢复机制

| 错误场景 | 触发方式 | 期望行为 |
|---------|---------|---------|
| 无效文件上传 | 上传非支持格式 | 显示错误提示 "不支持的文件格式" |
| 空问题提交 | 问答框为空时点击提交 | 禁用提交按钮或显示提示 |
| 网络错误 | 断网后操作 | 显示网络错误提示 + 重试按钮 |
| API 失败 | 服务返回 500 | 显示错误提示 + 重试按钮 |
| 超大文件 | 上传超过限制的文件 | 显示文件过大提示 |

**验证要求**:
- ✓ 错误提示清晰、易懂
- ✓ 提供恢复操作（重试、取消）
- ✓ 不泄露敏感信息（路径、密钥、堆栈）

---

### 7. 约束条件

#### 7.1 文件存放规则

| 路径 | 用途 | 允许操作 |
|------|------|---------|
| `H:\studybuddy` | 源码仓库 | ✗ 不创建任何文件 |
| `H:\studybuddy-data` | 正式数据 | ✗ 不写入测试数据 |
| `H:\studybuddy-test` | 测试目录 | ✓ 所有测试产物 |
| `H:\studybuddy-test\data_root` | 测试数据根 | ✓ 服务运行数据 |
| `H:\studybuddy-test\fixtures` | 测试材料 | ✓ 上传用测试文件 |
| `H:\studybuddy-test\verification` | 验证报告 | ✓ 所有验证产物 |

#### 7.2 数据隔离

**启动服务时必须指定测试数据目录**:
```powershell
-DataRoot H:\studybuddy-test\data_root
```

**验证数据隔离**:
- ✓ 确认 SQLite 数据库在 `H:\studybuddy-test\data_root\studybuddy.sqlite3`
- ✓ 确认原文件在 `H:\studybuddy-test\data_root\originals\`
- ✗ 不污染 `H:\studybuddy-data` 正式数据

#### 7.3 代码和配置不变性

**严格禁止**:
- ✗ 修改 `backend/app/` 源码
- ✗ 修改 `backend/app/static/` 前端代码
- ✗ 修改 `H:\studybuddy-data\config\` 正式配置
- ✗ 提交 Git

**允许**:
- ✓ 在 `H:\studybuddy-test` 创建测试配置
- ✓ 读取源码进行分析
- ✓ 查看 Git 状态（只读）

---

### 8. 成功标准

#### 完成标准

验证任务完成的标准（ALL 必须满足）:

- [x] 两份用户手册中的所有场景都已执行
- [x] 16+ 个主要页面的所有按钮都已点击
- [x] 16+ 个主要页面的所有链接都已验证
- [x] 所有操作都有截图记录（≥50 张）
- [x] 生成了完整的执行日志
- [x] 生成了 UI 元素清单
- [x] 生成了最终验证报告
- [x] 记录了所有发现的问题（按 P0-P3 分级）
- [x] 给出了手册修订建议

#### 质量标准

- **覆盖率**: ≥90% 的用户手册内容已验证
- **准确率**: ≥95% 的验证结果可复现
- **问题识别**: 所有 P0/P1 问题都已发现
- **文档完整性**: 报告包含所有必需章节
- **截图清晰度**: 所有截图清晰可读

---

### 9. 交付物清单

完成后应产生以下文件结构：

```
H:\studybuddy-test\verification\
├── browser_execution_log_20260927_103000.md         # 执行日志
├── ui_elements_inventory.md                          # UI 元素清单
├── browser_verification_report_20260927.md           # 最终验证报告
├── manual_inconsistencies.md                         # 手册不一致点
├── issue_summary.md                                  # 问题汇总
├── screenshots\                                      # 截图目录
│   ├── A01_001_initial.png
│   ├── A02_003_upload_success.png
│   ├── B04_002_qa_answer.png
│   └── ... (≥50 张)
├── scripts\                                          # 验证脚本（可选）
│   ├── run_verification.js
│   └── utils.js
└── data_root\                                        # 测试数据（服务运行时生成）
    ├── studybuddy.sqlite3
    ├── originals\
    └── config\
```

---

### 10. Playwright 脚本示例

#### 示例 1: 验证材料页面的所有按钮

```javascript
// H:\studybuddy-test\verification\scripts\verify_materials_page.js

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://127.0.0.1:8787';
const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');

async function verifyMaterialsPage() {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 500  // 慢速操作便于观察
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  
  const page = await context.newPage();
  
  const log = [];
  
  try {
    // 步骤 1: 打开材料页面
    log.push('## 场景 B-01: 材料管理\n');
    log.push('### 步骤 1: 打开页面');
    
    await page.goto(`${BASE_URL}/app/materials.html`);
    await page.waitForLoadState('networkidle');
    
    const title = await page.title();
    log.push(`- ✓ 页面标题: ${title}`);
    
    await page.screenshot({ 
      path: path.join(SCREENSHOT_DIR, 'B01_001_initial.png'),
      fullPage: true 
    });
    log.push(`- ✓ 截图: B01_001_initial.png\n`);
    
    // 步骤 2: 识别所有按钮
    log.push('### 步骤 2: 识别按钮');
    
    const buttons = await page.locator('button, .btn').all();
    log.push(`- 发现 ${buttons.length} 个按钮\n`);
    
    // 步骤 3: 点击每个按钮
    log.push('### 步骤 3: 点击按钮');
    
    for (let i = 0; i < buttons.length; i++) {
      const button = buttons[i];
      const btnId = await button.getAttribute('id') || `btn-${i}`;
      const btnText = await button.textContent();
      const isDisabled = await button.isDisabled();
      
      log.push(`\n#### 按钮 ${i+1}: ${btnId}`);
      log.push(`- 文本: "${btnText}"`);
      log.push(`- 状态: ${isDisabled ? 'disabled' : 'enabled'}`);
      
      if (!isDisabled) {
        try {
          // 点击前截图
          await button.scrollIntoViewIfNeeded();
          
          // 点击
          await button.click();
          await page.waitForTimeout(1000);
          
          // 点击后截图
          await page.screenshot({ 
            path: path.join(SCREENSHOT_DIR, `B01_btn_${btnId}.png`),
            fullPage: true 
          });
          
          log.push(`- ✓ 点击成功`);
          log.push(`- ✓ 截图: B01_btn_${btnId}.png`);
        } catch (error) {
          log.push(`- ✗ 点击失败: ${error.message}`);
        }
      } else {
        log.push(`- ⊘ 跳过（按钮禁用）`);
      }
    }
    
    // 步骤 4: 识别所有链接
    log.push('\n### 步骤 4: 识别链接');
    
    const links = await page.locator('a[href^="/app/"]').all();
    log.push(`- 发现 ${links.length} 个内部链接\n`);
    
    // 步骤 5: 点击每个链接
    log.push('### 步骤 5: 点击链接');
    
    for (let i = 0; i < links.length; i++) {
      const link = links[i];
      const href = await link.getAttribute('href');
      const text = await link.textContent();
      
      log.push(`\n#### 链接 ${i+1}: ${href}`);
      log.push(`- 文本: "${text}"`);
      
      try {
        await link.click();
        await page.waitForURL(`**${href}`);
        
        await page.screenshot({ 
          path: path.join(SCREENSHOT_DIR, `B01_link_${i}.png`),
          fullPage: true 
        });
        
        log.push(`- ✓ 跳转成功`);
        log.push(`- ✓ 截图: B01_link_${i}.png`);
        
        // 返回
        await page.goBack();
        await page.waitForLoadState('networkidle');
        
      } catch (error) {
        log.push(`- ✗ 跳转失败: ${error.message}`);
      }
    }
    
    log.push('\n### 验证结果');
    log.push('**状态**: PASS');
    
  } catch (error) {
    log.push(`\n### 验证结果`);
    log.push(`**状态**: FAIL`);
    log.push(`**错误**: ${error.message}`);
  } finally {
    await browser.close();
    
    // 保存日志
    const logPath = path.join(__dirname, '..', 'materials_page_log.md');
    fs.writeFileSync(logPath, log.join('\n'), 'utf-8');
    console.log(`日志已保存到: ${logPath}`);
  }
}

verifyMaterialsPage();
```

#### 示例 2: 验证完整的问答流程

```javascript
// verify_qa_flow.js

async function verifyQAFlow() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  const log = [];
  
  // 1. 先上传一个材料
  await page.goto(`${BASE_URL}/app/materials.html`);
  const fileInput = await page.locator('input[type="file"]');
  await fileInput.setInputFiles('H:\\studybuddy-test\\fixtures\\test.pdf');
  await page.waitForResponse(resp => resp.url().includes('/api/materials'));
  log.push('✓ 材料上传成功');
  
  // 2. 建立索引
  const material = await page.locator('.material-item').first();
  await material.click();
  await page.waitForURL('**/material-detail.html**');
  
  const indexBtn = await page.locator('#build-index');
  await indexBtn.click();
  await page.waitForResponse(resp => resp.url().includes('/ai-index/tasks'));
  log.push('✓ 索引任务已创建');
  
  // 等待索引完成（最多 60 秒）
  await page.waitForSelector('.index-status:has-text("已完成")', { timeout: 60000 });
  log.push('✓ 索引已完成');
  
  // 3. 提问
  await page.goto(`${BASE_URL}/app/qa.html`);
  const questionInput = await page.locator('textarea[name="question"]');
  await questionInput.fill('这个材料的主要内容是什么？');
  
  const askBtn = await page.locator('button:has-text("提问")');
  await askBtn.click();
  
  await page.waitForResponse(resp => resp.url().includes('/api/qa/ask'));
  await page.waitForSelector('.answer-content', { timeout: 30000 });
  log.push('✓ 获得回答');
  
  // 4. 验证引用
  const citations = await page.locator('.citation-link').all();
  if (citations.length > 0) {
    await citations[0].click();
    await page.waitForURL('**/material-detail.html**');
    log.push('✓ 引用定位成功');
  }
  
  await browser.close();
  return log;
}
```

---

## 附录：任务执行检查清单

### 执行前检查
- [ ] 服务已启动（端口 8787）
- [ ] 健康检查通过（/api/health）
- [ ] 测试数据目录已创建（H:\studybuddy-test\data_root）
- [ ] 截图目录已创建（H:\studybuddy-test\verification\screenshots）
- [ ] 测试材料已准备（H:\studybuddy-test\fixtures）
- [ ] Playwright 已安装

### 执行中检查
- [ ] 每个场景都有执行日志
- [ ] 每个关键步骤都有截图
- [ ] 所有按钮都已点击
- [ ] 所有链接都已验证
- [ ] 异步操作都有等待
- [ ] 错误都有记录

### 执行后检查
- [ ] 生成了执行日志
- [ ] 生成了 UI 元素清单
- [ ] 生成了最终验证报告
- [ ] 截图数量 ≥ 50 张
- [ ] 问题按 P0-P3 分级
- [ ] 给出了手册修订建议
- [ ] 所有文件都在 H:\studybuddy-test
- [ ] 源码目录保持干净

---

**模板版本**: v1.0  
**最后更新**: 2026-09-27  
**维护者**: 测试团队 + AI Agent  
**适用范围**: StudyBuddy 用户手册验证

---
