# Frontend Scenario 前后端整体设计合同

> 状态：`P2-FE-2 / scenario-1 + scenario-2 frozen / scenario-3 skeleton`
> 更新：2026-09-05
>
> 技术路线：HTML + CSS + 原生 JavaScript + FastAPI JSON API。
> 正式页面：`backend/app/static/` 下 20 个可操作页面和 1 个兼容跳转页。
> 本切片不新增 endpoint、schema、migration 或后端错误码；同时交付计划进度历史与 Today 可操作空态，避免成为纯文档切片。

## 1. 依据、目的与边界

本合同以当前代码和可重复扫描结果为事实源：

- [`../frontend-inventory-report.md`](../frontend-inventory-report.md)：21 页面、6 个共享资源、测试触达和路由分类的人工结论；
- [`../frontend-inventory-scan.md`](../frontend-inventory-scan.md)：扫描器生成的逐页、逐端点明细；
- `backend/scripts/scan-frontend-inventory.py`：只读扫描实现；
- `backend/app/static/js/api.js`：请求、取消、幂等 key 和安全错误显示的共享合同；
- `backend/app/static/js/state.js`：领域状态与来源状态的共享标签；
- 现有 FastAPI route、schema、repository 和正式 browser spec。

目标不是逐页罗列控件，而是以用户场景冻结跨页行为。页面实现必须同时满足入口、状态、下一步操作、API 语义、失败恢复、隐私和 browser evidence。

静态扫描标签只说明引用证据强弱：

- `direct`：页面或共享模块包含可归一化的字面 API 调用；
- `dynamic`：末段由变量拼接，扫描器无法断定具体动作；
- `unreached`：未找到正式前端引用。

`dynamic` 不等于已覆盖，`unreached` 也不自动等于产品缺口。最终判断以本合同的逐项定性为准。

## 2. 场景合同标准格式

每个场景必须包含以下四件套。

### 2.1 场景流程图

必须写明：起点、前置条件、跨页入口、成功路径、可恢复失败、空态出口和结束状态。流程图中的页面与 API 必须存在于当前代码；未来项明确标为 `planned`。

### 2.2 页面状态机

每个参与页面至少区分：

```text
initial → loading → ready
                  ├→ empty（有明确下一步）
                  ├→ domain-blocked（状态或来源不允许操作）
                  └→ failed → retry → loading
```

写操作另含 `submitting → succeeded/failed`。切换资源、刷新或离开页面后，过期响应不得覆盖新上下文。

### 2.3 元素行为表

每行记录真实 selector、出现条件、触发动作、busy/disabled 规则、成功反馈、失败反馈和下一目的地。动态生成按钮也必须写明稳定文本或容器 selector。

### 2.4 API 契约对照表

每行记录 method、endpoint、请求/响应关键字段、前端消费者、失败语义和扫描分类。页面不得从 `/legacy` 文案猜测字段，也不得把原始异常、路径、SQL、Provider secret 或 source text 放入错误提示。

每个场景还必须给出 browser evidence 矩阵。`implemented` 仅表示代码存在；只有测试实际覆盖的维度才可写 `scoped-browser-pass`，真实外部组件或生产规模仍为 `not_verified`。

## 3. 场景 1：计划 → 今天 → 进度

状态：`implemented / scoped-browser-pass`。

参与页面：

- `plans.html`：建立目标、模块、计划和计划项；确认/激活计划；设置时区和节奏；分配某日学习项；
- `today.html`：读取唯一 active plan，以该计划时区计算 `local_date`，只显示当天 allocation；
- `plan-detail.html`：显示计划项、记录 `started`/`completed`，并读取整份计划的进度摘要和事件历史；
- `material-detail.html`：仅在有效来源存在时作为“查看资料”目的地。

### 3.1 场景流程图

```text
plans.html
  创建目标 → 创建计划草稿 → 添加计划项
      → 确认草稿 → 激活计划
      → 保存节奏（含 IANA timezone）
      → 为 local_date 添加 allocation
      → today.html
          ├─ 有 active plan + 当天 allocation
          │    → 查看资料（仅 valid source）
          │    → 开始学习
          │         → plan-detail.html?plan_id&item_id&local_date&return_to=today
          │         → POST started → POST completed
          │         → GET progress → 历史和摘要更新
          │         → 返回 Today → 任务显示“查看进度”
          ├─ 完全无计划 → 创建学习计划 → plans.html
          ├─ 有计划但无 active plan → 前往激活 → plans.html?plan_id=...
          ├─ active plan 当日无 allocation
          │    → 查看计划详情 / 安排今日学习
          └─ 任一读取失败 → 安全文案 → 重新加载 → 当前状态重算
```

计划时区是 Today 的业务日期来源；不得使用浏览器本地日期或 UTC 日期代替。过期 allocation 可继续保留在计划中，但不会出现在当天任务列表。

### 3.2 页面状态机

#### `plans.html`

