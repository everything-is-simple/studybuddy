# 前端事实盘点报告（第一阶段）

> 更新：2026-09-05
> 范围：`backend/app/static/` 下 21 个 HTML 页面、6 个共享资源、53 个 `browser*.spec.js`、`backend/app/api/*.py` 的 165 条 `/api/*` 路由声明。
> 数据来源：`backend/scripts/scan-frontend-inventory.py`（只读扫描）+ `backend/scripts/audit-frontend-contract.py` + `npx playwright test --list`。
> 逐页/逐端点明细见自动产物 [`frontend-inventory-scan.md`](frontend-inventory-scan.md) 与 `frontend-inventory-scan.json`；本文只记结论与判断。

## 为什么要做这次盘点

之前的前端推进方式是一页一页孤立改动，缺少页面之间的场景合同。`docs/frontend-plan.md` 描述的是**目标设计**，不是**当前实现快照**，两者差异从未被记录，于是每次改动都要重新猜测既有事实。本次盘点只做一件事：把"前端现在到底是什么样"变成可核对的数据，作为第二阶段设计合同的输入。

盘点是只读的，不改变任何行为。唯一附带的代码改动是 `today.html` 补齐失败重试入口（见第 6 节），因为它是盘点过程中暴露的真实用户可见缺陷。

## 1. 结论摘要

已核实的事实：

- **共享层已经统一，不需要重构。** 20 个正式页面全部引用 `css/tokens.css` + `css/app.css` + `js/api.js` + `js/state.js` + `js/shell.js`（`practice.html` 额外引用 `js/cram.js`）。**0 个页面有内联 `<style>`，0 处绕过 `sbApi` 的直接 `fetch`，20 个页面都调用 `sbApi.setPageScope(...)`。** 唯一的 `fetch(` 出现在 `js/api.js` 内部实现里。
- **`index.html` 是空的兼容跳转页**，不引用任何共享资源，只有一段跳转脚本，符合设计。
- **内联脚本总量 167.8 KiB，分布在 20 个页面**，每页恰好 1 个 `<script>` 块。共享资源合计 36.5 KiB。最大的内联块是 `plans.html`（19.5 KiB）、`capture.html`（13.6 KiB）、`exercises.html`（11.1 KiB）。相较第一阶段的 162.3 KiB，增长来自场景 1 的进度历史和可操作空态；模块化仍是第三阶段对象。
- **契约审计 0 发现项**：`audit-frontend-contract.py --strict` 退出码 0，覆盖 21 页面 / 168 后端路由，无 `missing_route`、`direct_fetch`、`legacy_field`、`json_without_content_type`、`missing_request_scope`、`write_without_retry_signal`、`undefined_css_token`。
- **测试总量 177 个 browser test，分布在 53 个 spec**。其中 **19 个 spec（56 个 test）只访问旧 `/legacy` 入口**，不触碰任何 `/app` 页面。
- **21 个页面全部至少被 1 个 spec 引用**，覆盖数从 `index.html` 的 1 个到 `materials.html` 的 14 个。
- 后端 137 条去重 `/api/*` 路由路径中，**99 条**被前端字面调用（`direct`），**11 条**因页面用变量拼接末段而无法静态判定（`dynamic`），**27 条**未找到任何前端引用（`unreached`）。场景 1 新增明确的进度历史读取后，前端去重调用端点由 102 增至 103。

## 2. 页面分组与实现状态

21 个页面按用户场景归为 7 组。"实现状态"只依据代码事实：页面是否有真实 API 调用与渲染逻辑，不评价 UI 完成度。

