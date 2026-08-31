# Phase 10-5 Observability and Readiness Evidence

> Status: `implemented/backend-pass`
> Gate F: passed for the local single-process v1 scope.

## Implemented Contract

`backend/app/observability.py` now emits safe structured events with a fixed schema:

- timestamp, event, level, stable error code, component/outcome, duration, retry/lease facts;
- request correlation from `X-Request-ID` or a generated opaque request ID;
- operation, task and project correlation only from controlled server-side context;
- no arbitrary event fields, dynamic metric labels, paths, SQL, source text, raw provider payloads, Authorization, secrets, tracebacks, answer keys, user answers or report content.

Metrics remain process-local, reset at restart, are not persistent, and do not aggregate across processes. They use fixed low-cardinality labels for HTTP, imports, task result/duration, startup/readiness, audit/recovery, backup/verify/restore and operator diagnostics. Opaque IDs are event correlation fields, never metric labels.

The approved embedding task path now preserves request -> operation -> task correlation: the enqueue request ID is saved in existing `ai_operations.request_id`; the explicit runner restores it only into the task event context. It is not returned by the task API.

## Health and Diagnostics

- `GET /api/liveness` reports only that the process can answer HTTP and remains `200 {"status":"ok"}` during a degraded state.
- `GET /api/health` is `200 {"status":"ok"}` only after preflight, migration/connect, audit and recovery complete with no diagnostic degradation.
- `GET /api/readiness` returns `200 {"status":"ready"}` only in that state; otherwise it returns `503` with a stable `not_ready` or `degraded` reason and no internal details.
- Startup audit now reports a safe status rather than silently treating integrity, foreign-key, required-object or relation failures as healthy. It remains diagnostic-only and does not migrate, repair or rebuild indexes.
- A stale recovered task and a runtime database/diagnostic failure make readiness degraded. They do not start a runner, retry a task, alter source state or repair data.
- `python -m backend.app diagnostics --data-root <root>` uses a SQLite URI read-only connection. Its JSON contains only `application_version`, schema version, task status counts, stable reasons and recommended actions. It returns nonzero for degraded/unavailable states and never prints paths, SQL, raw errors or content.

Backup, verify and restore now add safe start/success/failure events and low-cardinality metrics. Restore behavior remains explicit and non-repairing.

## Verification

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/test_observability.py backend/tests/test_backup_restore.py backend/tests/test_db_integrity_audit.py backend/tests/test_phase10_task_integration.py backend/tests/test_task_runner.py backend/tests/test_recovery_consistency.py backend/tests/test_startup_preflight.py backend/tests/test_governance_consistency.py -q -p no:cacheprovider
# 65 passed

powershell -NoProfile -File .\backend\scripts\test-backend.ps1
# 388 passed, 2 skipped
```

The two skips are default-disabled opt-in real-provider smoke tests. No Chromium spec ran because this task changes no browser UI or browser workflow.

Focused tests cover request IDs, HTTP failure correlation, structured-event redaction, request -> task event correlation, metric low-cardinality, task duration, liveness/health/readiness transitions, startup failure, audit integrity/foreign-key/relation degradation, stale task degradation, backup/verify/restore failure redaction, diagnostics read-only behavior and diagnostics CLI safe output.

## Limits

This is not central logging, persistent telemetry, alert delivery, cross-process aggregation, a remote health service, automated repair, provider monitoring, real network/provider evidence, or global production `real-pass`. A degraded state is a local diagnostic signal and recommended-action aid; operators must inspect retained data and verified backups before any explicit recovery action.
