"""Core provider types, protocols, and constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

PROVIDER_NOT_CONFIGURED = "provider_not_configured"
FAKE_PROVIDER_ID = "fake"
FAKE_MODEL_ID = "fake-studybuddy-v1"
MAX_PROVIDER_PROMPT_CHARS = 8000
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderRequest:
    question: str
    context_blocks: list[dict[str, object]]
    max_output_tokens: int = 800
    max_prompt_chars: int = 30000
    max_answer_chars: int = 12000
    generation_kind: str | None = None
    generation_count: int = 1
    exercise_type: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    answer_text: str
    citation_keys: list[str]
    provider_id: str
    model_id: str
    prompt_tokens: int | None
    completion_tokens: int | None
    provider_request_id: str | None = None
    total_tokens: int | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None


class LLMProvider(Protocol):
    provider_id: str
    model_id: str

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        ...


@dataclass(frozen=True)
class CaptureTranscriptionRequest:
    """In-memory S7 input; raw asset bytes never cross the persistence boundary."""

    asset_kind: str
    media_type: str
    content_sha256: str
    content: bytes


@dataclass(frozen=True)
class CaptureTranscriptionResult:
    segments: list[dict[str, object]]
    language: str | None = None


class CaptureProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CaptureTranscriptionProvider(Protocol):
    provider_id: str
    model_id: str

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        ...


@dataclass(frozen=True)
class ImageOcrRequest:
    """In-memory OCR input; raw bytes never cross the persistence boundary."""

    media_type: str
    content_sha256: str
    content: bytes


class ImageOcrProvider(Protocol):
    provider_id: str
    model_id: str

    def recognize(self, request: ImageOcrRequest) -> CaptureTranscriptionResult:
        ...
