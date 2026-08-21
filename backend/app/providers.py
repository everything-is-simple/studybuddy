from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


PROVIDER_NOT_CONFIGURED = "provider_not_configured"
FAKE_PROVIDER_ID = "fake"
FAKE_MODEL_ID = "fake-studybuddy-v1"
MAX_PROVIDER_PROMPT_CHARS = 8000


class ProviderError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderRequest:
    question: str
    context_blocks: list[dict[str, object]]


@dataclass(frozen=True)
class ProviderResult:
    answer_text: str
    citation_keys: list[str]
    provider_id: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int


class LLMProvider(Protocol):
    provider_id: str
    model_id: str

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        ...


class FakeLLMProvider:
    provider_id = FAKE_PROVIDER_ID
    model_id = FAKE_MODEL_ID

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        question = request.question.strip()
        if not question or len(question) > MAX_PROVIDER_PROMPT_CHARS:
            raise ProviderError("provider_invalid_request")
        citation_keys: list[str] = []
        snippets: list[str] = []
        prompt_chars = len(question)
        for block in request.context_blocks[:3]:
            key = str(block.get("citation_key", ""))
            text = str(block.get("text", "")).strip()
            prompt_chars += len(text)
            if key and key not in citation_keys:
                citation_keys.append(key)
            if text:
                snippets.append(_snippet(text))
        fingerprint = hashlib.sha256((question + "\x1f" + "\x1f".join(citation_keys)).encode("utf-8")).hexdigest()[:12]
        if snippets:
            cited = " ".join(f"[{key}]" for key in citation_keys)
            answer = f"Fake answer {fingerprint}: {snippets[0]} {cited}".strip()
        else:
            answer = f"Fake answer {fingerprint}: no retrieved context was available."
        return ProviderResult(
            answer_text=answer,
            citation_keys=citation_keys,
            provider_id=self.provider_id,
            model_id=self.model_id,
            prompt_tokens=max(1, prompt_chars // 4),
            completion_tokens=max(1, len(answer) // 4),
        )


def _snippet(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


class ProviderRegistry:
    def __init__(self, provider_id: str | None, model_id: str | None = None) -> None:
        self.provider_id = provider_id
        self.model_id = model_id

    def configured_provider(self) -> LLMProvider:
        if self.provider_id != FAKE_PROVIDER_ID:
            raise ProviderError(PROVIDER_NOT_CONFIGURED)
        provider = FakeLLMProvider()
        if self.model_id not in (None, "", provider.model_id):
            raise ProviderError(PROVIDER_NOT_CONFIGURED)
        return provider

    def capabilities(self) -> dict[str, object]:
        try:
            provider = self.configured_provider()
        except ProviderError as error:
            return {
                "status": "not_configured",
                "configured": False,
                "provider_id": None,
                "model_id": None,
                "supports": {"qa": False},
                "error_code": error.code,
            }
        return {
            "status": "available",
            "configured": True,
            "provider_id": provider.provider_id,
            "model_id": provider.model_id,
            "supports": {"qa": True},
        }


def provider_registry(provider_id: str | None, model_id: str | None = None) -> ProviderRegistry:
    return ProviderRegistry(provider_id, model_id)
