# StudyBuddy Decisions

## 2026-08-25: project progress and priority boundary

- 当前项目整体阶段性完成度按功能加权估算为 45%–50%；该估算不是测试通过率。
- 文件材料导入、管理、搜索、导出已形成局部 `real-pass`；I1 migration/schema versioning、I2 backup/restore 运维闭环与 I3 最小可观察性已完成，I4 仍需收尾。
- 下一产品优先级是实现 AI/学习最小闭环：material revision/chunk → SQLite FTS5 retrieval → citation → provider/fake provider → Q&A。
- I1 migration/schema versioning 是 AI Phase 4 的硬前置，现已满足；Cards / Exercises 仍必须等待可信 revision/chunk/retrieval/citation/Q&A 链路。
- S1–S7、卡片、练习、学习计划、OCR、ASR、后台队列、多用户、云同步和多进程支持继续分阶段推进，不在同一阶段并行承诺。
- 长期 Phase 顺序、范围和完成标准以 [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md) 为准；进度总报告以 [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md) 为汇总入口；具体执行勾选项以 [`TODO.md`](TODO.md) 为准。

## 2026-08-25: minimal observability boundary

- Structured events use JSON fields `event`, `level`, UTC timestamp, stable `error_code`, optional request/operation correlation, fixed route/component/outcome fields and duration; they never include body, source text, paths, secrets, SQL, raw exceptions or traceback.
- `X-Request-ID` is generated or safely echoed per HTTP response. Invalid or oversized values are replaced. Operation IDs are currently request-scoped correlation IDs only; persistent `ai_operations` records remain an AI business-layer concern.
- `/api/liveness` means the process can respond; `/api/health` remains readiness and is not healthy before preflight, database migration/connect, audit/recovery startup sequence completes. Diagnostic-only audit events do not automatically make a usable service unready.
- `/api/metrics` is a bounded, in-process snapshot with low-cardinality counters and duration aggregates. It resets on restart and does not claim cross-process aggregation or persistence.
- Logging/metrics failure must never block startup or a business request. I4 real ACL, capacity and resource-exhaustion evidence remains separate and not implemented by this decision.

## 2026-08-25: I4 evidence boundary

- I4 capacity evidence uses synthetic TXT only and records S0–S3 import/search/export timings and a bounded 40-cycle lifecycle smoke.
- Windows ACL, real disk-full/quota, S4 pressure scale, peak memory, power-loss, network filesystem and hardware corruption remain `not_verified`; controlled failure tests must not be reported as real resource exhaustion evidence.
- The deployment contract remains one process, one instance, local storage and one data_root owner. I4 does not introduce cross-process locks, workers, queues or distributed coordination.

## 2026-08-26: explicit revision and deterministic chunk indexing

- AI indexing is explicit through `POST /api/materials/{id}/ai-index`; import and startup never auto-index existing materials.
- A revision fingerprint is derived from source hash, extraction text hash, parser id and parser version. Repeating indexing for the same source reuses the current revision and ready chunks; a new extraction supersedes the previous current revision.
- The first chunk strategy is deterministic `boundary_window` version `1.0.0`, using Python Unicode code-point offsets, stable whitespace normalization and a bounded overlap. Empty extraction produces zero chunks and reports `empty`.
- Existing `text_spans` store span text but not absolute offsets. Chunk-to-span links therefore use ordinal/id order plus exact sequential text matching in the extraction text. Unmatched or ambiguous source text is not linked; the system does not fabricate page/slide offsets.
- Purge relies on the existing foreign-key cascade to remove revisions, chunks and chunk_spans; chunk FTS rows are removed explicitly. Restore reuses derived rows and does not duplicate them.

## 2026-08-26: lexical chunk retrieval boundary

- Retrieval is explicit through `POST /api/retrieval`; it never auto-indexes materials and never calls a provider.
- Policy `lexical_fts_v1` uses safe ASCII token AND queries through `chunks_search` and parameterized substring fallback for Unicode/special tokens. Results are restricted to active material, current revision and ready chunks, with stable score/start-offset/id ordering and top-k 1–50.
- Each request persists a `retrieval_runs` row. Successful hits persist `retrieval_hits`; empty results use `retrieval_empty`; unindexed scope uses `retrieval_not_ready`. Lexical retrieval leaves embedding/provider/rerank fields NULL.
- `chunks_search` is synchronized when indexing and by an idempotent connection check that only reflects existing ready chunks and removes orphan rows; it never creates chunks or runs AI repair. Preview text is bounded and API responses do not expose paths, SQL, tracebacks or full source text.
- Citation verification, context assembly, fake provider and Q&A remain separate next steps.

