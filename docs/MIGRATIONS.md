# Database migrations

Current schema version: **14**.

The authoritative migration history is `schema_migrations`; SQLite `PRAGMA user_version` must match it. The execution engine and public migration API remain at `backend/app/migrations/runner.py`; individual migration bodies are maintained in the adjacent `_vNN_*.py` modules, with shared helpers in `_helpers.py`.

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
14 | fix_revision_fingerprint_material_id
```

## Repository layout

```text
backend/app/migrations/
  runner.py                 # execution engine, registry, history and version checks
  _helpers.py               # schema inspection and shared migration helpers
  _canonical.py             # canonical schema helper
  _ai_schema.py             # shared AI schema helper
  _v01_*.py ... _v14_*.py   # one idempotent body per registered version
```

Use `runner.py` as the only public execution entry point. Version modules are internal implementation modules and must not be invoked independently by application startup, backup, restore, or read paths.

## Rules

- Migrations are consecutive, recorded, idempotent, and run inside `BEGIN IMMEDIATE`.
- Schema DDL, migration-history insertion, and `PRAGMA user_version` are committed atomically.
- v11 adds the Phase 9C session/item snapshots, attempt linkage metadata, review/mistake/feedback facts, and cram-goal persistence schema. Domain validation and projections remain outside the migration.
- v12 adds the Phase 9D capture-session, transcript draft/segment, report snapshot, delivery-attempt, and capture-linked operation persistence schema. The approved 9D-0 partial scope now includes 9D-3 shared domain behavior, 9D-4 deterministic fake/loopback capture/transcription, 9D-5 explicit confirmed transcript ingestion into the existing S2 material/revision/chunk/retrieval/citation path, 9D-6 read-only report aggregation/redaction, 9D-7 default-off/allowlisted dry-run delivery audit, 9D-8 API, 9D-9 Chromium workspace, and 9D-10 source lifecycle plus backup/restore non-repair verification. Real OCR/ASR and live SMTP/Feishu delivery remain outside the v12 completion claim.
- v13 adds Phase 10 task envelopes (`operation_tasks`) and append-only task-attempt audit (`operation_task_attempts`). It preserves existing `ai_operations`, does not backfill historical operations or alter legacy synchronous APIs, and never persists raw content, secrets, paths, raw Provider payloads, answer keys, or submitted answers. The 10-3 runner uses the v13 schema but is explicit-only: startup, backup, restore and reads do not start or execute it. Composite project-scoped FKs, status/progress/retry checks, one-task-per-operation and at-most-one-running-attempt indexes provide structural protection; state transitions, progress monotonicity, lease compare-and-set, cancellation and retry policy remain repository/runner behavior.
- v14 fixes P14-P0-05: `revision_fingerprint` now includes `material_id` in its hash, so two materials with identical content get distinct fingerprints. This is an in-place UPDATE migration (no table rebuild, no CASCADE risk). All existing fingerprints are recomputed with the new formula during upgrade. The UNIQUE constraint remains on the same column and continues enforcing one revision per (material, content, parser) combination. Rollback recomputes fingerprints using the old 4-tuple formula (without `material_id`).
- A failure rolls back; the service never becomes ready with a half-upgraded schema.
- Migration history and `PRAGMA user_version` are never edited manually.
- There is no automatic down migration. Preserve the failed database and restore a verified backup into a new empty target when recovery is required.

## Upgrade preflight

升级前必须停止访问 live `data_root` 的所有 StudyBuddy/SQLite writer，先创建并 verify 新的 rollback backup，再执行：

```text
C:/miniconda/py310/python.exe -m app.cli upgrade-preflight \
  --data-root <live-data-root> \
  --backup <verified-backup-root>
```

该命令不执行 migration 或任何写入：检查 database header、integrity、foreign keys、连续 history/`PRAGMA user_version`、hash-derived originals、data root/database ACL access，以及 rollback backup 的重新 verify 和 schema match。`status=ready` 只是明确启动 migration 前的 operator go signal；它不是锁，也不代替 migration runner 的 `BEGIN IMMEDIATE` transaction。

历史 schema backup 只要 history 与 `user_version` 一致即可验证并作为 rollback evidence；restore 保留其版本，不自动升级。恢复后的目标只能由后续显式启动的新版本迁移。直接 current v1 restore target 必须通过 current-schema verify/acceptance。

## Inspecting a database

```text
C:/miniconda/py310/python.exe -m app.cli schema-version \
  --database <data-root>/studybuddy.sqlite3
```

The command validates; it does not migrate or repair.

## Upgrade and recovery

Use [`operations/OPERATOR_UPGRADE.md`](operations/OPERATOR_UPGRADE.md) for the stop, backup, verify, preflight, upgrade, acceptance, and failure-recovery procedure. The module split in A2.3 does not change this operator contract: callers use `backend/app/migrations/runner.py`; `_vNN_*.py` files are implementation modules, not independent migration entry points. Backup/restore version checks are described in [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md). On any schema/history/integrity/original failure, stop the service, preserve the failed database and verified backup, and restore only into a new empty target. v1 has no runtime read-only serving mode and does not claim real power-loss recovery.
