# Operator Upgrade Runbook

This runbook applies to the local single-process, single-instance StudyBuddy v1 deployment. Current target schema: **13**. Migrations run only during application startup through `backend/app/migrations/runner.py`; do not edit `schema_migrations` or `PRAGMA user_version` manually.

## Preconditions

- Stop StudyBuddy and every other process that could access the live `data_root`.
- Use one local data root only. Do not upgrade through a network/shared filesystem or with multiple writers.
- Confirm the live data root, database, originals, backup root, and intended restore target are not symlinks.
- Keep the backup root outside the live data root and restrict it with host ACLs. ACL verification/configuration is an operator responsibility and is not automated by this release.
- Do not delete, overwrite, repair, or run `VACUUM` on the live database to make an upgrade proceed.

## Prepare A Verified Rollback Backup

Create a new backup directory, then validate it:

```text
C:/miniconda/py310/python.exe -m app.cli backup --data-root <live-root> --output <new-backup>
C:/miniconda/py310/python.exe -m app.cli verify-backup --backup <new-backup>
C:/miniconda/py310/python.exe -m app.cli upgrade-preflight --data-root <live-root> --backup <new-backup>
```

`upgrade-preflight` is non-mutating. It validates the live database header, integrity, foreign keys, continuous migration history and `PRAGMA user_version`; verifies all referenced hash-derived originals; re-verifies the supplied backup; checks that backup and live schema versions match; and reports whether migration is required. It does not migrate, repair, rebuild FTS, run tasks, call a Provider, OCR/ASR, generate reports, or deliver anything.

Only `status = ready` with `backup_verified = true` is a go signal. It is not a lock and does not replace the actual migration transaction; keep the service stopped until the upgrade decision is complete.

## Execute And Verify

Start the new application version against the live data root. The controlled startup sequence is:

```text
preflight -> SQLite connect/migrate -> schema assertion -> diagnostic audit -> recovery -> ready
```

The migration runner applies missing consecutive migrations in one `BEGIN IMMEDIATE` transaction. DDL, migration-history insertion, and `PRAGMA user_version` commit together. It does not execute the task runner, retry queued tasks, index material, call external services, create learning content, generate reports, or send delivery.

After a ready result, perform:

```text
C:/miniconda/py310/python.exe -m app.cli schema-version --database <live-root>/studybuddy.sqlite3
C:/miniconda/py310/python.exe -m app.cli diagnostics --data-root <live-root>
```

Check `/api/liveness`, `/api/health`, and `/api/readiness`; only `health = 200` and `readiness = ready` are acceptable. Then run the appropriate material/read/search smoke tests. Do not treat liveness alone as storage safety.

## Failure Isolation

Stable startup/preflight errors include `database_schema_unsupported`, `database_schema_version_unknown`, `database_migration_history_mismatch`, `database_migration_incomplete`, and `database_migration_failed`.

On any preflight, migration, audit, readiness, original-hash, or schema failure:

1. Stop the service. There is no runtime read-only serving mode in v1.
2. Preserve the failed database, originals, backup, and stable error code as evidence. Do not hand-edit migration history, schema version, rows, or original paths.
3. Do not overwrite the live root. Restore a separately verified backup only to a new absent or empty target.
4. Run offline restore acceptance on that target, then optional online acceptance on an isolated port. Point a new service process to the accepted target only after an explicit operator decision.
5. Keep the failed root and verified rollback backup until diagnosis and the replacement target are accepted.

A migration transaction failure rolls back its own schema/history/version work. This does not prove protection against real power loss; real power-loss recovery remains `not_verified`.

## Completion Record

Record the application build identifier, prior/current schema version, verified backup identifier, `upgrade-preflight` result, startup result, schema-version result, diagnostics result, health/readiness result, smoke result, elapsed time, stable error codes, and recovery decision. Do not place live paths, source text, secrets, SQL, raw provider responses, or tracebacks in shared records.
