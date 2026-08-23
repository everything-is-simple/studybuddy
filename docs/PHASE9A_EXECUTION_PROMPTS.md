# Phase 9A 执行 Prompt 包：学习领域基础与计划核心

> 状态：planned，仅为执行上下文与任务拆分，不代表任何 Phase 9A 能力已实现。
>
> 本文是 Phase 9A 的执行 prompt 包。每次实现只使用一个子任务 prompt；完成一个子任务后，必须通过其门禁并同步事实文档，再进入下一个子任务。不得把本文中的设计、任务或 prompt 解释为代码完成证据。

## 使用规则

1. 执行 agent 必须先读取仓库根目录 `AGENTS.md`，再读取本文列出的权威文档和实际源码。
2. 每个子任务是独立提交候选，禁止一次性实现整个 9A。
3. 先冻结契约，再做 migration，再做 repository/domain，再做 API，再做 UI，再做 source lifecycle 与 backup/restore，最后 closeout。
4. 除非子任务明确要求，否则不要修改不相关的 Phase 8、Provider、Embedding、Material 导入逻辑。
5. 所有新业务表只能通过 `backend/app/migrations/runner.py` 的连续 migration 建立；禁止运行时建表。
6. 默认测试使用 `C:\miniconda\py310\python.exe -m pytest backend/tests/`；真实 Provider 不属于默认门禁。
7. 不提交数据库、originals、secrets、provider keys、私有路径、Playwright 输出、临时 session HTML 或未脱敏 artifact。
8. `implemented`、`backend-pass`、`browser-pass`、局部 `real-pass`、`not_verified` 必须严格区分。Phase 9A 完成不等于 Phase 9 完成，也不等于全局 production `real-pass`。

---

# 一、所有子任务共用的充分上下文 Prompt

以下内容应作为每一个 9A 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中实现 StudyBuddy Phase 9A 的一个明确子任务。

StudyBuddy 是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 学习材料系统。正式代码只能放在 backend/app/，正式测试只能放在 backend/tests/，长期文档只能放在 docs/。不得复制 Composer、Integration 或历史项目源码作为正式实现；历史项目只能提供需求线索，正式实现必须基于当前源码和已验证 contract 重新实现。

当前已完成的基础能力：
- materials、extractions、text_spans 是原始资料 source of truth；
- material active/deleted/restored/purged 生命周期；
- material_revisions、deterministic chunks、chunk_spans；
- lexical/vector/hybrid retrieval、retrieval_runs/hits、context assembly；
- server-side citation 验证和 citation source lifecycle；
- Q&A、ai_operations、deterministic fake provider，以及精确范围的真实 Provider evidence；
- Phase 8 Cards/Exercises：draft → ready/rejected/archived、citation 生命周期、append-only review/attempt、确定性评分、backup/restore closeout。

Phase 9A 只做“学习领域基础与计划核心”：learning goal、knowledge module、study plan、study plan item、dependency、append-only progress event、progress summary，以及与现有 source revision/citation 的安全关联。不得顺带实现 9B 的资料笔记/学习节奏，9C 的限时练习/错题/冲刺，9D 的报告/OCR/ASR，也不得引入 worker、scheduler、queue、multi-user、cloud sync 或外部 vector DB。

必须遵守：
- 当前 schema version 以源码为准；所有表/字段/索引/约束走 migrations runner；
- migration 连续、幂等、事务化并有 rollback 测试；
- 不得用运行时 CREATE TABLE IF NOT EXISTS；
- AI 生成内容必须先是 draft，不能覆盖用户编辑、确认或完成状态；
- source deleted/purged/stale/unavailable 时不得伪造正文或可用 citation；
- progress 历史不可静默覆盖；
- API/UI/日志不得泄露路径、SQL、正文、secret、provider raw response、原始异常或 traceback；
- 保持单进程/单实例边界，不宣称多进程共享 data_root；
- backup/restore、startup/read 不得自动 repair、rebuild、重新生成或提升 unavailable 状态。

