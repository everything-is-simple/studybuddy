# Phase 9B 资料学习工作流（S1/S2）现状审计与范围冻结初稿

> 状态：`planned/audit-draft`。
>
> 本文是 9B-0 的现状审计、候选边界和待决策记录，不是 9B-1 的正式契约冻结，也不是实现证据。当前没有为 Phase 9B 修改生产代码、migration、API 或 UI。
>
> 审计依据：当前 `H:\studybuddy` 正式源码、正式测试和权威文档。历史项目和 [`HISTORICAL_SCENARIO_REVIEW.md`](../HISTORICAL_SCENARIO_REVIEW.md) 只作为需求线索，不作为正式系统完成证据。

## 1. 审计结论摘要

### 1.1 当前正式基线

- 当前 schema version 是 **9**。`backend/app/migrations/runner.py` 定义 `CURRENT_SCHEMA_VERSION = 9`，`_MIGRATIONS` 连续注册 v1–v9；v9 名称为 `phase9a_learning_plan_schema`。
- `backend/app/migrations/runner.py:migrate()` 使用 `BEGIN IMMEDIATE`、migration history 和 `PRAGMA user_version`，失败时 rollback；Phase 9B 后续 schema 只能追加 v10 或更高连续 migration，不能修改 v1–v9。
- 当前 project scope 由 `AppConfig.project_id` 注入 API，默认值为 `default`。当前没有 `user_id`、认证、授权或多用户模型。
- 当前 source of truth 仍是 `materials`、`extractions`、`text_spans`。revision、chunk、embedding、retrieval、citation、AI operation、Cards/Exercises 和 9A 学习计划对象均不是原始材料 source of truth。
- Phase 9A 已经不是“只有设计”：当前正式代码、API、测试和浏览器测试已经实现 goal、knowledge module、study plan/item、dependency、append-only progress、source links 及其 source lifecycle。9A 限定范围的最终证据见 `docs/PHASE9A_ACCEPTANCE_EVIDENCE.md`。
- 当前没有 note、note block、note revision、note-to-module relation、资料笔记正文 artifact、节奏配置、学习时段、工作量分配、节奏时间线或节奏 summary 的正式对象。

### 1.2 Phase 9B 审计结论

Phase 9B 需要在已有 9A 计划核心之上新增两条不同但有关联的用户路径：

```text
S1 学习节奏：已有 plan/item/progress
  → 显式节奏配置、工作量/时段分配、时间线和可重算 summary

S2 资料笔记：已有 material/revision/chunk/retrieval/citation/module
  → 用户笔记、证据关联、知识模块整理、可选 fake-provider draft
```

建议保持两个事实源边界：

- S1 不再建立第二套计划或进度事实源，应扩展 Phase 9A 的 `study_plans`、`study_plan_items` 和 `study_progress_events` 语义，或增加与其明确关联的节奏表。
- S2 不把 `knowledge_modules.description` 误当作资料笔记系统。当前 `knowledge_modules` 只有标题、描述、生命周期和 project scope；正式 note/block/artifact 必须单独建模或通过契约明确说明为什么不需要单独对象。
- S2 的 source link 应继续保存 revision/chunk/span/citation identity，不复制材料正文；需要展示正文时复用当前 source/citation 读取和 unavailable contract。
- AI 生成的 note/module 内容只能是 draft，必须通过现有 retrieval/context/citation 验证和用户显式确认；真实 Provider generation 不应成为 9B 的完成前置。

## 2. 当前实现证据表

### 2.1 Migration、数据库和事务

