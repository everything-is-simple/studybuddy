# Phase 8 Cards / Exercises Acceptance Evidence

> Closeout date: 2026-08-28
>
> Scope: local single-process StudyBuddy, SQLite, deterministic `fake` LLM provider and Chromium. This is a scoped completion record, **not** real-provider or global production `real-pass`.

## Delivered contract

- Schema is migration-controlled through v7 `phase8_cards_exercises_schema` and v8 `phase8_exercise_provenance`. `schema_migrations` and `PRAGMA user_version` remain v8.
- Cards and exercises use `draft → ready | rejected | archived` transitions. AI-generated artifacts always start as drafts; draft-only editing marks user edits, and ready/archived artifacts are not overwritten.
- AI generation accepts one explicitly indexed active material, retrieves with lexical/vector/hybrid policy, assembles bounded context, validates structured output in memory, and revalidates every citation against the current revision/chunk/span before atomically persisting drafts and operation metadata.
- Citation lifecycle is explicit: `valid`, `source_deleted`, `source_unavailable`, or `stale`. Delete, restore, purge and re-index never fabricate source text or a usable location.
- Reviews and attempts are append-only. Multiple-choice and true/false are deterministically graded; short answers remain `pending_review`. No human-review workflow is implemented.
- Normal Cards/Exercises lists and attempt history exclude answer keys and submitted-answer JSON. Raw provider prompt/response is not persisted.
- Backup, verify and restore preserve Phase 8 artifacts, citations, reviews, attempts, generation operations and lifecycle states. Restore targets a new empty root; verify/restore/startup do not generate, repair, rebuild, or promote unavailable citations.

## Closeout evidence

| Gate | Command / test | Result |
|---|---|---|
| Focused Phase 8 backend | `/cygdrive/c/miniconda/py310/python -m pytest backend/tests/test_phase8_cards.py backend/tests/test_phase8_exercises.py backend/tests/test_phase8_generation.py backend/tests/test_phase8_closeout.py -q` | 18 passed (closeout environment) |
| Backup/restore lifecycle | `backend/tests/test_phase8_closeout.py` | Covers draft/ready/rejected/archived artifacts, valid and purged/unavailable citations, reviews, deterministic and pending-review attempts, successful generation operations, empty-target restore, post-restore startup/read non-repair invariant. |
| Full backend regression | `/cygdrive/c/miniconda/py310/python -m pytest backend/tests/ -q` | 250 passed, 2 skipped (opt-in real-provider smoke) |
| Phase 8 Chromium path | `npx playwright test backend/tests/browser_phase8.spec.js --reporter=line` | 3 passed |
| UI failure regression | `npx playwright test backend/tests/browser_phase8.spec.js backend/tests/browser_frontend_failure_contract.spec.js --reporter=line` | 9 passed |
| Migration / API / lifecycle regression | Full backend suite, including `test_migrations.py`, lifecycle/input-boundary/provider tests | Passed in full backend regression above. |

The direct Windows command documented by the project is `C:\miniconda\py310\python.exe -m pytest backend/tests/ -q`; this Bash session used its equivalent `/cygdrive/c/miniconda/py310/python` path.

## Explicit limits

- No real Provider Cards/Exercises generation evidence has been run. Existing DeepSeek and Agnes evidence applies to the separately documented Q&A/P6-E gates only.
- System-level screen-reader behavior, extreme/long generated content, real offline behavior and long-duration browser stability are `not_verified`.
- No human short-answer review API or UI, study plans, worker, progress/cancel/retry queue, multi-user deployment, multiple processes, shared `data_root`, cloud sync, or global production `real-pass` is claimed.