在动手前必须：
1. 读取 AGENTS.md；
2. 读取 docs/PHASE_ROADMAP.md、docs/STATUS.md、docs/TODO.md、docs/PROJECT_PROGRESS_REPORT.md、docs/ai-learning-architecture.md、docs/MIGRATIONS.md、docs/BACKUP_RESTORE.md、docs/CODE_TEST_GOVERNANCE.md；
3. 审计实际的 backend/app/migrations/、repository.py、main.py、backup.py、restore_acceptance.py、Phase 8 repository/API/tests；
4. 查明当前 schema version、事务边界、ID/时间/错误响应约定、测试 fixture 和前端 workspace 结构；
5. 不根据文档猜测实际接口，所有结论给出源码路径和函数/测试名称。

本子任务必须只修改它拥有的范围，并在结束时报告：
- 修改文件；
- 新增/修改测试；
- focused 命令和结果；
- 如涉及 migration/API/UI/backup，必须执行相应完整门禁；
- 未验证边界；
- 状态应使用的准确措辞；
- 后续阻塞项。

如果发现本子任务需要改变已冻结的领域契约，先停止实现并提出契约变更，不要擅自扩大范围。
```

---

# 二、Phase 9A 总规划 Prompt（只规划，不实现）

```text
请为 StudyBuddy 规划 Phase 9A“学习领域基础与计划核心”，不要修改任何文件。

先完整审计当前源码和权威文档，确认当前 migration version、repository 事务、material revision/citation lifecycle、Phase 8 source lifecycle、backup/restore、main.py 路由和现有 Chromium workspace。然后输出一份可直接转化为 TODO、migration、测试和逐 commit 实施计划的中文规划。

Phase 9A 最小对象：learning goal、knowledge module、study plan、study plan item、dependency、append-only progress event、progress summary、source revision/citation link。必须重新基于当前 StudyBuddy contract 设计，不得直接复制历史 KnowledgeModule。

必须明确：goal/module/plan/item 的关系；plan 是否必须绑定 goal；module 是否可复用；item 是否允许无 source；citation 绑定层级；dependency 是否只允许同一 plan；DAG/cycle 规则；draft→confirm→active 规则；pause/archive/complete 是否纳入；progress event 与 summary 重算；delete/restore/purge/re-index/source unavailable/stale 行为；AI draft 是否纳入 9A；用户编辑/确认/完成保护；日期与 timezone；project/user 边界；backup/restore non-repair。

请将 9A 拆成 9A-0 至 9A-8 的独立子任务，每个任务给出目标、前置、源码范围、测试、验收标准、风险、独立提交性和阻塞关系。至少覆盖：现状审计、领域契约、migration、repository/domain、API、最小 UI、source lifecycle、backup/restore、全量验收与文档收口。

明确排除 9B/9C/9D/Phase 10，并给出最终允许使用的状态措辞。输出只做规划，不实现。
```

---

# 三、子任务 Prompt

## 9A-0：现状审计与范围冻结

```text
执行 Phase 9A-0：只做审计与范围冻结，不实现业务代码、不新增 migration。

审计并记录：当前 schema version 和 migration runner；repository 事务模式；ID/时间/日期/状态/错误响应约定；现有 materials/revisions/chunks/citations 的 lifecycle 接口；Phase 8 Cards/Exercises 的 citation/source handling；backup/restore 是否自动覆盖 SQLite 表；main.py 路由与前端 workspace；测试临时 data_root fixture；是否已有 project/user 概念。

产出一份 docs/PHASE9A_DOMAIN_CONTRACT.md 初稿，包含 glossary、9A non-goals、实体关系候选、现有能力复用清单、9B/9C/9D 边界、风险和需要确认的问题。同步在 docs/TODO.md 中只增加或调整 9A 规划引用，不把任何实现标成完成。

验收：所有结论有源码路径；没有修改生产逻辑；文档明确 planned；git diff 只包含允许的文档。
```

## 9A-1：正式领域契约与状态机

```text
执行 Phase 9A-1：冻结 learning goal、knowledge module、study plan、study plan item、dependency、progress event、source link 的正式契约。

先读取 9A-0 文档和当前源码。只在契约文档中确定字段、关系、ID、时间/时区、状态枚举、合法转移、不变量、DAG 约束、progress summary 规则、source lifecycle 和用户编辑保护；不要实现表、API 或 UI。

