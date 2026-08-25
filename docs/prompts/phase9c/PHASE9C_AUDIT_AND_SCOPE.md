# Phase 9C-0：现状审计与范围冻结

> 状态：`planned/audit-draft`
>
> 本文是 Phase 9C-0 的审计产物，不是 S3/S4/S5 实现证据，也不是 Phase 9C contract-frozen。9C-1 必须基于本文和当时源码重新确认所有领域决策；本文不新增 migration、API、业务表或用户路径。
>
> 审计基线：当前工作树源码与测试；审计命令使用项目 Python 环境的等价 Bash 路径 `/cygdrive/c/miniconda/py310/python`。权威完成范围仍以 `docs/STATUS.md` 和既有 Phase 8/9A/9B evidence 为准。

## 1. 审计范围与方法

本次按 `docs/prompts/phase9c/9C-0_现状审计与范围冻结.md` 执行，检查了：

- `backend/app/migrations/runner.py`：当前 schema、migration history、baseline completeness、transaction/rollback boundary；
- `backend/app/repository.py`：Phase 8 exercise/card、attempt/review、AI generation、Phase 9A plan/progress/source link、Phase 9B note/rhythm/source refresh、material lifecycle；
- `backend/app/main.py`：实际 FastAPI routes、Pydantic input、错误映射、前端 workspace 与安全 DOM；
- `backend/app/backup.py`、`backend/app/restore_acceptance.py`：backup/verify/restore 与 non-repair 事实；
- Phase 8、9A、9B 的 focused backend tests 与 Chromium specs；
- `docs/PHASE_ROADMAP.md`、`STATUS.md`、`TODO.md`、`PROJECT_PROGRESS_REPORT.md`、`ai-learning-architecture.md`、`MIGRATIONS.md`、`BACKUP_RESTORE.md`、`CODE_TEST_GOVERNANCE.md`。

审计不把 `docs/prompts/HISTORICAL_SCENARIO_REVIEW.md` 或 Composer/Integration/前代项目视为正式实现证据；它们最多提供产品需求线索。

## 2. 当前事实基线

### 2.1 Schema 与 migration

| 结论 | 源码证据 | 影响 |
|---|---|---|
| 当前正式 schema 为 v10 | `backend/app/migrations/runner.py:CURRENT_SCHEMA_VERSION`；`docs/MIGRATIONS.md` | Phase 9C 若新增业务表，必须使用连续 v11 migration；不能修改 v10 或在 runtime 建表。 |
| migration 1–10 连续登记 | `backend/app/migrations/runner.py:_MIGRATIONS` | v11 必须追加新 name/version；不能手动修改 `schema_migrations` 或 `PRAGMA user_version`。 |
| migration 在 `BEGIN IMMEDIATE` 内执行，DDL、history 和 `user_version` 一致性由 `migrate()` 管理 | `backend/app/migrations/runner.py:migrate()`、`assert_schema_version()` | 失败必须 rollback；新库、v10 upgrade、幂等、失败 rollback 和 backup version 都要测试。 |
| v10 已包含 Phase 9B 表 | `backend/app/migrations/runner.py:_migration_v10()`、`_baseline_complete()` | 现有 `notes`、`note_blocks`、`rhythm_*` 是已完成 9B 能力，9C 不得把它们当作可随意改造的练习/错题表。 |
| 当前没有 S3/S4/S5 专用表 | v1–v10 migration 定义中没有 practice session、mistake、weak point、cram 等业务表 | 9C-1 必须先区分事实表、快照和 projection，再由 9C-2 设计最小 v11 schema。 |

### 2.2 Phase 8 Cards / Exercises 实际能力

#### Cards

已实现：

- `study_decks`、`study_cards`、`card_citations`、`card_reviews`；表定义见 `backend/app/migrations/runner.py:_migration_v7()`；
- card 状态 `draft/ready/rejected/stale/archived`，`create_card()`、`update_card()`、`confirm_card()`、`transition_card()`；
- card review 结果 `again/hard/good/easy`，由 `review_card()` append-only 写入 `card_reviews`；
- citation 生命周期通过 `_refresh_card_citations()`、`_refresh_card_citations_for_material()` 更新为 `valid/source_deleted/source_unavailable/stale`；
- 用户编辑保护：`update_card()` 对 `ready/archived` 拒绝普通编辑。