| 能力 | 当前事实 | 源码/测试证据 |
|---|---|---|
| schema version | 当前为 v9 | `backend/app/migrations/runner.py:CURRENT_SCHEMA_VERSION`；`docs/MIGRATIONS.md` |
| migration history | v1–v9 连续，v9 为 9A 学习计划 schema | `backend/app/migrations/runner.py:_MIGRATIONS`；`backend/tests/test_migrations.py` |
| migration rollback | migration 在事务中执行，失败回滚 | `backend/app/migrations/runner.py:migrate()`；`test_failed_migration_rolls_back_and_uses_stable_error` |
| 9A 表 | 已有 `learning_goals`、`knowledge_modules`、`study_plans`、`study_plan_items`、`study_plan_dependencies`、`study_progress_events`、`module_source_links`、`plan_item_source_links` | `backend/app/migrations/runner.py:_migration_v9()`；`backend/tests/test_migrations.py` |
| connection | 设置 foreign keys、WAL、busy timeout；连接时执行 migration 和 schema assertion | `backend/app/repository.py:connect()` |
| 写事务 | 主要 repository 写操作用 `with connection:`；长 AI 流程在 Provider I/O 前后分离事务 | `backend/app/repository.py` 中 9A、Cards/Exercises、embedding 和 generation functions |
| project scope | API 使用 `app.state.config.project_id`，客户端不能选择任意 project | `backend/app/main.py:create_app()` 和 study routes；`backend/app/config.py` |

### 2.2 Phase 9A 学习计划核心

| 能力 | 当前事实 | 源码/测试证据 |
|---|---|---|
| goal/module | create、list、detail、patch、archive | `backend/app/repository.py:create_learning_goal()`、`create_knowledge_module()` 等；`backend/app/main.py` `/api/study/goals*`、`/api/study/modules*` |
| plan | draft、confirm、active、paused、completed、archived | `backend/app/repository.py:transition_study_plan()`；`backend/app/main.py` `/api/study/plans/{plan_id}/*` |
| plan item | title/description/position，引用 module/deck/exercise set；draft/confirmed 可编辑 | `backend/app/repository.py:create_study_plan_item()`、`update_study_plan_item()` |
| dependency | same-plan dependency，repository 做 cycle detection，数据库做 self-edge/unique 约束 | `backend/app/repository.py:add_study_plan_dependency()`；`backend/tests/test_phase9a_domain.py:test_dependency_rejects_self_and_cycles_atomically` |
| progress | `started`、`completed`、`skipped`、`reopened`，event append-only，item projection 同事务更新 | `backend/app/repository.py:append_study_progress_event()`；`backend/tests/test_phase9a_domain.py:test_progress_is_append_only_and_summary_recomputes` |
| summary | 从当前 item projection 查询计算，不保存独立 summary snapshot | `backend/app/repository.py:study_progress_summary()` |
| source links | 当前只有 module source link 和 plan-item source link，没有 note source link | `backend/app/migrations/runner.py:_migration_v9()`；`backend/app/repository.py:create_module_source_link()`、`create_plan_item_source_link()` |
| 9A browser path | 创建 goal/module/plan、添加 item/dependency、cycle failure、confirm/activate、完成 item、reload | `backend/tests/browser_phase9a.spec.js` |

### 2.3 Material、revision、chunk、retrieval、citation

| 能力 | 当前事实 | 源码/测试证据 |
|---|---|---|
| source layer | materials/extractions/text_spans 是原始资料层 | `backend/app/migrations/runner.py` v1 schema；`backend/app/repository.py:save_material_with_extraction()` |
| revision | 显式 `index_material_revision()` 创建/复用 current revision | `backend/app/repository.py:create_or_get_revision()`、`index_material_revision()`；`backend/tests/test_ai_indexing.py` |
| chunk | deterministic chunk、chunk spans、显式 indexing | `backend/app/chunking.py`、`backend/app/repository.py:index_material_revision()` |
| lexical retrieval | chunk FTS5 retrieval、active/current/ready 过滤、top-k 和 empty 语义 | `backend/app/repository.py:run_chunk_retrieval()`；`backend/tests/test_retrieval.py` |
| vector/hybrid | vector cosine、hybrid RRF、fallback 已实现 | `backend/app/repository.py:run_vector_retrieval()`、`run_hybrid_retrieval()`；Phase 7 tests |
| context/citation | context assembly 产生 citation candidates；citation key 由服务端验证 | `backend/app/repository.py:assemble_context()`、`validate_citation_key()`；`backend/tests/test_context_assembler.py`、`test_ai_citation_lifecycle.py` |
| source lifecycle | delete/restore/purge/re-index 会使相关 citation/source link 进入 deleted/stale/unavailable 等状态；恢复后显式 refresh 语义由 9A 测试覆盖 | `backend/app/repository.py:_study_source_status()`、`refresh_study_source_links()`、`purge_material()`；`backend/tests/test_phase9a_source_lifecycle.py`、`browser_phase9a.spec.js` |

