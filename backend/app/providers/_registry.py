"""Provider registries and factory function."""

from __future__ import annotations

from ..embedding import (
    FAKE_EMBEDDING_MODEL_ID,
    MAX_EMBEDDING_BATCH,
    MAX_EMBEDDING_DIMENSIONS,
    MAX_EMBEDDING_TEXT_CHARS,
    EmbeddingError,
    EmbeddingProvider,
    FakeEmbeddingProvider,
)
from ._capture import DeterministicFakeCaptureProvider, LoopbackCaptureProvider, WhisperCliCaptureProvider
from ._core import (
    FAKE_PROVIDER_ID,
    PROVIDER_NOT_CONFIGURED,
    CaptureTranscriptionProvider,
    LLMProvider,
    ProviderError,
)
from ._fake import FakeLLMProvider
from ._openai_embedding import OpenAICompatibleEmbeddingProvider
from ._openai_llm import OpenAICompatibleLLMProvider


class EmbeddingProviderRegistry:
    def __init__(self, provider_id: str | None, model_id: str | None = None, *, model_revision: str = "1",
                 base_url: str | None = None, api_key: str | None = None,
                 timeout_seconds: float = 30.0, max_batch_size: int = MAX_EMBEDDING_BATCH,
                 max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS, max_dimensions: int = MAX_EMBEDDING_DIMENSIONS,
                 max_response_bytes: int = 2 * 1024 * 1024, max_retries: int = 0) -> None:
        self.base_url, self.api_key = base_url, api_key
        self.provider_id = provider_id
        self.model_id = model_id
        self.model_revision = model_revision or "1"
        self.timeout_seconds = timeout_seconds
        self.max_batch_size = max_batch_size
        self.max_text_chars = max_text_chars
        self.max_dimensions = max_dimensions
        self.max_response_bytes = max_response_bytes
        self.max_retries = max_retries

    def configured_provider(self) -> EmbeddingProvider:
        if self.provider_id is None and self.model_id is None:
            raise EmbeddingError("embedding_provider_not_configured")
        if self.provider_id != FAKE_PROVIDER_ID:
            if self.provider_id and self.model_id and self.base_url and self.api_key:
                return OpenAICompatibleEmbeddingProvider(
                    provider_id=self.provider_id, model_id=self.model_id, model_revision=self.model_revision,
                    base_url=self.base_url, api_key=self.api_key, timeout_seconds=self.timeout_seconds,
                    max_batch_size=self.max_batch_size, max_text_chars=self.max_text_chars,
                    max_dimensions=self.max_dimensions, max_response_bytes=self.max_response_bytes,
                    max_retries=self.max_retries)
            raise EmbeddingError("embedding_provider_not_configured")
        if isinstance(self.max_batch_size, bool) or not isinstance(self.max_batch_size, int) or not 1 <= self.max_batch_size <= MAX_EMBEDDING_BATCH:
            raise EmbeddingError("embedding_provider_invalid_config")
        if isinstance(self.max_text_chars, bool) or not isinstance(self.max_text_chars, int) or not 1 <= self.max_text_chars <= MAX_EMBEDDING_TEXT_CHARS:
            raise EmbeddingError("embedding_provider_invalid_config")
        if isinstance(self.max_dimensions, bool) or not isinstance(self.max_dimensions, int) or not 1 <= self.max_dimensions <= MAX_EMBEDDING_DIMENSIONS:
            raise EmbeddingError("embedding_provider_invalid_config")
        if self.model_id not in (None, "", FAKE_EMBEDDING_MODEL_ID):
            raise EmbeddingError("embedding_provider_invalid_config")
        provider = FakeEmbeddingProvider(model_revision=self.model_revision,
                                          max_batch_size=self.max_batch_size,
                                          max_text_chars=self.max_text_chars)
        if provider.dimensions > self.max_dimensions:
            raise EmbeddingError("embedding_invalid_dimensions")
        return provider

    def capabilities(self) -> dict[str, object]:
        try:
            provider = self.configured_provider()
        except EmbeddingError as error:
            return {"status": "not_configured" if error.code == "embedding_provider_not_configured" else "invalid_config",
                    "configured": False, "runtime_kind": "none", "verification_status": "not_applicable",
                    "network_required": False, "provider_id": None, "model_id": None, "model_revision": None,
                    "supports": {"embeddings": False, "batch": False}, "error_code": error.code}
        payload = provider.capabilities()
        payload["limits"] = {"max_batch_size": self.max_batch_size, "max_text_chars": self.max_text_chars,
                              "max_dimensions": self.max_dimensions, "max_response_bytes": self.max_response_bytes}
        return payload


