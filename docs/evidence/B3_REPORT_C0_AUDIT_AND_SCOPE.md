# B3 Report C0 Audit and Scope Freeze

> Status: `candidate-selected / audit-frozen`.
> This is C0 governance evidence only. It does not implement a new report component, pass C1, authorize Integration/Formal changes, or approve B4 delivery.

## Formal audit

The existing Phase 9D report domain already provides the semantic baseline B3 must reuse:

- `daily`, `weekly`, `monthly`, and `exam_alert` projections;
- IANA timezone handling and half-open periods;
- a fixed allowlisted aggregate payload with plan, rhythm, practice, feedback, source-quality, exam-alert, and quality-flag sections;
- deterministic aggregation fingerprint and JSON/Markdown rendering;
- project-scoped immutable snapshots and replay;
- source degradation buckets without source identity disclosure;
- safe API/list/detail/preview/export boundaries;
- backup/restore non-repair and no automatic report generation.

Relevant Formal evidence is in `docs/contracts/PHASE9D_DOMAIN_CONTRACT.md`, `docs/evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md`, `backend/tests/test_phase9d_report.py`, and `backend/tests/test_phase9d_backup_restore.py`.

B3 must not create a second report domain, schema, snapshot table, API family, or delivery audit. Composer and Integration may independently validate candidate semantics; any later Formal work must reimplement only verified gaps against the existing domain contract.

## Candidate decision

The selected C0 candidate is a project-defined local deterministic projection core, to be independently implemented in Composer. The legacy local reference is audit material only: it combines projection with email/Feishu formatting, delivery deduplication, and optional AI narrative, so it cannot be adopted as the B3 component.

The first scope is JSON and Markdown only. PDF is `not_verified` and excluded because renderer isolation, fixed layout, fonts, output limits, accessibility, and privacy evidence are absent. HTML/email, Feishu cards, AI summaries, delivery status, external targets, network access, scheduler/task execution, and live delivery are out of scope.

## Frozen C1 boundary

C1 must cover empty and normal synthetic facts, four report kinds, timezone and half-open period boundaries, source degradation, stable ordering, repeat/input-order determinism, fixed JSON schema, deterministic Markdown, output limits, malformed/corrupt input/output, timeout, temporary cleanup, network denial, privacy scans, and bounded resource measurements.

Evidence may retain only stable statuses, counts, timings, sizes, hashes, versions, and error codes. It must exclude report bodies, source content, answers, prompts, OCR/ASR text, local paths, credentials, raw tool output, database statements, and internal exception details.

## Gate conclusion

- B3 C0: `audit-frozen`.
- `report-core`: remains `researching`; no C1 evidence exists yet.
- Formal production, schema, migrations, API, UI, and database semantics: unchanged.
- B4 delivery: not authorized; `delivery=off`, dry-run, and live-reject boundaries remain unchanged.
- Next step: independently implement and run B3 C1 Composer smoke against the frozen matrix in `components/report-core/C0-DECISION-AND-C1-PLAN.md`.
