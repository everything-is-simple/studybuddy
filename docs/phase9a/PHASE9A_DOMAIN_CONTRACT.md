# Phase 9A 领域契约与现状审计（9A-0 至 9A-6 记录）

> 状态：9A-0 `audit-draft`、9A-1 `contract-frozen`、9A-2/9A-3/9A-4 `implemented/backend-pass`、9A-5 `browser-pass`、9A-6 `scoped-gates-pass`；9A-6 尚未 closeout，9A-7/9A-8 未完成。
>
> 本文记录当前正式代码审计、Phase 9A 的边界以及已冻结的领域契约。9A-2 至 9A-6 已形成 schema、repository/domain、API、source lifecycle 和本地 Chromium workspace 的 scoped evidence；9A-6 尚未 closeout，9A-7 backup/restore closeout、9A-8 acceptance 尚未完成。
>
> 审计基线：commit `c083975`，审计日期：2026-08-30。

## 1. 审计结论摘要

- 当前正式 schema version 是 **9**；`schema_migrations` 与 `PRAGMA user_version` 必须一致。
- migration 没有拆成独立 migration 文件，而是集中在 `backend/app/migrations/runner.py` 的 `_MIGRATIONS` tuple 中，当前 1–9 连续注册。
- 业务 repository 也集中在 `backend/app/repository.py`；大多数单个写操作使用 `with connection:`，由 SQLite connection context 提交或 rollback。部分需要跨阶段的 AI 流程会显式 `commit()` 后再进行 Provider I/O，再执行最终写入。
- 当前身份边界是 `project_id`，默认值为 `default`；没有 `user_id`、认证或授权模型。9A 应沿用 `project_id` 隔离，不提前设计多用户权限。
- 当前 source of truth 是 `projects`、`materials`、`extractions`、`text_spans`。`material_revisions`、`chunks`、retrieval、citations、AI operations 和 Cards/Exercises 是派生数据或用户状态。
- 当前 Cards/Exercises 已有独立 citation 表和 source lifecycle refresh 逻辑，可作为 9A source-link contract 的参考；不应直接把 `card_citations` 或 `exercise_citations` 复用为计划领域表。
- backup 通过 SQLite Online Backup API 快照数据库，因此新增 SQLite 表天然进入数据库备份；manifest 当前记录 database hash、integrity、foreign-key、schema version 和 originals 引用，未逐表列举业务对象。
- 当前 UI 是 `backend/app/main.py` 中生成的内嵌 HTML/JavaScript 单页，不是独立前端工程。Materials、Q&A、Cards/Exercises 共用页面导航、状态区和 workspace 风格。
- 9A 当前已有学习目标、知识模块、study plan/item、dependency、progress repository、API、source lifecycle 和本地 Chromium workspace 的 scoped implementation；artifact backup/restore 和 Phase 9A closeout 仍未完成。不能把历史版本实现当作正式系统证据。

## 2. 9A 正式术语

以下 glossary 已由 9A-1 冻结；“未实现”描述的是代码状态，不是术语仍待决策：

| 术语 | 当前候选含义 | 当前状态 |
|---|---|---|
| Learning Goal | 用户希望达成的学习方向或结果，可作为一个或多个计划的上层目标 | 正式契约，未实现 |
| Knowledge Module | 可复用的学习主题/知识单元，保存结构化标题和描述，并可关联正式 source revision/citation | 正式契约，未实现 |
| Study Plan | 一组有序学习项的用户计划，生命周期为 draft → confirmed → active，并支持 paused/completed/archived | 正式契约，未实现 |
| Study Plan Item | 计划中的一个可跟踪学习项，可关联 module、revision/citation、deck 或 exercise set | 正式契约，未实现 |
| Dependency | 同一 plan 内计划项之间的 prerequisite DAG 关系 | 正式契约，未实现 |
| Progress Event | 描述某项进度事实的 append-only 记录，事件类型为 started/completed/skipped/reopened | 正式契约，未实现 |
| Progress Summary | 从 progress event 和当前计划项状态计算出的只读展示摘要 | 正式契约，未实现 |
| Source Link | module/item 到 material revision/chunk/span/citation 的安全引用关系，不复制正文 | 正式契约，未实现 |
| User-edited | 用户对 draft 或 item 内容做过显式修改的保护标记 | 需与领域状态一起冻结 |

这些词的正式定义不表示前代 `KnowledgeModule`、历史 study plan 或其它参考项目已被正式系统吸收；正式代码仍未实现。

## 3. 当前实现审计

### 3.1 Schema 与 migration

**源码：** `backend/app/migrations/runner.py`

- `CURRENT_SCHEMA_VERSION = 9`（第 9 行）。
- `HISTORY_TABLE = "schema_migrations"`（第 10 行）。
- `_MIGRATIONS`（约第 600 行）注册连续 history：
  1. `canonical_material_schema`
  2. `ai_phase0_schema`
  3. `phase5_provider_metadata`
  4. `qa_operation_idempotency`
  5. `phase7_embedding_schema`
  6. `search_index_schema_contract`
  7. `phase8_cards_exercises_schema`
  8. `phase8_exercise_provenance`
  9. `phase9a_learning_plan_schema`
