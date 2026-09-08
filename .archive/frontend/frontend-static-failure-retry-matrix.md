# 静态前端失败与重试覆盖矩阵

> 状态：`A3-FC-3-2 / closed evidence index`（2026-09-05 修订 `today.html` 行）
> 更新：2026-09-05
> 本文件把 `/app` 静态页的已暴露能力与现有浏览器证据对应起来。`/`、`/app/`、`/app/index.html` 统一进入 `/app/today.html`；`legacy_only` 和 `not_exposed` 不以静态页操作测试伪造成功路径，详见 [`frontend-static-capability-matrix.md`](frontend-static-capability-matrix.md)。
>
> **2026-09-05 更正**：前端事实盘点（见 [`frontend-inventory-report.md`](frontend-inventory-report.md)）发现 `today.html` 此前虽标 `covered`，实际**没有任何重试控件**——三个区块加载失败后只显示错误文案，用户只能手动刷新浏览器。旧标记之所以成立，是因为审计规则只对「有写操作的页面」要求重试入口，而 Today 是只读页。该缺陷已修复（新增 `#retry-today`），并补上失败注入 + 重试恢复的浏览器证据；本行现为真实 `covered`。

## 状态定义

- **covered**：静态页的 loading/empty/failed/retry 或安全边界已有 browser evidence。
- **baseline**：页面没有相应写操作或 retry；验证安全初始状态、空状态、键盘和隐私边界。
- **deferred**：能力属于 `legacy_only` 或 `not_exposed`，不将旧入口或后端证据误记为静态页操作证据。

只读页同样需要重试入口：加载失败后如果只有错误文案而没有恢复控件，用户只能手动刷新浏览器，这按本表算缺口而不是 `baseline`。

## 页面覆盖表

| 静态页面 | 静态页已暴露能力 | failure/retry/安全证据 | 状态 |
|---|---|---|---|
| `index.html` | `/app/` 与旧书签兼容跳转到唯一 Today 页 | `browser_migration.spec.js`、`browser_static_pages.spec.js` | covered |
| `today.html` | 计划摘要、任务、近七日趋势、来源状态和材料入口；`#retry-today` 统一重试三个区块 | `browser_static_core.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_p1_4_c2_explainability.spec.js`、`browser_p1_4_c4_4_weekly_trend.spec.js`、`browser_plans_today_progress.spec.js`（失败注入 → 安全文案 → 重试恢复） | covered |
| `materials.html` | 导入、搜索、分页、删除、恢复、格式拒绝提示、批量 ZIP 导出 | `browser_static_core.spec.js`、`browser_material_management.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_4_real_input_restart.spec.js`、`browser_p1_4_c2_explainability.spec.js`、`browser_p1_4_c3_batch_export.spec.js` | covered |
| `material-detail.html` | 详情、解析解释、导出、索引、citation 定位、问答跳转 | `browser_static_core.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_1_material_qa_migration.spec.js`、`browser_p1_4_real_input_restart.spec.js`、`browser_p1_4_c2_explainability.spec.js` | covered |
| `qa.html` | 索引、同步问答、history、citation 跳转 | `browser_static_core.spec.js`、`browser_qa.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_4_real_input_restart.spec.js` | covered |
| `plans.html` | 列表、详情、状态/来源读取；source-link 添加/删除/刷新与安全失败重试 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js`、`browser_p1_4_c2_explainability.spec.js`、`browser_p1_4_c4_2_source_links.spec.js` | covered |
| `plan-detail.html` | 独立详情、项目状态/来源读取 | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `notes.html` | 列表、详情、草稿确认读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `note-detail.html` | 独立详情、内容/引用/来源状态读取 | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `cards.html` | 卡组/卡片读取、状态/来源读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `exercises.html` | 练习集/题目读取、确认、状态/来源读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `practice.html` | 会话、结果、错题读取、启动；cram 目标/选题/session 的空、过期、来源失效、重复提交与失败重试 | `browser_frontend_matrix.spec.js`、`browser_learning_pages.spec.js`、`browser_p1_4_c4_cram.spec.js` | covered |
| `practice-session.html` | 普通/cram 会话详情、start/submit/finish 与重试 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js`、`browser_practice_workflow.spec.js`、`browser_p1_4_c4_cram.spec.js` | covered |
| `practice-result.html` | 普通/cram 结果读取与安全重试 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js`、`browser_practice_workflow.spec.js`、`browser_p1_4_c4_cram.spec.js` | covered |
| `capture.html` | fake/loopback 创建、上传、转写、草稿确认/拒绝 | `browser_a4.spec.js`、`browser_phase9d.spec.js`、`browser_frontend_system_matrix.spec.js` | covered |
| `classroom.html` | 采集/报告兼容读取、交付边界 | `browser_phase9d.spec.js`、`browser_frontend_system_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `review.html` | 错题/详情、复盘、标记、反馈、redo、归档 | `browser_practice_workflow.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `reports.html` | 脱敏报告列表读取 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `settings.html` | 能力仪表盘、自检、配置读取/保存/清除 | `browser_frontend_static_baseline.spec.js`、`browser_p1_5_configuration_security.spec.js` | covered |
| `tasks.html` | 全局列表/筛选/分页、单任务 read/cancel/retry | `browser_a4.spec.js`、`browser_frontend_system_matrix.spec.js`、`test_p1_4_c4_3_task_list.py` | covered |
| `settings-provider.html` | capabilities/readiness、显式连接测试、测试通过后保存且不回显 secret | `browser_a4.spec.js`、`browser_frontend_system_matrix.spec.js`、`browser_p1_5_configuration_security.spec.js` | covered |

## 非静态页操作边界

以下能力均已在能力矩阵标记为 `legacy_only`、`not_exposed` 或 `a3_pages`：

- 计划、笔记、卡片、题目和练习的尚未迁移写操作；
- 全局任务列表；
- Provider/Email 凭据现已支持显式连接测试后保存；未暴露的是 report delivery 的 enable/mode/per-use authorization，保存凭据不能开启外发；
- capture archive；
- 历史 classroom 兼容入口以外的报告操作；正式 `reports.html` 已覆盖 JSON/Markdown export 与只读审计工作区。

它们的后端或 `/legacy` evidence 不构成 `/app` 静态页面已迁移的声明。后续仅由 A3-PAGES 按独立页面和浏览器路径迁移。

## A3-FC-3-2 完成使用方式

本矩阵与能力矩阵一起用于判断：现有静态页已暴露的能力是否都有相应失败、重试或安全基线；其余缺口已诚实冻结，而不是被静默遗漏。

审计脚本 `backend/scripts/audit-frontend-contract.py` 的 `write_without_retry_signal` 规则只覆盖有写操作的页面，因此**不能**单靠它证明本表的 retry 列。只读页的重试入口需要按本表逐页人工核对。剩余 5 个只读/详情页（`note-detail`、`practice-result`、`plan-detail`、`reports`、`review`）已确认各自带显式重试按钮（`retry-note`、`retry-result`、`retry-plan`、`retry-reports`、`retry-review`）；`index.html` 为跳转页，无需重试。
