"""Explicit synthetic checks of effective providers; never stores raw responses."""
from __future__ import annotations

import json
import math
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .config import AppConfig
from .embedding import EmbeddingError
from .providers import EmbeddingProviderRegistry, ProviderError, ProviderRequest, provider_registry

SYNTHETIC_CITATION = "ctx-synthetic-water"


class SavedCapabilityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: Literal["qa", "generation", "index"]


def verify_saved_capability(config: AppConfig, capability: str) -> dict[str, object]:
    """Exercise the configured adapter using fixed data, with no DB/config writes.

    A successful receipt covers this synthetic request only. It does not upgrade
    the global readiness matrix or claim material ingestion/retrieval succeeded.
    """
    started = time.monotonic()
    if capability == "index":
        provider = EmbeddingProviderRegistry(
            config.embedding_provider_id, config.embedding_model_id,
            model_revision=config.embedding_model_revision,
            base_url=config.embedding_base_url, api_key=config.embedding_api_key,
            timeout_seconds=config.embedding_timeout_seconds,
            max_batch_size=config.embedding_max_batch_size,
            max_text_chars=config.embedding_max_text_chars,
            max_dimensions=config.embedding_max_dimensions,
            max_response_bytes=config.embedding_max_response_bytes,
            max_retries=config.embedding_max_retries,
        ).configured_provider()
        vectors = provider.embed(["Water evaporates.", "Water condenses into clouds."])
        if (len(vectors) != 2 or not vectors[0] or len(vectors[0]) != len(vectors[1])
                or any(not math.isfinite(v) for vector in vectors for v in vector)):
            raise EmbeddingError("embedding_invalid_vector")
        details = {"vector_count": 2, "dimensions": len(vectors[0])}
    elif capability in {"qa", "generation"}:
        provider = provider_registry(
            config.ai_provider_id, config.ai_model_id,
            base_url=config.ai_base_url, api_key=config.ai_api_key,
            timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries,
        ).configured_provider()
        result = provider.generate_answer(ProviderRequest(
            question="Explain the water cycle using the supplied context.",
            context_blocks=[{"citation_key": SYNTHETIC_CITATION,
                             "text": "The water cycle includes evaporation, condensation and precipitation."}],
            max_output_tokens=config.ai_max_output_tokens,
            max_prompt_chars=config.ai_max_prompt_chars,
            max_answer_chars=config.ai_max_answer_chars,
            generation_kind="card" if capability == "generation" else None,
        ))
        if capability == "generation":
            try:
                payload = json.loads(result.answer_text)
                if not isinstance(payload, dict) or set(payload) != {"items"}:
                    raise ValueError
                items = payload["items"]
                if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
                    raise ValueError
                item = items[0]
                if set(item) != {"front", "back", "explanation", "tags", "citations"}:
                    raise ValueError
                if any(not isinstance(item[key], str) or not item[key].strip()
                       for key in ("front", "back", "explanation")):
                    raise ValueError
                if not isinstance(item["tags"], list) or any(not isinstance(v, str) for v in item["tags"]):
                    raise ValueError
                if item["citations"] != [SYNTHETIC_CITATION]:
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise ProviderError("provider_schema_mismatch") from None
            details = {"draft_count": 1, "valid_citation": True}
        else:
            if not result.answer_text.strip() or result.citation_keys != [SYNTHETIC_CITATION]:
                raise ProviderError("provider_schema_mismatch")
            details = {"has_answer": True, "valid_citation": True}
    else:
        raise ValueError("invalid_capability")
    return {"status": "PASS", "capability": capability, "scope": "synthetic_provider_request",
            "runtime_kind": "demo" if provider.provider_id == "fake" else "configured_provider",
            "provider_id": provider.provider_id, "model_id": provider.model_id,
            "elapsed_ms": round((time.monotonic() - started) * 1000), **details}
