# 21 页 A/B 审查权威总表（独立复核结项版）

> 定稿：2026-09-15 · 独立复核者（Prompt 3，新上下文）核对实际 spec 文件存在性与用例数后填写，未照抄文档。
> 基线 commit：`8ad2d4a`（capture/classroom 收口）；收尾改动（B-SET-5/6/7 根因修复、`browser_index_redirect_userpath.spec.js` 新增、material_search/recycle_bin 生命周期修复）**未提交**，仅落在工作区。
> 范围口径：仅页面 A/B 审查。真实 Provider、真实 OCR/ASR、live delivery、跨浏览器、系统级屏幕阅读器、全局生产 real-pass 不在本表范围内，列为各页 `not_verified` 项。
> A 类 = 纯用户路径（页面 UI 操作、断言用户可见结果，无 `page.request` 业务播种）；B 类 = 契约/故障注入/竞态/隐私边界（route 注入或只读 `page.request` 观察，均显式标注）。
> 「兼容跳转页边界通过」是 index.html 在其跳转页口径下的终态，不伪称完整业务 E2E。

<!-- STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->
## 统一执行协议（2026-09-27）

本文件与 `H:\studybuddy\docs\[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 使用同一套执行口径。本文档中早于 2026-09-27 的报告、表格和历史标签保留其原始事实；历史标签只能在原日期、原范围和原证据路径下解释，不能升级为当前全局结论。

### 可执行 Prompt 的必填字段
- **角色**：本次执行者的职责。
- **唯一目标**：一个可判定的结果，不把多个目标合并成“全部处理”。
- **当前阶段**：只能填写 `P0`（边界确认）、`P1`（真实状态读取）、`P2`（真实操作执行）、`P3`（证据核对）、`P4`（交付与结论）之一，并按顺序推进。
- **允许读取/写入**：逐项列出绝对路径、URL、端点、数据根和输入；未列出的对象禁止访问或修改。
- **指定工具/命令/端口/输入**：必须原样执行；对象不可用时返回 `BLOCKED`，不得替换。
- **禁止操作、停止条件和证据路径**：逐项写明；每个结论必须有实际命令/动作、结果和绝对证据路径。

### 统一状态与范围
`PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED` 是本项目当前统一结果状态。`implemented`、`configured`、`available`、测试通过、隔离环境通过只能描述实现或可见性，不能单独写成 `real-pass`。`real-pass` 只能表示本次指定真实目标、真实路径、真实输入和真实动作均有证据；未覆盖范围必须写 `NOT_VERIFIED`。

### 统一路径和运行基线
源码 `H:\studybuddy`；正式数据 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读）；组件测试 `H:\studybuddy-composer`；组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/today.html`。