- `migrate()` 使用 `BEGIN IMMEDIATE`，逐个执行 migration 并插入 history；最后设置 `PRAGMA user_version` 并 commit。`MigrationError` 或 SQLite/OSError 会 rollback。
- `_baseline_complete()` 只允许已知且完整的当前基础对象通过；未知 future version、history mismatch、缺失 required object 不会被启动自动修复。
- 9A-2 已以连续 v9 新增计划 schema；后续变更必须继续追加连续 migration，不得修改 v1–v9 history，也不应在连接初始化时 ad-hoc 建表。

**现有 migration 测试：** `backend/tests/test_migrations.py`

- `test_new_database_has_versioned_schema_and_is_idempotent` 验证新库、当前版本和主要表。
- `test_missing_search_schema_is_not_repaired_at_runtime` 验证缺失 schema 不自动 repair。
- `test_failed_migration_rolls_back_and_uses_stable_error` 验证失败 rollback。
- `test_backup_manifest_and_restored_database_retain_version` 验证 backup schema version。

### 3.2 Connection、事务与 repository

**源码：** `backend/app/repository.py`

- `connect()`（约第 131–149 行）设置 row factory、foreign keys、WAL、busy timeout，调用 `migrate()`、`assert_schema_version()` 和只读/补齐型 FTS index 初始化后 commit。
- `utc_now()`（约第 152 行）返回 timezone-aware UTC ISO 字符串。当前没有单独的 date-only 或用户 timezone domain helper。
- 导入写入 `save_material_with_extraction()`（约第 172 行）在同一 `with connection:` 中写入 project/material/extraction/text_spans/FTS。
- Materials mutation 如 `restore_material()`（约第 363 行）、`soft_delete_material()`（约第 1177 行）、`purge_material()`（约第 1037 行）使用连接上下文包裹写操作，并在 lifecycle 变化时刷新 Cards/Exercises citation 或标记 Q&A citation。
- Cards/Exercises 的创建、编辑、确认、状态迁移、review/attempt 约位于第 446–995 行；均以传入连接为事务边界，使用 `ValueError` 稳定错误码与显式状态校验。
- Embedding/QA 长流程在必要处显式提交 operation lease，再进行 Provider I/O，避免长时间持有 SQLite 写事务；9A 如引入 AI draft 必须复用该边界，不得将 Provider I/O 放入长期写事务。
- 9A-3 已选择在 `backend/app/repository.py` 增加可测试的领域 repository 函数；没有新增独立 domain service 文件，API handler 只负责 HTTP 输入/错误映射，不承载领域事务逻辑。

### 3.3 ID、项目与用户边界

**源码：** `backend/app/config.py`、`backend/app/main.py`、`backend/app/repository.py`

- `AppConfig.project_id` 默认是 `"default"`；环境变量为 `STUDYBUDDY_PROJECT_ID`。
- repository 通过 UUID4 hex 生成带领域前缀的 ID，例如 `material_...`、`card_...`、`exercise_...`、`retrieval_...`、`operation_...`。
- `projects` 表存在，materials、Cards、Exercises、retrieval/AI 查询普遍按 `project_id` 过滤；没有 `users` 表或 `user_id` 字段。
- API handler 从 `app.state.config.project_id` 注入 project scope，不从客户端接收任意 project ID。
- 推荐 9A 继续为所有顶层领域表保留 `project_id` 并在 repository/API 强制 scope；暂不增加 user_id、认证、权限、共享协作或 project 管理 UI。

### 3.4 错误响应与隐私

**源码：** `backend/app/main.py`、`backend/app/observability.py`、`docs/CODE_TEST_GOVERNANCE.md`

- API 通过 `HTTPException(status_code=..., detail=<stable_code>)` 返回稳定错误码；repository 的 `ValueError` 由 handler 映射为 4xx，SQLite/Provider 错误映射为安全的 5xx 或稳定 Provider code。
- `observability_middleware()` 生成/传递 `X-Request-ID` 和 request-scoped operation correlation；日志输出 event、route、status class 等低敏 metadata。
- 现有列表通常返回受控 dict，不把 stored_path、SQL、traceback 或 secret 暴露给客户端。Phase 8 普通 exercise/attempt response 还专门隐藏 answer key 和 submitted answer。
- 9A 错误码应沿用短稳定 snake_case，例如 `study_plan_not_found`、`study_plan_invalid_state`、`study_plan_dependency_cycle`、`study_progress_invalid_event`、`study_source_unavailable`；最终集合由 9A-1 冻结。

### 3.5 Source revision、chunk、retrieval 与 citation

**源码：** `backend/app/repository.py`、`backend/app/main.py`