```text
loading(goals/modules/plans) → ready
  ├─ 无目标 → 新建目标
  ├─ 无模块 → 新建模块（模块不是创建计划的强制前置）
  ├─ 无计划 → 新建计划草稿
  └─ 选中计划 → detail
       plan: draft → confirmed → active ↔ paused → completed
               └──────────────────────────────→ archived
       draft/confirmed 可编辑；active/paused/completed 不可编辑正文
       rhythm unconfigured → 保存节奏 → 添加/调整/删除 allocation
failed → `#plan-status` 安全文案 → `#refresh-all` → loading
```

编辑 confirmed 计划会按后端语义回到 draft。只有 active plan 可接受进度事件。依赖当前可添加但不可在正式 UI 删除；这是已确认缺口。

#### `today.html`

```text
initial → 三个区块并行 loading，共享一次 GET /api/study/plans
  ├─ plans=[]
  │    summary/task: “还没有学习计划”
  │    weekly: “还没有学习计划，暂无周趋势”
  │    exit: 创建学习计划
  ├─ plans 非空、active=null
  │    summary/task: “计划尚未启动”
  │    weekly: “计划尚未启动，暂无周趋势”
  │    exit: 前往激活
  ├─ active 存在、今日 allocation=[]
  │    summary/weekly 正常；task 显示计划名和“今日没有安排学习项”
  │    exits: 查看计划详情 / 安排今日学习
  ├─ active 存在、今日 allocation 非空
  │    ready：仅渲染匹配 item_id 且非 archived 的学习项
  └─ 任一区块 failed
       安全文案 + `#retry-today` → 全部区块重新计算
```

`loadGeneration` 丢弃过期响应；重试通过 `sbSubmit.once('today-reload', ...)` 合并重复点击。

#### `plan-detail.html`

```text
无 plan_id → plan/history 各自进入 settled failed，禁止无目标请求
有 plan_id → plan detail 与 progress history 并行 loading
  ├─ 两者成功 → detail ready + summary ready + events ready/empty
  ├─ detail 成功、history 失败 → detail 保留 + history 安全失败 + retry
  ├─ detail 失败、history 成功 → history 可读 + detail 安全失败 + retry
  └─ retry / refresh-progress → 新 generation → 并行重读

选中的 active item：
  pending → POST started → in_progress → POST completed → completed
```

事件按 API 返回顺序倒序显示；事件类型由页面局部映射为“开始学习 / 记录完成 / 跳过 / 重新开始”。刷新和写入成功后均重新读取详情与历史。

### 3.3 元素行为表

| 页面 / selector | 条件与行为 | 成功结果 | 失败与恢复 |
|---|---|---|---|
| `plans.html #goal-form` / `#goal-title` | 新建目标 | 目标进入 `#goals` | `#goal-status` 安全文案 |
| `plans.html #plan-form` / `#plan-title` / `#plan-goal` | 基于现有目标创建 draft plan | 计划进入 `#plans` 并可选中 | `#plan-status` 安全文案 |
| `plans.html #plan-detail` | 选中计划后显示编辑、状态迁移、计划项、依赖、来源、节奏 | 所有 mutation 完成后重读当前计划 | mutation busy 时阻止重复提交；失败可重试 |
| 动态“确认草稿 / 激活计划 / 暂停计划 / 恢复计划 / 完成计划” | 仅按当前 plan 状态出现 | 使用正式 transition endpoint | 冲突显示计划操作失败，不伪造状态 |
| 动态 `#rhythm-timezone` / `#rhythm-period-start` / `#rhythm-target-minutes` | 保存节奏设置 | 后续 Today 按该 timezone 算日期 | 映射 invalid timezone/date/target 错误 |
| 动态 `#rhythm-item` / `#rhythm-date` / `#rhythm-minutes` | 添加某日分配 | allocation 可调整或删除 | duplicate/limit/edit-not-allowed 明确提示 |
| `plans.html #refresh-all` | 手动重读 goals/modules/plans | 保持或恢复选中 plan | 可从读取失败恢复 |
| `today.html #summary-status` / `#summary` | 显示 active plan 摘要或无计划/未激活空态 | 四个摘要卡稳定渲染 | `#retry-today` 重读 |
| `today.html #weekly-status` / `#weekly-trend` | 显示计划时区下最近七天完成数 | 七个日期桶 | `#retry-today` 重读 |
| `today.html #task-status` / `#tasks` | 只渲染 active plan 当天 allocation | 每项显示来源、分钟、日期和入口 | 空态不渲染伪任务 |
| `today.html #today-exits` | 根据三类空态动态生成下一步 | 创建计划 / 前往激活 / 查看详情 / 安排今日学习 | reload 前清空，避免旧出口残留 |
| `today.html #retry-today` | 任一区块失败才显示 | 三个区块共用一次重新加载 | busy 时禁用；旧响应被 generation 丢弃 |
| 动态“查看资料” | 仅 valid source 且有 material_id 时可操作 | 进入对应材料详情 | 不可用来源设置 `aria-disabled`，不伪造链接 |
| 动态“开始学习 / 查看进度” | 有计划项和当天 allocation | 带 `plan_id/item_id/local_date/return_to` 进入详情 | URL 不携带 source text 或 secret |
| `plan-detail.html #back-plan` | `return_to=today` 时返回 Today，否则返回 Plans | 恢复跨页上下文 | 未知 return_to 收敛到 Plans |
| `plan-detail.html #progress-status` | 写进度专用状态，不与历史读取状态混用 | 显示保存中/已开始/已完成 | 安全文案，按钮恢复可操作 |
| 动态“开始学习 / 记录完成” | 仅选中 active、非 completed/archived item 时出现 | POST event 后详情和历史自动刷新 | `progressBusy` 阻止重复点击 |
| `plan-detail.html #history-status` | loading、empty、failed 独立 settled | 有事件时隐藏 | 失败不遮蔽已成功的 plan detail |
| `plan-detail.html #progress-summary` | progress 读取成功 | 已完成、进行中、待处理、已跳过、完成率 | 失败时隐藏旧摘要 |
| `plan-detail.html #progress-events` | progress 读取成功 | 最近事件在前，显示学习项、事件、时间和计划日期 | 空列表由 `#history-status` 明示 |
| `plan-detail.html #refresh-progress` | 用户主动重读 plan + progress | 更新摘要和历史 | 通过 `sbSubmit.once` 合并重复点击 |
| `plan-detail.html #retry-plan` | plan 或 progress 任一失败时显示 | 两个读取一起重试 | 恢复成功后隐藏 |