正式 API：

- `GET /api/study/decks`、`GET /api/study/decks/{deck_id}`、`GET /api/study/cards`；
- `POST /api/study/decks/{deck_id}/cards`；
- `PATCH /api/study/cards/{card_id}`；
- `POST .../confirm|reject|archive`；
- `POST /api/study/cards/{card_id}/reviews`。

证据：`backend/app/main.py:1830–1930`、`backend/tests/test_phase8_cards.py`、`backend/tests/browser_phase8.spec.js`。

**审计结论：** card 有复习评价，但没有 `exercise_attempts` 式题目作答、服务端评分或限时 session 事实。因此 9C-1 必须明确 S3 是只消费 exercises，还是另行定义 cards 在限时/冲刺中的可执行语义；不能把 `card_reviews` 直接当作练习 attempt。

#### Exercises

已实现：

- `exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`；表定义见 `backend/app/migrations/runner.py:_migration_v7()`；
- 题型只有 `multiple_choice`、`true_false`、`short_answer`，由 `_exercise_payload()` 校验；
- exercise 状态 `draft/ready/rejected/stale/archived`；`create_exercise()`、`update_exercise()`、`confirm_exercise()`、`transition_exercise()`；
- AI exercise 必须携带 `source_revision` 和有效 citation，`confirm_exercise()` 会再次刷新/验证 citation；
- `submit_exercise_attempt()`：MC/TF 服务端 deterministic grading；short answer 只写 `pending_review`；
- `list_exercise_attempts()` 只返回 `id/exercise_id/score/is_correct/grading_status/submitted_at/reviewed_at/feedback`，不返回 `answer_json`；
- 普通 `_exercise_public()` 不返回 `answer_key_json`，answer key 只在内部用于评分。

正式 API：

- `GET/POST /api/study/exercise-sets`、`GET /api/study/exercise-sets/{set_id}`；
- `GET /api/study/exercises`、`POST /api/study/exercise-sets/{set_id}/exercises`；
- `POST /api/study/exercise-sets/{set_id}/generate`；
- `PATCH /api/study/exercises/{exercise_id}`；
- `POST .../confirm|reject|archive`；
- `GET/POST /api/study/exercises/{exercise_id}/attempts`。

证据：`backend/app/repository.py:584–998`、`backend/app/main.py:1932–2045`、`backend/tests/test_phase8_exercises.py`、`backend/tests/test_phase8_generation.py`、`backend/tests/test_phase8_closeout.py`、`backend/tests/browser_phase8.spec.js`。

**审计结论：** Exercises 是 9C 的最直接依赖，但目前没有 session、题目快照、截止时间、错题 projection、人工 review 写入 API、weak point 或 cram 对象。

### 2.3 Phase 8 generation 与 provider 边界

已实现：

- `create_generation_operation()` 创建 `generate_card` / `generate_exercise` 的同步 `ai_operations`；
- 当前 generation 强制单材料、同 project、active material、current revision、ready chunk；
- provider I/O 前后分开事务，成功时 `persist_generated_draft()` 原子写入 draft/citation/operation；
- 支持 Idempotency-Key replay、running conflict、失败后 retry、stale source、malformed output、forged citation 和 rollback；
- `backend/app/main.py:_generated_items()` 只在内存校验结构化 output，raw provider response 不落库；
- 当前正式可重复验收范围是 deterministic fake provider；真实 Provider generation 不是 Phase 8 completion 的一部分。

证据：`backend/app/repository.py:create_generation_operation()`、`persist_generated_draft()`；`backend/app/main.py:1018–1120`；`backend/tests/test_phase8_generation.py`。

**对 9C 的影响：** 如果 9C 生成解析、变题或反馈，必须复用这一 operation/draft/citation 规则，不能让生成结果直接变成 ready、mistake fact、人工 review 结论或冲刺完成结果。9C-1 还必须决定是否在本阶段实现任何新的 generation operation type；默认建议先不扩大到 real provider。

### 2.4 Phase 9A 计划、progress、module 与 source link

已实现：

