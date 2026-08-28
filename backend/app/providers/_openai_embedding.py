"""OpenAI-compatible embedding provider."""

from __future__ import annotations

import json

from ..embedding import (
    EMBEDDING_ENCODING,
    MAX_EMBEDDING_BATCH,
    MAX_EMBEDDING_DIMENSIONS,
    MAX_EMBEDDING_TEXT_CHARS,
    EmbeddingError,
    validate_dimensions,
    _validate_vectors,
)
from ._core import ProviderError
from ._helpers import _request_json_with_limit


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, *, provider_id: str, model_id: str, model_revision: str, base_url: str,
                 api_key: str, timeout_seconds: float = 30.0, max_batch_size: int = MAX_EMBEDDING_BATCH,
                 max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS, max_dimensions: int = MAX_EMBEDDING_DIMENSIONS,
                 max_response_bytes: int = 2 * 1024 * 1024, max_retries: int = 0) -> None:
        if not provider_id or not model_id or not base_url or not api_key:
            raise ProviderError("embedding_provider_not_configured")
        self.provider_id, self.model_id, self.model_revision = provider_id, model_id, model_revision or "1"
        self.base_url, self._api_key = base_url.rstrip("/"), api_key
        self.timeout_seconds, self.max_batch_size = timeout_seconds, max_batch_size
        self.max_text_chars, self.max_dimensions = max_text_chars, max_dimensions
        self.max_response_bytes, self.max_retries = max_response_bytes, max_retries
        self.encoding = EMBEDDING_ENCODING
        self.dimensions = 0

    def capabilities(self) -> dict[str, object]:
        return {"status": "configured", "configured": True, "runtime_kind": "openai_compatible",
                "verification_status": "unverified", "network_required": True,
                "provider_id": self.provider_id, "model_id": self.model_id,
                "model_revision": self.model_revision, "encoding": self.encoding,
                "supports": {"embeddings": True, "batch": True}}

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or not texts or len(texts) > self.max_batch_size:
            raise EmbeddingError("embedding_batch_too_large")
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("embedding_invalid_request")
        if any(len(text.strip()) > self.max_text_chars for text in texts):
            raise EmbeddingError("embedding_text_too_long")
        payload = json.dumps({"model": self.model_id, "input": [text.strip() for text in texts]}).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        last: ProviderError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = _request_json_with_limit(f"{self.base_url}/embeddings", payload, headers,
                                                    self.timeout_seconds, self.max_response_bytes)
                data = response.get("data")
                if not isinstance(data, list) or len(data) != len(texts):
                    raise EmbeddingError("embedding_schema_mismatch")
                ordered = sorted(data, key=lambda item: item.get("index", -1) if isinstance(item, dict) else -1)
                vectors = [item.get("embedding") for item in ordered if isinstance(item, dict)]
                if len(vectors) != len(texts):
                    raise EmbeddingError("embedding_schema_mismatch")
                if not self.dimensions:
                    self.dimensions = len(vectors[0]) if isinstance(vectors[0], list) else 0
                validate_dimensions(self.dimensions)
                if self.dimensions > self.max_dimensions:
                    raise EmbeddingError("embedding_invalid_dimensions")
                return _validate_vectors(vectors, len(texts), self.dimensions)
            except ProviderError as error:
                last = error
                if error.code not in {"embedding_provider_connection_failed", "embedding_provider_unavailable", "embedding_provider_timeout", "embedding_provider_rate_limited"} or attempt >= self.max_retries:
                    raise EmbeddingError(error.code) from None
        raise EmbeddingError(last.code if last else "embedding_provider_failed")