### 3.4 API 契约对照表

| 行为 | Method / endpoint | 请求与响应关键字段 | 前端规则 / 失败语义 | 分类 |
|---|---|---|---|---|
| 列出计划 | `GET /api/study/plans` | plan 含 `id/title/status/items/source_links/progress` | Today 只选 `status=active`；空列表与未激活分开 | direct |
| 读取计划 | `GET /api/study/plans/{plan_id}` | 同上，另含 `dependencies` | 404 `study_plan_not_found` 只显示安全文案 | direct |
| 创建/编辑计划 | `POST /api/study/plans`; `PATCH /api/study/plans/{plan_id}` | 创建需 `goal_id/title`；编辑 title/description | active 之后编辑返回冲突；不本地猜状态 | direct |
| 计划迁移 | `POST .../confirm|activate|pause|complete|archive` | 返回迁移后的 plan | 按当前状态显示按钮；变量末段仍为 dynamic | dynamic/direct 混合 |
| 创建/编辑/归档计划项 | `POST .../items`; `PATCH .../items/{item_id}`; `POST .../items/{item_id}/archive` | item status 属计划详情 | archived 不进入 Today | direct |
| 读取/保存节奏 | `GET/PUT /api/study/plans/{plan_id}/rhythm` | `settings.timezone/cadence/period_start/target_minutes` | Today 用 timezone 计算 `local_date` | direct |
| allocation 管理 | `GET/POST .../rhythm/allocations`; `PATCH/DELETE .../allocations/{allocation_id}` | `item_id/local_date/planned_minutes` | Today 仅匹配当日；duplicate/limit/date 错误明确显示 | direct |
| 今日摘要 | `GET .../rhythm/summary` | `item_projection/source_warning_count` | 无 settings 仍返回合法空 buckets，不伪造失败 | direct |
| 七天趋势 | `GET .../rhythm/weekly-trend` | `days[].local_date/completed_count` | 默认结束日按计划 timezone | direct |
| 写进度 | `POST /api/study/plans/{plan_id}/items/{item_id}/progress` | `{event_type,metadata,event_id?}`；返回 `{event,summary}` | 支持 started/completed/skipped/reopened；只允许 active plan、非 archived item；event_id 幂等 | direct |
| 读进度 | `GET /api/study/plans/{plan_id}/progress` | `{plan_id,events,summary}`；可选 `item_id` | 详情页读取全计划；summary 使用后端计数，events 倒序展示 | direct |

进度摘要字段冻结为：`item_count`、`completed_count`、`skipped_count`、`in_progress_count`、`pending_count`、`archived_count`、`completion_ratio`、`last_event_at`、`source_warning_count`。页面不得自行重算 completed/item_count 取代后端值。

### 3.5 Browser evidence

`backend/tests/browser_plans_today_progress.spec.js` 当前 6 个测试覆盖：

- 创建目标、计划、计划项、激活、设置时区与当日 allocation；
- Today 只显示 active plan 当日 allocation，排除未分配、其他计划和非 active 项；
- started → completed 事件、local_date 保留、返回 Today 后状态一致；
- 进度摘要、空历史、事件倒序、刷新后 100% 完成率；
- progress 单独 5xx 时计划详情仍可读，DOM 不泄露路径/traceback，retry 后恢复；
- 完全无计划、已有计划未激活、active 但今日无 allocation 三类空态及各自出口；
- Today 读取失败后统一重试，且三个区块恢复。

共享 baseline / visual matrix 另覆盖 10 个 viewport、无横向溢出、状态在 5 秒内离开 loading、可见焦点和触控尺寸。真实容量、多进程、真实断电和跨时区夏令时边界为 `not_verified`。

## 4. `unreached` 路由逐项定性

当前扫描结果：165 条 route 声明、137 个唯一 path key；`direct=99`、`dynamic=11`、`unreached=27`。

27 与 31 不矛盾：`classify_routes()` 按 path key 分类，同一路径的 GET/PATCH 或 GET/POST 会合并为一个 key；展开 HTTP method 后共 31 行。下表每行对应一个唯一 path key，并在“方法”列保留所有方法。

定性值：

- `intentional`：运维、内部管道、安全边界或正式 UI 已采用更高层等价操作；
- `deferred`：有用户价值，但不属于场景 1，进入对应后续场景；
- `gap`：正式页面已有相邻工作区，却缺少应有操作；
- `decision-needed`：是否暴露需要单独产品/安全决策。