- `learning_goals`、`knowledge_modules`、`study_plans`、`study_plan_items`、`study_plan_dependencies`、`study_progress_events`、`module_source_links`、`plan_item_source_links`；
- plan 状态 `draft/confirmed/active/paused/completed/archived`，item 状态 `pending/in_progress/completed/skipped/archived`；
- 依赖 DAG cycle detection：`_study_dependency_cycle()`、`add_study_plan_dependency()`；
- progress 是 append-only：`append_study_progress_event()` 写 event 并更新 item projection；`study_progress_summary()` 读取 projection；
- source link 由 `_study_source_status()` 做 server-side current revision/chunk/citation 验证；
- project scope 由 API 注入 `app.state.config.project_id`，repository 继续验证跨 project 关系。

证据：`backend/app/repository.py:998–1718`、`backend/app/main.py:1183–1405`、`backend/tests/test_phase9a_domain.py`、`backend/tests/test_phase9a_api.py`、`backend/tests/test_phase9a_source_lifecycle.py`、`backend/tests/browser_phase9a.spec.js`。

**对 9C 的影响：** 9C 可以把 exercise set、deck、module、plan item 作为显式范围或来源上下文，但不能：

- 直接修改既有 progress event；
- 把 attempt/错题/冲刺结果伪装成 plan progress；
- 自动创建或移动 rhythm allocation；
- 静默改写 plan、item、module、note 或其用户编辑状态。

### 2.5 Phase 9B notes/rhythm

已实现：

- notes：`draft/confirmed/rejected/archived`，`user_created/ai_generated` provenance，至少一个 block，draft-only edit，confirmed 后保护；
- note block source link：server-side citation/context 验证与 `valid/source_deleted/source_unavailable/stale` 生命周期；
- note generation：`generate_note` operation、fake-provider、draft、citation revalidation、idempotency/retry/failure rollback；
- rhythm：daily/weekly、IANA timezone、local-date allocation、deterministic summary；不写 progress、不自动重排、不启动 scheduler。

证据：`backend/app/repository.py:1950–2710`、`backend/app/main.py:1420–1820`、`backend/tests/test_phase9b_domain.py`、`test_phase9b_notes.py`、`test_phase9b_rhythm.py`、`test_phase9b_api.py`、`test_phase9b_source_lifecycle.py`、`test_phase9b_backup_restore.py`、`browser_phase9b.spec.js`。

**对 9C 的影响：** S4 可以只读引用 note/module/plan context 作为反馈上下文，但 9C 不应在没有新契约的情况下修改 note 内容、note status、rhythm allocation 或自动生成学习安排。S5 的“冲刺目标”不能等同于 S1 rhythm；是否允许用户手动把 cram 结果关联到既有 plan item，需要 9C-1 明确。

## 3. Source、citation 与材料生命周期事实

### 3.1 当前 source chain

正式 source chain 是：

```text
materials / extractions / text_spans
  → material_revisions
  → chunks / chunk_spans
  → retrieval_runs / retrieval_hits
  → assemble_context()
  → validated citation key
  → card/exercise/note citation
```

证据：`backend/app/repository.py:run_chunk_retrieval()`、`assemble_context()`、`validate_citation_key()`；`docs/ai-learning-architecture.md`；Phase 8/9B tests。

`assemble_context()` 只读取同 project、active material、current revision、ready chunk，并生成 `ctx-...` citation key；`validate_citation_key()` 对格式、material、current revision 和 chunk 做服务端检查。客户端发送的 citation status、quote 或 source path 不能使 citation 变 valid。

### 3.2 delete/restore/purge/re-index

- soft delete：`soft_delete_material()` 将 material 标记 deleted，并刷新 card、exercise、9A/9B source link；相关状态变为 `source_deleted`；
- restore：`restore_material()` 只恢复 material 可见性，同时刷新 Phase 8 citations；9A/9B source link 不因普通 read/restore 自动 promotion，需显式 refresh；
- purge：`purge_material()` 在删除 material 前将 QA/card/exercise/note/module/plan source records 标成 `source_unavailable`，删除 material、chunks/search rows；保留 artifact/history 的数据库记录；
- re-index/new current revision：旧 citation/source identity 通过刷新变为 `stale`，不自动改写为新 revision；
- read/startup/verify/restore：当前 `connect()` 只执行 migration、FTS/chunk search index consistency；startup `reconcile()` 是 storage/recovery 处理，不是生成、重评分或 source promotion。

