# Phase 10-4 Approved Task Integration Evidence

> Status: `implemented/backend-pass`
> Gate E: passed for the explicitly approved `embedding_index` scope only.

## Approved Scope

Phase 10-4 approves only the provider-backed embedding stage of `embedding_index` for runner execution.

- New explicit enqueue API: `POST /api/materials/{material_id}/ai-index/tasks`.
- New project-scoped task read/cancel/retry APIs: `GET /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/cancel`, and `POST /api/tasks/{task_id}/retry`.
- New operator command: `python -m backend.app run-tasks --data-root <empty-or-existing-local-root> [--once|--max-tasks N]`.
- The FastAPI lifespan, startup recovery, backup, verify, restore, read paths, and normal material APIs do not start a runner or execute queued tasks.
- Existing `POST /api/materials/{material_id}/ai-index` remains synchronous and retains its response contract. Revision/chunk source-of-truth creation also remains in that existing synchronous transaction; the runner only performs approved embedding work for a fixed current revision.

A queued task fixes the project, material, current source revision, provider identity/model/revision and server-side fingerprint. The task row stores no source text, path, secret, raw request/response, or raw idempotency key. Public task projection excludes internal fingerprints and lease facts.

## Handler Guarantees

`backend/app/task_handlers.py` registers only `embedding_index`:

- provider configuration is validated before enqueue and rechecked by the handler;
- the task rechecks project, material, current revision and non-deleted source before and after provider calls;
- checkpoints before/after each provider batch heartbeat the lease and honor cooperative cancellation;
- provider timeout/connection/unavailable/rate-limit errors are the only retryable errors, with one explicit retry allowed by the task policy;
- configuration change, source stale/deleted, invalid response and schema errors are stable non-retryable task failures;
- embedding rows are idempotent upserts and each completed batch commits atomically; retrying an interrupted task does not create duplicate ready embeddings;
- successful task completion records only the opaque revision ID as `output_artifact_id`; no user-confirmed state, draft, citation, report, capture, source lifecycle status or delivery fact is overwritten.

Cancellation is cooperative. A request during a non-interruptible provider call becomes `cancel_requested`; after the call returns the handler checks again, does not write the returned vectors, and completes as `cancelled`. It does not claim to cancel a remote provider request.

## Explicitly Not Approved in 10-4

The following retain their existing synchronous or default-off behavior and have no runner handler:

- Q&A (`qa_answer`);
- card, exercise and note draft generation;
- deterministic fake/loopback capture transcription;
- report snapshot aggregation;
- report delivery, including dry-run. Live delivery remains blocked.

Those operations require separate approval because they involve generated drafts/citations, user-edit protection, raw capture handling, report content, or delivery audit/authorization boundaries. No real Provider, OCR/ASR, SMTP or Feishu call was performed for this gate.

## Verification

Commands run on the Gate E implementation commit:

```powershell
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase10_task_integration.py backend/tests/test_task_runner.py backend/tests/test_ai_indexing.py backend/tests/test_recovery_consistency.py backend/tests/test_governance_consistency.py -q -p no:cacheprovider
# 43 passed

powershell -NoProfile -File .\backend\scripts\test-backend.ps1
# 382 passed, 2 skipped
```

The two skips are the default-disabled opt-in real-provider smoke tests. No Chromium spec ran because 10-4 adds no browser UI or modifies an existing browser workflow.

Focused integration coverage includes enqueue/read/replay/mismatch, legacy synchronous compatibility, explicit runner and operator CLI execution, operator restart recovery (active task becomes stale and is not executed), retry/attempt history, queued/running cooperative cancellation, source deletion while a provider call is in progress, no ready embedding on stale source, and public task privacy projection.

## Remaining Limits

This is not a generic background-worker implementation, cross-process protocol, automatic dispatch, real-provider evidence, OCR/ASR evidence, delivery approval, or global production `real-pass`. The supported deployment remains one local process, one instance, SQLite and local disk. Provider execution is only tested with deterministic fake embeddings in this gate; the existing exact Mistral evidence remains separate and does not validate the new queue path.