| 组 | 页面 | 内联脚本 | API 数 | 覆盖 spec | 状态 |
|---|---|---:|---:|---:|---|
| 入口 | `index.html` | 0.0 KiB | 0 | 1 | 跳转页 |
| 今天 | `today.html` | 8.2 KiB | 6 | 10 | 有实现 |
| 计划 | `plans.html` | 19.5 KiB | 21 | 12 | 有实现 |
| 计划 | `plan-detail.html` | 7.5 KiB | 3 | 5 | 有实现 |
| 资料 | `materials.html` | 10.2 KiB | 6 | 14 | 有实现 |
| 资料 | `material-detail.html` | 6.3 KiB | 5 | 10 | 有实现 |
| 问答 | `qa.html` | 6.2 KiB | 5 | 12 | 有实现 |
| 笔记 | `notes.html` | 8.4 KiB | 8 | 8 | 有实现 |
| 笔记 | `note-detail.html` | 2.6 KiB | 1 | 4 | 只读详情 |
| 学习资产 | `cards.html` | 9.6 KiB | 9 | 8 | 有实现 |
| 学习资产 | `exercises.html` | 11.1 KiB | 8 | 8 | 有实现 |
| 练习 | `practice.html` | 10.6 KiB | 6 | 9 | 有实现 |
| 练习 | `practice-session.html` | 6.1 KiB | 4 | 5 | 有实现 |
| 练习 | `practice-result.html` | 1.9 KiB | 2 | 6 | 只读结果 |
| 复盘 | `review.html` | 6.8 KiB | 7 | 6 | 有实现 |
| 课堂 | `capture.html` | 13.6 KiB | 8 | 8 | 有实现 |
| 课堂 | `classroom.html` | 9.2 KiB | 6 | 6 | 有实现 |
| 报告 | `reports.html` | 3.5 KiB | 3 | 5 | 有实现 |
| 系统 | `tasks.html` | 6.8 KiB | 4 | 7 | 有实现 |
| 系统 | `settings.html` | 9.5 KiB | 4 | 5 | 有实现 |
| 系统 | `settings-provider.html` | 10.2 KiB | 5 | 6 | 有实现 |

没有占位页。`note-detail.html`（1 个 API）与 `practice-result.html`（2 个 API）数字偏低是因为它们是只读详情页，不是未完成。

## 3. 共享层事实

| 资源 | 体积 | 内容 |
|---|---:|---|
| `js/api.js` | 6.7 KiB | `sbApi`（`json`/`upload`/`download`/`scope`/`setPageScope`/`cancel`/`cancelAll`/`safeError`）、`sbSubmit.once`、`sbUi.status`/`sbUi.busy` |
| `js/cram.js` | 7.9 KiB | 冲刺复习专用逻辑，仅 `practice.html` 引用 |
| `js/state.js` | 1.9 KiB | `sbState`：状态中文标签表、`sourceForItem`/`materialForItem`/`linksForItem`、HTML 转义 |
| `js/shell.js` | 1.7 KiB | 15 项共享导航注入、窄屏"更多"折叠、`/api/readiness` 状态点、`pagehide` 时 `cancelAll` |
| `css/app.css` | 17.5 KiB | 组件与布局 |
| `css/tokens.css` | 0.9 KiB | 设计 token |

`sbApi` 已覆盖第二阶段需要的全部机制：非 GET 自动 `Idempotency-Key`、统一 `Accept: application/json`、页面级 `AbortController` scope、Request ID 追踪、以及把错误码映射成中文安全文案的 `safeError`（约 60 个错误码，未命中时回落到"请求失败，请重试"，不泄露 detail 原文）。**结论：`api.js` 不需要重构，第二阶段直接以它为 API 契约的事实来源。**

已有的交互基础同样可直接沿用，不需要新造：`sbSubmit.once(key, fn)` 防重复提交、`sbUi.status(el, state, msg)` 统一 `role=alert/status` 与 `aria-live`、`sbUi.busy(button, busy, label)` 按钮忙态。

### 导航覆盖缺口

`shell.js` 的共享导航只有 15 个链接。5 个详情页不在导航中：`material-detail`、`plan-detail`、`note-detail`、`practice-session`、`practice-result`。这是合理的（详情页需要 ID 参数，不能从导航直达），但意味着**这些页面完全依赖上游页面的入口链接**。当前静态出口链接：

| 页面 | HTML 中写死的 `/app/*.html` 出口 |
|---|---|
| `settings.html` | `capture.html`, `settings-provider.html`, `tasks.html`, `today.html` |
| `practice-result.html` | `practice.html`, `review.html`, `today.html` |
| `material-detail.html` | `materials.html`, `qa.html`, `today.html` |
| `exercises.html` / `practice.html` / `review.html` / `qa.html` / `plans.html` / `materials.html` / `notes.html` / `note-detail.html` / `plan-detail.html` / `practice-session.html` / `reports.html` | 各 1–2 个 + `today.html` |
| `today.html` | `plans.html`；任务卡的“查看资料”/“开始学习”和空态出口由 JS 动态生成 |

这是第二阶段"场景流程图"必须明确的部分：详情页的进入与返回路径属于场景合同，不能只靠约定。

## 4. 测试覆盖事实

