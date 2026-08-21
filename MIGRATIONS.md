# Database migrations

StudyBuddy uses a versioned SQLite schema. The current schema version is `1`.
The authoritative history is stored in `schema_migrations`; SQLite `PRAGMA user_version`
is kept in sync and is checked at startup and during backup verification.

## Inspecting the version

For an existing database, the operator can inspect the version without starting
StudyBuddy:

```text
D:/miniconda/py310/python.exe -m app.cli schema-version \
  --database <data-root>/studybuddy.sqlite3
```

The command validates both migration history and `PRAGMA user_version`; it does not
migrate or repair the database.

## Startup upgrade

The application performs this sequence before it becomes ready:

```text
startup preflight
-> SQLite connection
-> migration runner
-> schema consistency check
-> diagnostic audit
-> storage recovery
-> ready
```

A new database is created by migration 1. A database created by an older StudyBuddy
build without `schema_migrations` is adopted only after its known core objects are
validated. Missing legacy columns (`updated_at`, `deleted_at`, `error_code`) are
added and existing material timestamps are backfilled from `created_at`. Unknown
objects or incomplete schemas are rejected; data is never silently declared current.

Migrations execute in consecutive version order under a SQLite write transaction.
A successful migration is recorded only after its schema work succeeds. Repeated
starts do not rerun completed migrations. A migration error rolls back the active
transaction and the service never becomes ready. Startup exposes only stable codes,
including `database_schema_unsupported`, `database_schema_version_unknown`,
`database_migration_history_mismatch`, `database_migration_incomplete`, and
`database_migration_failed`; it does not expose paths, SQL, data, or tracebacks.

The current release has no automatic down migrations. Do not delete or edit
`schema_migrations` or `PRAGMA user_version` manually. If an upgrade cannot be
repaired and retried, stop the service, preserve the failed database for diagnosis,
verify a known-good backup, and restore it into a new empty target directory.
Never overwrite a live data root with an unverified copy.

## Pre-upgrade operator procedure

1. Stop StudyBuddy and ensure no other process uses the data root.
2. Create a backup outside the live data root:

```text
D:/miniconda/py310/python.exe -m app.cli backup \
  --data-root <live-data-root> \
  --output <backup-root>
```

3. Verify it:

```text
D:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
```

4. Start the application. The migration runner upgrades the database before
   `/api/health` can report `ok`.
5. Confirm `/api/health`, material listing, material detail, original download,
   text export, and search.

Backups must not be placed inside the live data root. The supported deployment is
single-process and single-instance on local storage; do not use multiple workers
against one data root.

## Backup and restore version checks

The backup manifest records `database.schema_version`. `verify-backup` checks that
value against the copied database's migration history and `PRAGMA user_version`, in
addition to SQLite integrity, foreign keys, and original file hashes. Verification
never migrates, repairs, rebuilds FTS, or changes the backup.

Restore requires `--confirm` and an absent or empty target. It verifies the backup,
verifies the staging copy again, then replaces the target. It does not start the
application or run migrations. After restore:

```text
D:/miniconda/py310/python.exe -m app.cli restore \
  --data-root <empty-target> \
  --backup <backup-root> \
  --confirm
```

Start the application against the restored target and check:

- `/api/health` returns `{"status":"ok"}`;
- active and deleted material lists are readable;
- a material detail is readable;
- original and extracted-text exports work;
- search returns the expected material;
- `schema_migrations` and `PRAGMA user_version` remain at version `1`;
- startup does not add another migration history row.

If backup verification or restore fails, the live data root is not modified. Isolate
the backup or target, retain the stable error code, and use another verified backup.