class ProviderRegistry:
    def __init__(self, provider_id: str | None, model_id: str | None = None, *, base_url: str | None = None,
                 api_key: str | None = None, timeout_seconds: float = 30.0, max_retries: int = 0) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.base_url = base_url
        self._api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def configured_provider(self) -> LLMProvider:
        if self.provider_id == FAKE_PROVIDER_ID:
            provider = FakeLLMProvider()
            if self.model_id not in (None, "", provider.model_id):
                raise ProviderError("provider_invalid_config")
            return provider
        # Any complete non-fake configuration uses the generic OpenAI-compatible
        # adapter. Configuration completeness is deliberately not real-provider verification.
        if self.provider_id and self.base_url and self._api_key and self.model_id:
            return OpenAICompatibleLLMProvider(
                provider_id=self.provider_id, model_id=self.model_id, base_url=self.base_url,
                api_key=self._api_key, timeout_seconds=self.timeout_seconds, max_retries=self.max_retries,
            )
        if any(value for value in (self.provider_id, self.model_id, self.base_url, self._api_key)):
            raise ProviderError("provider_invalid_config")
        raise ProviderError(PROVIDER_NOT_CONFIGURED)

    def capture_provider(self, *, runtime_path: str | None = None, model_path: str | None = None,
                         timeout_seconds: float = 120.0, max_output_bytes: int = 262144) -> CaptureTranscriptionProvider:
        if self.provider_id in {FAKE_PROVIDER_ID, None, ""}:
            if self.model_id not in (None, "", DeterministicFakeCaptureProvider.model_id):
                raise ProviderError("transcription_provider_not_configured")
            return DeterministicFakeCaptureProvider()
        if self.provider_id == "loopback":
            if self.model_id not in (None, "", LoopbackCaptureProvider.model_id):
                raise ProviderError("transcription_provider_not_configured")
            return LoopbackCaptureProvider()
        if self.provider_id == WhisperCliCaptureProvider.provider_id:
            if not runtime_path or not model_path or self.model_id in (None, ""):
                raise ProviderError("transcription_provider_not_configured")
            return WhisperCliCaptureProvider(runtime_path, model_path, model_id=str(self.model_id),
                                             timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)
        raise ProviderError("transcription_provider_not_configured")

    def embedding_provider(self, *, model_revision: str = "1", base_url: str | None = None, api_key: str | None = None,
                           timeout_seconds: float = 30.0,
                           max_batch_size: int = MAX_EMBEDDING_BATCH, max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS,
                           max_dimensions: int = MAX_EMBEDDING_DIMENSIONS, max_response_bytes: int = 2 * 1024 * 1024,
                           max_retries: int = 0) -> EmbeddingProvider:
        try:
            return EmbeddingProviderRegistry(self.provider_id, self.model_id, model_revision=model_revision,
                base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds, max_batch_size=max_batch_size, max_text_chars=max_text_chars,
                max_dimensions=max_dimensions, max_response_bytes=max_response_bytes, max_retries=max_retries).configured_provider()
        except EmbeddingError as error:
            raise ProviderError(error.code) from None

    def capabilities(self) -> dict[str, object]:
        try:
            provider = self.configured_provider()
        except ProviderError as error:
            return {
                "status": "not_configured" if error.code == PROVIDER_NOT_CONFIGURED else "invalid_config",
                "configured": False,
                "verification_status": "not_applicable",
                "runtime_kind": "none",
                "config_source": "process_environment",
                "provider_id": None,
                "model_id": None,
                "supports": {"qa": False},
                "error_code": error.code,
            }
        if provider.provider_id == FAKE_PROVIDER_ID:
            return {
                "status": "demo",
                "configured": True,
                "verification_status": "not_applicable",
                "runtime_kind": "deterministic_demo",
                "config_source": "process_environment",
                "provider_id": provider.provider_id,
                "model_id": provider.model_id,
                "supports": {"qa": True},
            }
        return {
            "status": "configured",
            "configured": True,
            "verification_status": "unverified",
            "runtime_kind": "openai_compatible",
            "config_source": "process_environment",
            "provider_id": provider.provider_id,
            "model_id": provider.model_id,
            "supports": {"qa": True},
        }


def provider_registry(provider_id: str | None, model_id: str | None = None, **kwargs: object) -> ProviderRegistry:
    return ProviderRegistry(provider_id, model_id, **kwargs)
