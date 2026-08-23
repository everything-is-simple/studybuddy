# StudyBuddy Decisions

## 2026-08-28: formal successor versus feature breadth

- StudyBuddy is the formal successor system for governance and verified local operation, not yet a feature-complete replacement for KaoBuddy or the prior `ai-studybuddy`/`pi-studybuddy` generations.
- The accepted evolution claim is limited to formal source ownership, Composer → Integration → formal reimplementation → system-test evidence flow, migration-controlled persistence, storage and backup safety, revision/chunk/retrieval/citation traceability, provider evidence discipline, and layered acceptance states.
- Historical cards, exercises, study plans, S1–S7 workflows, OCR/ASR, reports or worker concepts remain reference scope unless independently reimplemented and accepted in the formal system. Historical code, component smoke, fake-provider evidence and design documents do not establish formal completion.
- Phase 9 is split into 9A learning domain/plan foundation, 9B S1/S2 material learning, 9C S3/S4/S5 exercise and feedback workflows, and conditional 9D S6/S7 extension services. No single Phase 9 completion claim may cover all of these without independent gates.
- Phase 8 must close Cards/Exercises before Phase 9C can begin. Phase 7 must close its remaining real embedding, retrieval-mode Chromium and indexing lease/retry evidence before Phase 8 begins, according to the current roadmap gate.

## 2026-08-27: P6-E evidence and governance boundary

- P6-A through P6-D remain implemented; P6-E fake Provider core workflow acceptance is complete and recorded in [`P6E_ACCEPTANCE_EVIDENCE.md`](P6E_ACCEPTANCE_EVIDENCE.md).
- The accepted fake workflow is import → ready → explicit indexing → retrieval → thread → Q&A → citation → body/source location → material/Q&A return → export → refresh/history. Empty retrieval, unconfigured Provider, timeout/retry, duplicate click, stale thread response, deleted source/export safety and related failure contracts are part of the acceptance boundary.
- DeepSeek `deepseek-chat` and Agnes `agnes-ai-hub` / `agnes-2.5-flash` real Provider evidence remains scoped to exact provider/model/gateway configurations. A real Provider UI path is `not_verified` unless its explicit target, model, gateway and secret-backed runtime gate actually ran; fake/mock results never become real-pass.
- No P6-E API, business table or migration is required. Existing generation/context checks are the cancellation boundary: synchronous Provider requests are not cancelled, stale responses are ignored.
- Governance source of truth is split deliberately: `PHASE_ROADMAP.md` defines sequence and completion criteria, `STATUS.md` records evidence state, `TODO.md` is the executable checklist, and `P6E_ACCEPTANCE_EVIDENCE.md` records redacted P6-E gates. Contradictory claims in other documents must be corrected to these sources.
- P6-E exact real Provider UI evidence for DeepSeek `deepseek-chat` and Agnes `agnes-2.5-flash` has passed under explicit target/model/gateway gates. The current product priority is to close the remaining Phase 7 evidence: a real embedding provider, retrieval-mode Chromium acceptance, and lease/failure-retry coverage. Cards, exercises, plans, workers, multi-user and cloud capabilities remain unimplemented.

## 2026-08-25: project progress and priority boundary

- 当前项目整体阶段性完成度按功能加权估算为 45%–50%；该估算不是测试通过率。
- 文件材料导入、管理、搜索、导出已形成局部 `real-pass`；I1 migration/schema versioning、I2 backup/restore、I3 最小可观察性和 I4 时间盒基线均已完成，基础设施 v1 已按声明边界收口。
- 当前项目 Phase 4 的 AI 最小闭环已完成：material revision/chunk → SQLite FTS5 retrieval → citation → deterministic fake provider → Q&A/history/multi-material/citation navigation。下一产品优先级是 Phase 5 真实 Provider 接入。
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
- Context assembly and citation contract are now implemented. `assemble_context()` produces ordered context blocks with `ctx-{mid8}-{cid8}` citation keys; `validate_citation_key()` returns one of four statuses: `valid`, `invalid_format`, `source_deleted`, `source_purged`. Token budget truncation preserves complete blocks.
- Provider configuration is explicit. The default state is `provider_not_configured`; `GET /api/ai/capabilities` reports that stable boundary without leaking secrets. `STUDYBUDDY_AI_PROVIDER=fake` enables deterministic fake generation through the provider registry.
- Synchronous `POST /api/qa/ask` persists a running `ai_operations` record and user message before retrieval/provider work. On success it atomically writes the assistant message, ready cited answer, verified citations and succeeded operation. Provider calls happen outside the final SQLite write transaction. Only citation keys emitted by assembled context and revalidated server-side may persist; a provider-forged or unavailable key fails generation without an answer artifact.
- The minimal Q&A UI is material-scoped and only enables asking after explicit indexing. It shows response citations and uses a bounded citation-detail endpoint to locate the cited current-material chunk by offsets. Soft deletion keeps historical citations but reports `source_deleted`; purge transactionally changes only that material's valid historical citations to `source_unavailable`, retaining answer/message history without source text. Backup/restore tests preserve both valid and unavailable citation history.

