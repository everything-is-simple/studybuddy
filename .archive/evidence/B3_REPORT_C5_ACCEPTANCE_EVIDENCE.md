# B3 Report C5 Formal Acceptance Evidence

> Gate: B3 C5
> Status: `acceptance-pass`
> Scope: existing Phase 9D report domain, local single-process SQLite, project-scoped deterministic JSON/Markdown reports.

## Acceptance result

C5 verified the existing Phase 9D report boundary without adding a report domain, migration, API family, scheduler, provider invocation, external delivery, or network dependency.

The static reports page now reads an existing report snapshot through the existing detail endpoint and exports through the existing JSON/Markdown endpoints. It is a read-only view: it does not create reports, invoke delivery, or imply that a report was sent. The page states `交付：未发送` for the approved scope.

## Backend acceptance

`backend/tests/test_b3_report_c5_acceptance.py` verifies:

- all approved report kinds: `daily`, `weekly`, `monthly`, and `exam_alert`;
- safe response payloads, deterministic snapshot replay, JSON and Markdown export;
- stable rejection of unsupported report kind, timezone, date period, PDF export, and invalid pagination;
- server-injected project scope with cross-project report reads rejected;
- startup/readiness and ordinary report list reads create neither report snapshots nor delivery attempts.

The existing Phase 9D report, API, source lifecycle, and backup/restore tests additionally verify half-open IANA periods, redaction, read-only fact ownership, degradation aggregation, immutable history, restore to a new empty root, schema history, and no repair/provider/report/delivery side effect during restore.

Focused backend result: `15 passed`.

## Browser acceptance

`backend/tests/browser_b3_report_c5.spec.js` verifies in Chromium against an isolated local Uvicorn process:

- reports list/detail projection read, safe aggregate rendering, and JSON/Markdown downloads;
- reload preserves selected report rendering;
- default UI text stays `未发送` and does not expose delivery as sent;
- no path, answer, payload-storage field, secret, traceback, or private backend error leaks;
- list request failure is safely masked and retry recovers;
- mobile viewport has no horizontal overflow;
- no browser console/page errors and no external network requests.

Browser result: `2 passed`.

## Preserved boundaries

- Generation remains explicit and synchronous; reports page only reads existing snapshots.
- Delivery is not performed by this acceptance path. PDF, HTML/email, Feishu cards, AI narrative, recipients, scheduler/task execution, and network delivery remain outside B3.
- Backup, verify, restore, startup, and ordinary reads do not generate reports, repair source state, invoke providers, or create delivery attempts.
- Evidence contains test outcomes only and excludes report bodies, source text, paths, prompts, answers, provider output, and generated downloads.

## Limitations

This gate is acceptance evidence for the declared local scope only. PDF rendering, arbitrary formats, live delivery, scheduler reliability, concurrency/capacity, crash/power-loss recovery, multi-user authorization, and global production `real-pass` remain `not_verified`.

## Gate result

B3 C5 is `acceptance-pass`. B3 C6 scoped closeout remains required before B3 can be declared complete for its narrow JSON/Markdown report scope.
