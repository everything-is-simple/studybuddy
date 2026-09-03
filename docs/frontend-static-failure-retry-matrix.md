# 静态前端失败与重试覆盖矩阵

> 状态：`A3-FC-3-2 / closed evidence index`
> 更新：2026-08-31
> 本文件把 `/app` 静态页的已暴露能力与现有浏览器证据对应起来。`/app` 是默认正式入口；`legacy_only` 和 `not_exposed` 不以静态页操作测试伪造成功路径，详见 [`frontend-static-capability-matrix.md`](frontend-static-capability-matrix.md)。

## 状态定义

- **covered**：静态页的 loading/empty/failed/retry 或安全边界已有 browser evidence。
- **baseline**：页面没有相应写操作或 retry；验证安全初始状态、空状态、键盘和隐私边界。
- **deferred**：能力属于 `legacy_only` 或 `not_exposed`，不将旧入口或后端证据误记为静态页操作证据。

## 页面覆盖表

| 静态页面 | 静态页已暴露能力 | failure/retry/安全证据 | 状态 |
|---|---|---|---|
| `index.html` | 应用入口、导航、能力说明 | `browser_frontend_static_baseline.spec.js`、`browser_frontend_shared_layer.spec.js` | baseline |
| `today.html` | 计划摘要、任务、来源状态和材料入口 | `browser_static_core.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_p1_4_c2_explainability.spec.js` | covered |
| `materials.html` | 导入、搜索、分页、删除、恢复、格式拒绝提示、批量 ZIP 导出 | `browser_static_core.spec.js`、`browser_material_management.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_4_real_input_restart.spec.js`、`browser_p1_4_c2_explainability.spec.js`、`browser_p1_4_c3_batch_export.spec.js` | covered |
| `material-detail.html` | 详情、解析解释、导出、索引、citation 定位、问答跳转 | `browser_static_core.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_1_material_qa_migration.spec.js`、`browser_p1_4_real_input_restart.spec.js`、`browser_p1_4_c2_explainability.spec.js` | covered |
| `qa.html` | 索引、同步问答、history、citation 跳转 | `browser_static_core.spec.js`、`browser_qa.spec.js`、`browser_frontend_page_contract.spec.js`、`browser_p1_4_real_input_restart.spec.js` | covered |
| `plans.html` | 列表、详情、状态/来源读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js`、`browser_p1_4_c2_explainability.spec.js` | covered |
| `plan-detail.html` | 独立详情、项目状态/来源读取 | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `notes.html` | 列表、详情、草稿确认读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `note-detail.html` | 独立详情、内容/引用/来源状态读取 | `browser_frontend_page_contract.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `cards.html` | 卡组/卡片读取、状态/来源读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `exercises.html` | 练习集/题目读取、确认、状态/来源读取 | `browser_frontend_matrix.spec.js`、`browser_frontend_state_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `practice.html` | 会话、结果、错题读取、启动 | `browser_frontend_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `practice-session.html` | 独立会话详情读取 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `practice-result.html` | 独立练习结果读取 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `capture.html` | fake/loopback 创建、上传、转写、草稿确认/拒绝 | `browser_a4.spec.js`、`browser_phase9d.spec.js`、`browser_frontend_system_matrix.spec.js` | covered |
| `classroom.html` | 采集/报告兼容读取、交付边界 | `browser_phase9d.spec.js`、`browser_frontend_system_matrix.spec.js`、`browser_learning_pages.spec.js` | covered |
| `review.html` | 错题/详情、复盘、标记、反馈、redo、归档 | `browser_practice_workflow.spec.js`、`browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `reports.html` | 脱敏报告列表读取 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `settings.html` | Provider/系统就绪只读状态 | `browser_frontend_static_baseline.spec.js`、`browser_a3_pages.spec.js` | covered |
| `tasks.html` | 单任务 read/cancel/retry | `browser_a4.spec.js`、`browser_frontend_system_matrix.spec.js` | covered |
| `settings-provider.html` | capabilities/readiness 只读 | `browser_a4.spec.js`、`browser_frontend_system_matrix.spec.js` | covered |

## 非静态页操作边界

以下能力均已在能力矩阵标记为 `legacy_only`、`not_exposed` 或 `a3_pages`：

- 计划、笔记、卡片、题目和练习的尚未迁移写操作；
- 全局任务列表；
- Provider 配置写入、密钥保存和连接测试；
- capture archive；
- 历史 classroom 兼容入口以外的报告操作；正式 `reports.html` 已覆盖 JSON/Markdown export 与只读审计工作区。

它们的后端或 `/legacy` evidence 不构成 `/app` 静态页面已迁移的声明。后续仅由 A3-PAGES 按独立页面和浏览器路径迁移。

## A3-FC-3-2 完成使用方式

本矩阵与能力矩阵一起用于判断：现有静态页已暴露的能力是否都有相应失败、重试或安全基线；其余缺口已诚实冻结，而不是被静默遗漏。