推荐必须讨论并作出明确决定：plan 是否必须绑定 goal；module 是否可被多个 plan 使用；item 是否允许无 source；citation 是绑定 module 还是 item；dependency 是否只允许同一 plan；active plan 遇到 unavailable source 是允许并警告还是禁止；progress 是否只允许 append-only complete/skip/reopen；是否纳入 pause/archive/complete；AI plan 是否只生成 draft；是否需要新的 ai_operation 类型。

产出：docs/PHASE9A_DOMAIN_CONTRACT.md 的冻结版、状态转移表、不变量表、错误码草案、API resource 草案和 deferred decisions。不得把历史设计当实现证据。

验收：领域术语无歧义；边界覆盖 delete/restore/purge/re-index；没有隐式 scheduler/提醒/自动重排；契约可以直接驱动 migration 和测试。
```

## 9A-2：Migration 与 schema

```text
执行 Phase 9A-2：只实现 Phase 9A schema migration 和 migration 测试，不实现业务 repository、API 或 UI。

先确认当前实际 schema version，并按已冻结的 PHASE9A_DOMAIN_CONTRACT 设计连续 migration。至少评估 goals、knowledge_modules、study_plans、study_plan_items、study_plan_dependencies、study_progress_events、plan_source_links/module_source_links/item_source_links 的表拆分；明确外键、CHECK、unique、索引、软删除/归档、级联策略、跨 plan dependency 禁止方式和 append-only event 约束。

所有 schema 变更只能通过 backend/app/migrations/runner.py。禁止 ad-hoc runtime table creation。必须覆盖新库初始化、旧库升级、重复运行幂等、migration 中途失败 rollback、schema_migrations 与 PRAGMA user_version 一致、backup/restore version compatibility。

如果某个跨行约束无法由 SQLite CHECK 表达，必须记录由 repository/domain transaction enforcement，并为后续任务留下测试 contract。不要借 migration 顺便添加 9B/9C/9D 表。

验收：migration focused tests 通过；无业务表运行时创建；迁移失败不留下半成品；当前旧 schema 与新 schema 均能初始化/升级；状态仍是 migration implemented/backend-pass，不是 9A completed。
```

## 9A-3：Repository 与 domain transaction

```text
执行 Phase 9A-3：实现 9A repository/domain 最小事务闭环，不实现 HTTP 路由和完整 UI。

实现范围按 contract 拆开：goal/module CRUD 或 archive；plan draft 创建；item 增删改/排序；dependency 增删与 DAG cycle detection；draft confirm/active transition；progress event append；summary recompute；source link validation；source lifecycle refresh；用户编辑、confirmed、completed item 保护。

每个操作必须明确事务边界、输入校验、返回值、重复调用语义、失败 rollback、稳定错误码和并发/SQLite lock 行为。progress history 必须 append-only；summary 必须可从事件可靠重算，避免事件与 summary 不一致。source link 必须重新验证 current revision/chunk/span/citation，不能复制正文或信任客户端 citation。

如果实现 AI draft，则只允许显式 fake/provider abstraction 产生 draft，并保留 ai_operation metadata；真实网络 Provider generation 不属于本任务。任何重新规划不得覆盖 user-edited、confirmed 或 completed item。

新增 backend/tests/test_phase9a_domain.py、必要时拆为 test_phase9a_progress.py、test_phase9a_dependencies.py、test_phase9a_source_lifecycle.py。覆盖非法状态转移、重复请求、cycle、rollback、lock failure、source stale/unavailable、completed history 保留。

验收：repository/domain focused tests 通过；所有写入在事务内；没有 runtime CREATE TABLE；API/UI 不在此任务内。
```

## 9A-4：API contract

```text
执行 Phase 9A-4：把已通过 repository/domain 测试的 9A 能力暴露为最小 FastAPI API，不扩展业务范围，不实现完整 UI。

先读取当前 main.py 的路由风格、错误响应、safe serialization 和输入边界测试。按 contract 实现最小 goal/module/plan/item/dependency/progress/source link API：创建/列表/详情、draft edit、confirm/activate、item add/edit/reorder/remove、dependency add/remove、progress event append、summary、source status。明确哪些动作不做，例如提醒、调度、自动重排、复杂 AI re-plan、9B/9C/9D 能力。

