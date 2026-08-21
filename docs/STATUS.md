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
| AI/learning architecture | researching | `ai-learning-architecture.md`; architecture-only |
| Material revision / deterministic chunks | implemented / backend-tested | `backend/app/chunking.py`, `backend/app/repository.py`, `backend/tests/test_ai_indexing.py` |
| Chunk FTS5 retrieval | implemented / backend-tested | `backend/app/repository.py`, `backend/tests/test_retrieval.py` |
| Context assembler + citation contract | implemented / backend-tested | `backend/app/repository.py`, `backend/tests/test_context_assembler.py` |
| Deterministic fake provider | implemented / backend-tested | `backend/app/providers.py`, `backend/tests/test_ai_provider.py` |
| Q&A API + persistence | implemented / backend-tested | `backend/app/repository.py`, `backend/app/main.py`, `backend/tests/test_qa_api.py` |
| Minimal Q&A UI + citation location | implemented / browser-tested | `backend/app/main.py`, `backend/tests/browser_qa.spec.js` |
| Q&A citation lifecycle + backup/restore | implemented / backend-tested | `backend/tests/test_ai_citation_lifecycle.py`, `backend/tests/test_ai_backup_restore.py` |
| Cards/exercises/study plans | not started | `TODO.md` |

## Current limits

- Supported deployment: single process, single instance, local storage.
- Multiple workers or multiple instances must not share one `data_root`.
- I4 is time-box closed for infrastructure v1: synthetic TXT S0–S3 capacity and 40-cycle lifecycle smoke are real; disk-full, power-loss, network filesystem, hardware corruption, ACL, peak memory and S4 capacity are explicitly recorded as not verified and accepted as v1 deployment limits.
- Metrics are process-local, reset on restart, and do not provide cross-process aggregation; operation IDs are request-scoped correlation only.
- Material revision, explicit deterministic chunk indexing, lexical chunk retrieval, context assembly with citation contract, deterministic fake provider, synchronous Q&A API/persistence and a minimal Q&A UI are implemented. Real provider integration, complete Q&A history/multi-material UX, cards, exercises and study plans are not implemented.

For the authoritative project status and task order, see [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md), [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md), and [`TODO.md`](TODO.md).