| # | 方法与 path key | 定性 | 结论与归属 |
|---:|---|---|---|
| 1 | POST `/api/materials/{material_id}/ai-index/tasks` | intentional | 正式页当前使用同步 `/ai-index`；异步任务观测延后 Phase 10，不在浏览器伪造队列。 |
| 2 | POST `/api/citation/validate` | intentional | Q&A 内部管道；用户操作走高层问答 API。 |
| 3 | POST `/api/context/assemble` | intentional | Q&A 内部管道；不直接暴露组装 payload。 |
| 4 | POST `/api/retrieval` | intentional | Q&A 内部管道；正式页由问答流程调用检索。 |
| 5 | POST `/api/materials/{material_id}/purge` | decision-needed | 永久删除是破坏性操作；需单独确认、备份与不可恢复文案，不能顺手接入普通回收站。 |
| 6 | POST `/api/study/capture-sessions/{capture_id}/archive` | deferred | capture/classroom 生命周期工作区后续项。 |
| 7 | POST `/api/study/reports/{report_id}/delivery` | intentional | 外发默认关闭且逐次授权；不能作为普通报告按钮默认开放。 |
| 8 | GET `/api/study/reports/{report_id}/delivery-attempts` | deferred | 仅在显式 delivery 工作区中展示；当前外发关闭。 |
| 9 | GET `/api/study/reports/{report_id}/preview` | gap | reports 已有详情/导出相邻能力，正式预览入口仍缺失。 |
| 10 | GET `/api/study/decks/{deck_id}` | deferred | 卡片组详情场景，不阻塞当前 cards 列表与学习流程。 |
| 11 | GET `/api/study/exercise-sets/{set_id}` | deferred | 练习集详情场景，归入场景 3。 |
| 12 | GET+POST `/api/study/exercises/{exercise_id}/attempts` | gap | 练习页已有题目，正式逐题 attempt 读写面缺失，归入场景 3。 |
| 13 | DELETE+PATCH `/api/study/notes/{note_id}/blocks/{block_id}` | intentional | notes 正式页以 `PUT .../blocks` 整体提交有序 blocks；避免两套并行编辑语义。 |
| 14 | POST `/api/study/notes/{note_id}/blocks/{block_id}/sources` | intentional | 同上，block 来源随整体 blocks 合同提交。 |
| 15 | DELETE `/api/study/notes/{note_id}/blocks/{block_id}/sources/{link_id}` | intentional | 同上，不单独暴露细粒度删除。 |
| 16 | GET+PATCH `/api/study/goals/{goal_id}` | gap | Plans 可创建目标但不能查看/重命名现有目标。 |
| 17 | POST `/api/study/goals/{goal_id}/archive` | gap | Plans 缺目标归档入口和依赖影响提示。 |
| 18 | GET+PATCH `/api/study/modules/{module_id}` | gap | Plans 可创建模块但不能查看/重命名现有模块。 |
| 19 | POST `/api/study/modules/{module_id}/archive` | gap | Plans 缺模块归档入口和来源影响提示。 |
| 20 | DELETE `/api/study/plans/{plan_id}/dependencies/{dependency_id}` | gap | Plans 可添加依赖但不展示可删除的现有依赖。 |
| 21 | GET `/api/study/cram-goals/{goal_id}` | deferred | 冲刺目标详情工作区后续项；当前状态 mutation 由 `cram.js` 动态调用。 |
| 22 | GET `/api/study/weak-points` | gap | 场景 3 的错题复盘需要可见薄弱点汇总。 |
| 23 | POST `/api/study/practice-sessions/{session_id}/archive` | deferred | 会话归档应与场景 3 的完成/结果/复盘状态机一起实施。 |
| 24 | GET `/api/study/plans/{plan_id}/rhythm/export` | deferred | 有用户价值但不阻塞日常链路；后续提供 JSON 导出，保留 256 KiB/413 边界与 `phase9b-rhythm-v1`。 |
| 25 | GET `/api/health` | intentional | 运维探活；页面使用 readiness/system status，不直接暴露底层 health。 |
| 26 | GET `/api/liveness` | intentional | 进程编排探活，不是用户工作流。 |
| 27 | GET `/api/metrics` | intentional | 运维观测端点，不进入普通浏览器 UI。 |

更正记录：`GET /api/study/plans/{plan_id}/progress` 在 P2-FE-1 扫描中标为 `dynamic`，并不代表已有页面读取它。原因是 `plans.html` 的 `.../{plan_id}/` + 动态 action 被折叠成 `/api/study/plans/{id}/{id}`，placeholder 匹配误将同段数路由视为候选。场景 1 实现后，`plan-detail.html` 出现明确调用，该路由变为 `direct`：`direct 98→99`、`dynamic 12→11`、`unreached` 保持 27。真实修复是补上“进度只写不读”的用户缺口，而不是激活一条原 `unreached` 路由。

## 5. 场景 2：材料导入 → 解析 → 索引 → 问答（带引用）

状态：`implemented / scoped-browser-pass`（导入、解析、同步索引、问答与引用定位；材料管理正式 `/app` 的导入、回收站、删除/恢复和批量 ZIP 导出，以及正式 `/app/qa.html` 的材料选择、索引前置、提问、引用跳转、失败重试、重复提交保护和窄屏状态已有范围化 browser evidence）；`legacy_only`（QA 线程工作区多会话切换、rate-limit/unavailable 映射等等价证据和部分历史材料管理证据仍保留在 `/legacy`）；`not_exposed`（异步入队、purge）。

参与页面（真实代码已核实）：

- `materials.html`：导入（单文件/批量/文件夹）、列表、筛选、搜索、分页、回收站、批量导出；
- `material-detail.html`：解析状态、正文、索引状态与建立、引用定位、原件/文本导出；
- `qa.html`：Provider 状态、材料范围、检索模式、提问、线程历史、引用回跳；
- `tasks.html`：`embedding_index` 任务只读观测（列表/详情/取消/重试）。

### 5.1 场景流程图