证据：`backend/app/repository.py:364`、`2744–2790`、`2897–2915`；`backend/app/main.py:2080–2150`；`backend/app/recovery.py:reconcile()`；`backend/tests/test_phase9a_source_lifecycle.py`、`test_phase9b_source_lifecycle.py`、`test_phase9b_backup_restore.py`。

**9C 必须继承：** 历史 attempt、review、mistake、feedback、session/result 和 cram records 应保留；只允许服务端更新 citation/source status，不得伪造 source text、material name、stored path、quote 或定位按钮。

## 4. Backup / restore 与安全边界

### 4.1 当前 backup/restore

- `backup_data()` 使用 SQLite Online Backup API 复制完整数据库，并验证 integrity、foreign keys、schema version 和 originals hash；
- manifest 只保存版本、schema、hash/size/count 等安全 metadata，不保存 live data root、stored_path 或异常文本；
- `verify_backup()` 只验证，不 migration、repair、rebuild FTS 或修改 backup；
- `restore_backup()` 只恢复到不存在或空目录，经过 staging 和再次 verify，再重定位 restored material 的 hash-derived `stored_path`；不调用 provider、不启动服务、不运行业务 repair；
- `verify_restored_data()` 当前 `_study_checks()` 覆盖 9A 和 9B tables、projection、source status、notes/rhythm，不覆盖未来 9C 表。

证据：`backend/app/backup.py:backup_data()`、`verify_backup()`、`restore_backup()`；`backend/app/restore_acceptance.py:_study_checks()`、`verify_restored_data()`；`docs/BACKUP_RESTORE.md`。

**9C 缺口：** 未来必须由 9C-9 扩展 restore acceptance，不能以“SQLite snapshot 天然会包含新表”代替专项证据。需要保留 session、attempt、review、mistake、weak-point、cram 事实/投影、operation 和 source lifecycle；verify/restore/startup/read 不能重新评分、重建错题、重跑冲刺或调用 provider。

### 4.2 隐私边界

已验证：

- exercise 普通响应不返回 answer key；attempt history 不返回 `answer_json`；
- card/exercise/note export 和 UI 不返回 stored path；
- source unavailable 后 citation detail 不提供可用正文定位；
- provider raw response、raw prompt、secret 不持久化；
- API 错误使用稳定 code，不输出 traceback/raw provider error。

证据：`_exercise_public()`、`list_exercise_attempts()`、`main.py` exercise/note routes；`test_phase8_exercises.py`、`test_phase8_generation.py`、`test_phase9b_api.py`、`browser_phase8.spec.js`、`browser_phase9b.spec.js`。

**9C 风险：** session 提交接口天然接触用户答案和内部评分，S4 人工复核还可能接触 answer key。9C-1 必须明确哪些字段只存数据库、哪些只在本人 review/detail 中短暂返回、哪些永不返回；不能默认复制当前 `exercise_attempts.answer_json` 的存储/响应方式而不重新审查。

## 5. 前端与用户路径现状

当前是 `backend/app/main.py` 中的内嵌单页 HTML/JavaScript，不是独立前端工程。

已存在：

- `#study` 卡片/练习 workspace：deck/set、draft generation、edit、confirm/reject/archive、card review、exercise attempt；
- `#plans` 9A/9B plan/rhythm workspace：goal/module/plan、items/dependency/progress、rhythm settings/allocation/summary；
- `#notes` 9B workspace：user/AI note、module、citation dialog、confirm/reject/archive、source refresh/export；
- 统一 `status/alert/toast`、busy guard、retry、stale response protection、safe DOM `textContent`、keyboard focus、390x844 responsive CSS。

证据：`backend/app/main.py:INDEX_HTML`；`backend/tests/browser_phase8.spec.js`、`browser_phase9a.spec.js`、`browser_phase9b.spec.js`。

不存在：

- S3 timed session UI、server deadline display、session result page；
- S4 mistake list/detail、wrong-answer explanation、redo workflow、human review UI；
- S5 cram target/exam session UI；
- Phase 9C browser spec。

