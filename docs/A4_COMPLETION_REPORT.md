# A4 前端页面完成报告

## 完成日期
2026-08-30

## 实施范围

按照 `ROADMAP_CAPABILITIES.md` 和 `frontend-plan.md` 的 A4 要求，完成以下三个页面：

### 1. settings-provider.html — Provider 能力状态页面

**路径**: `backend/app/static/settings-provider.html`

**功能**:
- 查询并显示 `/api/ai/capabilities` 返回的 Provider 状态
- 展示 LLM Provider 和 Embedding Provider 的配置状态
- 显示每个 Provider 的支持能力（对话、补全、流式、工具调用、JSON 模式等）
- 查询并显示系统健康状态 `/api/readiness`
- 明确标注"配置写入契约尚未完成批准"，不提供密钥输入或配置修改功能

**设计特点**:
- 骨架屏加载状态
- 能力卡片网格布局，清晰展示可用/不可用状态
- 使用语义化的状态指示器（绿色/红色圆点）
- 响应式设计，支持窄屏设备

### 2. capture.html — 课堂采集页面

**路径**: `backend/app/static/capture.html`

**功能**:
- 创建新采集会话（音频/视频）
- 列表显示所有采集会话，支持筛选（包含已归档）
- 查看会话详情，包括状态、创建时间、转写草稿等
- 上传音频/视频文件到会话
- 触发转写（fake/loopback 流程）
- 编辑转写草稿
- 确认或拒绝转写草稿
- 明确标注"真实 ASR 尚未通过 B1 门禁验证"

**设计特点**:
- 会话卡片展示，带状态徽章
- 模态对话框用于创建会话和查看详情
- 拖放上传区域（带视觉反馈）
- 草稿编辑器支持实时编辑和多种操作（保存/确认/拒绝）
- 清晰的能力边界提示

### 3. tasks.html — 任务状态页面

**路径**: `backend/app/static/tasks.html`

**功能**:
- 通过 URL 参数 `?task_id=<id>` 查看单个任务详情
- 显示任务的完整元数据（类型、状态、创建/开始/完成时间、错误码、重试次数等）
- 显示任务进度条（0-100%）
- 支持取消运行中的任务
- 支持重试失败或已取消的任务
- 自动刷新任务状态（3 秒轮询）
- 明确标注"仅支持 embedding_index 任务类型"

**设计特点**:
- 任务卡片展示，使用等宽字体显示任务 ID
- 彩色状态徽章（等待中/运行中/已完成/失败/已取消）
- 进度条可视化
- 清晰的操作按钮（取消/重试）
- 友好的使用说明

## 导航更新

更新 `backend/app/static/js/shell.js`，在主导航中增加：
- **采集** → `/app/capture.html`
- **设置** → `/app/settings-provider.html`

任务页面不在主导航显示，通过其他页面的任务 ID 链接访问。

## 设计系统遵循

所有页面严格遵循 **Neutral Modern** 设计系统：

### 色彩
- 背景: `#FAFAFA`
- 表面: `#FFFFFF`
- 前景: `#111111`
- 弱化文本: `#6B6B6B`
- 边框: `#E5E5E5`
- 强调色: `#2F6FEB` (钴蓝)
- 语义色: 成功 `#17A34A`, 警告 `#EAB308`, 危险 `#DC2626`

### 字体
- Display/Body: Inter
- Monospace: JetBrains Mono（用于 ID、状态、数据）

### 组件
- 12px 圆角卡片
- 1px 实线边框
- 无阴影（除非交互需要）
- 一致的间距系统（8px、12px、16px、20px、24px）

### 动效
- 150ms 快速过渡（hover、focus）
- 200ms 标准过渡（状态变化）

### 响应式
- 640px 移动端断点
- 触控目标最小 44px

## 能力边界诚实标注

所有页面明确标注能力限制：

1. **settings-provider.html**: "配置写入契约尚未完成批准"
2. **capture.html**: "真实 ASR 尚未通过 B1 门禁验证"
3. **tasks.html**: "仅支持 embedding_index 任务类型"

不伪造成功状态，不隐藏未验证能力。

## 测试验证

### 文件大小检查
```bash
python backend/scripts/check-source-size.py
```
✅ 通过：所有文件均小于 32 KiB 限制

### 后端测试
```bash
C:\miniconda\py310\python.exe -m pytest backend/tests/
```
✅ 通过：413 passed, 2 skipped

### 浏览器验证
- ✅ `http://127.0.0.1:8787/app/settings-provider.html` — 200 OK
- ✅ `http://127.0.0.1:8787/app/capture.html` — 200 OK
- ✅ `http://127.0.0.1:8787/app/tasks.html` — 200 OK

### API 集成验证
- ✅ `/api/ai/capabilities` — 正确显示 Provider 状态
- ✅ `/api/readiness` — 正确显示系统健康状态
- ✅ `/api/study/capture-sessions` — 正确列出采集会话
- ✅ `/api/tasks/{task_id}` — 正确显示任务详情

## 未实现功能（按设计）

以下功能明确标注为"尚未实现"，符合 ROADMAP 要求：

1. **Provider 配置写入** — 等待安全契约批准
2. **真实 ASR 转写** — 等待 B1 门禁通过
3. **任务列表 API** — 当前仅支持单任务查询
4. **OCR 功能** — 等待 B2 门禁通过
5. **报告外发** — 等待 B4 门禁通过

## 后续工作

A4 完成后，下一步工作为：

- **B0**: 统一组件库 catalog
- **B1**: 真实 ASR 候选验证
- **B2**: 真实 OCR 候选验证
- **B3**: 本地脱敏报告
- **B4**: 真实外发验证

## 文档更新

- ✅ `docs/TODO.md` — 标记 A4 为已完成
- ✅ `docs/A4_COMPLETION_REPORT.md` — 创建完成报告（本文件）

## 交付物清单

1. `backend/app/static/settings-provider.html` (6,506 bytes)
2. `backend/app/static/capture.html` (13,915 bytes)
3. `backend/app/static/tasks.html` (8,865 bytes)
4. `backend/app/static/js/shell.js` (更新导航)
5. `docs/TODO.md` (更新 A4 状态)
6. `docs/A4_COMPLETION_REPORT.md` (本报告)

---

**结论**: A4 前端页面已按 ROADMAP 要求完成实施，所有页面均通过验证，诚实标注能力边界，遵循 Neutral Modern 设计系统，不伪造未验证功能。