### 2.4 Cards/Exercises 和 AI generation

| 能力 | 当前事实 | 源码/测试证据 |
|---|---|---|
| Cards/Exercises schema | v7/v8 已有 deck/card/exercise/citation/review/attempt 和 exercise provenance | `backend/app/migrations/runner.py:_migration_v7()`、`_migration_v8()`；`backend/tests/test_migrations.py` |
| artifact lifecycle | draft → ready/rejected/archived，另有 stale citation/source 状态 | `backend/app/repository.py` Cards/Exercises functions；`backend/tests/test_phase8_cards.py`、`test_phase8_exercises.py` |
| edit protection | draft-only edit，ready/archived 不允许普通 API 静默覆盖 | `backend/app/repository.py:update_card()`、`update_exercise()`；`backend/tests/test_phase8_cards.py`、`test_phase8_exercises.py` |
| generation | 当前 generation operation 只允许 `artifact_kind` 为 `card` 或 `exercise` | `backend/app/repository.py:create_generation_operation()` |
| provider validation | retrieval → context → Provider → structured in-memory validation → citation revalidation → atomic draft persistence | `backend/app/main.py:generate_draft()`；`backend/app/repository.py:persist_generated_draft()`；`backend/tests/test_phase8_generation.py` |
| fake provider | 有 deterministic fake LLM provider；Provider registry 不读取文件或直接操作数据库 | `backend/app/providers.py:FakeLLMProvider`、`ProviderRegistry` |
| note generation | 当前不存在 note/module generation operation 或 note artifact persistence | `backend/app/repository.py:create_generation_operation()` 的 artifact 限制；`backend/app/main.py:GenerationRequest` 和 Cards/Exercises routes |

### 2.5 API、UI、导出和恢复

| 能力 | 当前事实 | 源码/测试证据 |
|---|---|---|
| API style | FastAPI routes、Pydantic request models、stable `detail` error codes；study routes 位于 `create_app()` | `backend/app/main.py` 的 request models 和 `/api/study/*` routes |
| UI architecture | 内嵌 HTML/JavaScript 单页，共用 Materials、Q&A、Cards/Exercises、Plans 导航和状态模式 | `backend/app/main.py` `/` route 及内嵌 HTML/JS；`browser_phase9a.spec.js` |
| existing plan UI | goal/module/plan list、draft edit、item/dependency、status/progress/source warning | `backend/app/main.py` `renderPlanDetail()`、`refreshPlans()`、`selectPlan()` |
| note UI | 没有 note、note block 或 knowledge-module evidence workspace | `backend/app/main.py` 页面 DOM 和 JS 全文审计；无 note routes/DOM identifiers |
| rhythm UI | 没有节奏、时段、workload、timeline 或 cadence controls | `backend/app/main.py` plan models/routes/JS；`backend/tests/browser_phase9a.spec.js` |
| material export | 单材料 original/text 和批量 original/text/bundle ZIP；未覆盖 study artifacts | `backend/app/main.py` `/api/materials/{material_id}/original`、`/text`、`/api/materials/export`；`backend/tests/browser_material_export.spec.js` |
| database backup | SQLite Online Backup API 快照完整数据库；新增 SQLite 表会随 database snapshot 进入备份 | `backend/app/backup.py:backup_data()`；`docs/BACKUP_RESTORE.md` |
| restore acceptance | 当前 `restore_acceptance.py` 的业务检查覆盖 9A 对象；9B 新表/对象需要扩展专门断言 | `backend/app/restore_acceptance.py:_study_checks()`、`verify_restored_data()`；`backend/tests/test_phase9a_backup_restore.py` |
| non-repair | verify/restore/startup/read 不 migrate、rebuild、Provider generate 或自动 repair source state | `backend/app/backup.py`、`restore_acceptance.py`、`backend/app/main.py:lifespan()`；9A backup/restore tests |

## 3. 可复用能力与必须新增能力

