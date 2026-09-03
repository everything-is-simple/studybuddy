# 静态前端能力矩阵

> 状态：`A3-FC-3-2 / closed`；A3-PAGES 与 A3-VISUAL 已完成声明范围。
> 更新：2026-08-31
> 范围：只描述 `/app/*.html` 的当前真实能力；不把旧 `/legacy` workspace、后端 API 存在或历史浏览器证据自动视为静态页面已经迁移。`/app` 是默认正式入口，`/legacy` 只作为迁移期兼容回退；矩阵中的 `legacy_only` 是后续必须逐项补齐的正式集成工作。

## 状态定义

| 状态 | 含义 |
|---|---|
| `static_verified` | `/app` 页面已有真实读取或操作路径，且有对应静态页浏览器证据。 |
| `legacy_only` | 后端和/或 `/legacy` 已有验证路径，但 `/app` 页面尚未迁移该操作。 |
| `not_exposed` | 后端没有公共契约，或当前安全/能力边界明确禁止在浏览器暴露该动作。 |
| `a3_pages` | 历史 A3-PAGES 迁移分类；A3-PAGES 已关闭，遗留条目必须改列为 `legacy_only`、`static_verified` 或 `not_exposed`。 |

## 页面能力矩阵

| 静态页面 | 能力 | 当前状态 | 证据或边界 |
|---|---|---|---|
| `index.html` | 产品入口、导航、能力边界说明 | `static_verified` | 应用壳和移动导航由 shared-layer browser tests 覆盖；首页聚合仍未批准。 |
| `today.html` | 活动计划节奏摘要、计划项读取、材料跳转 | `static_verified` | `browser_static_core.spec.js`；C2 从 plan `source_links` 映射来源状态，非 valid 来源禁用材料跳转；真实 valid→source_deleted→restart 为 L2/L3 scoped evidence。 |
| `materials.html` | 导入、搜索、分页、删除、恢复、回收站 | `static_verified` | static-core/material-management browser tests；P1-4 C0 另以真实 PDF/DOCX/PPTX/MD/中文长名 TXT 验证导入→详情→索引→重启回读；C2 对 DOC/PPT/RTF/XML 提供转换/拒绝提示（`browser_p1_4_c2_explainability.spec.js`）。 |
| `materials.html` | 当前页多选、批量导出原件/文本/全部 ZIP | `static_verified` | P1-4 C3 复用既有 `/api/materials/export`；正式 `/app` Chromium 验证三种 ZIP、中文名/内容、失败重试、回收站边界和正常重启后再次导出（`browser_p1_4_c3_batch_export.spec.js`，2 passed）。 |
| `material-detail.html` | 读取材料详情、下载原件/文本、进入问答 | `static_verified` | static-core browser tests；C2 详情显示解析状态、解析器、warning 和空/失败/拒绝的下一步提示。 |
| `material-detail.html` | 从详情触发索引 | `static_verified` | P1-1 已迁移「建立 AI 索引」按钮；P1-4 C0 以真实 PDF 验证索引建立并在重启后仍显示已建立。 |
| `qa.html` | 材料范围、同步问答、材料级索引、history | `static_verified` | static-core/QA browser tests；同步请求不是后台任务。 |
| `qa.html` | citation 详情/正文定位 | `static_verified` | P1-1 已迁移 citation detail 与正文 offset 定位；P1-4 C0 以真实多页 PDF 验证点击 citation 跳回原文高亮，并在重启后用同一 citation URL 复现同一高亮。 |
| `plans.html` | 目标、模块、计划列表和详情读取、状态/来源显示 | `static_verified` | learning/matrix browser tests；C2 从 plan `source_links` 映射到 item，缺失来源显示“未关联来源”，详情选择会保留 `plan_id` 上下文。 |
| `plan-detail.html` | 独立计划详情、项目状态和来源状态读取、缺少标识/失败重试 | `static_verified` | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js`；不新增后端能力。 |
| `plans.html` | 创建/编辑目标、模块、计划、依赖、进度、节奏；source-link 工作区创建/删除/刷新 | `static_verified` | P1-2 `/app` 页面提供真实写操作；C4-2 提供当前候选、模块/学习项 owner 选择、source link 添加/删除/显式 refresh，`browser_p1_4_c4_2_source_links.spec.js` 覆盖生命周期、失败重试与归档保护。 |
| `notes.html` | 列表、详情、笔记类型/来源状态、AI 草稿确认 | `static_verified` | learning/state-matrix browser tests；详情选择会保留 `note_id` 上下文。 |
| `note-detail.html` | 独立笔记详情、内容/引用/来源状态读取、缺少标识/失败重试 | `static_verified` | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js`；不新增后端能力。 |
| `notes.html` | 创建、编辑、生成、拒绝、归档、来源刷新、导出 | `static_verified` | P1-2 `/app` 页面提供用户笔记创建/编辑、AI 草稿生成、确认/拒绝/归档、模块关联、来源刷新与导出；`browser_p1_2_plans_notes_migration.spec.js` 覆盖核心路径。 |
| `cards.html` | 卡组/卡片读取、draft/来源状态、引用键展示 | `static_verified` | learning/state-matrix browser tests。 |
| `cards.html` | 创建、生成、编辑、确认、拒绝、归档、复习 | `static_verified` | P1-3 `/app` 页面提供卡组/卡片创建、生成、编辑、确认、拒绝、归档与复习；浏览器验收覆盖创建→详情→编辑→确认→复习。 |
| `exercises.html` | 练习集/题目读取、draft/来源状态、题目确认 | `static_verified` | learning/state-matrix browser tests。 |
| `exercises.html` | 创建、生成、编辑、拒绝、归档、作答/attempt | `static_verified` | P1-3 `/app` 页面提供练习集/题目创建、生成、编辑、确认、拒绝、归档与作答入口；浏览器验收覆盖创建→详情→编辑及答案 key 隐私边界。 |
| `practice.html` | 会话、结果、错题读取、练习会话启动 | `static_verified` | learning browser tests；状态和读取边界已审计。 |
| `practice.html` | cram 目标创建/激活/完成/归档、有效题目选择与 session 创建 | `static_verified` | P1-4 C4-1 复用既有 API；完整路径、过期/空题/来源/重复/重试与正常重启由 `browser_p1_4_c4_cram.spec.js` 覆盖。 |
| `practice-session.html` | 普通与 cram 会话详情、start/submit/finish | `static_verified` | Practice workflow 与 C4-1 browser evidence；cram URL 保留 `cram_goal_id`。 |
| `practice-result.html` | 普通与 cram 结果读取 | `static_verified` | 按是否有 `cram_goal_id` 使用既有对应 endpoint；不暴露答案 key。 |
| `review.html` | 独立错题与薄弱点读取 | `static_verified` | `browser_frontend_static_baseline.spec.js`；不新增复盘写操作。 |
| `capture.html` | fake/loopback 会话创建、上传、fake 转写、草稿编辑、确认、拒绝 | `static_verified` | A4/Phase 9D browser tests；真实 ASR 仍未通过 B1。 |
| `capture.html` | archive | `not_exposed` | 正式 API 固定返回 `capture_invalid_state`；不能伪造归档成功控件。 |
| `classroom.html` | 采集/报告只读兼容列表、报告详情、交付边界说明 | `static_verified` | learning/Phase 9D/system-matrix tests。 |
| `classroom.html` | 正式报告页、JSON/Markdown 导出、只读审计工作区 | `static_verified` | `reports.html` 已提供此正式路径；保持 `delivery=off`、allowlisted dry-run 和 append-only audit 边界。 |
| `tasks.html` | 单任务读取、cancel、retry、状态/进度显示 | `static_verified` | A4/system-matrix tests；仅批准的 `embedding_index` 任务可由 runner 执行。 |
| `tasks.html` | 全局任务列表/筛选、分页、任务详情/取消/重试 | `static_verified` | C4-3 复用新增 project-scoped `GET /api/tasks` 与既有详情/取消/重试；列表只展示脱敏公共字段，支持状态筛选、空态、失败和刷新。 |
| `settings-provider.html` | capabilities/readiness 只读状态 | `static_verified` | A4/system-matrix tests。 |
| `settings-provider.html` | Provider 配置写入、密钥保存、连接测试 | `not_exposed` | 后端没有获批的安全配置写入契约；浏览器不得保存或回显密钥。 |
| `reports.html` | 独立报告列表、脱敏摘要读取 | `static_verified` | `browser_frontend_static_baseline.spec.js`；导出/审计扩展仍按后续能力边界处理。 |
| `settings.html` | 独立系统设置只读聚合、Provider/就绪状态跳转 | `static_verified` | `browser_frontend_static_baseline.spec.js`；不开放配置写入或密钥保存。 |

