# 前端盘点自动扫描结果

> 由 `backend/scripts/scan-frontend-inventory.py` 生成。只读扫描，反映当前代码事实。

- 静态页面：21
- 共享资源：6
- 浏览器 spec：54
- 去重后前端调用的 API 端点：103
- 后端 `/api/*` 路由声明：165（去重路径 137）

## 1. 页面资源与内联脚本

| 页面 | CSS | JS | 内联 style | 内联 script 块 | 内联脚本体积 | 直接 fetch | API 数 | 覆盖 spec 数 |
|---|---|---|---|---:|---:|---:|---:|---:|
| capture.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 13.6 KiB | 0 | 8 | 8 |
| cards.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 9.6 KiB | 0 | 9 | 8 |
| classroom.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 9.2 KiB | 0 | 6 | 6 |
| exercises.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 11.1 KiB | 0 | 8 | 8 |
| index.html | 无 | 无 | 否 | 1 | 0.0 KiB | 0 | 0 | 1 |
| material-detail.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 6.2 KiB | 0 | 5 | 10 |
| materials.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 11.0 KiB | 0 | 6 | 16 |
| note-detail.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 2.6 KiB | 0 | 1 | 4 |
| notes.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 8.4 KiB | 0 | 8 | 8 |
| plan-detail.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 7.5 KiB | 0 | 3 | 6 |
| plans.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 19.5 KiB | 0 | 21 | 12 |
| practice-result.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 1.9 KiB | 0 | 2 | 6 |
| practice-session.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 6.1 KiB | 0 | 4 | 5 |
| practice.html | tokens.css, app.css | api.js, state.js, cram.js, shell.js | 否 | 1 | 10.6 KiB | 0 | 6 | 9 |
| qa.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 6.2 KiB | 0 | 5 | 12 |
| reports.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 3.5 KiB | 0 | 3 | 5 |
| review.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 6.8 KiB | 0 | 7 | 6 |
| settings-provider.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 10.2 KiB | 0 | 5 | 6 |
| settings.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 9.5 KiB | 0 | 4 | 5 |
| tasks.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 6.8 KiB | 0 | 4 | 7 |
| today.html | tokens.css, app.css | api.js, state.js, shell.js | 否 | 1 | 8.2 KiB | 0 | 6 | 10 |

## 2. 共享资源

| 资源 | 体积 | API 数 | 直接 fetch |
|---|---:|---:|---:|
| `js/api.js` | 6.7 KiB | 0 | 1 |
| `js/cram.js` | 7.9 KiB | 4 | 0 |
| `js/shell.js` | 1.7 KiB | 1 | 0 |
| `js/state.js` | 1.9 KiB | 0 | 0 |
| `css/app.css` | 17.5 KiB | 0 | 0 |
| `css/tokens.css` | 0.9 KiB | 0 | 0 |

## 3. API 端点 → 调用方

