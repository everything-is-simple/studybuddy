# B3 Report C3 Formal Contract Evidence

> Gate: B3 C3
> Status: `contract-frozen`
> Scope: local single-process, single-instance, SQLite, project-scoped deterministic JSON/Markdown reports.

## Evidence basis

C3 reviewed the existing Phase 9D report contract and implementation boundaries, Composer C1 evidence, and isolated Integration C2 evidence. The review confirms that B3 can reuse the existing Formal report domain and does not require a new schema, migration, report table, API family, or delivery audit.

Reviewed sources:

- `docs/contracts/PHASE9D_DOMAIN_CONTRACT.md`
- `docs/evidence/B3_REPORT_C0_AUDIT_AND_SCOPE.md`
- `backend/app/repositories/capture.py`
- `backend/app/api/study_capture_reports.py`
- `backend/app/static/reports.html`
- `backend/tests/test_phase9d_report.py`
- `backend/tests/test_phase9d_backup_restore.py`
- Composer `report-core` C1 sanitized evidence
- Integration `report-core` C2 sanitized evidence

## Frozen decisions

- Reuse Phase 9D report projection, snapshot, API, UI, source lifecycle, and backup/restore boundaries.
- Support `daily`, `weekly`, `monthly`, and `exam_alert`.
- Keep generation explicit, synchronous, local, deterministic, project-scoped, read-only over learning facts.
- Keep JSON and Markdown as the only B3 export formats.
- Preserve safe aggregate payload, fingerprint replay, stable errors, and redaction validation.
- Preserve source degradation counts and flags without source identity or body disclosure.
- Preserve backup/restore non-repair: no report generation, source repair, provider invocation, or delivery during restore/read/startup/verify.
- Keep `delivery=off`; dry-run is not sent; live delivery remains a B4 concern and is rejected.
- Do not copy Composer or Integration implementation into Formal.

## C4 acceptance target

C4 must first verify current Formal behavior against `docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md`, then independently implement only evidenced gaps. Focused tests must cover empty/normal data, all four kinds, timezone/half-open period, project scope, deterministic snapshot replay, JSON/Markdown, read-only fact protection, source lifecycle, redaction, invalid input, output limits, and unsupported formats.

## Risk and non-goal record

The C3 contract does not establish PDF or arbitrary format support, AI narrative, delivery, scheduler/worker behavior, multi-user authorization, concurrent capacity, crash/power-loss recovery, or global production `real-pass`. A mismatch in these areas cannot be silently resolved in C4; it requires a contract update and new evidence.

## Gate result

`B3 C3 = contract-frozen`.

Formal production behavior is unchanged by this gate. B3 C4 is unblocked for independent Formal verification/implementation. B4 remains blocked.