### 3.1 可以复用的正式能力

1. **Project scope 与事务模式**：沿用 `project_id`，不引入 user/auth；所有跨对象关系在 repository/domain transaction 中验证。
2. **Materials source contract**：note/module 只关联 material/revision/chunk/span/citation identity，不替代原始材料。
3. **Retrieval/context/citation pipeline**：S2 draft 生成应复用 `run_chunk_retrieval()`、vector/hybrid mode、`assemble_context()` 和 `validate_citation_key()`，不能让模型自造 citation。
4. **Source lifecycle vocabulary**：复用 `valid`、`source_deleted`、`source_unavailable`、`stale`，并保持 explicit refresh/non-repair 行为。
5. **9A plan/progress**：S1 应复用已有 plan/item/progress，不创建平行的 task/event 事实源。
6. **Draft/edit protection**：复用 Phase 8 的 draft-first、用户编辑保护、确认/拒绝/归档和 operation metadata 原则。
7. **API/UI safety**：复用现有 stable error、status/alert、toast、busy guard、stale response、safe DOM text 和窄屏/键盘测试模式。
8. **Backup/restore**：复用 SQLite snapshot、manifest/schema checks、新空目录 restore 和 non-repair boundary，但增加 9B 专项验证。

### 3.2 必须新增或重新定义的能力

#### S1

- rhythm/cadence 的正式概念和时间计算规则；
- 与已有 plan/item/progress 的关联；
- 可用学习时段、工作量单位和分配事实；
- timeline/load/overdue 或 unassigned summary 的定义；
- 日期、timezone、DST 和跨周期边界；
- 明确“显式同步计算”与“后台 scheduler”的边界；
- S1 API、UI、failure contract、导出和 backup/restore 证据。

#### S2

- note、note block 或等价最小内容对象；
- note/module 的关系和 source/citation 绑定层级；
- 用户笔记、AI draft、confirmed artifact 的状态与编辑保护；
- note/module 的多 material、多 revision 或单 source 范围；
- note/module 读取、编辑、归档、导出和 source refresh；
- 可选 fake-provider note/module generation 的 operation type、结构化输出、幂等和 retry；
- S2 API、UI、failure contract、source lifecycle 和 backup/restore 证据。

## 4. S1 候选最小范围

以下是供 9B-1 决策的候选范围，不是冻结契约。

### 4.1 建议目标

S1 的最小用户路径建议是：

```text
选择一个已有 Phase 9A plan
→ 设置明确的 cadence/timezone/周期边界
→ 为 plan item 记录估计工作量和显式安排
→ 查看按周期的 timeline/load/unassigned summary
→ 手动调整安排
→ 完成 plan item
→ 从已有 progress event 和节奏事实重新计算 summary
→ reload 后从服务端恢复
```

### 4.2 建议边界

- S1 不应建立独立的 `StudyTask` 或 `StudyEvent` 事实源；如果需要新表，应明确其只是 schedule/rhythm projection 或用户安排事实，并与 `study_plan_items`、`study_progress_events` 建立单向关系。
- cadence 初版应选择有限且可测试的模型，例如 daily/weekly，而不是一开始支持任意 recurrence。
- 所有时间应保存明确的 UTC instant 或明确的 date + timezone 组合；不能将宿主机本地时间直接当作业务时间。
- 不引入 due-date reminders、calendar sync、push、自动排程、后台扫描、自动 re-plan 或按时间自动改变 progress。
- “逾期”只有在 9B-1 冻结了 date/timezone 语义后才可纳入；否则使用 `unassigned`、`planned_minutes`、`completed_minutes` 等确定性 summary，避免伪造时间语义。

### 4.3 S1 待决问题

- 节奏是固定 daily/weekly，还是允许自定义周期？
- 工作量单位是 minutes、sessions、items，还是只允许 minutes？
- 一个 item 是否允许拆分到多个周期/时段？
- 是否允许计划项没有安排？
- 是否需要显式学习 session，还是仅保存 item allocation？
- progress event 是否增加节奏 metadata，还是保持 9A event schema 不变？
- 是否需要导出节奏视图，还是复用计划/材料导出之外的 JSON/CSV？
- completed item 的 schedule 是否只读、可移动，还是保留历史安排并新增调整记录？

