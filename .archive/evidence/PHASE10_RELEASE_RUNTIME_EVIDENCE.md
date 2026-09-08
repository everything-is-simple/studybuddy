# Phase 10-7 Release Runtime Evidence

> Gate H status: `implemented/backend-pass` in the declared local single-process, single-instance, SQLite, local-disk scope. This is not an installer-for-all-Windows claim, not a multi-worker deployment claim, and not global `production real-pass`.

## Runtime Contract

- `AppConfig` freezes local release controls: loopback host, port, upload limit, provider/model/base URL, runtime-only key fields, demo mode, task concurrency, log level, and optional external backup root.
- Defaults are safe: `127.0.0.1`, port `8787`, one task concurrency, `INFO`, provider unset, delivery `off`, no automatic repair/send.
- Host configuration accepts only loopback addresses. Task concurrency is fixed at one for this release. `serve` always invokes Uvicorn with `workers=1` and `reload=False`; it does not accept secrets as arguments.
- `STUDYBUDDY_DEMO_MODE=true` explicitly selects the deterministic fake provider and rejects real provider endpoint/key settings. Provider secrets are environment/runtime-only and remain hidden from `AppConfig.__repr__`.
- Startup validates loopback host, port, concurrency, log level, demo/provider consistency, and backup root outside data root before creating/using storage.
- `InstanceLock` holds `.studybuddy-instance.lock` for the process lifetime and rejects a second OS process or second in-process app for the same data root. The lock releases on normal shutdown and startup database/audit/recovery failure.
- Windows scripts provide explicit local operation:
  - `backend/scripts/start-studybuddy.ps1`: creates the selected data root, forces loopback and delivery-off, starts `python -m backend.app serve`, and records a PID file.
  - `backend/scripts/health-studybuddy.ps1`: checks liveness, health, and readiness and returns nonzero unless health/readiness are HTTP 200.
  - `backend/scripts/stop-studybuddy.ps1`: targets only the recorded PID, requests graceful close, waits for exit, and reports a stable timeout instead of killing an unrelated process by port.
- `python -m backend.app version` reports only application/schema versions. Existing backup/verify/restore/diagnostics/upgrade CLI contracts remain explicit.

## Operator Commands

```text
C:/miniconda/py310/python.exe -m backend.app version
powershell -NoProfile -File .\backend\scripts\start-studybuddy.ps1 -DataRoot <local-data-root> -Port 8787
powershell -NoProfile -File .\backend\scripts\health-studybuddy.ps1 -Port 8787
powershell -NoProfile -File .\backend\scripts\stop-studybuddy.ps1 -DataRoot <local-data-root>
```

Use an untracked local environment or OS secret store for provider keys. Never put a key in a command argument, database, log, artifact, committed `.env`, or backup. `.env.example` contains placeholders/default-off values only.

## Automated Evidence

Focused command:

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase10_release.py backend/tests/test_startup_preflight.py backend/tests/test_ai_provider.py backend/tests/test_phase9d_delivery.py -q -p no:cacheprovider
```

Result: `38 passed`.

The release/config/startup focused tests cover default safety, invalid host/port/concurrency/log configuration, demo-mode provider restrictions, backup-root topology, secret repr redaction, version output, in-process and subprocess lock behavior, startup lock release after database failure, repeated-app rejection, script command safety, and loopback health/readiness expectations. Tests use temporary data roots and do not access real networks or providers.

The complete backend command is:

```text
powershell -NoProfile -File .\backend\scripts\test-backend.ps1
```

Result: `410 passed, 2 skipped`; the two skips are opt-in real-provider smoke tests.

## Boundaries Not Verified

- This gate does not claim a signed installer, MSI, service manager integration, universal Windows support, automatic upgrades, unattended deployment, or a real subprocess/console Ctrl+C drill.
- Windows ACL/permission denial, disk-full, power-loss, network filesystem, antivirus/file-lock interference, and long-running service resource behavior remain `not_verified` and are handled in Gate I.
- The runtime remains single-process/single-instance. Uvicorn workers, reload, multiple instances, shared data roots, cloud deployment, authentication, and multi-user operation are unsupported.
- Graceful shutdown is implemented as an explicit PID-targeted close request with timeout reporting; forced termination and true power-loss recovery remain `not_verified`.
