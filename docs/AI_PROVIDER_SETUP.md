# AI Provider Setup

## Scope and Boundaries

StudyBuddy accepts one OpenAI-compatible Chat Completions provider per process through `STUDYBUDDY_AI_*` environment variables. Provider configuration belongs to the local runtime environment, not the repository: do not store API keys, provider auth files, databases, raw responses or generated run output in the source tree.

The generic adapter applies the common `/chat/completions` contract. It does not establish that a provider endpoint, model, account, quota, region or response behavior is supported. Provider-specific evidence is tracked in [PROVIDER_CAPABILITY_MATRIX.md](PROVIDER_CAPABILITY_MATRIX.md).

## Configure StudyBuddy

Use [.env.example](../.env.example) only as a redacted template. Set the values in the process environment or an untracked local `.env` file. Configure provider ID, model ID, base URL and API key as a matching set supplied by the selected provider.

PowerShell example:

```powershell
$env:STUDYBUDDY_AI_PROVIDER = "<provider-id>"
$env:STUDYBUDDY_AI_MODEL = "<provider-issued-model-id>"
$env:STUDYBUDDY_AI_BASE_URL = "https://<provider-base-url>"
$env:STUDYBUDDY_AI_API_KEY = "<local-secret>"
$env:STUDYBUDDY_AI_TIMEOUT_SECONDS = "30"
$env:STUDYBUDDY_AI_MAX_RETRIES = "0"
```

Non-loopback provider endpoints must use HTTPS. The adapter appends `/chat/completions` to the configured base URL, sends a bearer token, and uses non-streaming OpenAI-compatible request and response fields. Do not mix a model ID, endpoint or API key from different providers.

## Agnes Dedicated Local Route

Use the dedicated [Agnes provider runbook](AGNES_PROVIDER_RUNBOOK.md) for Agnes local profiles. It maps `STUDYBUDDY_AGNES_*` into `STUDYBUDDY_AI_*` only inside a child process, does not modify the parent shell, accept keys as command-line arguments, or add fallback. `agnes-2.5-flash` has model-specific controlled API/UI evidence; `agnes-2.5-pro` remains not_verified after `provider_unavailable`, and all model evidence remains independent.

## Verification

DeepSeek `deepseek-chat` is the only provider/model with current StudyBuddy adapter, full API-path and Chromium UI opt-in smoke evidence. Run a provider's own smoke gate only with temporary local data and synthetic material:

```text
set STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE=1
set STUDYBUDDY_REAL_PROVIDER_TARGET=<provider-id>
set STUDYBUDDY_AI_PROVIDER=<provider-id>
set STUDYBUDDY_AI_MODEL=<provider-issued-model-id>
set STUDYBUDDY_AI_BASE_URL=https://<provider-base-url>
set STUDYBUDDY_AI_API_KEY=<local-secret>
D:/miniconda/py310/python.exe -m pytest backend/tests/test_real_provider_smoke.py -q
```

A successful short request does not prove quota, billing, model quality, long-context behavior, uptime or a different model. Record only redacted results and stable error codes in the capability matrix.

### Three-Attempt API Acceptance

Use `backend/scripts/run-provider-api-acceptance.ps1` only with a securely configured runtime Provider/model and explicit opt-in. It runs the existing adapter/API synthetic smoke serially up to three times, creates a separate temporary data root and pytest directory for every attempt, and discards child test output. Two passes stop the remaining attempt as `threshold_reached`; two failures stop it as `threshold_unreachable`. Its final `2_of_3_passed` result is API acceptance evidence only, not `real-pass`: a separate target-gated Chromium UI smoke is still required for the exact Provider/model/gateway combination.

```powershell
$env:STUDYBUDDY_RUN_THREE_ATTEMPT_PROVIDER_ACCEPTANCE = "1"
powershell -NoProfile -File .\backend\scripts\run-provider-api-acceptance.ps1 -ProviderId "<provider-id>" -ModelId "<model-id>" -BaseUrl "https://<provider-base-url>"
```

The runner accepts no key/token parameters. It reads `STUDYBUDDY_AI_API_KEY` only from its runtime environment, emits only provider/model, attempt status, allow-listed stable error codes, and the final threshold result, and never reads backup files or prints child output. No three-attempt acceptance run was performed when this runner was introduced.

## Safety and Limits

- Rotate or revoke any key that may have appeared in an untrusted backup or history; Git ignore rules are not revocation.
- Do not place keys in documentation, source, tests, logs, SQLite, frontend responses or test artifacts.
- `STUDYBUDDY_AI_MAX_RETRIES` defaults to `0`; retry only deliberate, bounded transient-failure cases.
- The adapter does not support native non-OpenAI protocols without a dedicated implementation.
- There is no automatic provider fallback or multi-provider routing.
