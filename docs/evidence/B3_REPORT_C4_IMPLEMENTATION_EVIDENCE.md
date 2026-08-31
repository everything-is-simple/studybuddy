# B3 Report C4 Formal Implementation Evidence

> Gate: B3 C4
> Status: `implemented / focused-pass`
> Scope: existing Phase 9D report domain, local single-process SQLite, project-scoped deterministic JSON/Markdown reports.

## Implementation

Formal implementation was completed independently in `H:\studybuddy`. The existing Phase 9D report domain remains the sole report system. No Composer or Integration implementation was copied into Formal.

The verified contract gap was the missing bounded report export. C4 now defines and enforces `PHASE9D_REPORT_MAX_EXPORT_BYTES = 1 MiB` for both JSON and Markdown export. Oversized output returns the stable `payload_too_large` error and is mapped to HTTP 400. The constant is exposed through the existing repository facade for contract/test visibility.

No schema, migration, `PRAGMA user_version`, task runner, scheduler, report snapshot shape, API route family, or delivery behavior was added or changed.

## Focused evidence

- `backend/tests/test_b3_report_c4.py`: normal JSON/Markdown export, media types, safe payload, fixed 1 MiB limit, oversized JSON rejection, oversized Markdown rejection.
- `backend/tests/test_b3_report_c3_governance.py`: C3 contract remains frozen and Formal authorization boundaries remain explicit.
- `backend/tests/test_phase9d_report.py`: existing report kinds, timezone half-open window, redaction, project scope, and source degradation.
- `backend/tests/test_phase9d_backup_restore.py`: source lifecycle and backup/restore non-repair behavior.

Focused result: `12 passed`.

## Preserved boundaries

- Supported kinds remain `daily`, `weekly`, `monthly`, and `exam_alert`.
- Supported exports remain JSON and Markdown only.
- Report generation remains explicit, synchronous, local, deterministic, project-scoped, and read-only over learning facts.
- Source degradation remains aggregate-only and does not reveal source identity, path, or body.
- Backup/restore remains non-repair and does not generate reports or invoke providers.
- `delivery=off` remains the default; dry-run is not sent and live delivery remains outside B3.

## Limitations

C4 focused implementation evidence is not browser acceptance or B3 closeout. PDF, arbitrary formats, AI narrative, delivery, scheduler behavior, concurrency/capacity, crash/power-loss recovery, and global production `real-pass` remain `not_verified`.

## Gate result

B3 C4 is `implemented / focused-pass` for the declared scope. B3 C5 remains required for backend/browser/source-lifecycle/backup-restore/operator acceptance and full regression evidence.
