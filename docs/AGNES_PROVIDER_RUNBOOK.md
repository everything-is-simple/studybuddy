# Agnes AI-Hub Local Runbook

## Status

Agnes AI-Hub is a long-term low-cost candidate, not a current `real-pass`. The project has a generic OpenAI-compatible adapter and an Agnes-specific local launcher, but Agnes remains unverified until its adapter, API and UI gates pass with a matching provider-issued model, HTTPS base URL and key.

The launcher does not add fallback or multi-provider routing. It starts one local StudyBuddy process configured for Agnes only.

## Local Configuration

Set these variables in the local PowerShell process or a secrets manager. Never put the key in a command line, tracked file, `.env.example`, documentation, logs or test artifacts.

```powershell
$env:STUDYBUDDY_AGNES_PROVIDER_ID = "agnes-ai-hub"
$env:STUDYBUDDY_AGNES_KEY = "<rotated-local-secret>"
$env:STUDYBUDDY_PYTHON = "D:\miniconda\py310\python.exe"
```

The launcher defaults to the official Agnes gateway `https://apihub.agnes-ai.com/v1`. Set `STUDYBUDDY_AGNES_BASE_URL` only when Agnes explicitly supplies a different HTTPS-compatible gateway. The base URL must not contain credentials, query or fragment values.

## Model Profiles

A StudyBuddy process uses exactly one Agnes model. To keep several low-cost candidates available without mixing model audit records, configure local named profiles. Profile names contain lowercase letters, digits and hyphens only; they are labels, not Agnes model IDs.

The official Agnes public model catalog documents these text Chat Completions defaults:

| Profile | Default model | Use in StudyBuddy |
|---|---|---|
| `budget` | `agnes-1.5-flash` | Low-latency Q&A and routine summaries |
| `balanced` | `agnes-2.0-flash` | General study Q&A, reasoning and coding material |
| `advanced` | `agnes-2.5-flash` | More demanding reasoning or coding material |

Start one profile explicitly:

```powershell
powershell -NoProfile -File .\backend\scripts\start-agnes.ps1 -Profile budget
powershell -NoProfile -File .\backend\scripts\start-agnes.ps1 -Profile balanced
powershell -NoProfile -File .\backend\scripts\start-agnes.ps1 -Profile advanced
```

A local `STUDYBUDDY_AGNES_MODEL_<PROFILE>` value overrides the corresponding default only when Agnes documents a replacement model ID for that profile. For example:

```powershell
$env:STUDYBUDDY_AGNES_MODEL_BUDGET = "<Agnes-confirmed-replacement-model-id>"
```

Without `-Profile`, the scripts require `STUDYBUDDY_AGNES_MODEL`. Do not run profiles concurrently against the same `STUDYBUDDY_DATA_ROOT`; StudyBuddy supports one local process/instance and SQLite data root at a time. Stop one server before starting another profile. A response records the selected provider/model ID in its normal Q&A audit metadata.

Optional non-secret settings are inherited only into the child process:

```powershell
$env:STUDYBUDDY_DATA_ROOT = "<temporary-or-local-data-root>"
$env:STUDYBUDDY_PROJECT_ID = "default"
$env:STUDYBUDDY_AI_TIMEOUT_SECONDS = "30"
$env:STUDYBUDDY_AI_MAX_RETRIES = "0"
```

## Preflight and Launch

All commands run from the repository root. The scripts fail closed if the provider ID, model, base URL or key is missing/invalid. They emit only stable status/error codes and never print secret values.

Start a local Agnes-configured server:

```powershell
powershell -NoProfile -File .\backend\scripts\start-agnes.ps1
```

The launcher maps the Agnes namespaced variables to `STUDYBUDDY_AI_PROVIDER`, `STUDYBUDDY_AI_MODEL`, `STUDYBUDDY_AI_BASE_URL` and `STUDYBUDDY_AI_API_KEY` only in the child process. It does not modify the parent PowerShell environment. The key is passed through the child environment, never through command-line arguments.

## Smoke Gates

API smoke uses temporary data and synthetic material:

```powershell
powershell -NoProfile -File .\backend\scripts\test-agnes-provider.ps1 -Profile budget
```

The script sets `STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE=1` and `STUDYBUDDY_REAL_PROVIDER_TARGET=agnes-ai-hub` in the child process. It runs only the target-gated real provider test.

Browser smoke:

```powershell
$env:STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE = "1"
$env:STUDYBUDDY_REAL_PROVIDER_UI_TARGET = "agnes-ai-hub"
powershell -NoProfile -File .\backend\scripts\test-agnes-ui.ps1 -Profile budget
```

The UI launcher sets the UI target in its child process and runs the existing browser suite. The suite includes the fake-provider regression tests; the targeted real case is enabled only by the child gate.

A successful request is not sufficient to claim all Agnes models are supported. The built-in profiles cover only the listed text chat models; image and video models use different endpoints and are not valid for StudyBuddy Q&A. Record only the actual provider ID/model ID, gate result and stable error code in [PROVIDER_CAPABILITY_MATRIX.md](PROVIDER_CAPABILITY_MATRIX.md). Never record raw responses, prompts, source text, paths, headers or key material.

## Stop and Cleanup

Stop the local Uvicorn process after use. Use a temporary `STUDYBUDDY_DATA_ROOT` for smoke runs and remove only that verified temporary test data. Do not overwrite a live data root with a test copy. Rotate or revoke any key that has appeared in an untrusted history or log; Git ignore rules do not revoke credentials.

## Boundaries

- Agnes is one explicitly selected process-local Provider.
- No automatic fallback, provider routing, worker queue, multi-user mode or cloud sync is added.
- Agnes real-pass remains pending until adapter, API and UI evidence exists.
- This runbook does not establish support for ARK, SiliconFlow, Sub2API, other Agnes models or other Provider protocols.