| API 端点 | 调用方 |
|---|---|
| `/api/ai/capabilities` | capture.html, qa.html, settings-provider.html |
| `/api/materials` | materials.html |
| `/api/materials/batch` | materials.html |
| `/api/materials/deleted` | materials.html |
| `/api/materials/export` | materials.html |
| `/api/materials/{id}` | material-detail.html, materials.html |
| `/api/materials/{id}/ai-index` | material-detail.html, qa.html |
| `/api/materials/{id}/original` | material-detail.html |
| `/api/materials/{id}/restore` | materials.html |
| `/api/materials/{id}/text` | material-detail.html |
| `/api/qa/ask` | qa.html |
| `/api/qa/citations/{id}` | material-detail.html |
| `/api/qa/threads` | qa.html |
| `/api/qa/threads/{id}` | qa.html |
| `/api/readiness` | js/shell.js, settings-provider.html |
| `/api/study/attempts/{id}/mark-mistake` | review.html |
| `/api/study/attempts/{id}/review` | review.html |
| `/api/study/capture-sessions` | capture.html, classroom.html |
| `/api/study/capture-sessions/{id}` | capture.html, classroom.html |
| `/api/study/capture-sessions/{id}/confirm` | capture.html, classroom.html |
| `/api/study/capture-sessions/{id}/reject` | capture.html |
| `/api/study/capture-sessions/{id}/transcribe` | capture.html |
| `/api/study/capture-sessions/{id}/transcript` | classroom.html |
| `/api/study/capture-sessions/{id}/transcript/edit` | capture.html |
| `/api/study/capture-sessions/{id}/upload` | capture.html |
| `/api/study/cards/{id}` | cards.html |
| `/api/study/cards/{id}/archive` | cards.html |
| `/api/study/cards/{id}/confirm` | cards.html |
| `/api/study/cards/{id}/reject` | cards.html |
| `/api/study/cards/{id}/reviews` | cards.html |
| `/api/study/cards?<query>` | cards.html |
| `/api/study/cram-goals` | js/cram.js |
| `/api/study/cram-goals/{id}/sessions` | js/cram.js |
| `/api/study/cram-goals/{id}/sessions/{id}/result` | practice-result.html |
| `/api/study/cram-goals/{id}/{id}` | js/cram.js |
| `/api/study/decks` | cards.html |
| `/api/study/decks/{id}/cards` | cards.html |
| `/api/study/decks/{id}/generate` | cards.html |
| `/api/study/exercise-sets` | exercises.html |
| `/api/study/exercise-sets/{id}/exercises` | exercises.html |
| `/api/study/exercise-sets/{id}/generate` | exercises.html |
| `/api/study/exercises` | js/cram.js |
| `/api/study/exercises/{id}` | exercises.html |
| `/api/study/exercises/{id}/archive` | exercises.html |
| `/api/study/exercises/{id}/confirm` | exercises.html |
| `/api/study/exercises/{id}/reject` | exercises.html |
| `/api/study/exercises?<query>` | exercises.html |
| `/api/study/goals` | plans.html |
| `/api/study/mistakes` | practice.html, review.html |
| `/api/study/mistakes/{id}` | review.html |
| `/api/study/mistakes/{id}/archive` | review.html |
| `/api/study/mistakes/{id}/feedback` | review.html |
| `/api/study/mistakes/{id}/redo` | review.html |
| `/api/study/modules` | notes.html, plans.html |
| `/api/study/modules/{id}/sources` | plans.html |
| `/api/study/modules/{id}/sources/{id}` | plans.html |
| `/api/study/notes` | notes.html |
| `/api/study/notes/generate` | notes.html |
| `/api/study/notes/sources/refresh` | notes.html |
| `/api/study/notes/{id}` | note-detail.html, notes.html |
| `/api/study/notes/{id}/export?<query>` | notes.html |
| `/api/study/notes/{id}/modules/{id}` | notes.html |
| `/api/study/notes/{id}/{id}` | notes.html |
| `/api/study/plans` | plans.html, today.html |
| `/api/study/plans/{id}` | plan-detail.html, plans.html, today.html |
| `/api/study/plans/{id}/archive` | plans.html |
| `/api/study/plans/{id}/dependencies` | plans.html |
| `/api/study/plans/{id}/items` | plans.html |
| `/api/study/plans/{id}/items/{id}` | plans.html |
| `/api/study/plans/{id}/items/{id}/archive` | plans.html |
| `/api/study/plans/{id}/items/{id}/progress` | plan-detail.html, plans.html |
| `/api/study/plans/{id}/items/{id}/sources` | plans.html |
| `/api/study/plans/{id}/items/{id}/sources/{id}` | plans.html |
| `/api/study/plans/{id}/progress` | plan-detail.html |
| `/api/study/plans/{id}/rhythm` | plans.html, today.html |
| `/api/study/plans/{id}/rhythm/allocations` | plans.html, today.html |
| `/api/study/plans/{id}/rhythm/allocations/{id}` | plans.html |
| `/api/study/plans/{id}/rhythm/summary` | today.html |
| `/api/study/plans/{id}/rhythm/weekly-trend` | today.html |
| `/api/study/plans/{id}/{id}` | plans.html |
| `/api/study/practice-recommendations?<query>` | practice.html |
| `/api/study/practice-sessions` | practice.html |
| `/api/study/practice-sessions/{id}` | practice-session.html, practice.html |
| `/api/study/practice-sessions/{id}/finish` | practice-session.html |
| `/api/study/practice-sessions/{id}/items/{id}/submit` | practice-session.html |
| `/api/study/practice-sessions/{id}/result` | practice-result.html, practice.html |
| `/api/study/practice-sessions/{id}/start` | practice-session.html, practice.html |
| `/api/study/reports` | classroom.html, reports.html |
| `/api/study/reports/{id}` | classroom.html, reports.html |
| `/api/study/reports/{id}/export?<query>` | reports.html |
| `/api/study/source-candidates` | plans.html |
| `/api/study/sources/refresh` | plans.html |
| `/api/study/sources?<query>` | plans.html |
| `/api/system/capabilities` | settings.html |
| `/api/system/capabilities/self-check` | settings.html |
| `/api/system/email-connection-test` | settings-provider.html |
| `/api/system/provider-connection-test` | settings-provider.html |
| `/api/system/settings` | settings-provider.html, settings.html |
| `/api/system/settings/clear` | settings.html |
| `/api/tasks` | tasks.html |
| `/api/tasks/{id}` | tasks.html |
| `/api/tasks/{id}/cancel` | tasks.html |
| `/api/tasks/{id}/retry` | tasks.html |

