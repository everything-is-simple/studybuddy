# B3 Report Component Formal Contract

> Status: `contract-frozen`.
> Gate: B3 C3. This document freezes the Formal report boundary for C4 implementation. It does not itself change production code, schema, migrations, API behavior, or UI behavior.

## 1. Decision

B3 reuses the existing Phase 9D report domain as the only Formal report system. Formal must not create a parallel report projection, snapshot table, report API family, report audit, or delivery state store.

The Composer C1 and isolated Integration C2 results establish candidate feasibility only for the declared synthetic scope. They do not authorize copying their implementation into Formal. C4 must independently implement or assemble against this contract and the existing Phase 9D domain/repository boundaries.

First Formal scope is local, deterministic, project-scoped report projection with JSON and Markdown export. The supported report kinds are `daily`, `weekly`, `monthly`, and `exam_alert`.

The following remain outside B3 and are not authorized by this contract: PDF, HTML/email rendering, Feishu cards, AI narrative, live delivery, external recipients, network access, scheduler/worker execution, automatic reminders, and multi-user/parent accounts.

## 2. Existing Formal reuse audit

The following existing Formal behavior is the baseline for C4 and must remain behaviorally compatible:

| Boundary | Existing source of truth | C4 rule |
|---|---|---|
| Report aggregation | `backend/app/repositories/capture.py` and report projection helpers | Reuse the existing read-only projection semantics; do not duplicate fact ownership |
| Snapshot persistence | existing `report_snapshots` schema and repository transaction | Preserve snapshot immutability, fingerprint replay, and project scope |
| API | `/api/study/reports`, detail, preview, and export routes | Preserve stable request/response/error behavior unless a separately evidenced gap is found |
| UI | `backend/app/static/reports.html` | Extend only for approved B3 states; do not imply delivery or unverified capabilities |
| Backup/restore | existing backup and restore acceptance contract | Preserve schema history and report facts; restore must not generate or repair reports |
| Source lifecycle | service-derived source-quality aggregation | Preserve `valid`, `stale`, `source_deleted`, and `source_unavailable` counts without source identity leakage |

C4 must first prove the current implementation against this contract. A new migration is not expected. Any discovered semantic conflict blocks C4 and requires a contract amendment before code changes.

## 3. Input contract

Report generation is an explicit synchronous request. The server supplies `project_id`; clients cannot select or override it.

Required request fields:

- `report_kind`: exactly one of `daily`, `weekly`, `monthly`, `exam_alert`.
- `timezone`: valid IANA timezone name, interpreted by the server.
- `period_start`, `period_end`: strict `YYYY-MM-DD` dates with `period_start < period_end`; the period is half-open `[start, end)`.

The projection reads only existing project-scoped 9A-9D facts. Clients cannot submit aggregate counts, source status, exam details, report body, prompts, answers, citations, stored paths, provider metadata, or arbitrary report JSON.

The server excludes facts outside the period, facts from other projects, future facts where the domain rule excludes them, invalid statuses, and records without a valid timestamp. Empty data is valid and returns safe zero/empty aggregates.

## 4. Output contract

A ready snapshot contains a fixed safe payload and deterministic Markdown derived from it. The safe payload may contain only:

- period metadata: report kind, normalized dates, timezone, and generated timestamp where applicable;
- plan aggregates: counts and planned minutes;
- rhythm aggregates: allocated day/minute totals, unallocated eligible count, overload day count;
- practice aggregates: session, attempt, deterministic correct/incorrect, pending review, and completed session counts;
- feedback aggregates: mistake/review/fixed/reopened/archived/weak-point counts;
- source-quality aggregates: valid, stale, source-deleted, source-unavailable, and uncertain capture counts;
- exam alert bucket and imminent boolean, without exam title, subject, or raw date;
- quality flags such as pending review, source warnings, and uncertain capture;
- server-generated content version and aggregation fingerprint as metadata.