- `create_or_get_revision()`（约第 1209 行）以 material/extraction 创建或复用 revision；`index_material_revision()`（约第 1248 行）为显式 indexing 创建/更新 revision、chunk 和 citation 可追溯基础。
- `material_state()`（约第 995 行）区分 missing/deleted/active 等 material 状态。
- `validate_citation_key()`（约第 2104 行）验证 citation key 是否能映射当前合法 chunk/source；`assemble_context()`（约第 2137 行）只输出经过检索和验证的 context/citation。
- `soft_delete_material()` 会更新 Cards/Exercises citation lifecycle（约第 1177–1187 行）。
- `restore_material()` 会清除 deleted 状态并刷新 Cards/Exercises citations（约第 363–374 行）。恢复不重新解析、不创建原始/派生材料。
- `purge_material()` 会保留历史 Q&A/卡片/练习 citation 记录并标记为 `source_unavailable`，再清理 material 及其级联 source rows（约第 1037–1065 行）。
- Card citation `_refresh_card_citations()`（约第 490–515 行）和 exercise citation `_refresh_exercise_citations()`（约第 616–641 行）通过 material deleted 状态、chunk/revision/extraction 一致性得到 `valid`、`source_deleted`、`source_unavailable` 或 `stale`。
- 该逻辑是 9A 可复用的行为参考，但其表和 artifact_id 绑定固定为 card/exercise；计划领域应定义自己的 source-link 表或明确独立 link model，不把计划链接硬塞进卡片/练习 citation 表。
- 当前 source link 不应复制 quote/full text。若 UI 需要定位，应保存受限 citation key 和 revision/chunk/span identity，并重新从当前 source contract 查询。

### 3.6 Phase 8 Cards/Exercises 生命周期

**源码：** `backend/app/migrations/runner.py` v7/v8；`backend/app/repository.py` 第 446–995 行；`backend/app/main.py` 第 994 行以后；测试 `backend/tests/test_phase8_cards.py`、`test_phase8_exercises.py`、`test_phase8_generation.py`、`test_phase8_closeout.py`、`backend/tests/browser_phase8.spec.js`

- Cards/Exercises 使用 `draft → ready | rejected | archived`，另有 `stale` source 状态。
- draft-only edit；confirmed/ready/archived 不允许被普通编辑接口静默覆盖。
- AI generation 经 retrieval/context/provider/结构化输出内存校验和 citation 重验后，原子保存 draft 和 operation metadata。
- reviews/attempts 是 append-only；短答为 `pending_review`，尚无人工复核 API/UI。
- source delete/restore/purge/re-index 会更新 citation lifecycle；历史 artifact 不因 source purge 被静默删除。
- 这些 contract 是 9A 的保护原则参考，但 plan status、progress event、dependency DAG 需要单独设计和测试。

### 3.7 Backup、restore 与 non-repair

**源码：** `backend/app/backup.py`、`backend/app/restore_acceptance.py`、`backend/app/cli.py`；文档 `docs/BACKUP_RESTORE.md`

- `backup_data()`（约第 166 行）通过 SQLite Online Backup API 将整个 SQLite database 快照到 backup `database.sqlite3`。
- `_checks()` 对 backup 数据库执行 `integrity_check`、`foreign_key_check`、`assert_schema_version()`。
- manifest（`backup_data()` 约第 198–200 行）包含 format/version、project_id、database hash/size/integrity/foreign/schema version、originals 文件清单和 material 引用统计；没有业务表白名单，因此新增 SQLite 表随数据库进入快照。
- `verify_backup()` 验证 manifest、数据库 hash/integrity/foreign/schema version、original layout/hash 和 references；不运行 migration、不 repair、不 rebuild。
- restore 只允许不存在或空目标目录，并要求显式 `--confirm`；restore acceptance 的 `_check_database()` 验证 schema version/history/integrity/foreign keys，online/offline 检查材料路径和导出。
- 9A 新增表预计不需要新增文件清单或外部 index manifest；但必须在 9A-7 验证新表、状态和 progress history 的 backup/restore，并考虑是否扩展 restore acceptance 的业务对象断言。

### 3.8 FastAPI 路由与前端 workspace

**源码：** `backend/app/main.py`

- `create_app()`（约第 366 行）在一个文件内声明 FastAPI app、lifespan、middleware、Pydantic request models、路由和内嵌 HTML/JavaScript。
- `/api/materials*` 提供导入、列表、详情、rename/delete/restore/purge/export；`/api/retrieval`、`/api/context/assemble`、`/api/citation/validate`、`/api/qa/*` 提供 AI/Q&A。
- `/api/study/decks*`、`/api/study/cards*`、`/api/study/exercise-sets*`、`/api/study/exercises*` 位于同一 `create_app()`，对应 Phase 8 workspace。
- 当前页面通过导航按钮切换 materials/Q&A/study 区域；Phase 8 browser test 使用 `#nav-study`、`#study-workspace`、`#study-status`、`#study-detail`、`#study-generate` 等 DOM contract，证明 UI 是内嵌单页而不是独立 bundle。
- 现有 browser 测试使用 `C:/miniconda/py310/python.exe -m uvicorn app.main:app`，`PYTHONPATH=H:/studybuddy/backend`，每个 spec 使用 `H:/studybuddy-test/runs/...` 隔离 data root、单独端口、`--workers=1`。
- 9A-5 已复用 study workspace/navigation/status/toast/busy/stale-response 模式，并通过独立 `browser_phase9a.spec.js` DOM/user-path contract；没有改变 Cards/Exercises 既有路径。

