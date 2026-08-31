"""Provider implementations for LLM, embedding, and transcription services."""

from __future__ import annotations

# Ensure SSL context is initialized
from ._ssl import _ensure_ssl_context  # noqa: F401

# Core types, protocols, and constants
from ._core import (
    FAKE_MODEL_ID,
    FAKE_PROVIDER_ID,
    MAX_PROVIDER_PROMPT_CHARS,
    MAX_PROVIDER_RESPONSE_BYTES,
    PROVIDER_NOT_CONFIGURED,
    CaptureProviderError,
    CaptureTranscriptionProvider,
    CaptureTranscriptionRequest,
    ImageOcrProvider,
    ImageOcrRequest,
    CaptureTranscriptionResult,
    LLMProvider,
    ProviderError,
    ProviderRequest,
    ProviderResult,
)

# Capture providers
from ._ocr import PaddleImageOcrProvider

from ._capture import (
    DeterministicFakeCaptureProvider,
    FakeCaptureProvider,
    LoopbackCaptureProvider,
    WhisperCliCaptureProvider,
)

# LLM providers
from ._fake import FakeLLMProvider
from ._openai_llm import OpenAICompatibleLLMProvider

# Embedding provider
from ._openai_embedding import OpenAICompatibleEmbeddingProvider

# Registries and factory
from ._registry import (
    EmbeddingProviderRegistry,
    ProviderRegistry,
    provider_registry,
)

__all__ = [
    # Constants
    "PROVIDER_NOT_CONFIGURED",
    "FAKE_PROVIDER_ID",
    "FAKE_MODEL_ID",
    "MAX_PROVIDER_PROMPT_CHARS",
    "MAX_PROVIDER_RESPONSE_BYTES",
    # Core types
    "ProviderError",
    "ProviderRequest",
    "ProviderResult",
    "LLMProvider",
    # Capture types
    "CaptureTranscriptionRequest",
    "CaptureTranscriptionResult",
    "CaptureProviderError",
    "CaptureTranscriptionProvider",
    "ImageOcrProvider",
    "ImageOcrRequest",
    "PaddleImageOcrProvider",
    # Capture providers
    "DeterministicFakeCaptureProvider",
    "FakeCaptureProvider",
    "LoopbackCaptureProvider",
    "WhisperCliCaptureProvider",
    # LLM providers
    "FakeLLMProvider",
    "OpenAICompatibleLLMProvider",
    # Embedding provider
    "OpenAICompatibleEmbeddingProvider",
    # Registries
    "EmbeddingProviderRegistry",
    "ProviderRegistry",
    "provider_registry",
]
