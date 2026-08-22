# AI Provider Setup

## Scope and Boundaries

StudyBuddy accepts one OpenAI-compatible Chat Completions provider per process through `STUDYBUDDY_AI_*` environment variables. The default runtime state is `not_configured`; no real Provider is selected unless all required values are explicitly supplied. `STUDYBUDDY_AI_PROVIDER=fake` explicitly enables the deterministic/demo provider and must not be interpreted as real AI. Provider configuration belongs to the local runtime environment, not the repository: do not store API keys, provider auth files, databases, raw responses or generated run output in the source tree.

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

## Runtime Status Contract

`GET /api/ai/capabilities` reports the safe runtime contract used by the UI. `not_configured` means no Provider is configured; `invalid_config` means a partial or invalid configuration was supplied; `demo` means the explicit deterministic fake Provider is active; `configured` means a generic OpenAI-compatible adapter can be constructed, but its exact endpoint/model has not been real-verified. The separate `verification_status` is `unverified` for generic configurations and `not_applicable` for demo or unconfigured states. Provider ID and model ID may be shown; API keys, Authorization headers, sensitive URLs, raw responses, paths and tracebacks are never returned.

A configured adapter is not evidence of availability, quota, billing, model support or uptime. The UI must not call it verified merely because the configuration is complete.

## Verification

DeepSeek `deepseek-chat` and Agnes `agnes-2.5-flash` are the only provider/model combinations with current StudyBuddy adapter, full API-path and Chromium UI opt-in smoke evidence. Each result is limited to its exact provider/model/gateway configuration. Run a provider's own smoke gate only with temporary local data and synthetic material:

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