每条 API 必须定义 method/path、request/response、status、stable error code、active/deleted/purged 边界、重复请求语义、malformed JSON/ID/date/status 行为、隐私边界。不要返回路径、SQL、traceback、raw provider data、完整 source text 或未授权的 citation quote。保持现有 request ID、observability 和 safe failure contract。

新增 API boundary tests，覆盖 4xx/409/404/422/500 安全错误、非法依赖和状态转移、重复 progress、source unavailable、失败后 retry、响应字段隐私。涉及 API 必须运行完整 backend suite。

验收：API contract 与 repository 行为一致；失败响应稳定脱敏；没有为 UI 方便而泄露内部字段。
```

## 9A-5：最小计划工作区 UI

```text
执行 Phase 9A-5：实现能够证明 9A 核心闭环的最小 Chromium workspace，不实现 9B/9C/9D 体验。

用户路径必须覆盖：创建 goal → 创建 module → 创建 plan draft → 添加/编辑/排序 item → 添加 dependency → 非法环依赖安全失败 → confirm → activate → 完成一个 item → 查看 append-only progress/summary → 查看 source citation 状态 → 刷新后恢复。

复用现有统一导航、页面 status/alert、toast、busy guard、stale response guard、retry、safe DOM text rendering、citation dialog/定位模式。必须有 draft/active 明显区分，用户编辑保护提示，source deleted/purged/stale/unavailable 的安全显示。不得渲染 source path、SQL、traceback、provider raw response 或超出 contract 的正文。

新增 browser_phase9a.spec.js，并覆盖桌面、390x844 窄屏、键盘 focus/操作、重复点击、网络/500/ malformed response failure contract。测试必须使用隔离临时 data root，并串行运行。

验收：Chromium happy path 和 failure path 通过；refresh/history 状态正确；窄屏无关键 overflow；不把 browser-pass 写成 real-pass。
```

## 9A-6：Source lifecycle 集成

```text
执行 Phase 9A-6：单独完成 9A 计划对象与材料 source lifecycle 的集成，不新增不必要的 AI 功能。

覆盖 material delete、restore、purge、新 extraction/new revision、chunk re-index 后的 plan/module/item source link 状态。明确 valid、source_deleted、source_unavailable、stale 的映射和返回 contract。已完成 item 的历史记录必须保留；purge 不得恢复名称、正文或可点击 source。恢复后是否自动 valid 必须遵守 contract，不能通过启动或读取自动 repair；如需 refresh，必须是显式动作。

测试 active plan 在 source unavailable 时的行为：是允许 active 并显示 warning，还是禁止 activate；对已完成、未开始、编辑中 item 分别验证。验证 delete/restore/purge/re-index 不会删除 progress event、不复制正文、不自动解析、不自动调用 Provider。

新增/修改 source lifecycle backend 和 Chromium tests，并运行完整 backend + Phase 9A browser tests。更新 domain contract/evidence 草案，但只有 closeout 才更新 completed 状态。

验收：source 状态不会被伪造提升；历史 progress 和 plan artifact 保留；UI/API 状态一致。
```

## 9A-7：Backup/restore 与 non-repair

```text
执行 Phase 9A-7：验证 9A 新增数据的 backup、verify、restore 和 non-repair 行为，不引入自动 repair/rebuild。

确认现有 SQLite Online Backup、manifest、schema version 和 restore acceptance 会覆盖所有 9A 表。若只需数据库快照，记录理由；若 manifest/restore verifier 需要调整，保持脱敏和新空目标目录规则。覆盖 goals/modules/plans/items/dependencies/progress/source links、draft/confirmed/active/paused/completed/archived、valid/stale/unavailable citation、用户编辑保护和 completed history。

必须证明 backup → verify → restore 到新空 data root 后：
- 数据和 migration history 保持一致；
- progress event 与 summary 一致；
- source unavailable 不会被提升为 valid；
- startup/read/verify/restore 不生成计划、不重建 chunk、不调用 Provider、不 repair 业务状态；
- 原有错误和 lifecycle 边界仍安全。

新增 test_phase9a_backup_restore.py，并运行完整 backend suite。必要时新增脱敏 evidence 文档，不提交真实 backup 文件。