177 个 test / 53 个 spec。**最大发现：19 个 spec（56 个 test，占 31.6%）只测 `/legacy`，完全不访问 `/app` 正式页面。**

| spec | test 数 |
|---|---:|
| `browser_qa.spec.js` | 10 |
| `browser_frontend_failure_contract.spec.js` | 6 |
| `browser_phase9d.spec.js` | 5 |
| `browser_p6e.spec.js` | 4 |
| `browser_material_recycle_bin.spec.js` / `browser_phase8.spec.js` / `browser_phase9a.spec.js` / `browser_phase9b.spec.js` / `browser_phase9c.spec.js` | 各 3 |
| `browser_material_export.spec.js` / `browser_material_management.spec.js` / `browser_material_search.spec.js` / `browser_p6d.spec.js` / `browser_p6e_real_provider.spec.js` / `browser_phase7.spec.js` | 各 2 |
| `browser_file_import.spec.js` / `browser_folder_import.spec.js` / `browser_material_pagination.spec.js` / `browser_multi_file_import.spec.js` | 各 1 |

这不是"测试失败"，这些 test 全部通过。问题在于**它们验证的是旧入口的行为，不能证明正式页面的等价能力**。其中集中在两个关键域：

- **资料导入/搜索/分页/回收站/导出**（8 个 spec，13 个 test）——正式页面 `materials.html` 确实有对应 UI（`选择文件夹导入`、`应用筛选`、`查看回收站`、3 个 ZIP 导出按钮），但覆盖它们的证据仍在 `/legacy`。
- **问答**（`browser_qa.spec.js`，10 个 test）——`qa.html` 有 `索引当前材料` / `提交问题`，`browser_static_core.spec.js` 与 `browser_p1_1_material_qa_migration.spec.js` 提供了正式页面证据，但 10 个细分 case 仍只在 `/legacy` 上跑。

同时需要更正一处过时表述：`docs/frontend-static-capability-matrix.md` 里已无 `legacy_only` 条目（仅 `capture.html` 的归档项为 `not_exposed`），说明 ROADMAP 中"剩余 legacy_only 待迁移"的说法已不准确 —— **能力已在正式页面暴露，缺的是把证据从 `/legacy` 迁到 `/app`。** 这是第三阶段的工作项，不是能力缺失。

## 5. 后端路由覆盖分类

137 条去重路由路径：`direct` 99 / `dynamic` 11 / `unreached` 27。

`dynamic` 是扫描器的不确定项而非缺口。例如 `plans.html` 写成 `'/api/study/plans/' + id + '/' + action`，静态扫描只能得到 `/api/study/plans/{id}/{id}`，于是 `confirm`/`activate`/`pause`/`complete` 四个状态迁移都落入 `dynamic`。同类情况还有 `notes.html` 的 `confirm`/`reject`/`archive`/`blocks` 与 `practice.html` 的 cram 目标状态迁移。

27 条 `unreached` 需要在第二阶段逐项定性，初步分组：

| 分组 | 条数 | 例子 | 初判 |
|---|---:|---|---|
| 运维/探活 | 3 | `GET /api/health`、`/api/liveness`、`/api/metrics` | 有意不进 UI |
| 检索内部管道 | 3 | `POST /api/retrieval`、`/api/context/assemble`、`/api/citation/validate` | 被问答链路间接使用，不是页面直调 |
| 笔记块级编辑 | 4 | `PATCH/POST/DELETE .../blocks/{block_id}` 及其 `sources` | 有意收敛到 `PUT .../blocks` 整体提交，不维护第二套编辑语义 |
| 计划目标/模块管理 | 7 | `GET/PATCH /api/study/goals/{id}`、`/modules/{id}`、`/archive`、依赖删除 | 目标/模块查看、重命名、归档及依赖删除为正式页缺口 |
| 学习资产读取 | 4 | `GET /api/study/decks/{id}`、`/exercise-sets/{id}`、`/exercises/{id}/attempts` 与 `POST .../attempts` | 详情读取推迟；exercise attempts 为场景 3 缺口 |
| 报告交付与预览 | 4 | `/reports/{id}/preview`、`/delivery`、`/delivery-attempts`、`capture-sessions/{id}/archive` | `report_delivery` 默认关闭属安全边界 |
| 其他 | 2 | `GET /api/study/weak-points`、`POST /api/materials/{id}/purge` | 需确认 |