浏览器测试基线：Phase 8 spec 覆盖 3 条路径；Phase 9A spec 覆盖 plan happy/lifecycle/failure；Phase 9B spec 覆盖 S1/S2 happy/failure/duplicate/narrow/keyboard/reload。它们不证明 Phase 9C 能力。

## 6. S3/S4/S5 现状、价值、依赖与风险

### 6.1 S3 PracticeRunner：限时练习

**产品价值：** 用户从已确认练习中选择有限题量，在明确时限内完成作答，获得可解释且安全的成绩/反馈；形成后续 S4 错题输入和 S5 模拟结果输入。

**已存在依赖：**

- `exercise_sets`、`exercises` 和三种题型；
- `confirm_exercise()` 的 ready/source/citation gate；
- `submit_exercise_attempt()` 的 append-only attempt 和 MC/TF deterministic grading；
- short answer `pending_review`；
- Phase 8 UI/API/privacy/source lifecycle。

**当前缺口：**

- 没有 practice session/selected-item snapshot；
- 没有服务端 start/deadline/expire/finish；
- attempt 没有 session id、排序、序号或重复请求 idempotency；
- 没有 session 级结果汇总、超时语义或 reload recovery contract；
- 没有把 attempt 与 plan/module/note/cram scope 做安全关联的对象。

**主要风险：**

1. 计时可信性：客户端 elapsed/score/finished_at 可被篡改；必须服务端生成并比较时间，但单进程同步模型没有后台 timer；
2. 题目变更：session 内 exercise 被编辑/归档/source stale 后，快照还是动态读；
3. 重复提交：网络重试可能创建重复 attempt；但默认无 key 的 Phase 8 attempt 目前每次都会追加；
4. 答案泄露：session payload 可能意外包含 answer key；
5. short answer：session 结束时是 pending，还是阻塞完成，必须定义；
6. cards 是否属于可作答项目尚未定义。

### 6.2 S4 ErrorFixer：错题改错与反馈

**产品价值：** 把错误作答转成可解释、可重做、可追踪的反馈，而不是删除失败记录或直接依赖 AI 猜测。

**已存在依赖：**

- `exercise_attempts` 的 `is_correct/score/grading_status/reviewed_at/feedback`；
- MC/TF deterministic wrong 事实；
- short answer `pending_review`，但当前无 reviewer operation；
- card review 的 `again/hard/good/easy` 仅能作为复习信号，不能直接等同错题；
- exercise citation/source lifecycle。

**当前缺口：**

- 没有 mistake/error-fix/weak-point 表或 projection；
- 没有 deterministic incorrect、pending_review、人工 review、用户标记之间的事实分类；
- 没有人工复核 API/UI、reviewer boundary、uncertain/override 语义；
- 没有 redo attempt 与 mistake 关联；
- 没有错因、用户反馈、AI suggestion 与 confirmed fact 的分层；
- 没有重复归并、reopen/fixed/archive 生命周期。

**主要风险：**

1. 将错误答案、AI 猜测、人工意见混为同一个事实；
2. 重做覆盖原 attempt，破坏审计和趋势统计；
3. 人工 review 返回 answer key 或提交原文；
4. source purge 后继续展示“可验证解析”；
5. 把一次错误永久归并到错误的 weak point，导致后续反馈污染。

### 6.3 S5 ExamCrammer：期末冲刺

**产品价值：** 用户在明确考试/截止目标下，手动选择练习范围，完成一轮模拟/速练，得到结果和薄弱点反馈；它应消费 S3 session 和 S4 facts，而不是建立第三套评分事实。

**已存在依赖：**

- Phase 8 exercise set/deck/module/plan item 的安全引用；
- S3 session/attempt/result（尚不存在）；
- S4 mistake/review/weak-point（尚不存在）；
- Phase 9A plan/module/progress 只读或显式关联；
- source/citation lifecycle 和 backup/restore。

**当前缺口：**

- 没有 cram target、exam session、selection snapshot、deadline/result；
- 没有题目范围、题量/时限限制和模拟卷快照；
- 没有 S3/S4 结果汇总或安全建议；
- 没有与 plan item 的显式关系；
- 没有“建议”与“事实”的数据边界。

