# Phase 7 Embedding Acceptance Evidence

## Run

- Date: 2026-08-28
- Material/input: synthetic controlled text only
- Secret handling: keys were read from local untracked sources into child processes; no key was written to the repository, database, logs, or this document.

## Passed Exact Gate: Mistral

- Provider: `mistral`
- Model: `mistral-embed`
- Gateway: `https://api.mistral.ai/v1`
- Direct embedding request: pass
- Batch count: `1`
- Vector dimensions: `1024`
- Isolated StudyBuddy indexing: pass, status `ready`
- Isolated vector retrieval: pass, status `succeeded`
- Persisted embedding identity: `mistral / mistral-embed / 1024 / ready`
- Persisted retrieval identity: `mistral / mistral-embed / succeeded`
- Persisted indexing operation: `embedding_index / succeeded`

This is an exact provider/model/gateway acceptance result. It does not establish global Mistral availability, quota, quality, uptime, or production readiness.

## Not Selected: Agnes

- Provider: `agnes-ai-hub`
- Model: `agnes-2.5-flash`
- Gateway: `https://apihub.agnes-ai.com/v1`
- Result: failed
- Stable classification: `embedding_provider_protocol_error`

The model is documented as a text chat model, not as a confirmed embedding model. It is not selected for Phase 7 embedding.

## Not Selected: ARK

- Provider: `ark`
- Model: `deepseek-v4-flash`
- Gateway: `https://ark.cn-beijing.volces.com/api/coding/v3`
- Result: failed
- Stable classification: `embedding_provider_invalid_config`

The supplied profile identifies a coding/chat endpoint and model, not a confirmed embedding model. It is not selected for Phase 7 embedding, but remains a separate possible LLM-provider candidate.

## Not Selected: MiniMax and NVIDIA

- MiniMax candidate: `minimax / embo-01 / https://api.minimax.chat/v1`
  - Direct probe: failed with `embedding_schema_mismatch`.
- NVIDIA candidate: `nvidia / nvidia/nv-embedqa-e5-v5 / https://integrate.api.nvidia.com/v1`
  - Direct probe: failed with `embedding_provider_protocol_error`.

Neither candidate is treated as real-pass.

## Boundary

The Mistral exact gate closes the Phase 7 external embedding acceptance requirement for the selected default embedding configuration. Retrieval UI/Chromium and indexing lease/retry/recovery gates were separately verified earlier. Phase 7 is completed for this scoped local single-process configuration; this does not claim generic multi-provider or global production readiness.

Keys supplied through user-visible local sources should be rotated after this run.