## 6. 盘点期间修复的真实缺陷：`today.html` 缺失失败重试

`audit-frontend-contract.py` 之前对 `today.html` 报告"retry 信号 = 否"且不算发现项，因为它的规则是"有写操作才要求重试入口"。`today.html` 是只读页，规则放过了它 —— 但这掩盖了一个真实的用户可见缺陷：**任一区块加载失败时，页面只显示错误文案，用户除了手动刷新浏览器没有任何恢复入口。**

已修复：

- 新增 `#retry-today`「重新加载」按钮，默认隐藏，任一区块失败时出现，成功恢复后隐藏。
- 三个区块（今日概览 / 近七天趋势 / 今日任务）原先各自独立请求 `/api/study/plans` 来找 active plan，同一次加载重复请求 3 次。改为**每次加载共享一次查询**，重试时重置。
- 重试使用 `sbSubmit.once('today-reload', ...)` 防重复点击，按钮忙态走 `sbUi.busy`，并用 `loadGeneration` 世代号丢弃过期响应。
- 加载/空/失败三态统一走内部 `pending`/`settled`/`fail` 辅助函数，保留各 notice 原有布局类（`mt-16` 等不会被覆盖丢失）。

新增回归测试 `backend/tests/browser_plans_today_progress.spec.js` 第 3 个 test：拦截 `/api/study/plans` 返回 500 且 detail 内含伪造路径 `H:/studybuddy/secret_traceback`，断言三个区块都显示安全文案「请求失败」、页面不泄露路径/traceback/SQL，然后放开拦截、点击重试，断言任务卡、概览、7 天趋势全部恢复且重试按钮与状态提示都隐藏。

场景 1 继续补齐后，该 spec 现为 6 passed：除原失败重试外，还覆盖进度历史读取/倒序/刷新、单独 history 失败恢复，以及“完全无计划 / 计划未激活 / active 但今日无 allocation”三类可操作空态。`audit-frontend-contract.py` 中 `today.html` 的 retry 信号已由「否」转为「是」。

## 7. 判定：第一阶段完成

进入第二阶段的前置条件已满足：

- [x] 21 个页面的资源引用、内联脚本体积、API 调用已逐页扫描并落盘为可复算数据
- [x] 共享层统一性已核实（0 内联 style、0 直接 fetch、20/20 页面有请求 scope）
- [x] 53 个 spec 的页面引用关系已建立，19 个 `/legacy` 专用 spec 已点名
- [x] 后端 137 条路由路径已按 `direct`/`dynamic`/`unreached` 分类
- [x] 与 `frontend-plan.md` 的定位差异已记录（目标设计 vs 实现快照）
- [x] 盘点脚本可重复执行，结论不依赖人工记忆

明确**不阻塞**第二阶段、推迟到第三阶段的两项：

1. **内联脚本模块化**（当前 167.8 KiB / 20 页；第一阶段基线 162.3 KiB）—— 先出设计合同再改代码，否则会按当前形状而非目标形状拆分。
2. **`/legacy` 证据迁移**（19 spec / 56 test）—— 需要先有场景合同定义"正式页面上等价的成功路径"，才能正确重写这些 test。

理由：共享层已统一，信息已足够支撑设计。不完美的盘点加完整的设计，胜过完美的盘点加没有设计。

## 8. 第二阶段输入

按场景而非按页面设计。每个场景闭环产出：流程图 → 页面状态机 → 元素行为表 → API 契约对照。

场景优先级：

1. **计划 → 今天 → 进度**（已实现并作为完整模板）。已覆盖无计划、计划未激活、当天无 allocation、allocation 过期不进入 Today、来源失效、加载失败重试、进度历史和刷新后状态恢复；合同见 [`contracts/frontend-scenario-contract.md`](contracts/frontend-scenario-contract.md)。
2. **材料导入 → 解析 → 索引 → 问答（带引用）**（核心链路，且 `/legacy` 证据集中在此）。
3. **练习会话 → 结果 → 错题复盘**（已有 `browser_practice_workflow.spec.js` 与 workflow 合同文档可依据）。

复算命令：

```bash
C:/miniconda/py310/python.exe backend/scripts/scan-frontend-inventory.py
C:/miniconda/py310/python.exe backend/scripts/audit-frontend-contract.py --strict
C:/miniconda/py310/python.exe backend/scripts/check-source-size.py
npx playwright test backend/tests --list
```