## 5. S2 候选最小范围

### 5.1 建议目标

S2 的最小用户路径建议是：

```text
选择 active 且已建立索引的材料
→ 创建用户 note
→ 选择一个或多个已验证 citation/source
→ 编辑 note 内容或 block
→ 创建/关联 knowledge module
→ 可选生成 citation-safe fake-provider draft
→ 查看 draft 来源
→ 用户编辑、确认、拒绝或归档
→ 显式刷新 source 状态
→ 导出受控 note/module 内容
→ reload 后恢复
```

### 5.2 现有 module 的准确定位

当前 `knowledge_modules` 是 9A 的可复用元数据对象，字段为标题、描述、状态和时间字段。它目前不是：

- 资料笔记正文；
- note block 容器；
- AI generation artifact；
- 自动从材料抽取的知识点；
- 自带 source citation 的完整知识模块。

因此 9B-1 必须决定是：

1. 新增 note/note-block，并让 module 通过显式 link 关联 note；或
2. 让 module 直接承载受限用户内容，但必须补齐版本、编辑保护、citation/source lifecycle 和 draft 语义。

在没有契约决定前，不应直接给 `knowledge_modules` 增加正文 JSON 或把 description 扩展成隐式笔记字段。

### 5.3 S2 待决问题

- note 是否允许完全没有 source？建议允许用户笔记无 source，但 AI-generated draft 必须有可验证 source/citation。
- note 是否由多个 block 构成？如果是，citation 应绑定 note 还是 block？建议以最小可定位单元绑定 block，同时提供 note-level summary。
- note/module 是否允许关联多个 material/revision？多 source 更符合资料整理，但会增加 revision lifecycle 和 UI 复杂度。
- source quote 是否保存？当前 citation 体系有受限 quote，但 source link 不应复制正文；需要区分 citation display cache 与 source truth。
- note 是否需要 revision history？用户编辑保护需要至少有明确状态和 append/replace 语义；是否保存完整版本历史需单独决策。
- AI draft 与用户 note 是同一个 artifact 的状态，还是 draft note 确认后生成新的 user note？必须避免 retry 覆盖用户内容。
- knowledge module 是用户整理对象、AI draft 目标，还是两者都支持？其 provenance 必须明确。
- source unavailable 时 active note/module 是保留内容并警告，还是禁止 confirm？建议保留 artifact 和历史，禁止伪造 citation，具体由 9B-1 冻结。
- fake-provider generation 是否新增 `ai_operations.operation_type`，还是复用 generic generation operation？现有 generation repository 只支持 card/exercise，不能未经设计直接调用。
- note/module export 是纯文本、Markdown、JSON，还是多种格式？必须定义 privacy、filename、citation unavailable 和 failure contract。

## 6. Source/citation 复用候选

当前 9A source link 的状态判断可以作为行为参考，但不应直接把 source link 当作 note content。推荐 9B 继续采用以下原则：

```text
materials/extractions/text_spans
        ↓
material_revisions/chunks/chunk_spans
        ↓
retrieval_runs/retrieval_hits/context blocks
        ↓
verified citation identity
        ↓
user note/module source association
```

必须保持：

- 客户端提交的 revision/chunk/span/citation 由服务端重新验证；
- source link 只存 identity 和受限 metadata，不存 stored_path 或正文全文；
- deleted material 不再是可用来源；
- purge 后历史 note/module 保留，但 citation/source 显示 `source_unavailable`；
- stale revision/chunk 不得显示为 valid；
- restore/read/backup/verify 不自动提升状态；
- 需要恢复 valid 时使用显式 refresh，并证明它没有重新生成 note/module。

需要在 9B-1 决定是否复用现有 `module_source_links`：

- 复用的优点：减少表和 lifecycle 代码，knowledge module 已有 source link。
- 复用的风险：当前 link 只有 module/source identity，没有 note/block owner；无法表达 note 的多 block provenance，也无法表达用户编辑和 AI draft provenance。
- 初步建议：保留现有 9A module source link 兼容性，新增 note/block 专属 link 或受限关联表，不改变 9A link 的既有语义。