```text
materials.html 进入材料库
  导入材料（#upload-area 点击/拖放 / #folder-btn 文件夹）
    ├─ 输入校验：accept 限制 .pdf,.txt,.md,.docx,.pptx；
    │   无效文件名/超限/不支持格式 → 后端稳定错误码 → 安全文案
    ├─ 上传中：`#upload-status`“正在上传 N 个文件...”
    ├─ 解析中：后端同步完成，无独立前端态
    ├─ 解析成功（status=success/empty）："已导入 n/total" → 列表重读
    ├─ 解析失败（status=rejected/failed）：逐文件错误码列表 + 安全文案
    └─ 上传异常：安全文案 + “可重试”
  列表/筛选/搜索/分页/回收站 → 每项 → material-detail.html?material=ID
  查看材料详情（GET /api/materials/{id}）
    ├─ 解析状态：success/empty/rejected/failed + 解析器/文件类型/文本长度/片段数/提示
    ├─ 空文本：下一步指导（OCR 生成可搜索 PDF，或上传 UTF-8 文本）
    ├─ 失败/拒绝：错误码安全文案 + 转换/修复后重新导入
    └─ 建立 AI 索引（#index → POST /ai-index，幂等 key）
         ├─ 成功 → 重读真实索引状态（ready / empty）
         ├─ 失败 → 安全文案 + 可重试
         └─ 任务观测：tasks.html?task_id=... 观察 embedding_index 任务
  进入问答（#qa → qa.html?material=ID，或“选择材料”）
    ├─ Provider 状态（configured / demo / not_configured / 检查失败）
    ├─ 材料范围（#materials，支持 URL material 预填）
    ├─ 检索模式（hybrid / lexical / vector）
    ├─ 提问（#submit-btn → POST /api/qa/ask，幂等 key）
    │    ├─ 成功 → 回答生成 → 线程列表重读
    │    ├─ 无命中/索引未就绪 → 稳定错误码安全文案
    │    └─ 失败 → 安全文案 + 可重试
    └─ 问答历史（#threads → GET /api/qa/threads → 线程详情 → .citation-link）
         └─ 引用定位回原文（material-detail.html?material&citation=KEY）
               ├─ valid → 高亮 #citation-location + scrollIntoView
               ├─ source_deleted → 安全提示“引用来源已删除”
               ├─ source_unavailable → 安全提示
               └─ 定位失败 → 安全提示 + 可返回问答历史重试
```

同步索引是正式 UI 当前采用的路径；异步 `POST .../ai-index/tasks` 是 approved 的 embedding 入队能力，仅由 `tasks.html` 只读观测，不在材料详情页伪造异步队列。引用必须保留 revision/chunk/span 定位并可回到材料；正式页面不得直接暴露 `/api/retrieval`、`/api/context/assemble`、`/api/citation/validate` 的内部 payload。

### 5.2 页面状态机

#### `materials.html`

```text
initial → loading(GET /api/materials) → ready
  ├─ items=[] → empty“还没有材料”（#state=暂无材料）
  ├─ items>0 → 列表 + 分页（#pagination）
  └─ failed → #error 安全文案；apply-filters/view-deleted/分页重新触发 load
upload: submitting → succeeded(已导入 n/total) / failed(可重试)
export: selecting → exporting(busy) → succeeded(download) / failed(可重试)
view: active ↔ deleted（回收站，GET /api/materials/deleted）
```

`loadGeneration` 丢弃过期响应；上传/导出用 `sbSubmit.once` + busy 标志防重复提交；删除/恢复用原生确认对话框。

#### `material-detail.html`

```text
无 material 参数 → title/state 安全失败（settled），#qa/#index/导出全部禁用
有 material 参数 → loading(GET /api/materials/{id}) → ready
  ├─ 解析态：success → 正文可用 + 可建立索引
  │           empty → 正文空 + 下一步指导
  │           rejected/failed → 错误码 + 转换指导
  └─ failed → “材料不可用”安全文案 + 动作禁用
索引：初始 not_indexed/empty/ready（GET /ai-index 并行）
  indexing → POST /ai-index（幂等 key + indexing 锁）→ 成功后重读真实状态
  failed → 安全文案 + 可重试（#index 恢复可点）
引用：有 citation 参数 → locating → valid（高亮）/ source_deleted / source_unavailable / 定位失败
导出：original/text → 链接跳转下载
```

`request` 为页面 scope，`pagehide` 时取消，避免过期响应覆盖新上下文。

#### `qa.html`

```text
initial → provider 检查（GET /api/ai/capabilities）
  ├─ configured/demo → 可提问
  ├─ not_configured → “问答功能不可用”
  └─ failed → “可刷新重试”
ask: submitting → succeeded(回答已生成) / 记录但回答空 / failed(可重试)
  ├─ 无 material_ids → 阻止提交“请先选择至少一个材料”
  └─ 空问题 → 阻止提交