**主要风险：**

1. S5 重复实现题目、评分和 attempt，产生多个 source of truth；
2. 自动修改 9A plan/rhythm，超出 9C 范围；
3. 将未复核 short answer 或失效 citation 纳入确定性成绩；
4. 用户改变 exercise set 后历史模拟卷失去可复现性；
5. “期末”日期和时区语义含糊，导致 deadline 与 summary 不一致。

## 7. Phase 9C 范围冻结（audit-level）

下列是 9C-0 层级的范围冻结：用于阻止范围漂移；实体字段、状态枚举和 HTTP 细节留给 9C-1。

### 7.1 纳入范围

- **S3**：显式创建/开始/读取/提交/结束的限时练习 session；复用 ready exercise 和 Phase 8 deterministic grading；session 结果只由服务端事实汇总；覆盖 timeout、刷新、重复提交、失败和隐私边界。
- **S4**：基于真实 attempt/grading/review 的错题事实或 projection；支持显式改错、重做、人工复核（至少覆盖 short answer 的最小本地单用户路径）、反馈历史和 weak-point 的最小可验收闭环；历史 attempt/review append-only。
- **S5**：用户显式创建冲刺目标/模拟 session，选择范围和练习；复用 S3 session、S4 feedback；保存结果/快照，提供安全 summary；不自动改计划。
- 三个子系统的 migration、repository/domain、API、Chromium、source lifecycle、backup/restore、隐私和文档 evidence。

### 7.2 明确排除

- 真实 Provider generation acceptance；Provider 生成的题目/解析/反馈只有在 9C-1 明确纳入后，才能以 deterministic fake-provider draft 形式进入最小范围；默认不作为 9C-0 的必要交付；
- scheduler、worker、queue、cancel、后台计时器、定时过期扫描、push、提醒、日历同步、自动排程、自动重排；
- 多用户、认证授权、teacher/parent roles、跨 project、云同步、协作；
- OCR、ASR、课堂采集、家长报告、S6/S7、Phase 9D；
- cloze、ordering、matching、essay/开放题自动评分等 Phase 8 未冻结题型；
- 外部真实题库/试卷导入、考试平台同步、外部 vector DB；
- 自动把错题或冲刺结果写成 9A progress/rhythm allocation；
- 自动删除/覆盖 attempt、review、feedback、confirmed artifact、note/module/plan 状态；
- 系统级 screen reader、极端长内容、长期稳定性和真实资源耗尽等不属于默认完成证据，除非另行立项。

### 7.3 依赖关系冻结

```text
Phase 8 ready exercise + deterministic grading/privacy
  → 9C shared attempt/session boundary
  → S3 timed practice
  → S4 mistake/review/redo/weak-point
  → S5 cram session/result
  → shared API/UI/source lifecycle/backup closeout
```

Cards 当前只有 append-only review，不足以直接成为 S3 scored attempt；若 9C-1 要纳入 cards，必须先冻结独立 card session semantics 和测试，不得隐式复用 exercise scoring。

9B note/rhythm 是可选只读上下文；9C 不依赖后台节奏服务，也不修改 rhythm。9A plan/module/progress 是显式关联上下文；9C 不改变既有 progress event 语义。

## 8. 9C-1 必须决定的未决问题

以下问题在 9C-0 之后仍未冻结，列为 Gate B 阻塞项。实现者不得自行选择后写入 schema/API。

### 8.1 时间与 session

