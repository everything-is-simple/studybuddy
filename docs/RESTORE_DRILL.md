# Restore Drill

This drill verifies that an operator can recover StudyBuddy without overwriting live data.

## Preconditions

- Select a backup that has passed `verify-backup`.
- Stop or isolate the live service before any replacement decision.
- Use a new target directory that is absent or empty.
- Confirm target disk capacity and operator permissions.
- Keep backup and target outside the live data root.
- Use a separate port for the drill; never run two services against one data root.

## Procedure

```text
D:/miniconda/py310/python.exe -m app.cli verify-backup --backup <backup-root>
D:/miniconda/py310/python.exe -m app.cli restore --data-root <drill-root> --backup <backup-root> --confirm
D:/miniconda/py310/python.exe -m app.cli verify-restored-data --data-root <drill-root>
```

For online verification, start a separate drill instance with the restored root:

```text
D:/miniconda/py310/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8792
D:/miniconda/py310/python.exe -m app.cli verify-restored-data --data-root <drill-root> --base-url http://127.0.0.1:8792
D:/miniconda/py310/python.exe -m app.cli schema-version --database <drill-root>/studybuddy.sqlite3
```

The online check covers health, active/deleted lists, one active detail when present,
original download, extracted text, and database consistency. An empty database reports
material detail/original/text checks as skipped, not failed. Stop the drill instance
and remove only the drill target after recording the result.

## Success criteria

- backup verification passed;
- restore staging verification passed;
- live data was not modified;
- health passed in online mode;
- active/deleted lists passed;
- detail passed, or no-active-material was explicitly skipped;
- original SHA-256 and size passed;
- extracted text passed UTF-8 and content checks;
- schema history and `PRAGMA user_version` agree;
- FTS/search remains available after startup;
- no automatic repair, migration of the backup, or hidden rebuild occurred;
- no sensitive path, source text, secret, SQL or traceback was written to the result.

## Record template

```text
Drill ID:
Date/time:
Operator:
Source backup identifier:
Backup verify: passed / failed (error code):
Restore target type: new empty directory
Schema version:
Active count:
Deleted count:
Offline acceptance: passed / failed:
Online acceptance: passed / failed / not run:
Health:
List:
Detail:
Original download:
Text export:
Search:
Duration:
Failures:
Remediation:
Next scheduled drill:
```

## Incident boundaries

A failed verify, integrity check, schema check, staging check, or post-restore check is
not a reason to start the target. Preserve the stable error code and use another verified
backup. There is no runtime read-only mode in this release; stop the service when the
storage state cannot be established as safe.
