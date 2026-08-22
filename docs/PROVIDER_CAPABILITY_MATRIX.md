# Phase 5 Provider Capability Matrix

> Updated: 2026-08-25
>
> This document records provider-specific evidence. A passed DeepSeek smoke does not establish support or real-pass for another OpenAI-compatible provider.

## Evidence Rules

A provider row may be marked `real-pass` only after both opt-in tests pass with that provider's own configuration:

1. adapter-level synthetic context smoke;
2. API-level synthetic material path: upload, explicit indexing, retrieval, Q&A, citation validation, and `ai_operations` metadata persistence;
3. Chromium UI smoke when browser acceptance is available: answer, citation display/location, failure UX, retry, duplicate click and redaction.

The test must use a temporary `data_root`, synthetic material, and environment variables supplied outside the repository. API keys, raw provider responses, source text, private paths and request transcripts must not be committed.

## Matrix

| Provider | `STUDYBUDDY_AI_PROVIDER` | Expected model/config | Endpoint shape | Adapter | API smoke | UI smoke | Current status | Blocking evidence |
|---|---|---|---|---|---|---|---|---|
| DeepSeek | `deepseek` | `STUDYBUDDY_AI_MODEL=deepseek-chat` | Provider base URL, adapter appends `/chat/completions` | passed | passed | passed | `real-pass` for `deepseek-chat` only | Other DeepSeek models/endpoints not covered |
| ARK | `ark` | Provider-issued model ID, no default assumed | OpenAI-compatible base URL; verify provider-specific path before run | implemented by generic adapter | pending | pending | `not_verified` | Provider endpoint/model/key unavailable in this environment |
| SiliconFlow | `siliconflow` | Provider-issued model ID, no default assumed | OpenAI-compatible base URL; verify provider-specific path before run | implemented by generic adapter | pending | pending | `not_verified` | Provider endpoint/model/key unavailable in this environment |
| Agnes AI-Hub | `agnes-ai-hub` | Provider-issued model ID, no default assumed | OpenAI-compatible base URL; verify provider-specific path before run | implemented by generic adapter | pending | pending | `not_verified` | Provider endpoint/model/key unavailable in this environment |
| Sub2API | `sub2api` | Provider-issued model ID, no default assumed | OpenAI-compatible base URL; verify provider-specific path before run | implemented by generic adapter | pending | pending | `not_verified` | Provider endpoint/model/key unavailable in this environment |

`implemented by generic adapter` means the code accepts the provider as an identifier and applies the common OpenAI-compatible contract. It is not provider-specific real evidence.

## Opt-In Commands

Set these values only in the process environment. Do not write them to tracked files, test artifacts or logs.

```text
set STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE=1
set STUDYBUDDY_AI_PROVIDER=<provider-id>
set STUDYBUDDY_AI_MODEL=<provider-issued-model-id>
set STUDYBUDDY_AI_BASE_URL=https://<provider-base-url>
set STUDYBUDDY_AI_API_KEY=<secret>
D:/miniconda/py310/python.exe -m pytest backend/tests/test_real_provider_smoke.py -q
```

For the browser gate:

```text
set STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE=1
npx playwright test H:/studybuddy/backend/tests/browser_qa.spec.js --workers=1 --reporter=line
```

The browser test uses `STUDYBUDDY_RUN_REAL_PROVIDER_UI_SMOKE=1` and the same provider configuration. It starts a temporary local server and must be run only when the provider endpoint and model are known to satisfy the OpenAI-compatible `/chat/completions` contract.

## Result Recording

After a real run, record only:

- provider identifier and model identifier;
- test command and timestamp;
- pass/fail/skip status;
- stable error code on failure;
- whether adapter, API and UI gates passed;
- explicit limitations.

Never record API keys, Authorization headers, raw response bodies, full prompts, source material, private paths or traceback text.

## Current Limitations

- The generic adapter does not prove provider-specific model availability, quota, regional routing, billing, safety policy or uptime.
- No automatic fallback between providers is implemented.
- HTTPS is required for non-loopback endpoints; loopback HTTP remains limited to local mock testing.
- Provider-specific validation remains opt-in and is not part of default CI.
