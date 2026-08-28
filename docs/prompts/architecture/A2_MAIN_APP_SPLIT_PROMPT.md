# A2：main.py 路由与应用工厂拆分 —— 任务 Prompt

## 一、角色与必读

你是 StudyBuddy 正式系统（`H:\studybuddy`）的编码代理。开始前必须完整阅读以下文件，并以其为约束：

- `AGENTS.md` —— 仓库规则、测试、安全与部署边界
- `docs/prompts/architecture/A0_BASELINE_AUDIT.md` —— A0 基线审计、A1 结果与拆分顺序
- `docs/prompts/architecture/A0_ROUTE_REPOSITORY_MAP.md` —— 151 条 FastAPI 路由、repository/domain map、外部调用点
- `docs/prompts/architecture/A0_STATIC_FRONTEND_CONTRACT.md` —— 当前内嵌前端契约；A2 不做 A3 静态化
- `docs/prompts/architecture/A0_REFACTOR_ROLLBACK_PLAN.md` —— A2 回退方案
- `docs/prompts/architecture/A1_REPOSITORY_SPLIT_PROMPT.md` —— A1 已执行的 repository 结构收口背景
- `docs/ARCHITECTURE.md`
- `docs/CODE_TEST_GOVERNANCE.md`
- `docs/MIGRATIONS.md`
- `docs/TODO.md`
- `docs/STATUS.md`

必须先读取实际源码：

- `backend/app/main.py`
- `backend/app/repository.py`
- `backend/app/repositories/`
- `backend/app/cli.py`
- `backend/app/recovery.py`
- `backend/app/task_runner.py`
- `backend/app/task_handlers.py`
- `backend/app/delivery.py`
- `backend/tests/` 中直接依赖 `app.main`、`create_app`、`app.main:app`、路由、HTML 或浏览器行为的测试

## 二、当前状态（A1 后已推送）

- 仓库：`H:\studybuddy`
- 远端：`https://github.com/everything-is-simple/studybuddy.git`
- 当前 HEAD：`dece274a4a2fed2f373d8ceb05025dd4ed68440d`
- 分支状态：`master` 与 `origin/master` 已同步
- A1 已完成并推送：`backend/app/repository.py` 是兼容 façade；`backend/app/repositories/` 存在 9 个域出口（connection/materials/ai/plans/learning/practice/capture/reports/tasks）和 `_legacy.py`
- A1 验证：完整 backend `413 passed, 2 skipped`；完整 browser `52 passed, 1 skipped`；repository façade 公开符号 inventory `305/305`
- A1 限制：为保留跨域私有 helper、monkeypatch、函数 identity 与事务行为，函数实现暂由 `repositories/_legacy.py` 单一载体承载；域模块是显式可审计出口，不是内部函数体完全解耦
- `backend/app/main.py` 当前约 3,183 行，仍承载 app factory、lifespan/preflight/recovery/readiness、middleware、所有 HTTP 路由、上传/下载编排、错误映射和完整内嵌 `INDEX_HTML`
- 当前 AST 路由基线为 151 条（含 `/` HTML 入口）
- 当前前端入口仍为 `GET /` 返回 `INDEX_HTML` 字符串；不存在正式 static root 或 `StaticFiles` mount

实施前仍必须重新采集实际基线，不得只信本文数字。

## 三、A2 目标

在不改任何行为的前提下，把 `backend/app/main.py` 按应用工厂、运行生命周期、schemas、错误映射、上传/导出编排和业务路由域拆分为独立模块；旧 `backend/app/main.py` 保留为兼容入口，使以下路径继续工作：

- `backend.app.main:create_app`
- `backend.app.main:app`
- `python -m app` / `python -m backend.app` 的既有 CLI 行为
- `uvicorn app.main:app`（`backend` 为 cwd）
- 现有测试、browser specs、operator scripts、task runner、delivery、recovery

A2 是后端应用结构拆分，不是功能开发，不是前端迁移。

## 四、兼容性硬约束（不可违反）

