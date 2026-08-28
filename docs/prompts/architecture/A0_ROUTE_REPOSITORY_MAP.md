# A0 路由与 Repository 职责地图

## 1. FastAPI 路由清单（冻结）

以下为从 `backend/app/main.py` AST 实际扫描得到的 151 条路由；未列出的 HTTP method 不应被拆分后意外开放。

### System / AI / materials / tasks

| Method | Path | 默认成功码 | 归属 |
|---|---|---:|---|
| GET | `/api/liveness` | 200 | system |
| GET | `/api/metrics` | 200 | system |
| GET | `/api/health` | 200 | system |
| GET | `/api/readiness` | 200 | system |
| GET | `/api/ai/capabilities` | 200 | Provider |
| GET | `/api/materials` | 200 | materials |
| GET | `/api/materials/deleted` | 200 | materials |
| POST | `/api/materials/export` | 200 | materials |
| POST | `/api/retrieval` | 200 | AI/retrieval |
| POST | `/api/context/assemble` | 200 | AI/context |
| POST | `/api/citation/validate` | 200 | AI/citation |
| GET | `/api/qa/threads` | 200 | Q&A |
| GET | `/api/qa/threads/{thread_id}` | 200 | Q&A |
| GET | `/api/qa/citations/{citation_key}` | 200 | Q&A/citation |
| POST | `/api/qa/ask` | 200 | Q&A/Provider |
| POST | `/api/materials/{material_id}/ai-index` | 200 | AI/embedding |
| POST | `/api/materials/{material_id}/ai-index/tasks` | 202 | tasks/embedding |
| GET | `/api/tasks/{task_id}` | 200 | tasks |
| POST | `/api/tasks/{task_id}/cancel` | 200 | tasks |
| POST | `/api/tasks/{task_id}/retry` | 200 | tasks |
| GET | `/api/materials/{material_id}/ai-index` | 200 | AI/embedding |
| POST | `/api/materials` | 201 | materials |
| POST | `/api/materials/batch` | 201 | materials |
| GET | `/api/materials/{material_id}/original` | 200 bytes | materials/storage |
| GET | `/api/materials/{material_id}/text` | 200 bytes | materials/storage |
| GET | `/api/materials/{material_id}` | 200 | materials |
| POST | `/api/materials/{material_id}/restore` | 200 | materials |
| POST | `/api/materials/{material_id}/purge` | 200 | materials |
| PATCH | `/api/materials/{material_id}` | 200 | materials |
| DELETE | `/api/materials/{material_id}` | 204 | materials |

### Study: practice, mistakes, cram

- `GET /api/study/practice-sessions` 200; `POST` 201
- `GET /api/study/practice-sessions/{session_id}` 200
- `POST /api/study/practice-sessions/{session_id}/start` 200
- `POST /api/study/practice-sessions/{session_id}/items/{item_id}/submit` 200
- `POST /api/study/practice-sessions/{session_id}/finish` 200
- `POST /api/study/practice-sessions/{session_id}/archive` 200
- `GET /api/study/practice-sessions/{session_id}/result` 200
- `GET /api/study/mistakes`, `/api/study/mistakes/{mistake_id}`, `/api/study/weak-points` 200
- `POST /api/study/attempts/{attempt_id}/review`, `/mark-mistake` 200
- `POST /api/study/mistakes/{mistake_id}/feedback` 201; `/redo`, `/archive` 200
- `GET /api/study/cram-goals` 200; `POST` 201; `GET /{goal_id}` 200
- `POST /api/study/cram-goals/{goal_id}/{active|completed|archived}` 200
- `POST /api/study/cram-goals/{goal_id}/sessions` 201
- `GET /api/study/cram-goals/{goal_id}/sessions/{session_id}/result` 200

### Study: plans, notes, rhythm, cards, exercises, capture, reports

All paths and default codes are frozen in the AST inventory in the A0 audit commit. The compact grouping is:

- goals/modules/plans/items/dependencies/sources: GET 200, create 201, PATCH 200, transitions 200, dependency delete 204;
- rhythm settings/summary/list/export: GET 200, PUT 200, allocation create 201, patch 200, delete 204;
- notes/blocks/source links/export: GET 200, create 201, PUT/PATCH 200, destructive link/block deletes 204, transitions/generate 200;
- decks/cards/exercise-sets/exercises/attempts: reads 200, creates 201, updates/transitions/generate 200, reviews/attempts 201;
- capture: session create 201, list/detail/upload/transcribe/transcript edit/confirm/reject/archive 200;
- reports: create 201, list/detail/preview/export/delivery/attempts 200.

### Error contract

`HTTPException.detail` is the public error payload. Stable mappings include:

- lifecycle/material: `material_not_found`, `material_deleted`, `material_not_found_or_deleted`, `material_invalid_state`, `material_rename_failed`, `material_delete_failed`, `material_restore_failed`, `material_purge_failed`;
- input/upload/export: `invalid_filename`, `file_too_large`, `invalid_pagination`, `invalid_status`, `export_*`, `invalid_request`;
- Provider: `provider_timeout`→504; rate/quota→429; not configured/invalid/connection/unavailable→503; other provider failures→502;
- Phase 9D: `capture_not_found`, `report_not_found`, `transcript_not_found`→404; invalid state/source/idempotency conflicts→409; unconfigured transcription→503; other mapped domain failures→400;
- study domain uses explicit `ValueError` codes translated by `_study_error` / `_phase9c_error` and must remain opaque/safe.