## 2026-08-20: AI / learning architecture boundary

- AI/学习当前只完成 architecture-only 设计，不接入真实 provider、不自动索引历史材料、不引入外部 vector DB、不引入后台队列。
- `materials`、`extractions`、`text_spans` 保持 source of truth；revision、chunks、embeddings、retrieval、answers、cards、exercises、plans 都是派生数据或用户状态，不能覆盖 source。
- 第一阶段明确采用 SQLite FTS5 lexical retrieval first；embedding 先预留 provider/model/content-hash 接口，规模证据充分前不引入外部向量数据库。
- provider 通过独立 Protocol/adapter 接收已组装 messages/texts，不读本地文件、不写 SQLite、不接触 FastAPI request；provider 未配置时应用仍应启动，AI 请求返回稳定 `provider_not_configured`。
- 所有 AI 生成操作预留 `ai_operations` 状态、input fingerprint、source revision、prompt/policy/provider/model metadata；第一阶段可同步执行但不自动引入 worker。
- citation 使用独立可验证记录，模型不能自行创造 citation；source 删除/purge 后历史 artifact 可保留，但 citation 标记 `source_unavailable`。
- AI 生成卡片、练习、计划必须先是 draft，用户确认/编辑后才 ready/active；重新生成不得静默覆盖用户状态。
- 当前 migration v2 已为 Phase 0/1 schema 预留表；AI 业务逻辑仍未实现。

## 2026-08-19: four-directory boundary

- `H:\studybuddy` is the only formal product directory.
- `H:\studybuddy-composer` stores reference registrations, component cards and independent smoke evidence.
- `H:\studybuddy-test` stores isolated system-test runs and artifacts.
- `H:\studybuddy-integration` validates real component combinations before formal assembly.
- Composer and integration code must not be imported by the formal product.
- No component may be called available before a real test proves it works.

## Durable implementation decisions

- Formal parsing is independently reimplemented from approved contracts; Composer and Integration are not runtime dependencies.
- Parser supports TXT, Markdown, PDF, DOCX and PPTX; unsupported legacy formats are rejected with stable errors.
- Parser does not own original storage or database persistence.
- SQLite is the current local source of persistence; database evolution must use the migration runner.
- Backup/restore is explicit operator functionality. Verify never repairs; restore targets a new empty directory and preserves schema version/history.
- AI follows revision → chunks → retrieval → citations → Q&A → cards/exercises. Generated artifacts begin as drafts and must preserve user edits.

## 2026-08-25: infrastructure v1 closeout

- I1 migration/schema versioning、I2 backup/restore operator 闭环、I3 最小可观察性与 I4 真实环境/容量基线（时间盒）均已完成。
- I4 中 Windows ACL/只读目录、真实磁盘满或配额、S4 更高压力规模、peak memory、断电、网络盘、硬件/文件系统损坏等项保持 `not_verified`，并已明确作为 v1 运行边界接受；这些项目不阻塞基础设施 v1 收口，也不得标记为已通过。
- 自此可以正式宣告 StudyBuddy **本地单进程文件材料基础设施 v1 基本完工**，并作为 AI MVP 的数据基础。
- 下一产品优先级为 AI Phase 1：material revision → deterministic chunking → chunk FTS5 lexical retrieval → citation contract → deterministic fake provider → Q&A API/UI。

## 2026-08-25: local environment governance map

- 记录 StudyBuddy 全部本地目录职责、远端、Git 状态和相互关系于 [`LOCAL_ENVIRONMENT_MAP.md`](LOCAL_ENVIRONMENT_MAP.md)。
- 核心四级目录：`studybuddy`（正式系统）、`studybuddy-composer`（组件实验工厂）、`studybuddy-integration`（集成装配工厂）、`studybuddy-test`（测试与 artifact）。
- 参考与历史版本：`kaobuddy-remote-audit`、`pi-studybuddy`、`AIStudyBuddy`、`ai-studybuddy`、`ai-studybuddy-composer`、`pi-references`，只用于提取契约，不得直接复制源码。
- `pi-references` 含 API key/token/account，绝不进入仓库、日志、数据库或前端；只用于 Provider 契约研究。
- 前两版本的组件选择参考位于 `ai-studybuddy-composer` 与 `pi-references`，正式接入必须经 Composer smoke + Integration 组装 + 主系统重新实现。
