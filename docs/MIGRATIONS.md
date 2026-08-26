# Database migrations

Current schema version: **13**.

The authoritative migration history is `schema_migrations`; SQLite `PRAGMA user_version` must match it. The migration runner is `backend/app/migrations/runner.py`.

```text
1 | canonical_material_schema
2 | ai_phase0_schema
3 | phase5_provider_metadata
4 | qa_operation_idempotency
5 | phase7_embedding_schema
6 | search_index_schema_contract
7 | phase8_cards_exercises_schema
8 | phase8_exercise_provenance
9 | phase9a_learning_plan_schema
10 | phase9b_material_learning_schema
11 | phase9c_exercise_feedback_schema
12 | phase9d_extended_learning_schema
13 | phase10_operation_task_schema
```

## Rules

- Migrations are consecutive, recorded, idempotent, and run inside `BEGIN IMMEDIATE`.
- Schema DDL, migration-history insertion, and `PRAGMA user_version` are committed atomically.
- v11 adds the Phase 9C session/item snapshots, attempt linkage metadata, review/mistake/feedback facts, and cram-goal persistence schema. Domain validation and projections remain outside the migration.
- v12 adds the Phase 9D capture-session, transcript draft/segment, report snapshot, delivery-attempt, and capture-linked operation persistence schema. The approved 9D-0 partial scope now includes 9D-3 shared domain behavior, 9D-4 deterministic fake/loopback capture/transcription, 9D-5 explicit confirmed transcript ingestion into the existing S2 material/revision/chunk/retrieval/citation path, 9D-6 read-only report aggregation/redaction, 9D-7 default-off/allowlisted dry-run delivery audit, 9D-8 API, 9D-9 Chromium workspace, and 9D-10 source lifecycle plus backup/restore non-repair verification. Real OCR/ASR and live SMTP/Feishu delivery remain outside the v12 completion claim.
- v13 adds Phase 10 task envelopes (`operation_tasks`) and append-only task-attempt audit (`operation_task_attempts`). It preserves existing `ai_operations`, does not backfill historical operations or alter legacy synchronous APIs, and never persists raw content, secrets, paths, raw Provider payloads, answer keys, or submitted answers. The 10-3 runner uses the v13 schema but is explicit-only: startup, backup, restore and reads do not start or execute it. Composite project-scoped FKs, status/progress/retry checks, one-task-per-operation and at-most-one-running-attempt indexes provide structural protection; state transitions, progress monotonicity, lease compare-and-set, cancellation and retry policy remain repository/runner behavior.
- A failure rolls back; the service never becomes ready with a half-upgraded schema.
- Migration history and `PRAGMA user_version` are never edited manually.
- There is no automatic down migration. Preserve the failed database and restore a verified backup into a new empty target when recovery is required.

## Inspecting a database

```text
C:/miniconda/py310/python.exe -m app.cli schema-version \
  --database <data-root>/studybuddy.sqlite3
```

The command validates; it does not migrate or repair.

## Upgrade and recovery

Use [`prompts/OPERATOR_UPGRADE.md`](prompts/OPERATOR_UPGRADE.md) for the stop, backup, verify, upgrade, acceptance, and failure-recovery procedure. Backup/restore version checks are described in [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md).