### 3.9 测试 fixture 与证据

**源码：** `backend/tests/*.py`、`backend/tests/browser_phase8.spec.js`

- backend 测试普遍使用 pytest `tmp_path`，通过 `TestClient(create_app(AppConfig(data_root=tmp_path, ...)))` 创建隔离 app。
- 直接 repository 测试使用 `connect(tmp_path / "studybuddy.sqlite3")`；migration 测试也直接使用 sqlite3 临时数据库。
- browser 测试使用 Node `spawn()` 启动 uvicorn，环境变量指定隔离 `STUDYBUDDY_DATA_ROOT`，用 polling 等待 `/api/health`，结束时 kill server。
- 默认后端命令为 `C:\miniconda\py310\python.exe -m pytest backend/tests/ -q`；浏览器必须使用 `backend/scripts/test-browser.ps1` 串行执行单个 spec。
- 运行结果、数据库、原文件和浏览器 artifact 应位于 `H:\studybuddy-test` 或系统临时目录，不得写入仓库。

## 4. 9A-0 范围冻结

### 4.1 明确纳入 9A 的最小范围

9A 只建立可验证的学习领域/计划核心：

1. goal 的最小创建、查看、编辑/归档边界；
2. module 的最小创建、查看和 source link 候选；
3. plan draft、item、dependency 和 draft → confirm → active 生命周期；
4. progress event 与可重算 summary；
5. plan/module/item 与现有 revision/chunk/span/citation 的安全关联；
6. active/deleted/purged/stale/unavailable source 的安全展示和状态传播；
7. 单进程 SQLite backend、API、最小 Chromium workspace、backup/restore 验证。

具体字段、状态、pause/archive/complete、AI draft 和 source link 层级已在 9A-1 冻结，详见第 5–7 节。

### 4.2 明确排除

9A 不实现：

- 9B S1/S2：学习节奏、资料笔记、完整资料学习/知识模块工作流；
- 9C S3/S4/S5：限时练习、错题改错、期末冲刺、人工简答复核；
- 9D S6/S7：家长报告、课堂采集、OCR、ASR、外发交付；
- Phase 10：worker、queue、scheduler、cancel、长任务恢复、多用户、认证授权、云同步、协作；
- 提醒、推送、日历、recurrence、自动每天规划、自动 re-plan、后台进度扫描；
- 外部 vector DB、历史材料自动索引、真实 Provider plan generation 作为 9A 完成前置；
- 复杂推荐、评分、教师/家长视图和国际化。

### 4.3 正式不变量

以下不变量由 9A-1 冻结，9A-2 及后续实现必须逐项测试：

- 所有 9A 对象按 `project_id` 隔离，客户端不能跨 project 读取或修改；
- source link 只保存 identity/受限 metadata，不复制正文；
- plan/item 的状态转移由服务端校验，非法转移不会部分写入；
- dependency 只允许同一 plan 内，必须拒绝自依赖、重复边和环依赖；
- progress history append-only，summary 可以从事件和当前 item 事实重算；
- confirmed、active、completed 或 user-edited 内容不得被重新生成静默覆盖；
- source purge 保留用户计划和进度历史，但 source link 只能显示 unavailable，不能伪造可定位来源；
- restore/verify/startup/read 不自动 repair、rebuild、重新生成或升级 source link；
- 所有 migration history、`user_version` 和 backup manifest schema version 一致；
- 错误和日志不泄露路径、SQL、正文、secret、raw provider response 或 traceback。

## 5. 正式实体关系（9A-1 已冻结）

以下关系是 9A-1 冻结的领域关系，具体 SQLite DDL 留给 9A-2；不得将本节直接解释为已实现 schema：

```text
project
  ├── learning_goals
  │     └── study_plans (一对多；每个 plan 必须绑定一个 goal)
  ├── knowledge_modules (project 内独立可复用；不直接挂 goal)
  └── study_plans
        ├── study_plan_items
        │     ├── optional reusable module reference
        │     ├── optional deck/exercise_set reference（仅引用已存在对象）
        │     └── optional source links (revision/chunk/span/citation identity)
        ├── dependencies (same-plan DAG)
        └── progress_events (append-only facts + atomic item projection)
```

9A-1 决策：