## 4. 页面入口与控件清单

`静态出口` 只算 HTML 里写死的 `/app/*.html` 链接；`shell.js` 注入的共享导航不计入。

| 页面 | 静态出口 | 按钮数 | 具名按钮 | 表单控件 |
|---|---|---:|---|---|
| capture.html | today.html | 5 | `#new-session-btn` 新建采集会话<br>`#refresh-btn` 刷新<br>`#cancel-dialog-btn` 取消<br>`#close-detail-btn` 关闭 | form: `#new-session-form`<br>input: `#file-input-${captureId}`, `#include-archived`, `#media-type`, `#original-name`<br>select: `#asset-kind` |
| cards.html | today.html | 4 | `#refresh-decks` 刷新列表 | form: `#card-create-form`, `#card-generate-form`, `#deck-create-form`<br>input: `#card-material-ids`, `#card-topic`, `#new-card-front`, `#new-deck-title`<br>textarea: `#new-card-back` |
| classroom.html | today.html | 2 | `#refresh-captures` 刷新列表<br>`#refresh-reports` 刷新 | 无 |
| exercises.html | practice.html, today.html | 4 | `#refresh-sets` 刷新列表 | form: `#exercise-create-form`, `#exercise-generate-form`, `#set-create-form`<br>input: `#exercise-material-ids`, `#exercise-topic`, `#new-exercise-answer`, `#new-exercise-prompt`, `#new-set-title`<br>select: `#new-exercise-type` |
| index.html | today.html | 0 | 无 | 无 |
| material-detail.html | materials.html, qa.html, today.html | 3 | `#index` 建立 AI 索引<br>`#export-original` 下载原文件<br>`#export-text` 导出解析文本 | 无 |
| materials.html | material-detail.html, today.html | 7 | `#folder-btn` 选择文件夹导入<br>`#apply-filters` 应用筛选<br>`#view-deleted` 查看回收站<br>`#retry-materials` 重新加载材料<br>`#export-originals` 导出原件 ZIP<br>`#export-texts` 导出文本 ZIP<br>`#export-all` 导出全部 ZIP | input: `#file-input`, `#folder-input`, `#search-input`, `#select-page`<br>select: `#status-filter` |
| note-detail.html | notes.html, today.html | 1 | `#retry-note` 重试 | 无 |
| notes.html | today.html | 5 | `#link-module` 关联到当前笔记<br>`#generate` 生成 AI 草稿<br>`#refresh` 刷新列表<br>`#refresh-notes` 刷新笔记 | form: `#create-form`<br>input: `#material-id`, `#module-title`, `#new-title`, `#topic`<br>textarea: `#new-content` |
| plan-detail.html | plans.html, today.html | 2 | `#retry-plan` 重试<br>`#refresh-progress` 刷新进度 | 无 |
| plans.html | plan-detail.html, today.html | 6 | `#refresh-all` 刷新数据<br>`#source-refresh` 刷新来源<br>`#source-add` 添加来源链接 | form: `#goal-form`, `#module-form`, `#plan-form`<br>input: `#goal-title`, `#module-title`, `#plan-title`<br>select: `#plan-goal`, `#source-candidate`, `#source-owner` |
| practice-result.html | practice.html, review.html, today.html | 1 | `#retry-result` 重试 | 无 |
| practice-session.html | practice.html, today.html | 1 | `#retry-session` 重试 | 无 |
| practice.html | practice-session.html, today.html | 6 | `#refresh-cram` 刷新冲刺<br>`#create-cram-goal` 创建冲刺目标<br>`#create-recommended-session` 创建练习会话<br>`#refresh-recommendations` 刷新推荐<br>`#refresh-sessions` 刷新列表<br>`#refresh-mistakes` 刷新 | form: `#cram-goal-form`<br>input: `#cram-count`, `#cram-date`, `#cram-title`<br>select: `#recommendation-limit` |
| qa.html | materials.html, today.html | 2 | `#index-btn` 索引当前材料<br>`#submit-btn` 提交问题 | form: `#qa-form`<br>input: `#materials`<br>select: `#retrieval-mode`<br>textarea: `#question` |
| reports.html | classroom.html, today.html | 3 | `#retry-reports` 重试<br>`#export-json` 导出 JSON<br>`#export-markdown` 导出 Markdown | 无 |
| review.html | practice.html, today.html | 1 | `#retry-review` 重试 | 无 |
| settings-provider.html | today.html | 6 | `#provider-copy` 复制到剪贴板（仅内存生成）<br>`#provider-test` 测试 Provider 连接<br>`#provider-save` 保存此配置<br>`#email-copy` 复制 Email 环境变量（仅内存生成）<br>`#email-test` 测试 Email 连接<br>`#email-save` 保存此配置 | form: `#email-form`, `#provider-form`<br>input: `#email-timeout`, `#feishu-webhook`, `#provider-id`, `#provider-key`, `#provider-model`, `#provider-timeout`, `#provider-url`, `#smtp-host`, `#smtp-password`, `#smtp-port`, `#smtp-recipient`, `#smtp-sender`, `#smtp-username`<br>select: `#email-channel`, `#provider-type`, `#smtp-secure` |
| settings.html | capture.html, settings-provider.html, tasks.html, today.html | 8 | `#capability-recheck` 重新自检<br>`#capability-refresh` 刷新状态<br>`#ai-save` 保存并生效<br>`#ai-clear` 清除已保存配置<br>`#embedding-save` 保存并生效<br>`#embedding-clear` 清除已保存配置<br>`#local-save` 保存并生效<br>`#local-clear` 清除本机组件覆盖 | form: `#ai-form`, `#embedding-form`, `#local-form`<br>input: `#ai-key`, `#ai-model`, `#ai-provider`, `#ai-url`, `#asr-model`, `#asr-runtime`, `#embedding-key`, `#embedding-model`, `#embedding-provider`, `#embedding-url`, `#ocr-root`<br>select: `#ocr-enabled` |
| tasks.html | today.html | 2 | `#apply-filters` 应用筛选<br>`#refresh-btn` 刷新 | select: `#status-filter` |
| today.html | plans.html | 1 | `#retry-today` 重新加载 | 无 |