## A3-FC-3-2 收口要求

> 历史完整 browser 基线（2026-08-30）：126 passed, 3 skipped / 129 项；当前完整基线以 `STATUS.md` 为准：144 passed, 4 skipped；skip 均为 opt-in 真实 smoke。

### 全静态页面基线

所有 21 个当前正式静态页面必须具有或继承以下证据：

- 加载、空、失败状态；
- 适用页面的刷新/retry；
- 安全错误映射：不出现路径、SQL、traceback、secret、token、raw provider response、答案 key 或不应公开的正文；
- 可见键盘焦点和移动端“更多”导航；
- 360、390、430、600、768、820、1024、1366、1440、1920px 无意外横向滚动；
- 已暴露写操作使用共享请求层、幂等策略和页面请求取消。

### 来源生命周期读取证据

适用页面必须诚实显示从服务端读取到的状态，而不是伪造操作或成功：

```text
valid / stale / source_deleted / source_unavailable
pending_review / uncertain
```

优先完成：`plans.html`、`notes.html`、`cards.html`、`exercises.html`、`capture.html`、`classroom.html`。未迁移写操作只记为 `legacy_only`，不以测试 mock 伪造静态页成功路径。

## 失败与重试证据

[`frontend-static-failure-retry-matrix.md`](frontend-static-failure-retry-matrix.md) 是静态页失败、重试和安全 evidence 的唯一索引。它只为 `static_verified` 的已暴露能力建立 browser evidence；`legacy_only`、`not_exposed` 与 `a3_pages` 明确为 deferred，不能用 `/legacy` 或后端存在替代静态页证据。