1. 不改 SQLite schema、migration 顺序/history、`PRAGMA user_version`；不新增表；不新增 runtime ad-hoc DDL。
2. 不改 API 路径、HTTP method、默认/显式成功状态码、错误状态码、`HTTPException.detail` 形状、稳定 error code、response JSON shape、下载 media type 或 filename 逻辑。
3. 不改前端行为：`GET /` 仍返回同一个内嵌 `INDEX_HTML` 内容；不创建正式 static root；不 mount `StaticFiles`；不拆 HTML/CSS/JS 到文件系统；不修改 DOM id/class/text、URL query 行为、keyboard/narrow/failure/privacy 行为。
4. 不改 repository 层行为；A2 可更新 import 来源以使用 A1 façade或域出口，但不得改 SQL、事务、返回值或 repository 函数签名。
5. 保留 `backend.app.main.create_app` 与 `backend.app.main.app` 兼容导出；外部 import 不应被迫迁移。
6. 不改启动顺序：preflight → connect/migrate/schema/index init → audit → recovery → ready。不得在 startup/read path 自动 backup、restore、repair、run task 或 provider probe。
7. 不改 middleware、correlation、observability、metrics、health/readiness/liveness 语义和安全输出。
8. 不泄露路径、SQL、traceback、provider 原始错误、secret 或正文。
9. 不夹带 A3/A4/B/D 任务：不做静态前端、不接真实 Provider 设置页、不接 ASR/OCR/report-core/live delivery、不做 Tauri。
10. 不从 Composer/Integration 项目复制实现；A2 是正式系统内的机械拆分。
11. 若发现必须通过业务 bug fix 才能拆分的阻塞问题，先暂停并向用户报告；不要夹带修复。

## 五、目标结构（建议）

最终结构可根据实际依赖微调，但必须保持清晰边界和兼容 façade。

```text
backend/app/
├── main.py                    # 兼容入口：导出 create_app、app，尽量薄
├── app_factory.py             # create_app、router/middleware/lifespan 组装
├── lifespan.py                # startup preflight、connect/audit/recovery/readiness 状态
├── http_errors.py             # provider/study/phase9d/task/material 等错误码到 HTTP 的稳定映射
├── schemas.py                 # Pydantic request models；不改变字段/default/validation 行为
├── web_ui.py                  # INDEX_HTML 常量与 index route helper；仍为内嵌字符串，不是 static root
├── api/
│   ├── __init__.py
│   ├── system.py              # liveness/metrics/health/readiness/capabilities
│   ├── materials.py           # material list/import/batch/export/detail/download/restore/purge/rename/delete
│   ├── ai.py                  # retrieval/context/citation/Q&A/sync indexing/index status
│   ├── tasks.py               # task create/status/cancel/retry where currently exposed
│   ├── study_learning.py      # decks/cards/exercise-sets/exercises/generation/attempts
│   ├── study_plans.py         # goals/modules/plans/items/dependencies/progress/source links/rhythm
│   ├── study_practice.py      # practice sessions/mistakes/weak points/cram
│   └── study_capture_reports.py # capture/transcription/reports/delivery audit
└── services/
    ├── imports.py             # upload/file validation and parser/storage transaction orchestration
    ├── exports.py             # material/text/bundle/rhythm/note/report export helpers
    └── ai_generation.py       # provider-call orchestration currently embedded in routes, if useful
```

Boundary notes:

- `web_ui.py` may hold the existing `INDEX_HTML` verbatim. It must not transform the page into static files.
- `app_factory.py` should assemble routers and retain lifespan/middleware behavior. Avoid import cycles by passing `AppConfig` or using small dependency closures.
- If router modules need shared config/database access, prefer a small explicit app-state helper or dependency function that mirrors current behavior. Do not introduce global mutable state beyond current `app.state` usage.
- Keep request model names stable where tests or docs import them from `app.main`; if moved to `schemas.py`, re-export them from `main.py` or otherwise preserve compatibility.
- Existing `backend/app/delivery.py` remains external delivery orchestration. Do not move repository delivery audit into it; A1 mapped audit persistence to `repositories/reports.py`.

## 六、拆分方法

1. **Inventory first**：生成并保存到仓库外临时目录，禁止提交：
   - current HEAD and git status
   - route inventory: method/path/name/status_code/response_class
   - `app.main` public symbol inventory and `inspect.signature(create_app)`
   - request model field/default/schema inventory
   - `HTTPException.detail`/stable error code inventory
   - download/export media type and filename inventory
   - tests importing from `app.main` or relying on `uvicorn app.main:app`