1. goal 与 plan 为一对多；每个 study plan 必须绑定一个同 project 的 learning goal。一个 goal 可以有多个 draft/confirmed/active/archived plan，但同一时间是否允许多个 active plan 留给实现约束；9A 默认允许。
2. knowledge module 独立属于 project，不直接绑定 goal；可被多个 plan item 复用。module archive 后不能新挂载，但既有 plan item 保留并显示 archived module。
3. source link 只绑定 knowledge module 或 study plan item，不绑定 goal/plan 本身；同一对象可有多个 link。module link 表达知识模块证据，item link 表达执行项证据，避免 plan 级重复和多态外键。
4. item 允许没有 source，支持用户自定义学习项；AI/资料约束不是 9A 激活前置。若存在 source link，必须指向 current/可验证 revision identity；无 source 不伪造 citation。
5. dependency 只允许同一 plan 内的两个不同 item，强制 DAG；拒绝自依赖、重复边、跨 plan、跨 project、归档/不存在 item 和任何会形成环的新增边。
6. active plan 允许存在 source_deleted/source_unavailable/stale link 并激活；激活/详情返回 source warning 和 item source status。不可用 source 不会自动 repair、重新解析或伪造正文；是否能开始该 item 由后续 workflow 决定，不在 9A 阻止计划激活。
7. 9A 只支持 `started`、`completed`、`skipped`、`reopened` 四类 progress event；不支持 cancelled。completed/skipped 可通过 reopened 产生新的事实回到 in_progress，历史事件永不修改或删除；只有 active plan 的 item 可产生事件。
8. plan 状态纳入 `draft → confirmed → active`，并支持 `active → paused/completed/archived`、`paused → active/completed/archived`、`confirmed → draft/active/archived`、`draft/confirmed → archived`。item 使用 `pending/in_progress/completed/skipped/archived` 投影。confirmed 不是 active；只有 active/paused plan 可按 contract 继续处理，completed/archived 是终态（除非未来独立迁移）。
9. 9A 不实现 due date、time zone、recurrence、提醒或 scheduler。所有审计时间统一保存 UTC ISO-8601；不把客户端本地日期伪装成截止时间。日期计划需求延期到后续阶段单独设计。
10. 9A 不实现 AI plan generation 或 fake-provider plan draft。9A 只实现用户创建/编辑 draft；真实 Provider、fake Provider、自动 re-plan 和 prompt/operation contract 延期，不新增 ai_operations 类型。
11. 不需要新的 `ai_operations.operation_type`。如果未来加入 AI plan draft，必须另立契约并保证只创建新 draft、不覆盖 confirmed/active/completed/user-edited 内容。
12. 9A 业务对象不做物理 delete。goal/module/plan 使用 archive；draft plan/item 可在事务内移除未确认 item，但已有 progress 或被 dependency 引用的 item 不直接删除。active/confirmed/completed plan 不能物理删除；所有历史 progress 保留。
13. 不保存可独立修改的 summary snapshot。summary 从当前 item projection 与 append-only progress facts 在读取/明确重算时计算；event append 与 item projection 必须同一事务，失败整体 rollback。

以上 13 项问题已由 9A-1 决策。9A-2 可以据此提出 schema/DLL；若实现发现需要改变本契约，必须先提交契约修订，不能在 migration 中隐式改变语义。

## 6. 正式字段与生命周期契约

### 6.1 统一字段约定

所有 9A 表必须保留 `id`、`project_id`（progress event 和 source link 通过所属对象间接归属 project，但推荐直接保留以便 scope 查询）、`created_at`；可变对象使用 `updated_at`；archiveable 对象使用 `archived_at`。ID 使用当前系统的带领域前缀 UUID4 hex，例如 `goal_...`、`module_...`、`plan_...`、`plan_item_...`、`plan_dependency_...`、`progress_...`、`plan_source_...`、`module_source_...`。

时间字段统一使用 UTC timezone-aware ISO-8601 字符串；9A 不接受客户端任意 timezone 作为业务计算输入，不实现 due date、recurrence 或 scheduler。用户输入的 title/description/item content 必须使用服务端长度和空白校验；source identity 不能由客户端自由填写后直接落库。

### 6.2 Entity contract

| Entity | 正式最小字段语义 | 生命周期/保护 |
|---|---|---|
| Learning Goal | `id`, `project_id`, `title`, `description`, `status`, `created_at`, `updated_at`, `archived_at` | `active`/`archived`；不物理删除；archive 后不能创建新 plan 绑定，但历史 plan 保留 |
| Knowledge Module | `id`, `project_id`, `title`, `description`, `status`, `created_at`, `updated_at`, `archived_at` | `active`/`archived`；可被多个 item 复用；archive 后不能新挂载，历史引用保留 |
| Study Plan | `id`, `project_id`, `goal_id`, `title`, `description`, `status`, `user_edited`, `created_at`, `updated_at`, `confirmed_at`, `activated_at`, `completed_at`, `archived_at` | draft 可编辑；confirmed/active 不被重生成覆盖；active 可 pause/complete/archive；历史保留 |
| Study Plan Item | `id`, `plan_id`, `project_id`, `module_id?`, `deck_id?`, `exercise_set_id?`, `title`, `description`, `position`, `status`, `user_edited`, `created_at`, `updated_at`, `completed_at`, `archived_at` | draft/confirmed 可编辑；active item 通过 progress event 产生 projection；有历史/依赖时不物理删除 |
| Dependency | `id`, `plan_id`, `project_id`, `predecessor_item_id`, `successor_item_id`, `created_at` | append/delete edge；同 plan、不同 item、无重复、无环 |
| Progress Event | `id`, `plan_id`, `item_id`, `project_id`, `event_type`, `created_at`, `metadata`（受限 JSON） | append-only；不 update/delete；event 写入与 item projection 同事务 |
| Source Link | `id`, `project_id`, `owner_type`（仅 module/item 的独立表或等价受限枚举）、`owner_id`, `material_id`, `revision_id`, `extraction_id?`, `chunk_id?`, `span_id?`, `citation_key?`, `status`, `created_at`, `updated_at` | identity link；状态由服务端刷新，不信任客户端 status；不保存正文/quote |