1. **S3 执行对象**：只支持 exercises，还是纳入 cards？若纳入 cards，card review 与 timed answer 的关系是什么？
2. **时间单位**：session limit 是整数秒、分钟还是 ISO duration？最小/最大值是多少？
3. **时区**：deadline 是否以 UTC instant 保存，是否额外保存 IANA timezone/display date？DST 如何只影响显示而不改变时长？
4. **start 语义**：创建即开始，还是 create → start 两阶段？服务端是否使用 monotonic deadline 辅助但持久化 wall-clock UTC？
5. **暂停/恢复**：9C 是否明确不支持 pause；若支持，如何防止客户端伪造累计时长？
6. **超时边界**：deadline 前到达但事务晚提交如何判定；过期 session 是否允许只读提交、自动 finish，还是拒绝并保留 unanswered？
7. **刷新/重启**：是否仅通过持久化 session 恢复；如何处理进程崩溃、未结束 session 和无 worker 的 stale 状态？
8. **session item snapshot**：保存 exercise identity、题型、prompt/options/citation/source revision 的完整快照，还是只保存 identity 并要求当前 exercise unchanged？
9. **题目变化**：ready exercise 被 archive、citation stale 或用户 edit 后，已有 session 是保留快照、标 warning，还是禁止提交？
10. **提交幂等**：是否要求每题 submission key；同 key replay 的 fingerprint 组成是什么；没有 key 是否保持 append-only 新 attempt？

### 8.2 答案安全、评分与人工复核

11. **response 分层**：session start/detail、逐题题面、submit response、history、review detail 哪些字段允许返回 `is_correct/score/feedback`？
12. **本人答案**：是否允许用户在自己的历史详情中看到自己的提交原文；普通 list、导出、日志和 DOM 的禁止边界是什么？
13. **answer key**：人工复核是否在服务端临时读取 answer key；任何 API/UI/导出是否允许显示参考答案，需怎样脱敏？
14. **short answer completion**：pending_review 是否不计入 session final score、显示 unknown、还是阻塞 finalization？
15. **人工 reviewer**：当前单用户是否由本地 operator/本人复核；是否需要 reviewer identity、reviewed_at、decision、feedback、uncertain/override？
16. **deterministic 与 reviewed 的优先级**：人工 override 是否允许覆盖 deterministic MC/TF；若允许，原 deterministic 结果如何保留？
17. **AI feedback**：9C 是否纳入 fake-provider explanation/feedback；若纳入，draft/suggestion/confirmed 的状态和 citation 关系是什么？
18. **错误事实**：wrong 的进入条件是 `is_correct=false`、review decision、用户显式标记，还是分层事件；pending_review 在复核前是否可以进入错题候选？

### 8.3 错题归并、重做与 weak point

19. **mistake identity**：按 exercise、exercise revision、knowledge module、source revision、session 或 concept 归并？
20. **重复错误**：一次错误一个 mistake row，还是一个 mistake case 下 append-only occurrences；首次/最近/累计次数如何计算？
21. **生命周期**：open、in_review、fixed、reopened、archived/ignored 是否需要；谁可以转换，是否允许 restore？
22. **用户改错**：改错内容是否独立 append-only feedback/event；confirmed correction 能否编辑，是否需要新版本？
23. **重做**：重做是否只能从 mistake 详情启动；必须创建新 attempt，并如何把新 attempt 关联到原 mistake/case？
24. **weak point**：是只读实时 projection，还是保存带规则版本的 snapshot；source/module 缺失时如何降级；AI suggestion 是否永远非事实？

### 8.4 S5 冲刺

25. **目标定义**：cram 是目标、exam session，还是两者；deadline/date/timezone 和目标题量/分数如何表达？
26. **范围**：按 exercise set、deck、module、plan item、手动 exercise IDs 选择；是否允许混合范围；跨 project 如何拒绝？
27. **快照**：模拟 session 是否冻结题目/题面/citation/source revision，还是动态读取；selection 为空/重复/超过上限如何处理？
28. **结果**：S5 是否只汇总 S3 facts，还是直接创建自己的 attempts；short answer/pending_review 如何计入；S4 mistake/weak-point 是否只读？
29. **计划关系**：是否允许显式关联一个既有 plan/item；是否禁止自动写 progress、rhythm allocation、due date 和重排？
30. **建议边界**：冲刺建议是 deterministic summary，还是 fake-provider draft；如果是 AI，如何避免成为 confirmed plan/feedback 事实？

## 9. 风险登记