## 7. Backup、导出和恢复审计结论

### 7.1 Backup/restore

当前 `backend/app/backup.py:backup_data()` 对完整 SQLite database 使用 Online Backup API，因此未来 9B SQLite 表在物理层面会天然进入数据库快照。当前 manifest 不逐表列举业务对象，但包含 database hash、integrity、foreign key、schema version 和 originals 清单。

这不等于 9B 已经有 restore evidence。9B-8 仍必须验证：

- 新增 note/block/module relation、rhythm allocation 和 AI operation metadata 在 backup/restore 后存在；
- draft、user-edited、confirmed、archived、stale、source_unavailable 状态保持；
- progress event 和 rhythm summary 不发生隐式变化；
- restore/read/verify/startup 不调用 Provider、不生成 note、不重建 chunk、不 repair source state；
- 新增表不会造成 foreign key 或 restore acceptance 失败。

`backend/app/restore_acceptance.py:_study_checks()` 当前专门检查 9A 表和计划投影。9B 实现后需要扩展对应 acceptance，但只能在 9B-8/9B-9 中完成，不能在 9B-0 修改生产逻辑。

### 7.2 导出

当前正式导出只覆盖 materials：

- `/api/materials/{material_id}/original`；
- `/api/materials/{material_id}/text`；
- `/api/materials/export` 的 original/text/bundle ZIP。

当前没有计划、module、note 或 rhythm export。9B 必须先定义导出资源和格式，再由后续 API/UI 任务复用安全的 fetch/blob/error contract。不得把服务器路径、原始 provider response 或不可验证 source quote 写入导出。

## 8. 明确纳入和排除范围

### 8.1 计划纳入 Phase 9B

#### S1 学习节奏

- 复用 Phase 9A study plan/item/progress；
- 显式节奏配置；
- 有确定性日期/timezone/周期定义的学习安排；
- item 工作量或安排事实；
- timeline/load/unassigned 等只读 summary；
- 用户手动调整；
- API、最小 UI、失败、reload、导出和 backup/restore；
- 与 active/deleted/stale/source_unavailable 的状态展示保持一致。

#### S2 资料笔记

- 用户 note 和/或 note block；
- note 与材料 revision/chunk/span/citation 的安全关联；
- knowledge module 与 note 的明确关联或明确的内容承载契约；
- 用户编辑、确认、拒绝、归档和 source refresh；
- deterministic fake-provider 下可选的 citation-safe draft generation；
- API、最小 UI、失败、reload、导出和 backup/restore；
- 真实 source lifecycle 和不可伪造 citation。

### 8.2 明确排除

Phase 9B 不实现或不作为完成前置：

- S3 限时练习、S4 错题改错、S5 期末冲刺；
- S6 家长报告；
- S7 课堂采集、OCR、ASR；
- 真实 Provider 下 note/module/plan generation 的 real-pass；
- 人工简答复核和教师/家长审核；
- reminders、push、calendar sync、recurrence engine、background scheduler；
- worker、queue、cancel、长任务恢复、跨进程协调；
- 多用户、认证授权、云同步、协作；
- 外部 vector DB；
- 自动索引历史材料、自动重建 note/module、自动 re-plan；
- 复杂导图/图数据库/语义图谱；除非 9B-1 明确纳入最小范围，否则不实现导图或额外图模型；
- 国际化、系统级 screen reader、极端长内容和长时间稳定性作为本 Phase 的默认通过条件。

## 9. 风险与开放问题

### 9.1 高风险

