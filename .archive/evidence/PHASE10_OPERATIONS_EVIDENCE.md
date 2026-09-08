# Phase 10-6 Operations Evidence

> Gate G status: `implemented/backend-pass` / `restore-gates-pass` in the declared local single-process, single-instance, SQLite, local-disk scope. This is not a release-candidate drill or global `production real-pass`.

## Implemented Contract

- `backup_data()` creates a SQLite Online Backup snapshot and verifies integrity, foreign keys, continuous migration history/`PRAGMA user_version`, database hash/size, and every referenced hash-derived original's layout/hash/size before writing a complete manifest.
- `verify_backup()` is read-only: it validates a complete backup and accepts a prior schema only when its history and `user_version` are internally consistent. It does not migrate, repair, rebuild, execute tasks, call a Provider, or modify the backup.
- `restore_backup()` remains explicit (`--confirm`), staged, and restricted to an absent/empty target. It preserves the backup schema version and does not migrate. A restored historical target is upgraded only by a later explicit new-version startup.
- `rotate-backups --backup-root ... --retain N` defaults to dry-run. `--confirm` retains at least one verified set, validates the complete deletion set before deleting, and never selects symlinks, files, incomplete, unknown, invalid, or corrupt backup directories.
- `upgrade-preflight --data-root ... --backup ...` is non-mutating. It validates live database/originals/integrity/FK/history/version/access, re-verifies the rollback backup, checks schema-version match, and reports whether migration is required.
- `inspect_schema_version()` validates continuous migration history and `PRAGMA user_version` without applying a migration. The normal migration runner remains the only schema-change entry point.
- Corruption, original mismatch, migration/history failure, restore-acceptance failure, and degraded readiness are stop-and-preserve-evidence conditions. Local v1 has no runtime read-only serving mode.

## Operator Material

- `docs/BACKUP_RESTORE.md`: command boundaries, historical backup behavior, rotation, preflight, and stop policy.
- `docs/MIGRATIONS.md`: non-mutating upgrade preflight and rollback/restore boundary.
- `docs/../operations/BACKUP_OPERATIONS.md`: retention, rotation, permissions, quarantine and failure isolation.
- `docs/../operations/OPERATOR_UPGRADE.md`: stop -> backup -> verify -> preflight -> startup -> acceptance procedure.
- `docs/../operations/RESTORE_DRILL.md`: offline/online drill template, task/attempt state checks, health/readiness/diagnostics, and incident stop conditions.

## Automated Evidence

Focused Gate G command, using pytest temporary data roots and backup artifacts outside the repository:

```text
C:\miniconda\py310\python.exe -m pytest \
  backend/tests/test_phase10_operations.py \
  backend/tests/test_backup_restore.py \
  backend/tests/test_migrations.py \
  backend/tests/test_restore_acceptance.py \
  backend/tests/test_phase9a_backup_restore.py \
  backend/tests/test_phase9b_backup_restore.py \
  backend/tests/test_phase9c_backup_restore.py \
  backend/tests/test_phase9d_backup_restore.py \
  backend/tests/test_observability.py \
  backend/tests/test_governance_consistency.py -q -p no:cacheprovider
```

Focused result: `67 passed`.

Coverage includes:

- snapshot/manifest database size/hash/integrity/FK/history/schema verification;
- v12 verified backup accepted as rollback evidence, restore to a new target without migration, then explicit v13 startup upgrade;
- current v13 schema/history/task/attempt preservation and restore non-run boundary;
- missing/mismatched original isolation without repair;
- dry-run rotation, explicit confirmed deletion, minimum verified retention, and invalid-artifact preservation;
- upgrade preflight success, rollback backup re-verification, schema/history failure handling, controlled unwritable-root preflight, and non-mutation;
- offline restore acceptance and existing 9A-9D source lifecycle/report/delivery/task facts;
- safe metrics/events and no raw path/source/secret/SQL/traceback output in operator failures.

Full backend command:

```text
powershell -NoProfile -File .\\backend\\scripts\\test-backend.ps1
```

Result: `396 passed, 2 skipped`. The two skips are opt-in real-provider smoke tests.

## Explicit Limits

- No real power-loss, hardware corruption, network filesystem, host ACL, or disk-full validation ran in this gate; these remain `not_verified`.
- Rotation is explicit and count-based. This release does not provide a scheduler, calendar classification, cloud replication, encryption service, or automatic restore.
- Operator documents require host ACL restrictions but do not configure or verify them automatically.
- Restore/acceptance, backup/verify, rotation, and upgrade preflight do not run providers, OCR/ASR, report delivery, task runner/handler, indexing, or repair.
