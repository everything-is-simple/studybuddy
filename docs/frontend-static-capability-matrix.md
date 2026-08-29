# 静态前端能力矩阵

> 状态：`A3-FC-3-2 / in_progress`
> 更新：2026-08-30
> 范围：只描述 `/app/*.html` 的当前真实能力；不把旧 `/legacy` workspace、后端 API 存在或历史浏览器证据自动视为静态页面已经迁移。

## 状态定义

| 状态 | 含义 |
|---|---|
| `static_verified` | `/app` 页面已有真实读取或操作路径，且有对应静态页浏览器证据。 |
| `legacy_only` | 后端和/或 `/legacy` 已有验证路径，但 `/app` 页面尚未迁移该操作。 |
| `not_exposed` | 后端没有公共契约，或当前安全/能力边界明确禁止在浏览器暴露该动作。 |
| `a3_pages` | 已冻结为 A3-PAGES 的独立页面迁移目标；在该任务开始前不能把它声明为静态页已完成。 |

## 页面能力矩阵

| 静态页面 | 能力 | 当前状态 | 证据或边界 |
|---|---|---|---|
| `index.html` | 产品入口、导航、能力边界说明 | `static_verified` | 应用壳和移动导航由 shared-layer browser tests 覆盖；首页聚合仍未批准。 |
| `today.html` | 活动计划节奏摘要、计划项读取、材料跳转 | `static_verified` | `browser_static_core.spec.js`；没有计划时诚实显示空状态。 |
| `materials.html` | 导入、搜索、分页、删除、恢复、回收站 | `static_verified` | static-core/material-management browser tests。 |
| `material-detail.html` | 读取材料详情、下载原件/文本、进入问答 | `static_verified` | static-core browser tests；页面没有独立索引按钮。 |
| `material-detail.html` | 从详情触发索引 | `legacy_only` | 后端正式路由存在；当前静态页只提供读取、导出和问答跳转。 |
| `qa.html` | 材料范围、同步问答、材料级索引、history | `static_verified` | static-core/QA browser tests；同步请求不是后台任务。 |
| `qa.html` | citation 详情/正文定位 | `legacy_only` | 后端和旧 workspace 有证据；静态页当前只提供材料详情链接，未迁移正式 citation detail 面板。 |
| `plans.html` | 目标、模块、计划列表和详情读取、状态/来源显示 | `static_verified` | learning/matrix browser tests。 |
| `plans.html` | 创建/编辑目标、模块、计划、依赖、进度、节奏 | `legacy_only` | 已有后端和旧 workspace 契约；静态页未迁移写操作。 |
| `notes.html` | 列表、详情、笔记类型/来源状态、AI 草稿确认 | `static_verified` | learning/state-matrix browser tests。 |
| `notes.html` | 创建、编辑、生成、拒绝、归档、来源刷新、导出 | `legacy_only` | 后端和旧 workspace 契约已存在；静态页仅迁移确认读取路径。 |
| `cards.html` | 卡组/卡片读取、draft/来源状态、引用键展示 | `static_verified` | learning/state-matrix browser tests。 |
| `cards.html` | 创建、生成、编辑、确认、拒绝、归档、复习 | `legacy_only` | 后端和旧 workspace 契约已存在，未迁移到静态页。 |
| `exercises.html` | 练习集/题目读取、draft/来源状态、题目确认 | `static_verified` | learning/state-matrix browser tests。 |
| `exercises.html` | 创建、生成、编辑、拒绝、归档、作答/attempt | `legacy_only` | 后端和旧 workspace 契约已存在，未迁移到静态页。 |
| `practice.html` | 会话、结果、错题读取、练习会话启动 | `static_verified` | learning browser tests；状态和读取边界已审计。 |
| `practice.html` | 创建会话、逐题作答、finish、反馈、redo、冲刺 | `legacy_only` | 后端和旧 workspace 契约已存在，未迁移到静态页。 |
| `capture.html` | fake/loopback 会话创建、上传、fake 转写、草稿编辑、确认、拒绝 | `static_verified` | A4/Phase 9D browser tests；真实 ASR 仍未通过 B1。 |
| `capture.html` | archive | `not_exposed` | 正式 API 固定返回 `capture_invalid_state`；不能伪造归档成功控件。 |
| `classroom.html` | 采集/报告只读兼容列表、报告详情、交付边界说明 | `static_verified` | learning/Phase 9D/system-matrix tests。 |
| `classroom.html` | 正式报告页、导出、完整审计工作区 | `a3_pages` | 迁移目标为 `reports.html`；当前兼容页保持可回退。 |
| `tasks.html` | 单任务读取、cancel、retry、状态/进度显示 | `static_verified` | A4/system-matrix tests；仅批准的 `embedding_index` 任务可由 runner 执行。 |
| `tasks.html` | 全局任务列表/筛选 | `not_exposed` | 后端没有全局 task-list API；页面不得伪造列表。 |
| `settings-provider.html` | capabilities/readiness 只读状态 | `static_verified` | A4/system-matrix tests。 |
| `settings-provider.html` | Provider 配置写入、密钥保存、连接测试 | `not_exposed` | 后端没有获批的安全配置写入契约；浏览器不得保存或回显密钥。 |
| `reports.html` | 独立报告、导出、审计页面 | `a3_pages` | 当前由 `classroom.html` 兼容入口承载。 |
| `settings.html` | 独立系统设置页 | `a3_pages` | 当前由 `settings-provider.html` 与 `tasks.html` 分担只读边界。 |

## A3-FC-3-2 收口要求

### 全静态页面基线

所有 14 个当前静态页面必须具有或继承以下证据：

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

## 进入 A3-PAGES 的门槛

只有以下同时成立，才可开始页面拆分：

1. 本矩阵中的每项都有 `static_verified`、`legacy_only`、`not_exposed` 或 `a3_pages` 的明确分类；
2. 自动契约审计为 0 findings；
3. 14 个现有静态页面的 loading/empty/failed/privacy/keyboard 基线和 360–1920 矩阵通过；
4. 适用页面具备来源生命周期读取证据；
5. 完整 browser/backend suite、source-size 和 diff 检查通过；
6. `TODO.md`、`ROADMAP_CAPABILITIES.md`、`frontend-plan.md`、`STATUS.md` 同步真实状态。