1. **S2 对象膨胀风险**：note、block、module、citation、版本、draft、source link 如果一次全部设计，容易重复 9A/Phase 8 对象。9B-1 必须先冻结最小 artifact 边界。
2. **知识模块语义冲突**：9A 的 module 是可复用 metadata；历史系统的 KnowledgeModule 还包含 AI 拆分、重点和证据。不能用同名对象直接吸收历史语义。
3. **S1 第二套计划事实源风险**：历史 `StudyTask/StudyEvent` 不能直接复制。节奏必须成为 9A plan/item 的显式扩展或受控安排投影。
4. **AI generation transaction 风险**：当前 `create_generation_operation()`/`persist_generated_draft()` 只支持 Cards/Exercises。S2 若复用必须先扩展 contract；Provider I/O 不能持有长事务，失败不能留下半成品或覆盖用户内容。
5. **source lifecycle 扩散风险**：note/module 与多个 revision/material 关联后，delete/restore/purge/re-index 的状态可能比 9A module link 更复杂；必须有表级和用户路径测试。
6. **时间语义风险**：S1 如果未冻结 timezone、date-only、DST 和周期边界，会产生宿主机相关的不可复现结果。
7. **导出隐私风险**：笔记可能包含用户正文、AI draft、citation 和 source unavailable 历史；导出格式和字段必须先定义，不能直接 dump 数据库行。

### 9.2 中风险

1. `module_source_links` 当前对 module/citation 的 unique 约束和 note/block 多来源模型可能不兼容。
2. 9A source link 的 material/revision/chunk foreign key 使用 `ON DELETE SET NULL`，purge 后的 link 状态需要在删除顺序和显式 refresh 上保持一致。
3. 当前内嵌单页 `main.py` 已包含较大的 Materials/Q&A/Study/Plans workspace；S1/S2 UI 继续堆入同一文件会增加 stale response、DOM contract 和回归风险。
4. 当前 `ai_operations` schema 可记录 operation metadata，但没有通用 artifact table 或 note-specific output linkage；S2 需要避免只保存一个不透明 `output_artifact_id`。
5. 当前默认测试 fixture 没有用户、认证或多 project UI；不能从 project scope 测试推断多用户安全。

## 10. 建议的后续子任务边界

本审计建议保留 prompt 包中的 9B-0 至 9B-9 划分：

| 子任务 | 审计后的单一责任 | 9B-0 发现的阻塞 |
|---|---|---|
| 9B-0 | 审计、范围和风险初稿 | 本文完成后进入契约决策 |
| 9B-1 | 冻结 S1/S2 对象、状态、时间、source/citation、导出和错误契约 | 必须先解决 note/module 关系、节奏模型、AI draft 边界 |
| 9B-2 | 追加 migration/schema | 等 9B-1；不得提前假定表结构 |
| 9B-3 | 共用 repository/domain transaction | 等 schema；必须处理跨 project/source/编辑保护 |
| 9B-4 | S2 note/module 工作流和 fake draft | 依赖 note/block/provenance 契约与 retrieval/citation contract |
| 9B-5 | S1 rhythm 工作流 | 依赖 timezone/cadence/workload 契约和 9A plan/item |
| 9B-6 | API boundary | 依赖 S1/S2 domain API resource 和稳定错误 |
| 9B-7 | Chromium workspace | 依赖 API；必须避免继续扩大内嵌页面范围 |
| 9B-8 | source lifecycle、backup/restore/non-repair | 依赖新表、artifact 和 lifecycle 完成；需要扩展 restore acceptance |
| 9B-9 | full regression、evidence、文档收口 | 所有 gates 通过前不能标记 completed |

9B-4 和 9B-5 只有在 9B-1/9B-2/9B-3 完成后才可考虑并行；正式推荐继续串行执行。

## 11. 9B-0 结论与下一步

### 当前状态措辞

> Phase 9B 当前为 `planned/audit-draft`。现状审计已完成，S1/S2 的正式对象、状态机、时间语义、source/citation 绑定、AI draft persistence 和导出格式仍需在 9B-1 中冻结。当前没有正式 note 工作流或学习节奏实现。

### Gate A 结论

- 当前实际 schema、9A、Phase 8、source/retrieval/citation、API/UI、导出、backup/restore 和测试边界已完成审计。
- S1/S2 的最小方向和明确 non-goals 已记录。
- 风险和关键开放问题已记录。
- 未修改生产代码、migration、API 或 UI。

因此 9B-0 可进入后续的：

```text
9B-1：正式领域契约与状态机
```

9B-1 必须先解决本文第 4、5、6、7、9 节的开放决策，之后才能进入 migration。9B-0 不允许使用 `implemented`、`backend-pass`、`browser-pass`、`real-pass` 或 `Phase 9B completed`。