`deck_id`/`exercise_set_id` 只能引用同一 project 已存在的 Phase 8 容器；9A 不改变 Cards/Exercises 状态或 attempt 语义。若 SQLite 外键不能安全表达跨表 project 一致性，必须在 repository transaction 中验证并测试。

### 6.3 状态枚举与转移

**Goal：** `active → archived`；archived 为终态。新建 goal 为 active。Goal archive 后不能绑定新 plan，但不级联 archive 既有 plan。

**Module：** `active → archived`；archived 为终态。新建 module 为 active。Module archive 后不能新挂载，但历史 item 保留。

**Plan：** 新建为 `draft`。允许转移：

```text
draft → confirmed | archived
confirmed → draft | active | archived
active → paused | completed | archived
paused → active | completed | archived
completed → archived
archived → terminal
```

`confirmed → draft` 仅允许显式用户编辑动作，且必须重新确认；confirmed/active/completed 不允许普通 patch 静默改变结构。active/paused/completed/archived 的 plan 不能物理删除。

**Item projection：** 新建 draft plan item 为 `pending`；计划激活后仍为 `pending`。允许：

```text
pending → in_progress | completed | skipped | archived
in_progress → completed | skipped | reopened | archived
completed → reopened | archived
skipped → reopened | archived
reopened → in_progress | completed | skipped | archived
archived → terminal
```

`started` 事件将 pending/reopened 投影为 in_progress；`completed`、`skipped`、`reopened` 分别更新 projection。item 只有其 plan 为 active 时才接受 progress event；paused/completed/archived plan 拒绝新的 event。

**Progress event：** 只允许 `started`、`completed`、`skipped`、`reopened`。不支持取消事件；撤销完成使用新的 reopened 事实，不修改历史 completed event。重复请求若没有显式幂等 contract，不得假定事件自然去重；实现必须通过 event ID 或请求幂等策略决定并测试。

### 6.4 Source lifecycle

Source link 的服务端状态只能从实际 source 关系计算：

| 条件 | link status | 是否可定位 |
|---|---|---|
| material active、revision current、chunk/span identity 一致且可验证 | `valid` | 是 |
| material soft-deleted | `source_deleted` | 否 |
| material purged 或历史 material identity 已不存在 | `source_unavailable` | 否 |
| material active 但 revision 非 current、chunk stale/missing 或 identity 不一致 | `stale` | 否 |
| 客户端提供不存在/伪造 citation key 或无法验证的 relation | reject，不落库 | 否 |

Delete、restore、purge、new extraction/new revision、re-index 不得复制 source text，不得自动解析或调用 Provider。restore 只使 material lifecycle 恢复；link 是否回到 valid 必须由显式 link refresh/read-time validation 依据 current source contract 判断，不能由 startup/restore 自动 repair。purge 保留 module/item/plan/progress 历史和 link 记录，但 link 变为 `source_unavailable`，不得恢复 material 名称、正文或可点击位置。

Active plan 允许上述非 valid link，并返回 warning；9A 不把 source availability 当作计划激活前置。具体学习 item 是否可执行属于后续 workflow。

### 6.5 Progress summary

summary 是只读派生响应，不是独立可编辑事实。至少返回：`item_count`、各 item status count、`completed_count`、`skipped_count`、`in_progress_count`、`pending_count`、`completion_ratio`、`last_event_at` 和 source warning count。分母为未 archived 的 plan items；若没有可计数 item，ratio 为 `0.0`，不得除零。

每次 progress event 必须在同一个 SQLite transaction 内：校验 plan/item 状态 → 插入 append-only event → 更新 item projection → commit。任一步失败全部 rollback。summary 可通过查询 event/projection 重算；不允许用户直接写入 summary 快照。

## 7. 正式错误码与 API resource 草案

以下是 9A-1 冻结的稳定错误码初稿，9A-4 只能使用这些语义或在契约修订后增加：