threads: loading → ready / empty“暂无问答历史” / failed
thread detail: loading → messages + citations / failed（动态 .thread-detail 安全文案）
citation：可用 → material-detail 深链；source_deleted/source_unavailable → aria-disabled
```

`threadGeneration` 丢弃过期线程列表；`sbSubmit.once('qa-ask')` 合并重复提问。

#### `tasks.html`（只读观测参与者）

```text
无 task_id → list loading / ready / empty / failed（#tasks）
有 task_id → detail loading → 每 3s 轮询 GET /api/tasks/{id} → ready/failed
cancel/retry → confirm → POST → 重读详情
```

### 5.3 元素行为表

| 页面 / selector | 条件与行为 | 成功结果 | 失败与恢复 |
|---|---|---|---|
| `materials.html #upload-area` | 点击/拖放/键盘打开 `#file-input` | 触发上传 | 拖入无效仍被拦截，不离开页面 |
| `materials.html #file-input` | 多选，accept `.pdf,.txt,.md,.docx,.pptx` | 单文件走 `/api/materials`，多文件走 `/api/materials/batch` | 超限/格式拒绝逐项安全文案 |
| `materials.html #folder-btn` / `#folder-input` | 文件夹批量导入（webkitdirectory） | 与批量导入一致 | 同批量 |
| `materials.html #upload-status` | 上传与解析结果展示（aria-live） | 已导入 n/total（success 计 n） | 失败可重试；8s 后隐藏 |
| `materials.html #status-filter` / `#search-input` / `#apply-filters` | 按状态/关键词重读列表 | 列表与分页更新 | `#error` 安全文案 |
| `materials.html #view-deleted` | active ↔ deleted 回收站视图 | 切换列表与标题 | `#error` 安全文案 |
| `materials.html #select-page` / `.material-select` | 当前页/逐项勾选 | 计数更新、导出按钮解锁 | exportBusy 时禁用 |
| `materials.html #export-originals` / `#export-texts` / `#export-all` | 按选择导出 ZIP | 下载 `studybuddy-materials.zip` | `#export-status` 安全文案 + 可重试 |
| `materials.html #items li a` | 进入材料详情 | `/app/material-detail.html?material=ID` | 链接始终指向详情 |
| `materials.html #items li .btn 删除/恢复` | 软删除/恢复单份材料 | 列表重读 | alert 安全文案，不伪造状态 |
| `materials.html #pagination` | 上一页/下一页 | 按 offset 重读 | 无更多时禁用 |
| `material-detail.html #content` | 材料信息（解析状态/解析器/文本长度/片段数/提示） | meta-grid 渲染 | `#state` 安全失败 |
| `material-detail.html #body` / `#body-location` | 解析正文与引用定位 | 正文 + `#citation-location` 高亮 | 引用失败安全文案 |
| `material-detail.html #index` | 建立 AI 索引（POST，幂等） | 重读真实索引状态（ready/empty） | 安全文案 + 可重试 |
| `material-detail.html #index-status` | 索引状态展示（aria-live） | ready/empty/not_indexed 明示 | 暂不可用安全文案 |
| `material-detail.html #qa` | 进入问答 | `/app/qa.html?material=ID` | 材料不可用时禁用 |
| `material-detail.html #export-original` / `#export-text` | 下载原件/解析文本 | 文件下载 | 材料不可用时禁用 |
| `qa.html #provider-status` | Provider 能力检查 | configured/demo/not_configured 明示 | 检查失败可刷新重试 |
| `qa.html #material-picker` | 列出真实材料并勾选写回 `#materials` | 勾选/取消同步材料范围 | 列表失败时提示可手动输入材料 ID |
| `qa.html #qa-form` / `#question` / `#materials` / `#retrieval-mode` | 提问表单 | 空问题或空材料范围阻止提交 | `#submit-status` 安全文案 |
| `qa.html #index-btn` | 对选定材料逐个建立索引 | 索引建立完成 | 安全文案 + 可重试 |
| `qa.html #submit-btn` | 提交问题（幂等 key + sbSubmit.once） | 回答已生成 + 线程重读 | 安全文案 + 可重试 |
| `qa.html #thread-status` / `#threads` | 问答历史 | 线程列表 / 空态 | failed 安全文案 |
| 动态“查看对话与引用” / `.thread-detail` | 内联加载线程消息与引用 | 消息 + `.citation-link` | 详情失败安全文案 |
| 动态 `.citation-link` | 引用深链回材料 | `material-detail.html?material&citation=` | source_deleted/unavailable 置 `aria-disabled` |
| `tasks.html #tasks` / `#task-detail` | 任务列表 / 详情（轮询） | 状态徽章 + 进度条 | `#error` / `#detail-error` 安全文案 |
| `tasks.html` 动态取消/重试 | 对 pending/running 取消、failed/cancelled 重试 | confirm → POST → 重读 | alert 安全文案 |

### 5.4 API 契约对照表

