# Phase 9A 领域契约与现状审计（9A-0 初稿）

> 状态：`planned` / 9A-0 audit draft。
>
> 本文只记录当前正式代码审计、Phase 9A 的边界和待冻结问题。本文不是 migration、API、repository 或 UI 的实现证据；在 9A-1 之前，候选模型和决策问题仍可调整。
>
> 审计基线：commit `c86b160`，审计日期：2026-08-30。

## 1. 审计结论摘要

- 当前正式 schema version 是 **8**；`schema_migrations` 与 `PRAGMA user_version` 必须一致。
- migration 没有拆成独立 migration 文件，而是集中在 `backend/app/migrations/runner.py` 的 `_MIGRATIONS` tuple 中，当前 1–8 连续注册。
- 业务 repository 也集中在 `backend/app/repository.py`；大多数单个写操作使用 `with connection:`，由 SQLite connection context 提交或 rollback。部分需要跨阶段的 AI 流程会显式 `commit()` 后再进行 Provider I/O，再执行最终写入。
- 当前身份边界是 `project_id`，默认值为 `default`；没有 `user_id`、认证或授权模型。9A 应沿用 `project_id` 隔离，不提前设计多用户权限。
- 当前 source of truth 是 `projects`、`materials`、`extractions`、`text_spans`。`material_revisions`、`chunks`、retrieval、citations、AI operations 和 Cards/Exercises 是派生数据或用户状态。
- 当前 Cards/Exercises 已有独立 citation 表和 source lifecycle refresh 逻辑，可作为 9A source-link contract 的参考；不应直接把 `card_citations` 或 `exercise_citations` 复用为计划领域表。
- backup 通过 SQLite Online Backup API 快照数据库，因此新增 SQLite 表天然进入数据库备份；manifest 当前记录 database hash、integrity、foreign-key、schema version 和 originals 引用，未逐表列举业务对象。
- 当前 UI 是 `backend/app/main.py` 中生成的内嵌 HTML/JavaScript 单页，不是独立前端工程。Materials、Q&A、Cards/Exercises 共用页面导航、状态区和 workspace 风格。
- 当前没有学习目标、知识模块、study plan/item、dependency 或 progress event 表、repository、API 或 UI。Phase 9A 必须从正式 contract 开始，不能把历史版本实现当作已存在能力。

## 2. 9A 术语候选

以下是 9A-1 需要冻结的候选 glossary：

| 术语 | 当前候选含义 | 当前状态 |
|---|---|---|
| Learning Goal | 用户希望达成的学习方向或结果，可作为一个或多个计划的上层目标 | 候选，未实现 |
| Knowledge Module | 可复用的学习主题/知识单元，保存结构化标题和描述，并可关联正式 source revision/citation | 候选，未实现 |
| Study Plan | 一组有序学习项的用户计划，候选生命周期为 draft → confirmed/active → paused/completed/archived | 候选，未实现 |
| Study Plan Item | 计划中的一个可跟踪学习项，可关联 module、revision/citation、deck 或 exercise set | 候选，未实现 |
| Dependency | 计划项之间的 prerequisite 关系 | 候选，未实现 |
| Progress Event | 描述某项进度事实的 append-only 记录 | 候选，未实现 |
| Progress Summary | 从 progress event 和当前计划项状态计算出的展示摘要 | 候选，未实现 |
| Source Link | 计划对象到 material revision/chunk/span/citation 的安全引用关系，不复制正文 | 候选，未实现 |
| User-edited | 用户对 draft 或 item 内容做过显式修改的保护标记 | 需与领域状态一起冻结 |

这些词不表示前代 `KnowledgeModule`、历史 study plan 或其它参考项目已被正式系统吸收。

## 3. 当前实现审计

### 3.1 Schema 与 migration

**源码：** `backend/app/migrations/runner.py`

- `CURRENT_SCHEMA_VERSION = 8`（第 9 行）。
- `HISTORY_TABLE = "schema_migrations"`（第 10 行）。
- `_MIGRATIONS`（约第 455–465 行）注册：
  1. `canonical_material_schema`
  2. `ai_phase0_schema`
  3. `phase5_provider_metadata`
  4. `qa_operation_idempotency`
  5. `phase7_embedding_schema`
  6. `search_index_schema_contract`
  7. `phase8_cards_exercises_schema`
  8. `phase8_exercise_provenance`
- `migrate()` 使用 `BEGIN IMMEDIATE`，逐个执行 migration 并插入 history；最后设置 `PRAGMA user_version` 并 commit。`MigrationError` 或 SQLite/OSError 会 rollback。
- `_baseline_complete()` 只允许已知且完整的当前基础对象通过；未知 future version、history mismatch、缺失 required object 不会被启动自动修复。
- 当前新 Phase 9A 应新增 v9 或后续连续版本，不应修改 v1–v8 history，也不应在连接初始化时 ad-hoc 建表。

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
- 当前 repository 没有通用 domain service 层；9A-3 需要决定是在 repository 内增加小型领域函数，还是新增专门的 `study_plans.py`/domain 模块，但不得把所有业务继续堆入不可测试的 API handler。

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
- 9A-5 可以复用 study workspace/navigation/status/toast/busy/stale-response 模式，但应新增独立 DOM contract，不改变 Cards/Exercises 既有路径。

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

