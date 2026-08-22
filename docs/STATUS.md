# StudyBuddy Status

> 当前整体阶段性估算为 **45%–50%**：文件材料管理局部 `real-pass`，完整 StudyBuddy 尚未达到全局 `real-pass`。

| Area | Status | Evidence |
|---|---|---|
| Formal file parser Adapter | implemented / local real-pass | `backend/app/adapters/file_parsers/` and test artifacts |
| Formal file import | real-pass | `H:\studybuddy-test\artifacts\formal-file-import-final\latest.json` |
| Batch and folder import | real-pass | formal multi-file/folder artifacts |
| Material management and recycle bin | real-pass | formal management/recycle-bin artifacts |
| Material export and search | real-pass | formal export/search artifacts |
| SQLite/storage consistency | implemented | backend transaction, recovery, security and contention tests |
| Startup preflight/readiness | implemented | `backend/app/startup_preflight.py`, tests |
| I1 migration/schema versioning | implemented | `backend/app/migrations/`, `backend/tests/test_migrations.py` |
| I2 operator backup/restore | implemented | `backend/app/backup.py`, CLI, restore acceptance tests |
| I3 minimal observability | implemented | `backend/app/observability.py`, `backend/tests/test_observability.py` |
| I4 real environment/capacity baseline | time-box closed (v1) | `H:\studybuddy-test\artifacts\infrastructure-i4\latest.json`, `latest.md` |
| Local single-process infrastructure v1 | basically complete | I1+I2+I3 implemented; I4 time-box closed with declared limits |
| AI/learning architecture | architecture plus Phase 4 implementation | `ai-learning-architecture.md`; real provider and later learning design remain future scope |
| Material revision / deterministic chunks | implemented / backend-tested | `backend/app/chunking.py`, `backend/app/repository.py`, `backend/tests/test_ai_indexing.py` |
| Chunk FTS5 retrieval | implemented / backend-tested | `backend/app/repository.py`, `backend/tests/test_retrieval.py` |
| Context assembler + citation contract | implemented / backend-tested | `backend/app/repository.py`, `backend/tests/test_context_assembler.py` |
| Deterministic fake provider | implemented / backend-tested | `backend/app/providers.py`, `backend/tests/test_ai_provider.py` |
| Q&A API + persistence | implemented / backend-tested | `backend/app/repository.py`, `backend/app/main.py`, `backend/tests/test_qa_api.py`; history API covered in same suite |
| Q&A UI + history + citation navigation | Phase 4 complete / browser-tested | `backend/app/main.py`, `backend/tests/browser_qa.spec.js` |
| Q&A citation lifecycle + backup/restore | implemented / backend-tested | `backend/tests/test_ai_citation_lifecycle.py`, `backend/tests/test_ai_backup_restore.py` |
| Phase 5 OpenAI-compatible adapter | implemented / mock-tested / DeepSeek and Agnes `agnes-2.5-flash` API+UI smoke passed; redacted three-attempt API acceptance runner implemented; other-provider validation pending | `backend/app/providers.py`, `backend/scripts/agnes-*.ps1`, `backend/tests/test_agnes_launcher.py`, `backend/tests/test_phase5_provider.py`, `backend/tests/test_real_provider_smoke.py`, `backend/tests/browser_qa.spec.js`; one explicit Agnes profile/model is used per process; `agnes-2.5-pro` remains not_verified after `provider_unavailable` API evidence |
| Phase 6 P6-A Provider runtime contract | implemented / backend-tested / Chromium-tested | `backend/app/providers.py`, `backend/app/main.py`, `backend/tests/test_ai_provider.py`, `backend/tests/browser_qa.spec.js`; default is `not_configured`, explicit fake is deterministic/demo, complete generic configuration is `configured` + `unverified`; capabilities does not perform a network probe |
| Phase 6 P6-B Q&A thread workspace | implemented / backend-tested / Chromium-tested | `backend/app/main.py`, `backend/app/repository.py`, `backend/tests/test_qa_api.py`, `backend/tests/browser_qa.spec.js`; thread list/status, new/switch/continue flow, timeline, citation states, scope/request stale-response protection and session refresh recovery are implemented; thread scope is not persisted and Provider HTTP is not truly cancelled |
| Phase 6 P6-C cross-material citation/export bridge | implemented / backend-tested / Chromium-tested | `backend/app/main.py`, `backend/app/repository.py`, `backend/tests/test_ai_citation_lifecycle.py`, `backend/tests/test_material_export.py`, `backend/tests/browser_qa.spec.js`; material/detail to Q&A, multi-material scope context, URL/history material/thread/scope/citation identifiers, citation revision/chunk/span/body location, return to Q&A, original/text export continuity and deleted/purged unavailable behavior are covered; no migration, purge does not restore a deleted material name |
| Phase 6 P6-D navigation/notification/responsive/accessibility | implemented / backend-regression-tested / Chromium-tested desktop+narrow+keyboard | `backend/app/main.py`, `backend/tests/browser_p6d.spec.js`; unified header/nav and current view/material/thread/scope context, page-level status/alert plus supplementary toast, safe failure/retry messaging, keyboard view switching, visible focus, dialog Escape/focus return, landmark/label/current/status/alert/dialog semantics and 390x844 overflow checks are covered; no API or migration, no axe dependency, real Provider and system screen-reader evidence remain not_verified |
| Cards/exercises/study plans | not started | `TODO.md` |

## Current limits

- Supported deployment: single process, single instance, local storage.
- Multiple workers or multiple instances must not share one `data_root`.
- I4 is time-box closed for infrastructure v1: synthetic TXT S0–S3 capacity and 40-cycle lifecycle smoke are real; disk-full, power-loss, network filesystem, hardware corruption, ACL, peak memory and S4 capacity are explicitly recorded as not verified and accepted as v1 deployment limits.
- Metrics are process-local, reset on restart, and do not provide cross-process aggregation; operation IDs are request-scoped correlation only. `ai_operations.input_fingerprint` remains audit metadata. Synchronous Q&A supports explicit `Idempotency-Key`: succeeded requests replay the persisted response without provider/artifact duplication, running requests conflict, failed keys may retry, and a request transaction reclaims operations running beyond a five-minute lease as `stale/qa_operation_stale`. This is not a background scan, cross-process coordination, cancel workflow or real crash-recovery guarantee.
- Material revision, explicit deterministic chunk indexing, lexical chunk retrieval, context assembly with citation contract, deterministic fake provider, synchronous Q&A API/persistence, explicit idempotent Q&A replay and request-triggered stale recovery, Q&A history, multi-material scope, citation detail/navigation and the Phase 4 full-path browser E2E are implemented and verified. Phase 5 now has a tested OpenAI-compatible adapter, v3 provider metadata migration, v4 Q&A idempotency migration, and DeepSeek `deepseek-chat` adapter/API-level/Chromium UI synthetic smoke passes; other provider-specific validation remains pending. Background stale scanning, cancel and cross-process recovery are not implemented. Cards, exercises and study plans are not implemented.

For the authoritative project status and task order, see [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md), [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md), and [`TODO.md`](TODO.md).