## 5. 页面 → 覆盖 spec

| 页面 | spec 数 | spec |
|---|---:|---|
| capture.html | 8 | browser_a4.spec.js, browser_b2_ocr_c5.spec.js, browser_formal_asr.spec.js, browser_frontend_shared_layer.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_system_matrix.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js |
| cards.html | 8 | browser_e2e.spec.js, browser_frontend_matrix.spec.js, browser_frontend_state_matrix.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_3_cards_exercises_review_migration.spec.js |
| classroom.html | 6 | browser_e2e.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_system_matrix.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js |
| exercises.html | 8 | browser_e2e.spec.js, browser_frontend_matrix.spec.js, browser_frontend_state_matrix.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_3_cards_exercises_review_migration.spec.js |
| index.html | 1 | browser_migration.spec.js |
| material-detail.html | 10 | browser_frontend_page_contract.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_1_material_qa_migration.spec.js, browser_p1_4_c2_explainability.spec.js, browser_p1_4_real_input_restart.spec.js, browser_static_core.spec.js, browser_static_operations.spec.js, browser_static_pages.spec.js |
| materials.html | 16 | browser_e2e.spec.js, browser_frontend_page_contract.spec.js, browser_frontend_shared_layer.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_1_material_qa_migration.spec.js, browser_p1_4_c2_explainability.spec.js, browser_p1_4_c3_batch_export.spec.js, browser_p1_4_c4_5_measurement.spec.js, browser_p1_4_real_input_restart.spec.js, browser_p2_fe3_materials_app.spec.js, browser_static_core.spec.js, browser_static_operations.spec.js, browser_static_pages.spec.js |
| note-detail.html | 4 | browser_a3_pages.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js |
| notes.html | 8 | browser_e2e.spec.js, browser_frontend_matrix.spec.js, browser_frontend_state_matrix.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_2_plans_notes_migration.spec.js |
| plan-detail.html | 6 | browser_a3_pages.spec.js, browser_frontend_page_contract.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_plans_today_progress.spec.js |
| plans.html | 12 | browser_e2e.spec.js, browser_frontend_matrix.spec.js, browser_frontend_state_matrix.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_2_plans_notes_migration.spec.js, browser_p1_4_c2_explainability.spec.js, browser_p1_4_c4_2_source_links.spec.js, browser_p1_4_plan_status_race.spec.js, browser_plans_today_progress.spec.js |
| practice-result.html | 6 | browser_a3_pages.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_4_c4_cram.spec.js, browser_practice_workflow.spec.js |
| practice-session.html | 5 | browser_a3_pages.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_practice_workflow.spec.js |
| practice.html | 9 | browser_e2e.spec.js, browser_frontend_matrix.spec.js, browser_frontend_state_matrix.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_4_c4_cram.spec.js, browser_practice_recommendations.spec.js |
| qa.html | 12 | browser_e2e.spec.js, browser_frontend_page_contract.spec.js, browser_frontend_shared_layer.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_1_material_qa_migration.spec.js, browser_p1_4_real_input_restart.spec.js, browser_static_core.spec.js, browser_static_operations.spec.js, browser_static_pages.spec.js |
| reports.html | 5 | browser_a3_pages.spec.js, browser_b3_report_c5.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js |
| review.html | 6 | browser_a3_pages.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_3_cards_exercises_review_migration.spec.js, browser_practice_workflow.spec.js |
| settings-provider.html | 6 | browser_a4.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_system_matrix.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_5_configuration_security.spec.js |
| settings.html | 5 | browser_a3_pages.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_5_configuration_security.spec.js |
| tasks.html | 7 | browser_a4.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_system_matrix.spec.js, browser_frontend_visual_matrix.spec.js, browser_migration.spec.js, browser_p1_4_c4_3_task_list.spec.js, browser_p1_4_c4_5_measurement.spec.js |
| today.html | 10 | browser_e2e.spec.js, browser_frontend_static_baseline.spec.js, browser_frontend_visual_matrix.spec.js, browser_learning_pages.spec.js, browser_migration.spec.js, browser_p1_4_c2_explainability.spec.js, browser_p1_4_c4_4_weekly_trend.spec.js, browser_plans_today_progress.spec.js, browser_static_core.spec.js, browser_static_pages.spec.js |