2. **Baseline test first**：运行完整 backend；Chromium 可用时运行完整 browser；若当前基线不绿，暂停并报告，不开始 A2 拆分。
3. **Create scaffolding without behavior change**：先新增目标模块，再让 `main.py` 继续导出原入口。第一批提交只允许移动常量/helper/schema，不改路由语义。
4. **Move in narrow batches**：按可验证域拆分，每批只迁移一组 route/helper：
   - schemas + error helpers
   - lifespan/app factory/system routes
   - materials/import/export routes
   - AI/retrieval/Q&A/index routes
   - tasks routes
   - study learning routes
   - study plans/rhythm/notes routes
   - study practice/cram routes
   - capture/report/delivery routes
   - `INDEX_HTML` verbatim move to `web_ui.py` only after route behavior is stable
5. **Keep router registration explicit**：each router exposes `router` or `register_routes(app, ...)`; no implicit module side effects that register routes on import. `create_app` owns assembly order.
6. **Preserve dependencies and state**：database path/config/provider registries/request IDs/metrics/recovery readiness must be sourced exactly as before. If current code uses closure over `config`, replicate that via dependency factory or app state without changing behavior.
7. **Avoid route collisions/order drift**：FastAPI route registration order must remain stable where dynamic paths could shadow static paths (especially `/api/materials/deleted`, `/api/materials/export`, `/api/materials/{material_id}/...`, study routes, and `/`). Compare route inventory after each batch.
8. **Re-export compatibility**：`main.py` must continue to expose any public request classes/helpers/constants that tests or scripts import. If in doubt, re-export explicitly and include in inventory comparison.
9. **Commit per domain**：after each validated batch, commit independently with messages such as:
   - `refactor: split app schemas into schemas.py`
   - `refactor: split system routes into api/system.py`
   - `refactor: split material routes into api/materials.py`
   - `refactor: split ai routes into api/ai.py`
10. **No cleanup refactors**：do not rename routes/functions for style, consolidate duplicated error handling, change pydantic model definitions, change response building, or reformat `INDEX_HTML` unless required for the move.

## 七、每域 focused 验证建议

Run relevant focused backend tests after each batch, then full backend before the next high-risk domain.

- schemas/errors/system/lifespan:
  - `backend/tests/test_observability.py`
  - `backend/tests/test_recovery_consistency.py`
  - `backend/tests/test_phase10_gate_j.py`
  - migration/audit/readiness related tests
- materials/import/export:
  - `test_file_import_path.py`
  - `test_import_failure_boundaries.py`
  - `test_material_pagination.py`
  - `test_material_export.py`
  - `test_storage_path_security.py`
  - `test_lifecycle_invariants.py`
  - relevant browser material specs
- AI/retrieval/Q&A/indexing:
  - `test_ai_indexing.py`
  - `test_retrieval.py`
  - `test_context_assembler.py`
  - `test_qa_api.py`
  - `test_ai_citation_lifecycle.py`
  - `test_phase7_acceptance.py`
  - `browser_qa.spec.js`, `browser_phase7.spec.js`, `browser_p6e.spec.js`
- tasks:
  - `test_task_runner.py`
  - `test_phase10_operations.py` if present
  - `test_phase10_task_integration.py`
  - `test_phase10_gate_j.py`
- study learning/cards/exercises:
  - `test_phase8_cards.py`
  - `test_phase8_exercises.py`
  - `test_phase8_generation.py`
  - `test_phase8_closeout.py`
  - `browser_phase8.spec.js`
- study plans/rhythm/notes:
  - `test_phase9a_domain.py`
  - `test_phase9a_api.py`
  - `test_phase9a_source_lifecycle.py`
  - `test_phase9b_domain.py`
  - `test_phase9b_notes.py`
  - `test_phase9b_rhythm.py`
  - `test_phase9b_api.py`
  - `browser_phase9a.spec.js`, `browser_phase9b.spec.js`
- practice/cram/mistakes:
  - `test_phase9c_domain.py`
  - `test_phase9c_api.py`
  - `test_phase9c_source_lifecycle.py`
  - `browser_phase9c.spec.js`
- capture/report/delivery:
  - `test_phase9d_domain.py`
  - `test_phase9d_capture.py`
  - `test_phase9d_capture_ingest.py`
  - `test_phase9d_report.py`
  - `test_phase9d_delivery.py`
  - `test_phase9d_api.py`
  - `browser_phase9d.spec.js`

If test filenames differ, discover with `rg` and use the closest focused suite. Do not invent missing tests.

## 八、最终验收门

All commands run from `H:\studybuddy` unless stated otherwise:

```powershell
git status --short --branch
git rev-parse HEAD
C:\miniconda\py310\python.exe -m pytest backend/tests/ -q
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_file_import.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_folder_import.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_frontend_failure_contract.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_material_export.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_material_management.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_material_pagination.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_material_recycle_bin.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_material_search.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_multi_file_import.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_p6d.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_p6e.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase7.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase8.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9a.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9b.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9c.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9d.spec.js
pwsh -NoProfile -File .\backend\scripts\test-browser.ps1 browser_qa.spec.js
git diff --check
git status --short --branch
```

Additional smoke checks:

```powershell
cd backend
C:\miniconda\py310\python.exe -c "import app.main; print(app.main.create_app, app.main.app)"
C:\miniconda\py310\python.exe -m app --help
C:\miniconda\py310\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port <free-port>
```

For the uvicorn smoke, perform `GET /api/liveness`, `GET /api/health`, `GET /api/readiness`, and `GET /`; verify safe status and that `/` still returns HTML.

Expected final baseline unless tests are deliberately added/removed and documented:

- Backend: **413 passed, 2 skipped**
- Browser: **52 passed, 1 skipped**
- Route inventory: exactly same method/path/status/response-class set and order as pre-A2
- Public `app.main` compatibility symbols: no missing tested imports
- No schema/migration/storage/provider/frontend behavior changes
- Worktree clean after commits and push

## 九、Documentation updates

After validation, update only the relevant fact sources:

- `docs/STATUS.md`：record A2 status, commit range, backend/browser evidence, and any `not_verified` limits
- `docs/TODO.md`：mark A2 complete only if all acceptance gates pass
- `docs/prompts/architecture/A0_BASELINE_AUDIT.md`：append A2 actual baseline/result and revised responsibility conclusion
- `docs/prompts/architecture/A0_ROUTE_REPOSITORY_MAP.md`：update route/module mapping and external import/call sites
- `docs/prompts/architecture/A0_REFACTOR_ROLLBACK_PLAN.md` only if rollback mechanics changed; otherwise leave it intact
- `docs/ARCHITECTURE.md` only if the app factory/router boundary changed enough that architecture readers need the new module map

Do not create duplicate status documents. Do not commit temporary inventory files, Playwright output, SQLite databases, originals, `.incoming-*`, provider keys, raw logs, private paths, or generated artifacts.

## 十、风险提示

- Dynamic route order is high risk. Static material routes must continue to register before `{material_id}` routes where required.
- Error mapping is public behavior. Preserve exact `HTTPException.detail` strings/dicts and status codes.
- `INDEX_HTML` is large and fragile. Move verbatim only, with hash/byte comparison before and after; do not pretty-print or modify embedded JS/CSS.
- Lifespan/readiness ordering is a deployment boundary. Do not simplify startup by removing preflight/audit/recovery sequencing.
- Route closures may depend on `config`, provider registry, request IDs, app state, or helper functions. Preserve those dependencies explicitly when moving to routers.
- Browser tests rely on accessible names, DOM timing, retry behavior, and safe failure text. Any DOM change belongs to A3 or later, not A2.
- A1 repository modules are compatibility exports over `_legacy.py`; do not assume repository internals are fully decoupled.
- If browser has a one-off `ERR_CONNECTION_RESET`, rerun the affected spec once and report both first failure and rerun result; do not mark browser-pass unless the final spec pass is real.

## 十一、明确不在 A2 范围

- A3 static frontend extraction or multi-page frontend
- A4 Provider settings/capture page changes
- B1 ASR, B2 OCR, B3 report-core expansion, B4 live delivery
- D0/D1 Tauri desktop work
- Repository internal function-body decoupling beyond using existing A1 façade/domain exports
- Schema/migration changes
- API contract changes
- UI text/DOM/style/behavior changes
- Provider network probing or real-provider evidence expansion
- New worker/scheduler/multi-process behavior

## 十二、完成判定

A2 完成 = `main.py` 保留兼容入口且变薄；app factory/lifespan/schemas/errors/routes 已按域拆出；151 条路由及顺序、状态码、error/detail、JSON shape、media type、`INDEX_HTML` 行为和 startup/readiness 语义均与基线一致；完整 backend 和完整 browser 通过；文档事实源更新；每批独立提交；最终工作区干净并推送。若任何门失败，按 `A0_REFACTOR_ROLLBACK_PLAN.md` 回退对应批次并停止，不进入 A3。