| 行为 | Method / endpoint | 请求与响应关键字段 | 前端规则 / 失败语义 | 分类 |
|---|---|---|---|---|
| 导入单文件 | `POST /api/materials` | multipart `file`；返回 `{original_name,status,material_id,extraction_id,text_length,span_count,error_code,warnings}` | 材料记录的 `empty` 结果仍保留在列表中，但导入计数只把 `status==='success'` 计为成功；rejected/failed 逐项显示安全文案；单文件成功计数以 `status==='success'` 判定 | direct |
| 批量导入 | `POST /api/materials/batch` | multipart `files[]`；返回 `{total,success,empty,rejected,failed,items[]}` | 以 `items` 中 `status==='success'` 计数 | direct |
| 列表/搜索 | `GET /api/materials` | `status/q/limit/offset`；返回 `{items,total,has_more}` | 分页；`invalid_status`/`invalid_pagination` 安全文案；`qa.html #material-picker` 以 `limit=100&offset=0` 读取可选材料 | direct |
| 回收站 | `GET /api/materials/deleted` | `limit/offset`；返回 `{items,total,has_more}` | 独立视图与分页 | direct |
| 批量导出 | `POST /api/materials/export` | `{material_ids,include_original,include_text}`；返回 ZIP | zip 校验失败抛 `export_failed`；413/404 安全文案 | direct |
| 删除材料 | `DELETE /api/materials/{id}` | 204 | 软删除；`material_not_found`/`material_delete_failed` 安全文案 | direct |
| 恢复材料 | `POST /api/materials/{id}/restore` | 返回材料 payload | `material_not_deleted`/`material_restore_failed` 安全文案 | direct |
| 永久删除 | `POST /api/materials/{id}/purge` | 返回 `{status:'purged'}` | 破坏性；正式 UI 不开放，`decision-needed` | unreached |
| 材料详情 | `GET /api/materials/{id}` | 返回材料/解析字段 `{id,original_name,media_type,status,parser_id,parser_version,text,warnings,error_code,extraction_id,created_at,updated_at,spans[]}`；后端剔除 `stored_path` | 前端对未返回的 `text_length/span_count` 使用 0 fallback；404 `material_not_found` 安全文案 | direct |
| 下载原件 | `GET /api/materials/{id}/original` | 文件流 | 404 安全处理 | direct |
| 导出文本 | `GET /api/materials/{id}/text` | text/plain | 404 安全处理 | direct |
| 索引状态 | `GET /api/materials/{id}/ai-index` | 返回 `{status:not_indexed\|ready\|empty\|deleted,revision_id,chunk_count,is_current}` | 页面并行读取并明示状态 | direct |
| 建立索引 | `POST /api/materials/{id}/ai-index` | 幂等 key；返回 `{status,chunk_count,embedding:{status,embedded_count},revision_id,index_operation_id}` | 成功后重读真实状态；失败安全文案可重试 | direct |
| 异步入队 | `POST /api/materials/{id}/ai-index/tasks` | 幂等 key；202 返回 task | 正式 UI 用同步路径；`tasks.html` 只读观测；`intentional` | unreached |
| 检索 | `POST /api/retrieval` | 内部管道 | `qa/ask` 内部调用，不直接暴露；`intentional` | unreached |
| 上下文组装 | `POST /api/context/assemble` | 内部管道 | `qa/ask` 内部调用；`intentional` | unreached |
| 引用校验 | `POST /api/citation/validate` | 内部管道 | 详情页走 `GET /api/qa/citations/{id}`；`intentional` | unreached |
| AI 能力 | `GET /api/ai/capabilities` | 返回 `{llm_status,llm_provider,llm_model,llm_verification_status,ocr,asr,capture}` | qa.html/capture.html 读取；不显示 secret/path | direct |
| 提问 | `POST /api/qa/ask` | `{question,material_ids,retrieval_mode,allow_retrieval_fallback,top_k}` + 幂等 key；返回 `{status,thread_id,answer_text,citations[],retrieval{}}` | 空材料范围阻止；`retrieval_empty`/`retrieval_not_ready`/Provider 错误安全文案；幂等回放 | direct |
| 线程列表 | `GET /api/qa/threads` | 返回 `{items:[{id,title,updated_at,message_count,status}]}` | 历史加载/空态/failed | direct |
| 线程详情 | `GET /api/qa/threads/{id}` | 返回 `{messages:[{role,content,citations[]}]}` | 内联展开；失败安全文案 | direct |
| 引用详情 | `GET /api/qa/citations/{id}` | 返回 `{status:valid\|source_unavailable\|source_deleted,start_offset,end_offset,excerpt,span_ids}` | valid 高亮正文；失效安全提示 | direct |
| 任务列表 | `GET /api/tasks` | `status/task_kind` 过滤；返回 `{items,total}` | tasks.html 列表 | direct |
| 任务详情 | `GET /api/tasks/{id}` | 返回 `{task_id,operation_type,status,error_code,retry_count,progress_percent,...}` | 详情轮询 | direct |
| 任务取消/重试 | `POST /api/tasks/{id}/cancel` / `.../retry` | 返回任务 | confirm 后触发，重读 | direct |

### 5.5 Browser evidence

`/app` 直接证据（scoped-browser-pass）：

- `browser_p2_fe3_qa_app.spec.js` `4 passed`（P2-FE-3-3）：正式 `/app/qa.html` 的 `#material-picker` 真实材料选择并双向同步 `#materials`；未建索引时如实提示 `材料索引尚未建立`；`#index-btn` 后提问得到 `回答已生成`；`.citation-link` 跳转到 `material-detail.html?material=...&citation=...` 并高亮引用位置；`?material=` 预选保持；504 失败只显示 `Provider 请求超时` 且不泄露 detail/path/traceback，保留问题可直接重试；提交期间 `#submit-btn` 禁用且只发一次 `/api/qa/ask`；多材料范围得到 2 条引用；`/api/qa/threads` 失败显示 `请求失败，请重试`；390px 无横向溢出；Provider 未配置时 `#provider-status` 安全提示。
- `browser_p2_fe3_qa_threads_errors_app.spec.js` `3 passed`（P2-FE-3-4）：正式 `/app/qa.html` 线程工作区多会话切换（两次提问创建两个独立 `.thread-item`，分别展开/折叠，刷新后持久化）；`provider_rate_limited` (429) 映射为 `请求过于频繁，请稍后重试`，不泄露 `provider_rate_limited`/path/traceback；`provider_unavailable` (503) 映射为 `Provider 暂时不可用，请重试`，不泄露内部错误码。
- `browser_p1_1_material_qa_migration.spec.js` `5 passed`：索引 + 正文展示；问答引用深链 + `#citation-location` 高亮；引用不可用安全文案（不泄露 traceback/path）；**单文件导入成功计数 1/1**；**空文本索引状态如实显示“没有可用于问答的正文”**（本轮新增 2 项）。
- `browser_frontend_page_contract.spec.js`：materials 空态与失败安全、material-detail 缺 ID 安全、qa 空历史与 Provider 状态、线程过期响应丢弃。
- `browser_e2e.spec.js` / `browser_static_core.spec.js` / `browser_learning_pages.spec.js` / `browser_migration.spec.js`：导入 → 问答 → 学习全链与跨页导航。
- `browser_p1_4_c2_explainability.spec.js` / `browser_p1_4_c3_batch_export.spec.js`：接受/拒绝指导与批量导出。
- 共享 baseline / visual matrix 覆盖 10 个 viewport、无横向溢出、状态在 5 秒内离开 loading、可见焦点与触控尺寸。