正式启动命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`。隔离验证命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。不得把 `python -m backend.app serve`、其他端口、其他数据根或其他浏览器替换到已指定任务中。

### 强制禁止
不得凭推测输出；不得用 HTML 解析、按钮清单、curl/API 请求、静态检查或 headless 结果冒充可视浏览器点击；不得读取、复制、提交或展示密钥、Token、Cookie、真实教材正文、Provider 原始响应、SQL 或完整 traceback；不得在未授权时调用真实 Provider/OCR/ASR、发送 Email/飞书或扩大文件范围。工具、路径、页面、服务状态或证据不满足前置条件时，立即停止并报告 `BLOCKED`。

<!-- /STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->

| # | 页面 | 状态 | A 类 spec + 用例数 | B 类 spec + 用例数 | 收口轮次 / commit | not_verified 项 |
|---|---|---|---|---|---|---|
| 1 | today.html | e2e-real-pass（限定范围） | `browser_today_userpath.spec.js` (7) + `browser_plans_today_progress.spec.js` (6) + `browser_a3_pages.spec.js`/`browser_e2e.spec.js` | `browser_frontend_page_contract.spec.js`（today 区，部分）+ `browser_frontend_state_matrix.spec.js` | 09-10 二审 | 真实 Provider、跨浏览器、屏幕阅读器 |
| 2 | qa.html | e2e-real-pass（限定范围） | `browser_qa_userpath.spec.js` (9) + `browser_qa.spec.js` (10) + `browser_p2_fe3_qa_app.spec.js` (5) + `browser_p2_fe3_qa_p6c_app.spec.js` (2) + `browser_p2_fe3_qa_threads_errors_app.spec.js` (3) | `browser_qa.spec.js` 内含 rate-limit/unavailable 安全映射（A 类含 B 要素），无独立 B 类文件 | 09-10 二审 | 真实 Provider |
| 3 | practice.html | e2e-real-pass（限定范围） | `browser_practice_userpath.spec.js` (7) + `browser_practice_workflow.spec.js` (7) + `browser_p2_fe3_practice_session_app.spec.js` (4) | `browser_practice_workflow.spec.js` 含错误/过期响应安全（A 类含 B 要素） | 09-10 二审 | 真实 Provider |
| 4 | practice-session.html | e2e-real-pass（限定范围） | `browser_practice_userpath.spec.js`（PRAC 含会话）+ `browser_practice_workflow.spec.js` (7) + `browser_p2_fe3_practice_session_app.spec.js` (4) | 同上 | 09-10 二审 | 真实 Provider |
| 5 | practice-result.html | e2e-real-pass（限定范围） | `browser_exercises_practice_result_userpath.spec.js` (8) + `browser_p2_fe3_practice_result_app.spec.js` (4) + `browser_practice_workflow.spec.js` | 同上 | 09-10 二审 | 真实 Provider |
| 6 | exercises.html | e2e-real-pass（限定范围） | `browser_exercises_practice_result_userpath.spec.js` (8) + `browser_a3_pages.spec.js` + `browser_learning_pages.spec.js` | `browser_exercises_practice_result_userpath.spec.js` 含 EXR-7 故障补充 | 09-10 二审 | 真实 Provider |
| 7 | notes.html | e2e-real-pass（限定范围） | `browser_notes_userpath.spec.js` (9) | `browser_notes_b_class.spec.js` (10) | 09-11 A+B 审 | 真实 Provider、JSON 导出 UI、系统级屏幕阅读器 |
| 8 | note-detail.html | e2e-real-pass（限定范围） | `browser_notes_userpath.spec.js`（ND 含 note-detail） | `browser_notes_b_class.spec.js`（notes/note-detail 接口契约） | 09-11 A+B 审 | 同上 |
| 9 | cards.html | e2e-real-pass（限定范围） | `browser_cards_userpath.spec.js` (8) | XSS 纯文本在 A 类 CARD-2/6 覆盖；无独立 B 类文件 | 09-11 二轮收口 (f95c9de) | 真实 Provider |
| 10 | materials.html | e2e-real-pass（限定范围） | `browser_material_management.spec.js` (10) + `browser_material_search.spec.js` (2) + `browser_material_pagination.spec.js` (1) + `browser_material_recycle_bin.spec.js` (3) + `browser_material_export.spec.js` (2) + `browser_p2_fe3_materials_app.spec.js` (4) + `browser_p2_fe3_materials_management_app.spec.js` (5) + `browser_static_core.spec.js` + `browser_static_operations.spec.js` + `browser_a4.spec.js` | `browser_materials_b_class.spec.js` (4) | 09-13 materials/plans B 审 | 真实 OCR/ASR、跨浏览器 |
| 11 | material-detail.html | e2e-real-pass（限定范围） | `browser_material_detail_userpath.spec.js` (7) | 无独立 B 类；故障/边界在 A 类 MD-6/7 覆盖 | 09-13 同上 | 真实 OCR 质量 |
| 12 | plans.html | e2e-real-pass（限定范围） | `browser_plans_plan_detail_userpath.spec.js` (5) + `browser_plans_today_progress.spec.js` (6) + `browser_p1_2_plans_notes_migration.spec.js` (3) + `browser_p2_fe_b3_templates.spec.js` (2) | `browser_plans_b_class.spec.js` (4) | 09-13 同上（b39bba8 URL plan_id 怪癖修复） | 真实 Provider |
| 13 | plan-detail.html | e2e-real-pass（限定范围） | `browser_plans_plan_detail_userpath.spec.js` (5) + `browser_plans_plan_detail_full.spec.js` (24, B-assisted) | `browser_plans_b_class.spec.js` (4，含 plan-detail) | 09-13 同上 | 真实 Provider |
| 14 | reports.html | e2e-real-pass（限定范围） | `browser_reports_userpath.spec.js` (14) + `browser_b3_report_c5.spec.js` (2) + `browser_p2_fe4_report_preview_app.spec.js` (2) | `browser_reports_b_class.spec.js` (3) | 09-12 A+B 审 | live delivery、真实 Provider |
| 15 | review.html | e2e-real-pass（限定范围） | `browser_review_userpath.spec.js` (12) + `browser_p2_fe3_review_app.spec.js` (5) + `browser_p1_3_cards_exercises_review_migration.spec.js` (1) | `browser_review_b_class.spec.js` (5) | 09-13 A+B 审 | 真实 Provider |
| 16 | settings.html | e2e-real-pass（限定范围） | `browser_settings_userpath.spec.js` (12) | `browser_settings_b_class.spec.js` (17；B-SET-1..15，含 B-SET-5/6/7 根因已修) | 09-13 A+B 审 + 09-15 B-SET-5 根因修复 | 真实第三方 Provider |
| 17 | settings-provider.html | e2e-real-pass（限定范围） | `browser_settings_userpath.spec.js`（SET-2 覆盖 settings-provider 首状态） | `browser_settings_b_class.spec.js`（B-SET-3/4/7/9b/11/12 覆盖 provider/email 连接测试与凭据隔离） | 09-13 A+B 审 + 09-15 | 真实 Provider/SMTP/Feishu 外发 |
| 18 | capture.html | e2e-real-pass（限定范围） | `browser_capture_classroom_userpath.spec.js` (12；含 CAP-8/12 route 故障注入 B 类要素) | `browser_capture_classroom_b_class.spec.js` (15；B-CAP-1..15) | 09-14 A+B 审 | 真实 ASR/OCR 转写质量 |
| 19 | classroom.html | e2e-real-pass（限定范围） | `browser_capture_classroom_userpath.spec.js` (12，两页共用) | `browser_capture_classroom_b_class.spec.js` (15，两页共用) | 09-14 A+B 审 | 真实 ASR/OCR 转写质量 |
| 20 | tasks.html | e2e-real-pass（限定范围）【由 scoped browser-pass 升级】 | `browser_tasks_userpath.spec.js` (7) + `browser_p1_4_c4_3_task_list.spec.js` (1) | `browser_tasks_b_class.spec.js` (7) | 09-13 A+B 审 + 09-15 升级判据四项全满足 | 真实 embedding Provider 长时稳定性（TK-5 仅用 loopback 合成） |
| 21 | index.html | 兼容跳转页边界通过（限定范围） | `browser_index_redirect_userpath.spec.js` (6；纯 A 类 4：IDX-1/2/4/5) + `browser_migration.spec.js`（根路由重定向) | 无独立 B 类 spec；IDX-3/6 以 `page.request` 读静态源码断言（B 类要素，注释明确不计入纯 A 通过） | 09-15 Prompt1 任务 B | 跨浏览器、屏幕阅读器；真实业务链路不适用（页面无业务面） |

## 共用 spec 覆盖关系说明

- `browser_capture_classroom_userpath.spec.js` / `browser_capture_classroom_b_class.spec.js`：capture.html 与 classroom.html 共用同一对 A/B spec（CAP-1..12 / B-CAP-1..15），两页均在本对 spec 内被独立断言，非「互相代审」。
- `browser_notes_userpath.spec.js` / `browser_notes_b_class.spec.js`：notes.html 与 note-detail.html 共用。
- `browser_plans_plan_detail_userpath.spec.js` / `browser_plans_plan_detail_full.spec.js` / `browser_plans_b_class.spec.js`：plans.html 与 plan-detail.html 共用；`plan_detail_full` 标 `B-class API-assisted`（部分用例经 API 建数据以覆盖全链路，已显式标注）。
- `browser_settings_userpath.spec.js` / `browser_settings_b_class.spec.js`：settings.html 与 settings-provider.html 共用，SET-2 / B-SET-3/4/7/9b/11/12 明确覆盖 settings-provider。
- `browser_exercises_practice_result_userpath.spec.js`：exercises.html 与 practice-result.html 共用。
- `browser_practice_userpath.spec.js` / `browser_practice_workflow.spec.js`：practice / practice-session / practice-result 共用。
- `browser_qa_userpath.spec.js` / `browser_qa.spec.js`：qa.html 主审；`browser_material_detail_userpath.spec.js` 的 QA 入口用例也覆盖 qa.html。
- 无独立 B 类 spec 的页面（qa / practice* / cards / material-detail / index）：其 B 类要素（route 故障注入、XSS 纯文本、迟到响应竞态、隐私边界）已写入对应的 A 类 spec 内并显式标注为「含 B 类要素」，不伪称纯 A 全绿。

## 独立复核结果摘要（见 STATUS / TODO 顶部独立复核条目）

- 21 个正式页面全部存在（`backend/app/static/*.html` 精确 21 个），无遗漏/误计。
- 21 页均具备 A + B 覆盖映射；每页至少一条 A 类用户路径与一条 B 类契约/故障/竞态证据（index 按跳转页口径）。
- 完整 Chromium 分组串行（g1–g4，2026-09-15 143500）：**431 passed / 4 skipped / 1 failed**，唯一失败为 `browser_phase9b.spec.js`（/legacy 工作区集成 spec，**非 21 正式页面**），已如实标注、未宣称全绿。
- 后端全量：**631 passed / 3 skipped**（EXIT 0）。focused `-k task` 独立复跑：**24 passed**（EXIT 0）。
- 门禁：`check-source-size.py --base HEAD` 通过；`audit-frontend-contract.py --strict` **0 findings**；`git diff --check` 对 `backend/app/` 干净（生产代码工作区零 diff）。
- 高风险 8 页（settings/settings-provider/tasks/capture/classroom/reports/review/index）A/B spec 独立复跑：capture+classroom 通过；index（6 passed）、reports（14 passed）隔离复跑通过（批跑中因 9 个重 spec 同 `npx` 引发的浏览器会话不稳属 harness 伪失败，非产品缺陷）。
- B-SET-5 根因已真修：以等待路由 `fulfill` 确定性事件替代 2600ms 固定等待对 2500ms 路由延迟的 100ms 余量猜测；B-SET-6 vacuous 测试已重写到 settings.html 真实竞态路径。
- 双标签已清零：tasks.html 终态唯一 = `e2e-real-pass`；index.html 终态唯一 = 兼容跳转页边界通过；无任何页面并存 `not_verified` 页面级标签。

## 已知小缺口（如实记录，不阻塞 21/21 A/B 审查结论）

1. **phase9b 隔离复跑用例数未落盘**：`review-phase9b-iso-1/2/.../.last-run.json` 仅记录 `status=passed` 与 `failedTests=[]`，无 passed 计数，「3 passed」无法从产物独立核实。属记录缺口，非产品缺陷；该 spec 不在 21 页 A/B 范围内。
2. **focused `-k task 24 passed` 原无独立日志**：本次独立复跑已得 24 passed（EXIT 0），缺口已补。
3. **Prompt 2 以「分组串行」代替单次连续运行**：已如实标注；唯一失败 `browser_phase9b.spec.js` 在 21 正式页面范围之外且未宣称全绿。独立判断：**该偏差可接受**——失败局限于非页面 A/B 集成 spec，不影响任何一页的 A/B 终态，且偏差被透明标注。
4. **`browser_phase9b.spec.js:105` 在 g3 失败（EXIT 1）**：属 /legacy 工作区集成 spec，非 21 正式页面；其 notes 重复创建路径在专用 `browser_notes_userpath`/`browser_notes_b_class` 中独立通过。该失败标为 **not_verified**（未独立复跑/定位根因），建议另立专项排查，但不影响 21 页 A/B 审查结论。
