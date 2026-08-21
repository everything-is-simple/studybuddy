# Backup Operations

StudyBuddy backup is an explicit operator operation. The application does not run a scheduler, retention engine, cloud upload, encryption service, or automatic restore.

## Backup location and permissions

- Store backups outside the live `data_root`.
- Do not store backups under a web root or a directory exposed to ordinary users.
- Backups contain user originals and must be treated as sensitive data.
- Restrict the backup directory to the operator/service account using the host ACL. Windows ACL configuration is an operator prerequisite; this release does not configure or verify ACLs automatically.
- Confirm sufficient free space before backup. A backup contains the SQLite snapshot and every referenced original; shared hashes are stored once.
- Verify after copying to another disk or host. Use controlled encryption at rest and in transit when backups leave the machine.

## Retention policy

The following is the recommended operator policy, not an implemented scheduler:

- daily: retain 7 verified backups;
- weekly: retain 4 verified backups;
- monthly: retain 6 verified backups.

An external scheduler such as Windows Task Scheduler may run the CLI. It must write to a new output directory and must not overwrite a live data root. Before rotation:

1. create the new backup;
2. run `verify-backup`;
3. record the timestamp, identifier and verification result;
4. delete only old backups that are verified and not the only known-good backup.

Never delete the most recent verified backup or the only available verified backup. A failed backup remains an incomplete/failed artifact and is not a restore candidate. Rotation failure must not affect live data.

## Routine commands

```text
D:/miniconda/py310/python.exe -m app.cli backup --data-root <live-root> --output <new-backup>
D:/miniconda/py310/python.exe -m app.cli verify-backup --backup <new-backup>
D:/miniconda/py310/python.exe -m app.cli verify-restored-data --data-root <restored-root>
```

The final command is offline unless `--base-url` is supplied. It never starts a service, migrates, repairs, rebuilds FTS, or modifies data.

## Failure isolation

- Backup creation failure: preserve existing verified backups, retain the stable error code, isolate the incomplete output, and retry with a new output directory.
- Verify failure: quarantine the backup, do not repair or restore it, and use another verified backup.
- Manifest failure: do not trust paths, hashes, sizes, or schema version from that manifest. Quarantine the backup.
- SQLite integrity or foreign-key failure: stop the service, preserve a diagnostic copy, and restore a verified backup into a new target.
- Original missing or hash mismatch: do not substitute a same-name file or delete the mismatch. Treat the affected material as unavailable; if more than one material or the backup set is affected, escalate as a recovery incident.
- Restore failure: do not start the incomplete target. Confirm the live root is unchanged, isolate the staging/target, and retry only in a new empty target.

This release has no runtime read-only mode. When database integrity, schema, restore verification, or readiness cannot be established, stop the service rather than continuing in ordinary read/write mode.