The payload must not contain material names, goal/plan/item titles, notes, source text, transcript/OCR/ASR text, answer keys, submitted answers, question text, Q&A text, raw prompts, local paths, secrets, SQL, provider responses, or complete private dates/details.

JSON export is canonical stable-key JSON. Markdown is deterministic output derived only from the safe payload. Both are bounded by the existing server output limit and must be rejected if redaction validation fails. PDF and arbitrary formats are rejected.

## 5. Snapshot, lifecycle, and idempotency

A snapshot is project-scoped, read-only after creation, and identified by report kind, normalized half-open period, content version, and aggregation fingerprint. Repeating the same request against unchanged facts returns a safe replay rather than creating an additional snapshot. A changed fact, period, timezone, report kind, or content rule produces a new snapshot.

Allowed report states remain `draft`, `ready`, `failed`, and `archived` as defined by Phase 9D. Current synchronous generation may create `ready` or safe failure outcomes; no background job is introduced by B3. Archive is explicit and terminal for ordinary writes.

Report generation is read-only with respect to learning facts. It does not update goals, plans, rhythm, notes, practice, attempts, reviews, mistakes, weak points, capture sessions, transcripts, or materials.

## 6. Source lifecycle and backup/restore

Source quality is derived server-side. The report may retain aggregate degradation counts and flags only:

- `valid`: source remains safely available and identity is valid;
- `stale`: source identity exists but derived content is no longer current;
- `source_deleted`: source was soft-deleted;
- `source_unavailable`: source was purged, missing, or cannot be safely verified.

Soft delete or purge must not erase report history, transcript history, operation metadata, or confirmed revision metadata. It must not make a historical report claim that an unavailable source is valid. Report output must not reveal the source name, path, quote, or body.

Backup, verify, restore, startup, and ordinary report reads must not invoke OCR, ASR, AI providers, report generation, delivery, scheduler, or repair. Restore targets a new empty data root and preserves schema migration history, `PRAGMA user_version`, report snapshots, source tombstone/degradation state, and append-only audit facts.

## 7. Errors and security

Formal responses expose stable safe errors only. At minimum:

- `project_scope_violation`
- `report_invalid_kind`
- `report_invalid_period`
- `report_not_found`
- `report_invalid_state`
- `report_redaction_violation`
- `report_generation_failed`
- `payload_too_large`
- `invalid_pagination`

No response or log may expose traceback, SQL, absolute private path, secret, raw provider/tool error, source body, or report serialization internals.

All report mutations that support retries use applicable `Idempotency-Key` semantics. The report component does not add delivery behavior. `delivery=off` remains the default; `dry_run` is not sent; `live` remains rejected and belongs to B4.

## 8. C4/C5 acceptance requirements

C4 must provide focused Formal tests for safe empty/normal projections, all four report kinds, timezone and half-open boundaries, project scope, deterministic fingerprint/replay, stable JSON/Markdown, read-only fact protection, source degradation, redaction, invalid input, output limits, and unsupported PDF/arbitrary formats.

C5 must provide backend, browser, source lifecycle, backup/restore, privacy, reload/retry, and operator/runtime evidence. It must verify that the UI exposes projection and export states without presenting delivery as sent or unverified features as available. Full backend regression is required when shared repository/API behavior changes.

## 9. Non-goals and not_verified boundaries

This contract does not establish general report quality, educational or medical suitability, multi-user authorization, arbitrary document/report formats, PDF rendering quality, external delivery, AI narrative quality, scheduler reliability, concurrency/capacity, crash/power-loss recovery, or global production `real-pass`.

## 10. Gate conclusion

B3 C3 is `contract-frozen` for the exact local single-process, single-instance, SQLite, project-scoped, deterministic JSON/Markdown report scope. B3 C4 may begin. B4 delivery remains blocked until B3 scoped closeout and its separate delivery gates are complete.