| 风险 | 当前状态 | 9C-1/后续控制 |
|---|---|---|
| 客户端篡改计时/分数 | 未实现 | server-authoritative UTC deadline；不信任 client elapsed/score；无后台 timer 的 stale 处理先冻结 |
| attempt 被重做覆盖 | 当前 Phase 8 attempt 是 append-only，但没有 session/redo relation | 新 session/redo 只能写新 attempt；旧事实只读；测试 row count/history |
| answer key 泄露 | Phase 8 普通 API 已防护，人工 review 尚未存在 | 设计 response DTO/DOM/privacy tests；禁止 answer key/raw answer 进入普通 list/export/log |
| short answer 无人工复核 | 当前仅 `pending_review`，没有 API/UI | 9C-1 冻结最小本地 review 角色和 decision；否则 S4 只能标 not implemented |
| 错题事实污染 | 当前没有 mistake projection | 分离 deterministic fact、review fact、AI suggestion、user override；每类保留 provenance |
| 题目/来源变化 | Phase 8 citation status 可刷新为 stale/deleted/unavailable | session snapshot 或 immutable reference 必须冻结；source status 不得 promotion |
| S5 重复造事实 | 当前没有 cram/session | S5 只消费 S3/S4 facts；一个明确的 attempt source of truth |
| backup/restore 遗漏新表 | restore acceptance 目前只检查 v9/v10 学习表 | 9C-9 扩展 `_study_checks()` 与专项 snapshot/non-repair test |
| 范围扩张到 worker/真实 Provider | 历史需求有流式生成、自动排程、模拟考试等暗示 | 9C-0 排除；任何新增能力先做 contract change 和独立 gate |

## 10. 推荐的后续执行边界

9C-0 之后推荐严格按既定顺序：

```text
9C-0 本审计
  → 9C-1 冻结上述未决契约
  → 9C-2 v11 migration/schema
  → 9C-3 shared repository/domain transaction
  → 9C-4 S3
  → 9C-5 S4
  → 9C-6 S5
  → 9C-7 API
  → 9C-8 Chromium
  → 9C-9 source lifecycle + backup/restore
  → 9C-10 closeout
```

在 9C-1 通过前不得实现 v11 migration 或任何 S3/S4/S5 表。9C-4 与 9C-5 理论上可在共享 domain 通过后并行，但推荐串行；9C-6 必须等待 S3/S4 稳定结果模型。

## 11. 审计验证结果

### Focused backend regression

命令：

```text
/cygdrive/c/miniconda/py310/python -m pytest \
  backend/tests/test_phase8_cards.py \
  backend/tests/test_phase8_exercises.py \
  backend/tests/test_phase8_generation.py \
  backend/tests/test_phase8_closeout.py \
  backend/tests/test_phase9a_domain.py \
  backend/tests/test_phase9a_api.py \
  backend/tests/test_phase9a_source_lifecycle.py \
  backend/tests/test_phase9b_domain.py \
  backend/tests/test_phase9b_notes.py \
  backend/tests/test_phase9b_rhythm.py \
  backend/tests/test_phase9b_api.py -q
```

结果：**55 passed**。

本任务未修改业务代码，因此未重新运行 full backend 或 Chromium；既有 browser evidence 已通过源码和 spec 审计。正式实现阶段仍必须按变更范围运行对应 focused、full backend 和 Chromium 门禁。

### 当前工作树与本任务变更

- 本 9C-0 任务新增：`docs/prompts/phase9c/PHASE9C_AUDIT_AND_SCOPE.md`；
- 未修改 `backend/app/`、`backend/tests/`、migration、README、STATUS、TODO；
- 仓库中此前已有的 Phase 9C prompt 包及其它未提交文档变更不属于本次 9C-0 审计实现；
- 未生成数据库、上传原件、provider artifact、secret 或测试输出。

## 12. Gate A 结论与准确状态

Gate A 达到审计层面的通过条件：当前 Phase 8/9A/9B 实际能力、S3/S4/S5 边界、9D/Phase 10 non-goals、风险和后续未决问题均有源码/测试证据或明确记录。

准确状态只能写：

> **Phase 9C-0：`planned/audit-draft`。** 已完成当前源码与测试审计、S3/S4/S5 范围边界和风险登记；未实现任何 Phase 9C 业务能力，未完成 Gate B，不能称为 Phase 9C completed。

下一阻塞任务：**9C-1 正式领域契约与状态机**。在 9C-1 冻结时间、答案安全、重做、错题归并、人工复核和冲刺范围前，不得开始 9C-2 migration 或业务实现。
