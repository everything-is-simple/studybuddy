# Restore Drill

This drill proves a local StudyBuddy v1 backup can be restored without overwriting live data. It does not prove power-loss recovery, ACL correctness, network filesystem safety, live Provider/OCR/ASR/delivery behavior, or multi-process operation.

## Preconditions

- Select a backup that has passed `verify-backup`; quarantine a failed backup rather than repairing it.
- Stop or isolate the live service before any replacement decision.
- Use an absent or empty drill target outside the live data root, backup root, and web roots.
- Confirm free space and operator permissions. Do not follow symlinks for source, backup, or drill directories.
- Use a separate port for online verification. Never run two processes against one data root.
- Preserve the live root and verified source backup throughout the drill.

## Procedure

```text
C:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
C:/miniconda/py310/python.exe -m app.cli restore --data-root <drill-root> --backup <backup-root> --confirm
C:/miniconda/py310/python.exe -m app.cli verify-restored-data --data-root <drill-root>
```

The offline acceptance validates database integrity, foreign keys, continuous schema history/version, originals hash/size/layout, material state, and Phase 9A-9D/Phase 10 operation/task/attempt/source lifecycle facts. It never runs migration, task runner/handler, index/rebuild, Provider, OCR/ASR, report generation, delivery, source refresh, or repair.

For online acceptance, start one isolated drill instance configured with the drill root and a separate port, then run:

```text
C:/miniconda/py310/python.exe -m app.cli verify-restored-data --data-root <drill-root> --base-url http://127.0.0.1:8792
C:/miniconda/py310/python.exe -m app.cli schema-version --database <drill-root>/studybuddy.sqlite3
C:/miniconda/py310/python.exe -m app.cli diagnostics --data-root <drill-root>
```

Check `/api/liveness`, `/api/health`, and `/api/readiness`; only health `200` and readiness `ready` pass. The online acceptance also checks lists, one active material when present, original download, and extracted text. An empty database reports material detail/original/text checks as skipped, not failed. Stop the drill instance before removing only the drill target after recording the result.

## Success Criteria

- backup and restore staging verification passed;
- live root was not modified;
- offline acceptance passed;
- online acceptance passed or is explicitly recorded `not_run`;
- schema history and `PRAGMA user_version` agree;
- diagnostics is `ok`; health and readiness are ready in online mode;
- active/deleted list, original hash/size, extracted text, and task/attempt state checks passed or their allowed empty-data skips are recorded;
- no automatic migration of the backup, repair, rebuild, task execution, source-state promotion, Provider call, report generation, or delivery occurred;
- output and records contain no live path, source text, secret, SQL, raw response, or traceback.

## Record Template

```text
Drill ID:
Date/time:
Operator:
Application build identifier:
Source backup identifier:
Backup verify: passed / failed (stable error code):
Restore target: new empty directory
Backup schema version:
Restored schema version:
Offline acceptance: passed / failed:
Online acceptance: passed / failed / not_run:
Liveness:
Health:
Readiness:
Diagnostics:
Active/deleted counts:
Original hash/size:
Task/attempt state:
Duration:
Failures and stable error codes:
Recovery decision:
Next scheduled drill:
Known not_verified limits:
```

## Incident Boundaries

A failed verify, integrity, foreign-key, schema/history, staging, original hash, readiness, or post-restore check is a stop condition. Do not start the target, overwrite a live root, substitute originals, manually edit schema history/version, or treat liveness as readiness. Preserve the failed target/backup and stable error code, then use another verified backup into a new target. There is no runtime read-only serving mode in this release; stop the affected service until an explicit recovery decision is accepted.