| 错误码 | 语义 |
|---|---|
| `learning_goal_not_found` | goal 不存在或不属于当前 project |
| `learning_goal_archived` | goal 已 archive，不能执行要求 active 的动作 |
| `knowledge_module_not_found` | module 不存在或不属于当前 project |
| `knowledge_module_archived` | module 已 archive，不能新挂载 |
| `study_plan_not_found` | plan 不存在或不属于当前 project |
| `study_plan_item_not_found` | item 不存在或不属于当前 project/plan |
| `study_plan_invalid_state` | plan 状态转移非法 |
| `study_plan_item_invalid_state` | item 状态或操作不允许 |
| `study_plan_confirm_required` | 需要先确认 draft |
| `study_plan_goal_invalid` | goal 不存在、跨 project 或不可绑定 |
| `study_plan_dependency_invalid` | dependency 输入非法、跨 plan、重复或归档对象 |
| `study_plan_dependency_cycle` | 新 dependency 会形成环 |
| `study_progress_invalid_event` | event type、plan/item 状态或 payload 非法 |
| `study_progress_event_duplicate` | 显式相同事件请求重复提交 |
| `study_source_invalid` | source revision/chunk/span/citation 不能验证 |
| `study_source_deleted` | source 已 soft-delete |
| `study_source_unavailable` | source 已 purge 或不可恢复 |
| `study_source_stale` | source link 指向非 current 或不一致 revision |
| `study_plan_edit_not_allowed` | confirmed/active/completed/user-protected 内容不可静默编辑 |
| `study_plan_item_edit_not_allowed` | item 已受保护或不属于可编辑状态 |
| `study_plan_conflict` | SQLite/状态并发导致写入冲突 |
| `study_plan_persist_failed` | 安全的持久化失败响应 |

API resource 只冻结资源边界，不在 9A-1 实现：

- goals：list/create/detail/patch/archive；客户端不能提交 project_id；
- modules：list/create/detail/patch/archive；source links 只接受经服务端验证的 source identity；
- plans：list/create draft/detail/patch/confirm/activate/pause/complete/archive；detail 返回 items、dependency、progress summary 和受限 source status；
- items：在 draft plan 下 create/patch/reorder/archive；confirmed/active 后只允许 contract 规定的受限操作；
- dependencies：在 plan 下 add/remove；服务端验证 same-plan DAG；
- progress：在 active plan item 下 append event；读取 event history 和只读 summary；
- source：读取 module/item source link 状态和安全定位 metadata；不返回 stored_path 或正文。

9A 不实现提醒、推送、due-date scheduler、recurrence、自动 re-plan、AI plan generation、取消任务、后台任务或跨用户 API。

## 8. 9B/9C/9D 边界

- 9B 可以复用 9A 的 KnowledgeModule、source link 和 plan item，但必须单独设计资料笔记/学习节奏 API、UI、状态和 evidence。
- 9C 可以复用 9A 对 deck/exercise set 的引用以及 Phase 8 attempt/grading，但限时、错题和冲刺仍是独立 domain，不在 9A 添加专用表或 scheduler。
- 9D 在需求、隐私、保留策略、真实组件证据和运维成本评审通过前不立项；9A 不预留 OCR/ASR/report 业务表。
- 9A 完成不代表以上任何子阶段实现，也不代表 Phase 9 完成。

## 9. 9A-2 schema implementation record

### 9.1 Migration decision

9A-2 implements one consecutive migration: **v9 `phase9a_learning_plan_schema`** in `backend/app/migrations/runner.py`. It creates only the 9A persistence contract and indexes; it does not add repository/domain operations, FastAPI routes, UI, AI generation, scheduler, worker or automatic lifecycle refresh.

| Table | Ownership and schema boundary |
|---|---|
| `learning_goals` | project-scoped active/archived goal; plans reference it with `ON DELETE RESTRICT` |
| `knowledge_modules` | project-scoped active/archived reusable module |
| `study_plans` | project-scoped plan, required goal, plan lifecycle and user-edited/timestamp fields |
| `study_plan_items` | project-scoped item with optional module/deck/exercise-set links and stable per-plan `position` |
| `study_plan_dependencies` | same-plan edge storage with self-edge CHECK and unique edge constraint |
| `study_progress_events` | append-only event storage with frozen event-type CHECK |
| `module_source_links` | module-specific source identity links and lifecycle status |
| `plan_item_source_links` | plan-item-specific source identity links and lifecycle status |

The source-link tables are intentionally separate rather than a polymorphic owner table: SQLite can enforce an owner foreign key without trigger-based polymorphism. Source material/revision/extraction/chunk foreign keys use `ON DELETE SET NULL`, preserving historical link rows on purge; 9A-6 must persist `source_unavailable` before/with lifecycle cleanup and must not infer valid source from a null identity.

`study_plan_items` uses `UNIQUE(plan_id, position)`. It references module/deck/exercise-set with `ON DELETE SET NULL`; this protects historical plan items from future physical deletion of those referenced artifacts. Dependency endpoints use `ON DELETE RESTRICT` to prevent accidental removal of an item that remains part of a graph or progress history. Parent plan/project deletion cascades only as a database/project teardown boundary, not as a user-facing 9A delete workflow.

### 9.2 Schema-enforced versus repository-enforced constraints

SQLite v9 enforces lifecycle enum membership, `user_edited` boolean values, non-negative item position, dependency self-edge rejection, unique item positions, unique dependency edges, unique source citation key per owner, source-link status membership and foreign-key existence where identities remain available.

9A-3 enforces transactionally and tests: same-project ownership across every optional reference; same-plan dependency endpoints; full DAG cycle detection; plan/item transition graph; goal/module archive action restrictions; append-only operation policy; active-plan-only progress events; item projection from events; source identity/citation validation; source lifecycle refresh; title/description/metadata size and JSON validation; duplicate-progress idempotency policy; and user-edit/confirmed/completed protection. These repository/domain rules are implemented and covered by `backend/tests/test_phase9a_domain.py`; SQLite CHECK/foreign keys alone cannot prove the cross-row or temporal rules.