## 6. 未被任何 spec 引用的页面

无。所有页面至少被一个 spec 引用。

## 7. 未引用 `/app/*.html` 的 spec

这些 spec 只测 API、契约、治理规则或旧 `/legacy` 入口，不访问正式页面。

| spec | 仅测 /legacy |
|---|---|
| browser_file_import.spec.js | 是 |
| browser_folder_import.spec.js | 是 |
| browser_frontend_failure_contract.spec.js | 是 |
| browser_material_export.spec.js | 是 |
| browser_material_management.spec.js | 是 |
| browser_material_pagination.spec.js | 是 |
| browser_material_recycle_bin.spec.js | 是 |
| browser_material_search.spec.js | 是 |
| browser_multi_file_import.spec.js | 是 |
| browser_p6d.spec.js | 是 |
| browser_p6e.spec.js | 是 |
| browser_p6e_real_provider.spec.js | 是 |
| browser_phase7.spec.js | 是 |
| browser_phase8.spec.js | 是 |
| browser_phase9a.spec.js | 是 |
| browser_phase9b.spec.js | 是 |
| browser_phase9c.spec.js | 是 |
| browser_phase9d.spec.js | 是 |
| browser_qa.spec.js | 是 |

## 8. 后端路由覆盖分类

- 去重路由路径：137
- `direct`（页面/共享模块出现字面调用）：99
- `dynamic`（页面用变量拼最后一段，静态扫描无法判定具体动作）：11
- `unreached`（未找到任何前端引用）：27