验收：restore closeout 通过且证据可复现；明确哪些真实断电/磁盘损坏能力仍 not_verified。
```

## 9A-8：完整验收、证据与文档收口

```text
执行 Phase 9A-8：只做全量回归、验收证据和文档收口。若发现实现缺陷，创建明确修复子任务，不在 closeout 中偷偷扩大功能。

运行：9A focused backend、migration/domain/API/source lifecycle/backup tests、完整 backend suite、browser_phase9a.spec.js、相关 frontend failure contract、Phase 8 regression。记录实际命令、环境、passed/skipped/failed 和 artifact 位置；真实 Provider、screen reader、极端内容、长时稳定性、磁盘满、断电、多进程等未执行项必须保持 not_verified。

更新唯一事实源：docs/STATUS.md、docs/TODO.md、docs/PHASE_ROADMAP.md、docs/PROJECT_PROGRESS_REPORT.md；必要时更新 docs/ai-learning-architecture.md 和 docs/INDEX.md。新增 docs/PHASE9A_ACCEPTANCE_EVIDENCE.md，记录范围、用户路径、测试和限制。

只有以下全部满足才可将 9A 标为 completed：领域契约冻结；migration/version/rollback；repository/domain；API boundary；source lifecycle；Chromium happy/failure/narrow/keyboard；backup/restore non-repair；完整 backend regression；文档和脱敏 evidence 同步。

准确状态措辞应类似：
“Phase 9A completed in the deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore scope.”
中文可写：“Phase 9A 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表 Phase 9B–9D、Phase 9 全部完成或全局 production real-pass。”
```

---

# 四、推荐执行顺序与提交拆分

推荐严格按以下顺序执行：

```text
9A-0 审计与范围冻结
  ↓
9A-1 领域契约与状态机冻结
  ↓
9A-2 migration/schema
  ↓
9A-3 repository/domain
  ↓
9A-4 API
  ↓
9A-5 UI
  ↓
9A-6 source lifecycle 集成
  ↓
9A-7 backup/restore
  ↓
9A-8 acceptance/documentation closeout
```

推荐每个任务单独 commit：

| Commit | 单一责任 |
|---|---|
| `docs: freeze phase 9a audit boundaries` | 9A-0 审计与边界文档 |
| `docs: define phase 9a domain contract` | 9A-1 领域契约与状态机 |
| `db: add phase 9a schema migration` | 9A-2 migration 与 migration tests |
| `feat: add phase 9a plan domain repository` | 9A-3 repository/domain 与 focused tests |
| `feat: expose phase 9a plan api` | 9A-4 API 与 boundary tests |
| `feat: add phase 9a plan workspace` | 9A-5 UI 与 Chromium tests |
| `feat: integrate phase 9a source lifecycle` | 9A-6 source lifecycle tests |
| `test: verify phase 9a backup restore` | 9A-7 backup/restore closeout tests |
| `docs: close phase 9a acceptance` | 9A-8 evidence、状态与 TODO 收口 |

若某任务必须修复前一任务的问题，应使用独立 fix commit，并说明它修复哪个 gate；不得把多个未验收任务压成一个大 commit。

# 五、Phase 9A 完成门槛

- **Gate A：契约**：领域关系、状态机、不变量、source lifecycle、progress、dependency 规则冻结。
- **Gate B：数据库**：migration 连续、幂等、rollback、schema history 和 backup version 一致。
- **Gate C：领域层**：事务、cycle detection、append-only progress、用户编辑保护通过。
- **Gate D：API**：输入边界、生命周期、稳定错误和隐私 contract 通过。
- **Gate E：Source lifecycle**：delete/restore/purge/re-index 后状态真实、安全且不可伪造。
- **Gate F：UI**：创建→draft→confirm→active→完成→summary→refresh 路径及 failure/narrow/keyboard 通过。
- **Gate G：Restore**：backup→verify→新空目录 restore，non-repair 和历史保留通过。
- **Gate H：收口**：完整 backend、相关 Chromium、evidence、STATUS/TODO/ROADMAP 同步。

在 Gate H 之前，不得写 `Phase 9A completed`。9A 完成后仍必须保留：真实 Provider plan generation、人工计划审核、提醒/调度、S1/S2、S3/S4/S5、S6/S7、后台任务、多用户和全局 production real-pass 为未完成或未验证。