## 2026-08-20: AI / learning architecture boundary

- AI/学习架构仍包含后续 architecture-only 设计；当前项目 Phase 4 的 deterministic fake provider Q&A 已实现并验收。真实 provider、不自动索引历史材料、外部 vector DB 和后台队列仍不在当前支持范围。
- `materials`、`extractions`、`text_spans` 保持 source of truth；revision、chunks、embeddings、retrieval、answers、cards、exercises、plans 都是派生数据或用户状态，不能覆盖 source。
- 第一阶段明确采用 SQLite FTS5 lexical retrieval first；embedding 先预留 provider/model/content-hash 接口，规模证据充分前不引入外部向量数据库。
- provider 通过独立 Protocol/adapter 接收已组装 messages/texts，不读本地文件、不写 SQLite、不接触 FastAPI request；provider 未配置时应用仍应启动，AI 请求返回稳定 `provider_not_configured`。
- 所有 AI 生成操作预留 `ai_operations` 状态、input fingerprint、source revision、prompt/policy/provider/model metadata；第一阶段可同步执行但不自动引入 worker。
- citation 使用独立可验证记录，模型不能自行创造 citation；source 删除/purge 后历史 artifact 可保留，但 citation 标记 `source_unavailable`。
- AI 生成卡片、练习、计划必须先是 draft，用户确认/编辑后才 ready/active；重新生成不得静默覆盖用户状态。
- 当前 migration v5 已包含 revision/chunk/retrieval/Q&A 与 embedding 所需 schema；v3/v4 分别补充 Provider metadata 与 Q&A idempotency，v5 补充 embedding identity/status/payload contract。Phase 7.1–7.7 的 fake/backend 主体已实现，但真实 embedding provider、retrieval-mode Chromium acceptance 和完整 lease/失败重试专项仍未完成；Cards、Exercises、Plans 等后续业务逻辑仍未实现。

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
- 当前项目 Phase 4 的可信 Q&A 用户闭环、Phase 5 adapter/精确 Provider smoke、Phase 6 P6-A–P6-E fake/default/UI 产品化验收已按对应 evidence 收口；DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 的 P6-E 精确真实 UI gate 也已通过。下一优先级是 Phase 7 的真实 embedding provider、retrieval-mode Chromium acceptance 和 lease/失败重试专项；Phase 4/6 已完成的 history/multi-material/citation navigation 不应重新列为待办。

## 2026-08-25: local environment governance map

- 记录 StudyBuddy 全部本地目录职责、远端、Git 状态和相互关系于 [`LOCAL_ENVIRONMENT_MAP.md`](LOCAL_ENVIRONMENT_MAP.md)。
- 核心四级目录：`studybuddy`（正式系统）、`studybuddy-composer`（组件实验工厂）、`studybuddy-integration`（集成装配工厂）、`studybuddy-test`（测试与 artifact）。
- 参考与历史版本：`kaobuddy-remote-audit`、`pi-studybuddy`、`AIStudyBuddy`、`ai-studybuddy`、`ai-studybuddy-composer`、`pi-references`，只用于提取契约，不得直接复制源码。
- `pi-references` 含 API key/token/account，绝不进入仓库、日志、数据库或前端；只用于 Provider 契约研究。
- 前两版本的组件选择参考位于 `ai-studybuddy-composer` 与 `pi-references`，正式接入必须经 Composer smoke + Integration 组装 + 主系统重新实现。