`legacy_only`（等价证据尚未全部迁移到 `/app`）：`browser_qa.spec.js`（10 test）仍只访问 legacy QA 入口，保留不变；P2-FE-3-3 的 `browser_p2_fe3_qa_app.spec.js` 已迁移核心用户流程（材料选择、索引前置、问答、引用跳转、失败重试、重复提交、窄屏、Provider 未配置），P2-FE-3-4 的 `browser_p2_fe3_qa_threads_errors_app.spec.js` 已迁移线程工作区多会话切换与 rate-limit/unavailable 错误映射到正式 `/app`。剩余 `legacy_only` 维度：opt-in 真实外部 provider 路径、P6-C 跨页连接完整等价证据（正式页面对应维度为 `not_verified`）。材料管理的原有 legacy spec 继续保留并验证兼容入口；`browser_p2_fe3_materials_management_app.spec.js` 已覆盖正式 `/app` 的回收站、删除/恢复、刷新状态、三种批量 ZIP 导出、导出失败恢复、响应式和删除重复提交；与 `browser_p2_fe3_materials_app.spec.js` 合并覆盖正式材料导入/搜索/分页。其余历史证据仍不能直接证明正式页面等价能力，后续继续归入 P2-FE-3。

`not_verified`：真实 Provider 大文本问答、真实 OCR/ASR 采集链、生产规模、多进程、真实断电与跨时区边界。

## 6. 场景 3：练习会话 → 结果 → 错题复盘

状态：`design-skeleton / not_frozen`。既有 [`frontend-practice-workflow-contract.md`](frontend-practice-workflow-contract.md) 已覆盖练习会话/结果/复盘单场景的绝大部分真实事实，本合同**不复制其内容**：场景 3 的流程、状态与 API 对照以该文档为事实源，本节只记录本合同范围内的整合骨架、参与页面和待补齐项。场景 3 的正式实施（P2-FE-2 冻结后、P2-FE-3）以本节 + 既有 practice-workflow-contract 共同为基线。

### 6.1 已确认骨架

```text
practice.html 选择练习/建议
  → practice-session.html start / submit / finish
  → practice-result.html 查看安全结果
  → review.html 查看错题详情与来源
  → feedback / review / mark-mistake / redo
  → 薄弱点汇总 → 下一轮练习
```

参与页面暂定：`practice.html`、`practice-session.html`、`practice-result.html`、`review.html`、`exercises.html`。必须保持答案 key、内部 grading payload 和未批准正文不进入 DOM、URL、storage 或普通日志。

### 6.2 待补齐项

- `GET+POST /api/study/exercises/{exercise_id}/attempts` 的正式逐题行为；
- `GET /api/study/weak-points` 的复盘展示与下一轮练习入口；
- practice session archive 的入口、确认与状态迁移；
- exercise-set/cram-goal 详情是否独立成页或收敛在现有工作区；
- expired、archived、source unavailable、redo failed 的跨页恢复；
- `/legacy` practice evidence 与正式 `/app` 页面的一一迁移表。

## 7. 实施顺序与门禁

1. 场景 1 已作为模板完成实现与专项 browser evidence。
2. 场景 2 四件套已冻结（本切片，2026-09-05）；本轮已开始并完成材料管理核心 `/app` evidence 迁移与列表失败重试补强；QA legacy evidence、回收站/导出等剩余等价证据，以及合同认定的正式页缺口（purge 决策、异步索引入口决策）继续进入 P2-FE-3 后续独立可用切片。
3. 冻结场景 3 的四件套（以 [`frontend-practice-workflow-contract.md`](frontend-practice-workflow-contract.md) 为事实源），再补 attempt、weak-points 和归档行为。
4. 目标/模块管理、依赖删除、报告预览和 rhythm export 按上表归属进入独立可用切片。
5. 每个切片运行 focused tests；涉及 API、存储或基础设施时运行完整 backend；所有用户页面变更运行完整 Chromium。
6. 每次交付运行 contract audit、frontend inventory scan、source-size 和治理测试；更新 `STATUS.md`、`TODO.md`，不新增重复 evidence 文档。

## 8. 明确不在本合同中

- 改造为 Vue/React/TypeScript 或新增前端构建链；
- 新 endpoint、schema、migration、错误码或复制 `/legacy` 实现；
- 默认开启 report delivery；
- 多用户、云同步、多 worker、共享 data root 或生产规模承诺；
- 将 deterministic fake-provider、mock browser 或本地演练写成真实外部能力 `real-pass`；
- 仅因静态扫描显示 `dynamic`/`unreached` 就宣称能力存在或缺失。
