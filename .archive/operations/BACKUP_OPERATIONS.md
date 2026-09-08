# Backup Operations

StudyBuddy backup is an explicit operator operation. The application does not run a scheduler, retention engine, cloud upload, encryption service, automatic restore, migration, repair, task runner, Provider, OCR/ASR, report generation, or delivery as part of backup/verify/rotation.

## Backup Location And Permissions

- Store backups outside the live `data_root`, web roots, and ordinary-user directories.
- Backups contain user originals and are sensitive. Restrict the backup directory to the operator/service account with host ACLs. Windows ACL configuration and verification are operator prerequisites; v1 does not configure or verify ACLs automatically.
- Confirm free space before a backup. A set contains the SQLite snapshot and every referenced original; shared hashes are stored once.
- Verify after copying a backup to another disk or host. Use controlled encryption at rest and in transit whenever a backup leaves the machine.
- Use a newly named output directory. The CLI rejects an existing output and any output inside the live data root.

## Create And Verify

```text
C:/miniconda/py310/python.exe -m app.cli backup --data-root <live-root> --output <new-backup>
C:/miniconda/py310/python.exe -m app.cli verify-backup --backup <new-backup>
```

The manifest is complete only after the SQLite Online Backup snapshot, SQLite integrity/foreign-key checks, continuous migration-history/`PRAGMA user_version` consistency, database hash/size, and all referenced original layout/hash/size checks pass. It records the backup schema version and application schema at backup time, but never live paths, `stored_path`, source/body text, secrets, SQL, raw provider responses, recipient data, or raw exceptions.

A verified historical schema backup is valid as an upgrade rollback artifact when its migration history and `PRAGMA user_version` agree. It may be restored only to a new empty target; then explicitly start the current application to run the controlled migration before treating that target as current v1. Use `upgrade-preflight` before upgrading an older live schema.

## Retention And Rotation

Recommended policy: retain 7 daily, 4 weekly, and 6 monthly **verified** backups. This local v1 does not infer calendar classes or run a scheduler. An external scheduler may create new backup directories, but it must not overlap service writes, overwrite a live root, or delete on its own outside the following explicit command.

```text
C:/miniconda/py310/python.exe -m app.cli rotate-backups --backup-root <backup-root> --retain <count>
C:/miniconda/py310/python.exe -m app.cli rotate-backups --backup-root <backup-root> --retain <count> --confirm
```

The first command is a dry run. The confirmed command re-verifies every candidate before deletion, retains at least `count >= 1` verified sets, sorts only by manifest `created_at`, and deletes only older verified backup directories. Symlinks, files, incomplete directories, unknown artifacts, and invalid/corrupt backups are preserved as evidence and never selected for deletion. A validation failure occurs before any selected set is deleted; deletion failure stops rotation and never touches live data. Record each result externally without paths or sensitive material.

## Failure Isolation

- Backup creation failure: preserve existing verified backups, retain the stable error code, isolate incomplete output, and retry only to a new output directory.
- Verify failure: quarantine that backup from restore/rotation decisions, do not repair it, and use another verified backup.
- Manifest failure: do not trust paths, hashes, sizes, or schema version from that manifest. Preserve it for diagnosis.
- SQLite integrity, foreign-key, migration-history, or schema failure: stop the service, preserve the live database and originals, and restore a verified backup to a new target if recovery is required.
- Original missing or hash mismatch: never substitute a same-name file or delete the mismatch. Treat source state as unsafe/unavailable; stop ordinary service writes and escalate if the material or backup set cannot be verified.
- Restore or staging failure: do not start the target. Confirm the live root is unchanged, isolate staging/target evidence, and retry only with a verified set into a new absent or empty target.

This release has no runtime read-only serving mode. When database integrity, schema, originals, restore verification, or readiness cannot be established, stop the service rather than operating in ordinary read/write mode.