`dynamic` 不是结论，只是静态扫描的不确定项；`unreached` 也不等于能力缺失，部分是 `/legacy` 专用、运维/探活端点或按安全边界有意不暂开。逐项定性属于第二阶段设计合同。

| 后端模块 | dynamic | unreached | 路由 |
|---|---:|---:|---|
| `ai_indexing.py` | 0 | 1 | `POST /api/materials/{material_id}/ai-index/tasks` — unreached |
| `ai_retrieval_qa.py` | 0 | 3 | `POST /api/citation/validate` — unreached<br>`POST /api/context/assemble` — unreached<br>`POST /api/retrieval` — unreached |
| `materials_detail.py` | 0 | 1 | `POST /api/materials/{material_id}/purge` — unreached |
| `study_capture_reports.py` | 0 | 4 | `GET /api/study/reports/{report_id}/delivery-attempts` — unreached<br>`GET /api/study/reports/{report_id}/preview` — unreached<br>`POST /api/study/capture-sessions/{capture_id}/archive` — unreached<br>`POST /api/study/reports/{report_id}/delivery` — unreached |
| `study_learning.py` | 0 | 4 | `GET /api/study/decks/{deck_id}` — unreached<br>`GET /api/study/exercise-sets/{set_id}` — unreached<br>`GET /api/study/exercises/{exercise_id}/attempts` — unreached<br>`POST /api/study/exercises/{exercise_id}/attempts` — unreached |
| `study_notes.py` | 5 | 4 | `POST /api/study/notes/{note_id}/archive` — dynamic<br>`POST /api/study/notes/{note_id}/blocks` — dynamic<br>`POST /api/study/notes/{note_id}/confirm` — dynamic<br>`POST /api/study/notes/{note_id}/reject` — dynamic<br>`PUT /api/study/notes/{note_id}/blocks` — dynamic<br>`DELETE /api/study/notes/{note_id}/blocks/{block_id}` — unreached<br>`DELETE /api/study/notes/{note_id}/blocks/{block_id}/sources/{link_id}` — unreached<br>`PATCH /api/study/notes/{note_id}/blocks/{block_id}` — unreached<br>`POST /api/study/notes/{note_id}/blocks/{block_id}/sources` — unreached |
| `study_plans.py` | 4 | 7 | `POST /api/study/plans/{plan_id}/activate` — dynamic<br>`POST /api/study/plans/{plan_id}/complete` — dynamic<br>`POST /api/study/plans/{plan_id}/confirm` — dynamic<br>`POST /api/study/plans/{plan_id}/pause` — dynamic<br>`DELETE /api/study/plans/{plan_id}/dependencies/{dependency_id}` — unreached<br>`GET /api/study/goals/{goal_id}` — unreached<br>`GET /api/study/modules/{module_id}` — unreached<br>`PATCH /api/study/goals/{goal_id}` — unreached<br>`PATCH /api/study/modules/{module_id}` — unreached<br>`POST /api/study/goals/{goal_id}/archive` — unreached<br>`POST /api/study/modules/{module_id}/archive` — unreached |
| `study_practice.py` | 3 | 3 | `POST /api/study/cram-goals/{goal_id}/active` — dynamic<br>`POST /api/study/cram-goals/{goal_id}/archived` — dynamic<br>`POST /api/study/cram-goals/{goal_id}/completed` — dynamic<br>`GET /api/study/cram-goals/{goal_id}` — unreached<br>`GET /api/study/weak-points` — unreached<br>`POST /api/study/practice-sessions/{session_id}/archive` — unreached |
| `study_rhythm.py` | 0 | 1 | `GET /api/study/plans/{plan_id}/rhythm/export` — unreached |
| `system.py` | 0 | 3 | `GET /api/health` — unreached<br>`GET /api/liveness` — unreached<br>`GET /api/metrics` — unreached |