### 9.3 v9 migration transaction and test evidence

`_migration_v9()` executes each DDL statement through `connection.execute()` rather than `executescript()`: Python sqlite `executescript()` can commit a pending transaction before executing, which would violate the runner's v9 rollback boundary. This preserves `migrate()`'s `BEGIN IMMEDIATE` atomicity for an upgrade from v8.

Focused migration coverage in `backend/tests/test_migrations.py` verifies:

- clean database initializes at v9 with all eight 9A tables;
- required v9 indexes and representative CHECK constraints exist;
- a v8 database upgrades once to v9 and repeated open does not duplicate history;
- an injected v9 failure rolls an existing v8 database back to v8 with no v9 table/history/user-version residue;
- backup manifest and restore history preserve v9 in `backend/tests/test_backup_restore.py`.

No migration writes plan/goal/module data, creates runtime tables, repairs source links or changes existing Phase 8 data.

## 10. 9A-0/9A-1/9A-2/9A-3/9A-4/9A-5 验收与下一步

### 已完成的 9A-0/9A-1/9A-2/9A-3/9A-4/9A-5 输出

- 当前 migration version、history 和 rollback 机制已定位；
- repository 事务边界和 ID/time/project 约定已定位；
- material revision/citation、Cards/Exercises source lifecycle 已定位；
- backup/restore 全 SQLite snapshot 与 non-repair 边界已定位；
- main.py 路由、内嵌 UI、测试 fixture 和 browser 运行方式已定位；
- 9A 纳入范围、明确排除、正式不变量、正式关系和 9A-1 决策已记录；
- v9 `phase9a_learning_plan_schema` 已通过 migration runner 创建八张 9A 表及约束/索引；
- 新库、v8→v9、重复运行、v9 failure rollback、backup/restore schema history 已有 focused backend coverage；
- repository/domain 已实现 goal/module archive 与编辑、plan draft/confirm/active、item 编辑/归档、同 plan DAG dependency、append-only progress/projection/summary、source identity validation 和材料 lifecycle refresh；
- `backend/tests/test_phase9a_domain.py` 覆盖状态转移、cycle、progress rollback/replay、cross-project rejection、completed protection、source stale/unavailable 和 archive boundary；
- `backend/tests/test_phase9a_api.py` 覆盖最小 API path、404/409/400 边界、project scope、progress replay、dependency cycle、source privacy；
- `backend/tests/browser_phase9a.spec.js` 覆盖本地 Chromium happy path、failure/retry、narrow viewport、keyboard 和 reload recovery。

### 9A-0/9A-1/9A-2/9A-3/9A-4/9A-5 的准确状态

`Phase 9A-0 completed as planned/audit-draft`：代码审计、范围和边界已形成。

`Phase 9A-1 completed as planned/contract-frozen`：正式实体关系、字段语义、状态机、不变量、progress、source lifecycle、错误码、API resource 边界和 deferred decisions 已冻结。

`Phase 9A-2 implemented/backend-pass`：v9 migration/schema、new-db/v8-upgrade/idempotency/failure-rollback 和 backup/restore schema-history tests 已通过。

9A-2 只代表 v9 schema/migration gate；它不单独代表学习领域用户路径完成。当前 schema 为 v9；startup/read/backup/restore 不创建 plan data、不 repair source link、不生成内容。

`Phase 9A-3 implemented/backend-pass`：repository/domain transaction、DAG cycle detection、append-only progress、状态投影、跨表/project 验证、用户编辑保护和 source lifecycle refresh 已通过 focused domain tests，并通过完整 backend regression。

`Phase 9A-4 implemented/backend-pass`：goal/module/plan/item/dependency/progress/source 的最小 API、project scope、稳定错误映射、malformed input、404/409 边界和隐私 contract 已通过 `backend/tests/test_phase9a_api.py` 与完整 backend regression。

`Phase 9A-5 browser-pass`：内嵌计划 workspace 已覆盖 goal → module → draft plan → items → dependency/cycle failure → confirm → active → item progress → summary → reload recovery，以及 500/retry、390x844、keyboard 和安全错误显示；证据为 `backend/tests/browser_phase9a.spec.js` 的本地 Chromium 路径。该状态不代表 real-pass 或 Phase 9A completed。

`Phase 9A-6 scoped-gates-pass`：材料 delete/restore/purge/re-index 已与 9A source links 接入；restore 保持 source status，显式 refresh 才重算；purge 保留 plan/progress/link 历史并固定 unavailable；active plan 在 source warning 下保持 active；module/item link、progress projection 和 source privacy 已覆盖。focused backend `16 passed`、full backend `270 passed, 2 skipped`、Phase 9A Chromium `3 passed`，脱敏草案见 `docs/PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md`。9A-6 尚未作最终 closeout，不能写成 Phase 9A completed。

### 下一步

进入 9A-7 backup/restore closeout；不扩展到 9B/9C/9D。