## 后续冻结能力的处理规则

- `legacy_only`：按唯一正式 `/app` 入口目标逐项迁移，一项能力一份页面/路径、状态/隐私合同和 browser evidence；不复制 `/legacy` 实现，也不以 API 存在替代静态页证据。
- `not_exposed`：保持不暴露。必须先获得安全、稳定的公共后端契约，再单独评审 UI；不得用 mock 或静态文案伪造可执行成功。
- practice workflow（逐题作答、submit、finish、redo）是首个后续行为切片，须先冻结答案 key 隐私、幂等、stale response、失败/retry。
- B3 report export/audit 已在声明范围内完成，持续显示 `delivery=off`、dry-run 和 append-only audit 边界；Provider 写入仅在安全写入/验证契约批准后另行立项，浏览器永不保存、回显或持久化密钥。

## 进入 A3-PAGES 的门槛

只有以下同时成立，才可开始页面拆分：

1. 本矩阵中的每项都有 `static_verified`、`legacy_only`、`not_exposed` 或 `a3_pages` 的明确分类；
2. 自动契约审计为 0 findings；
3. 21 个现有正式静态页面的 loading/empty/failed/privacy/keyboard 基线和 360–1920 矩阵通过；
4. 适用页面具备来源生命周期读取证据；
5. 完整 browser/backend suite、source-size 和 diff 检查通过；
6. `TODO.md`、`ROADMAP_CAPABILITIES.md`、`frontend-plan.md`、`STATUS.md` 同步真实状态，并按 `CODE_TEST_GOVERNANCE.md` 区分当前状态与历史快照。