Before deleting or changing a code, generate an error-code inventory from `HTTPException` and `ValueError` paths and add/adjust contract tests. Do not infer a complete list from this summary alone.

## 2. Repository function/domain map

`backend/app/repository.py` is 6,243 lines and is a compatibility boundary, not a pure model file. Public and internal functions fall into these groups:

| Range / representative functions | Target repository module | Boundary notes |
|---|---|---|
| `connect`, `utc_now`, search-index helpers, task row/claim/progress/recover | `connection.py`, `tasks.py` | `connect` must still run migration, assert v13, sync FTS; task runner imports old names |
| `save_extraction`, `save_material_with_extraction`, listing/page/search, restore/rename/purge/delete, `get_material`, `get_spans` | `materials.py` | storage/hash/parser remain in caller or storage layer; transaction semantics unchanged |
| `create_or_get_revision`, `index_material_revision`, chunk/retrieval candidates, `run_*_retrieval`, `assemble_context`, citation validation | `ai.py` | revision/chunk/retrieval/citation are coupled; preserve policy/version constants |
| Q&A operation/fingerprint/idempotency/persist/history/detail | `ai.py` | provider call remains app orchestration; citation/source lifecycle crosses materials |
| embedding encode/decode/staleness/index/verify/rebuild | `ai.py` | provider adapter remains `embedding.py/providers.py`; task name remains `embedding_index` |
| decks/cards/generation and exercise sets/exercises/attempts | `study.py` / `learning.py` | generated artifacts start draft and keep citations/source revision |
| learning goals/modules/plans/items/dependencies/progress/source links | `plans.py` | append-only progress and DAG invariants stay in one transaction |
| rhythm settings/allocations/summary | `plans.py` | timezone/date and allocation limits are domain invariants |
| notes/blocks/modules/source links/generation | `learning.py` | generated note citation/source lifecycle crosses materials |
| practice sessions/mistakes/weak points/cram | `practice.py` | immutable session snapshot, deadline, review facts, redo boundaries |
| capture assets/transcription operations/segments/confirm/reject | `capture.py` | original path/hash and confirmed transcript→material pipeline are coupled |
| report projection/snapshot/export/delivery audit | `reports.py`, `delivery.py` | safe payload, fingerprint, default-off delivery, audit/idempotency |
| operation task state machine | `tasks.py` | explicit-only runner; no scheduler/worker added by split |

## 3. A1 repository structure

A1 adds `backend/app/repositories/` with explicit domain export modules: `connection.py`, `materials.py`, `ai.py`, `plans.py`, `learning.py`, `practice.py`, `capture.py`, `reports.py`, and `tasks.py`. `backend/app/repository.py` remains the compatibility façade and re-exports all 305 public symbols, including legacy private helpers needed by existing transaction monkeypatch tests. To preserve cross-domain helper identity, transaction behavior, and patching semantics, the current A1 implementation bodies remain in `repositories/_legacy.py`; the domain modules are auditable exports, not a claim of complete internal function-body decoupling. No production caller was changed.

## 4. A2 application structure

A2 keeps `backend/app/main.py` as the public compatibility façade and the sole non-growing legacy holder of the existing inline `INDEX_HTML`; no `web_ui.py`, formal static root or new large UI file exists. `backend/app/app_factory.py` owns FastAPI construction, application state and middleware; `backend/app/lifespan.py` owns the unchanged startup sequence; small `schemas/`, helpers and services own their extracted support code. `backend/app/api/registration.py` calls 14 domain route modules in the original registration order: system, material collection, retrieval/Q&A, indexing, tasks, generation, practice, plans, rhythm, notes, learning, capture/reports, material detail and `/`.

The route modules receive an explicit dependency context. `main.py` forwards existing monkeypatch assignments to the factory, route modules, import service and lifespan dependencies so direct test imports continue to behave as before. `backend/scripts/check-source-size.py` enforces a 32 KiB limit for new or substantially rewritten managed source files, forbids growth of pre-existing oversized files, and verifies the inline UI payload hash.

## 5. External import/call sites

Direct imports of `repository` found in production code:

- `backend/app/main.py`: broad compatibility import plus local lazy imports for vector/hybrid retrieval and embedding indexing;
- `backend/app/cli.py`: `connect`, `recover_active_operation_tasks`;
- `backend/app/recovery.py`: `connect`, `recover_active_operation_tasks`;
- `backend/app/task_handlers.py`: `connect`, `index_embeddings_for_material`;
- `backend/app/task_runner.py`: task claim/update/heartbeat/finish/recovery functions and `connect as connect_database`;
- `backend/app/delivery.py`: `find_report_delivery_replay`, `record_report_delivery_attempt`.

Test code additionally imports repository functions directly. Preserve all tested public symbols through a re-export façade until a separately accepted API migration.

## 6. Cross-domain seams to preserve

- material source identity → revision/chunks → retrieval/citation → generated card/note/report;
- capture confirmed transcript → extraction/revision/chunk/FTS search;
- soft/hard delete → citation/source degradation and safe export;
- task operation ↔ embedding index only;
- provider adapter errors ↔ route-safe stable HTTP mapping;
- every write uses caller-owned `with connect(...)` transaction and migration-controlled schema.
