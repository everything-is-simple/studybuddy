# Database migrations

Current schema version: **12**.

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
```

## Rules

- Migrations are consecutive, recorded, idempotent, and run inside `BEGIN IMMEDIATE`.
- Schema DDL, migration-history insertion, and `PRAGMA user_version` are committed atomically.
- v11 adds the Phase 9C session/item snapshots, attempt linkage metadata, review/mistake/feedback facts, and cram-goal persistence schema. Domain validation and projections remain outside the migration.
- v12 adds the Phase 9D capture-session, transcript draft/segment, report snapshot, delivery-attempt, and capture-linked operation persistence schema. Domain validation, OCR/ASR execution, report aggregation, and delivery behavior remain outside the migration.
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
