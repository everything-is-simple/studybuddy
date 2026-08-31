# Phase 10 Release Candidate Acceptance Evidence

> Gate J status: `completed` in the declared **local single-process / single-instance / SQLite / local-disk v1** scope. This records a release-candidate drill and regression evidence; it is not a global `production real-pass` claim.

## Release conclusion

Phase 10 is complete. StudyBuddy has completed productionization and release closeout within the supported local-v1 envelope: explicit single-process task execution and recovery, safe observability/readiness/diagnostics, versioned migration and backup/restore operations, local runtime release controls, bounded capacity evidence, and the Gate J release-candidate drill have passed.

The conclusion is limited to Windows local operation with one process, one instance, one local data root, SQLite, local disk, and deterministic fake-provider release evidence. It does **not** claim support for multi-user authentication/authorization, cloud sync, collaboration, multiple processes/workers sharing a `data_root`, real power-loss recovery, universal installers, all real Providers/OCR/ASR/delivery channels, or global production `real-pass`.

## Release-candidate drill

`backend/tests/test_phase10_gate_j.py` creates a new `mkdtemp` workspace for every run and removes it in a `finally` block. It uses `AppConfig` with fake AI and embedding providers; it stores no data, backup, browser report, source text, path, secret, SQL, raw provider payload, or traceback in the repository or acceptance output.

The isolated drill passed these ordered stages:

| Stage | Result | Contract verified |
|---|---|---|
| Startup and readiness | passed | liveness, health and readiness report healthy only after normal startup |
| Material path | passed | synthetic TXT import, detail, search, original/text export and explicit synchronous indexing |
| Q&A/citation | passed | fake-provider Q&A succeeds and a server-issued citation remains valid/readable |
| Approved learning paths | passed | Cards/Exercises, Phase 9A plan/progress, Phase 9C practice setup, and Phase 9D capture/report snapshot |
| Explicit task execution | passed | only approved `embedding_index` task is queued and explicitly run; public task projection remains redacted |
| Retry and cancellation | passed | deterministic retryable embedding failure retains history, explicit retry succeeds on attempt 2, queued cancellation remains terminal |
| Backup and verify | passed | verified current-schema backup preserves database/original snapshot facts |
| Restore and restart | passed | restore to a new empty target preserves schema/history, does not auto-run tasks/providers/delivery, and survives a second startup |
| Diagnostics | passed | read-only CLI reports safe schema/task summary without path or traceback leakage |

The drill deliberately does not invoke real provider, OCR/ASR, report delivery, automatic scheduler, repair, rebuild, or migration side effects.

## Commands and results

All commands ran from the repository root with the project Python environment.

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase10_gate_j.py -q -p no:cacheprovider
# 1 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase10_gate_j.py backend/tests/test_phase10_release.py backend/tests/test_phase10_operations.py backend/tests/test_phase10_task_integration.py backend/tests/test_task_runner.py backend/tests/test_observability.py backend/tests/test_backup_restore.py backend/tests/test_restore_acceptance.py backend/tests/test_migrations.py backend/tests/test_phase10_boundary.py -q -p no:cacheprovider
# 83 passed

C:\miniconda\py310\python.exe -m pytest backend/tests/ -q -p no:cacheprovider
# 413 passed, 2 skipped

C:\miniconda\py310\python.exe backend/scripts/phase10_boundary.py
# passed; every local time-box threshold passed
```

The two backend skips are the explicitly opt-in real-provider smoke tests. They are not interpreted as passes.

The release-path Chromium regression was serial:

```text
powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_qa.spec.js
# 9 passed, 1 skipped (opt-in real-provider path)

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase8.spec.js
# 3 passed

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9a.spec.js
# 3 passed

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9b.spec.js
# 3 passed

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9c.spec.js
# 3 passed

powershell -ExecutionPolicy Bypass -NoProfile -File .\backend\scripts\test-browser.ps1 browser_phase9d.spec.js
# 4 passed
```

`backend/scripts/test-backend.ps1` is the normal backend gate. The host PowerShell execution policy blocked direct script execution in this run; the identical underlying pytest command above was run explicitly with `-p no:cacheprovider` and passed. Browser scripts were run with an explicit process-local `-ExecutionPolicy Bypass`; this changes no repository configuration.

## Gate summary

| Gate | Status | Evidence |
|---|---|---|
| A — launch scope | passed | `PHASE10_AUDIT_AND_SCOPE.md` |
| B — task contract | passed | `PHASE10_OPERATION_TASK_CONTRACT.md` |
| C — schema | passed | v13 migration and migration/backup tests |
| D — explicit runner | passed | `task_runner.py`, `test_task_runner.py` |
| E — approved integration | passed | `PHASE10_TASK_INTEGRATION_EVIDENCE.md` |
| F — observability/readiness | passed | `PHASE10_OBSERVABILITY_READINESS_EVIDENCE.md` |
| G — operations | passed | `PHASE10_OPERATIONS_EVIDENCE.md` |
| H — release runtime | passed | `PHASE10_RELEASE_RUNTIME_EVIDENCE.md` |
| I — bounded boundary evidence | passed | `PHASE10_BOUNDARY_EVIDENCE.md` |
| J — release closeout | passed | this file and `test_phase10_gate_j.py` |

## Hygiene, rollback and failure record

- The release drill used disposable isolated roots and removed them after completion.
- Repository hygiene inspection found no generated SQLite database, originals, backup/restore data, Playwright report, test-results directory, secret, or private test path created by Gate J work.
- No release-drill failure or rollback was triggered. Existing rollback evidence remains the verified backup → new empty target → restore procedure; live data is never overwritten by restore.
- The pre-existing untracked `pi-session-*.html` session artifact was not created, modified, or included by this Gate J work and remains outside the implementation change set.

## Not verified / outside the release claim

The following remain `not_verified` or deliberately outside local v1:

- Windows ACL/read-only-directory behavior, real quota/disk-full behavior, power loss, forced termination, hardware or filesystem corruption, antivirus interference, and network filesystems;
- unbounded production load, large-S4 memory/capacity, real traffic, service-manager operation, unattended upgrades, and a universal/signed Windows installer;
- multi-worker/multi-process coordination, shared `data_root`, multi-user deployment, authentication/authorization, cloud sync, collaboration, and remote storage;
- every Provider/model combination other than separately documented exact evidence; real OCR/ASR; live SMTP/Feishu delivery; scheduler/automatic dispatch; and generic worker execution;
- system-level screen-reader validation, true offline behavior, extreme content, and long-duration browser reliability.

These boundaries do not block the accepted local-v1 release scope defined in Gate A, but require separate evidence before any broader support claim.