具体字段、状态、是否纳入 pause/archive/complete、AI draft 以及 source link 层级必须在 9A-1 冻结。

### 4.2 明确排除

9A 不实现：

- 9B S1/S2：学习节奏、资料笔记、完整资料学习/知识模块工作流；
- 9C S3/S4/S5：限时练习、错题改错、期末冲刺、人工简答复核；
- 9D S6/S7：家长报告、课堂采集、OCR、ASR、外发交付；
- Phase 10：worker、queue、scheduler、cancel、长任务恢复、多用户、认证授权、云同步、协作；
- 提醒、推送、日历、recurrence、自动每天规划、自动 re-plan、后台进度扫描；
- 外部 vector DB、历史材料自动索引、真实 Provider plan generation 作为 9A 完成前置；
- 复杂推荐、评分、教师/家长视图和国际化。

### 4.3 不变量候选

以下候选不变量必须在 9A-1 变成正式 contract 或明确延期：

- 所有 9A 对象按 `project_id` 隔离，客户端不能跨 project 读取或修改；
- source link 只保存 identity/受限 metadata，不复制正文；
- plan/item 的状态转移由服务端校验，非法转移不会部分写入；
- dependency 必须拒绝自依赖和环依赖；若允许跨 plan，必须验证同 project 和生命周期；
- progress history append-only，summary 可以从事件和当前 item 事实重算；
- confirmed、active、completed 或 user-edited 内容不得被重新生成静默覆盖；
- source purge 保留用户计划和进度历史，但 source link 只能显示 unavailable，不能伪造可定位来源；
- restore/verify/startup/read 不自动 repair、rebuild、重新生成或升级 source link；
- 所有 migration history、`user_version` 和 backup manifest schema version 一致；
- 错误和日志不泄露路径、SQL、正文、secret、raw provider response 或 traceback。

## 5. 候选实体关系（待 9A-1 冻结）

一个保守候选关系如下，不是最终 schema：

```text
project
  ├── learning_goals
  │     └── study_plans (可能一对多；是否允许无 goal 待定)
  ├── knowledge_modules (可复用；是否直接挂 goal 待定)
  └── study_plans
        ├── study_plan_items
        │     ├── optional module reference
        │     ├── optional deck/exercise_set reference
        │     └── source links (revision/chunk/span/citation identity)
        ├── dependencies (DAG)
        └── progress_events
```

待决问题：

1. goal 与 plan 是一对多还是多对多？一个 plan 是否必须绑定 goal？
2. module 是否独立于 goal，并允许被多个 plan/item 复用？
3. source link 绑定 module、plan、item，还是允许多层但只保留一种 canonical link？
4. item 是否允许没有 source，尤其是用户自定义计划项？
5. dependency 是否只允许同一 plan 内？是否只允许 DAG？
6. active plan 遇到 unavailable source 是阻止激活还是允许激活并显示 warning？
7. progress event 支持哪些事件：started、completed、skipped、reopened、cancelled？是否允许撤销完成？
8. `paused`、`completed`、`archived` 是否全部属于 9A，还是先只做 draft/confirmed/active？
9. 是否支持 due date/timezone；若支持，是否只保存 UTC instant，不支持 recurrence？
10. 9A 是否支持 fake-provider 生成 plan draft，还是只实现用户手工 draft，把 AI re-plan 留到后续？
11. 是否需要新 `ai_operations.operation_type`，以及 operation 与 plan draft 的原子关系？
12. 删除 goal/module/plan/item 采用 archive、soft delete、禁止删除还是有限制的 cascade？
13. 是否需要保存 summary snapshot，还是每次从 append-only event 计算？

这些问题必须在 9A-1 解决，未解决前不得开始 9A-2 migration。

## 6. 9B/9C/9D 边界

- 9B 可以复用 9A 的 KnowledgeModule、source link 和 plan item，但必须单独设计资料笔记/学习节奏 API、UI、状态和 evidence。
- 9C 可以复用 9A 对 deck/exercise set 的引用以及 Phase 8 attempt/grading，但限时、错题和冲刺仍是独立 domain，不在 9A 添加专用表或 scheduler。
- 9D 在需求、隐私、保留策略、真实组件证据和运维成本评审通过前不立项；9A 不预留 OCR/ASR/report 业务表。
- 9A 完成不代表以上任何子阶段实现，也不代表 Phase 9 完成。

## 7. 9A-0 验收与下一步

### 已完成的 9A-0 审计输出

- 当前 migration version、history 和 rollback 机制已定位；
- repository 事务边界和 ID/time/project 约定已定位；
- material revision/citation、Cards/Exercises source lifecycle 已定位；
- backup/restore 全 SQLite snapshot 与 non-repair 边界已定位；
- main.py 路由、内嵌 UI、测试 fixture 和 browser 运行方式已定位；
- 9A 纳入范围、明确排除、候选不变量、关系候选和待决问题已记录。

### 9A-0 的准确状态

`Phase 9A-0 planned/audit-draft`：审计和范围冻结文档已形成；没有实现学习目标、知识模块、计划、计划项、依赖或进度能力；没有新增 migration、业务表、API 或 UI。

### 下一步

进入 9A-1 前，产品/领域决策至少需要确认第 5 节的关系、状态、progress、source link、日期和 AI draft 问题。9A-1 只冻结契约，不实现 schema；契约冻结后才进入 9A-2。
