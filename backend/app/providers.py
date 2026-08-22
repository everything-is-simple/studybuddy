from __future__ import annotations

import hashlib
import json
import ssl
import time
from dataclasses import dataclass
from typing import Protocol

from .embedding import (EmbeddingError, EmbeddingProvider, FakeEmbeddingProvider,
                         EMBEDDING_ENCODING, FAKE_EMBEDDING_MODEL_ID, FAKE_EMBEDDING_MODEL_REVISION,
                         MAX_EMBEDDING_BATCH, MAX_EMBEDDING_TEXT_CHARS, MAX_EMBEDDING_DIMENSIONS)
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, Request, build_opener, install_opener, urlopen


def _ensure_ssl_context() -> None:
    """Windows 证书存储损坏时，用 certifi 的证书包兜底。

    某些 Windows 环境下系统证书存储包含坏条目，导致 Python ssl 默认 context
    初始化失败（SSLError: NOT_ENOUGH_DATA）。这里做一次探测：如果默认 context
    不可用且安装了 certifi，就切换到 certifi 的证书包。

    这不会修改任何安全语义，只是把证书来源从"系统存储"换成"certifi 包"，
    仍然是标准的 TLS 验证。
    """
    try:
        ssl.create_default_context()
        return  # 默认正常，什么都不做
    except ssl.SSLError:
        pass
    try:
        import certifi  # type: ignore
        ctx = ssl.create_default_context(cafile=certifi.where())
        install_opener(build_opener(HTTPSHandler(context=ctx)))
    except Exception:
        pass  # 没有 certifi 或其它问题，保持原状


_ensure_ssl_context()

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
        if prompt_chars > request.max_prompt_chars:
            raise ProviderError("provider_invalid_request")
        fingerprint = hashlib.sha256((question + "\x1f" + "\x1f".join(citation_keys)).encode("utf-8")).hexdigest()[:12]
        if snippets:
            cited = " ".join(f"[{key}]" for key in citation_keys)
            answer = f"Fake answer {fingerprint}: {snippets[0]} {cited}".strip()
        else:
            answer = f"Fake answer {fingerprint}: no retrieved context was available."
        if len(answer) > request.max_answer_chars:
            raise ProviderError("provider_output_too_large")
        prompt_tokens = max(1, prompt_chars // 4)
        completion_tokens = max(1, len(answer) // 4)
        return ProviderResult(
            answer_text=answer,
            citation_keys=citation_keys,
            provider_id=self.provider_id,
            model_id=self.model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
        )


def _snippet(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


class OpenAICompatibleLLMProvider:
    def __init__(self, *, provider_id: str, model_id: str, base_url: str, api_key: str,
                 timeout_seconds: float = 30.0, max_retries: int = 0) -> None:
        if not model_id or not base_url or not api_key:
            raise ProviderError("provider_not_configured")
        self.provider_id = provider_id
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        question = request.question.strip()
        if not question or len(question) > MAX_PROVIDER_PROMPT_CHARS:
            raise ProviderError("provider_invalid_request")
        user_content = _prompt_content(question, request.context_blocks)
        if len(user_content) > request.max_prompt_chars:
            raise ProviderError("provider_invalid_request")
        payload = json.dumps({
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": "Answer only from the supplied context. Your answer must include at least one exact citation key copied from the supplied context, using the format [ctx-...]. Do not invent or alter citation keys."},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }).encode("utf-8")
        endpoint = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        last_error: ProviderError | None = None
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            try:
                response = _request_json(endpoint, payload, headers, self.timeout_seconds)
                latency_ms = round((time.perf_counter() - started) * 1000)
                result = _parse_openai_response(response, self.provider_id, self.model_id,
                                                request.max_answer_chars)
                return ProviderResult(
                    answer_text=result.answer_text,
                    citation_keys=result.citation_keys,
                    provider_id=result.provider_id,
                    model_id=result.model_id,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    provider_request_id=result.provider_request_id,
                    total_tokens=result.total_tokens,
                    latency_ms=latency_ms,
                    finish_reason=result.finish_reason,
                )
            except ProviderError as error:
                last_error = error
                if error.code not in {"provider_connection_failed", "provider_unavailable"} or attempt >= self.max_retries:
                    raise
        raise last_error or ProviderError("provider_internal_error")


def _prompt_content(question: str, blocks: list[dict[str, object]]) -> str:
    parts = [f"Question:\n{question}\n\nContext:"]
    for block in blocks:
        key = str(block.get("citation_key", ""))
        text = str(block.get("text", ""))
        parts.append(f"[{key}]\n{text}")
    return "\n\n".join(parts)


def _request_json(endpoint: str, payload: bytes, headers: dict[str, str], timeout: float) -> dict[str, object]:
    try:
        request = Request(endpoint, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if int(length) > MAX_PROVIDER_RESPONSE_BYTES:
                        raise ProviderError("provider_output_too_large")
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, MAX_PROVIDER_RESPONSE_BYTES - total + 1))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_PROVIDER_RESPONSE_BYTES:
                    raise ProviderError("provider_output_too_large")
            raw = b"".join(chunks)
    except ProviderError:
        raise
    except HTTPError as error:
        if error.code == 401:
            raise ProviderError("provider_auth_failed") from None
        if error.code == 403:
            raise ProviderError("provider_forbidden") from None
        if error.code == 429:
            raise ProviderError("provider_rate_limited") from None
        if error.code in {500, 502, 503, 504}:
            raise ProviderError("provider_unavailable") from None
        raise ProviderError("provider_protocol_error") from None
    except TimeoutError:
        raise ProviderError("provider_timeout") from None
    except URLError as error:
        if getattr(error, "reason", None).__class__.__name__ == "timeout":
            raise ProviderError("provider_timeout") from None
        raise ProviderError("provider_connection_failed") from None
    except OSError:
        raise ProviderError("provider_connection_failed") from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderError("provider_malformed_response") from None
    if not isinstance(value, dict):
        raise ProviderError("provider_schema_mismatch")
    return value


def _parse_openai_response(payload: dict[str, object], provider_id: str, model_id: str,
                           max_answer_chars: int) -> ProviderResult:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("provider_schema_mismatch")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ProviderError("provider_schema_mismatch")
    content = message.get("content")
    if not isinstance(content, str):
        raise ProviderError("provider_schema_mismatch")
    if not content.strip():
        raise ProviderError("provider_malformed_response")
    if len(content) > max_answer_chars:
        raise ProviderError("provider_output_too_large")
    finish_reason = choices[0].get("finish_reason")
    if finish_reason in {"content_filter", "refusal"}:
        raise ProviderError("provider_refusal")
    usage = payload.get("usage")
    prompt_tokens = completion_tokens = total_tokens = None
    if isinstance(usage, dict):
        prompt_tokens = _optional_int(usage.get("prompt_tokens"))
        completion_tokens = _optional_int(usage.get("completion_tokens"))
        total_tokens = _optional_int(usage.get("total_tokens"))
    return ProviderResult(
        answer_text=content,
        citation_keys=_extract_citation_keys(content),
        provider_id=provider_id,
        model_id=model_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider_request_id=_safe_request_id(payload.get("id")),
        total_tokens=total_tokens,
        finish_reason=str(finish_reason) if isinstance(finish_reason, str) else None,
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _safe_request_id(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 200:
        return None
    return value if value and all(char.isalnum() or char in "._:-" for char in value) else None


def _extract_citation_keys(text: str) -> list[str]:
    import re
    return list(dict.fromkeys(re.findall(r"\[(ctx-[a-zA-Z0-9_-]{1,70})\]", text)))


class EmbeddingProviderRegistry:
    def __init__(self, provider_id: str | None, model_id: str | None = None, *, model_revision: str = "1",
                 timeout_seconds: float = 30.0, max_batch_size: int = MAX_EMBEDDING_BATCH,
                 max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS, max_dimensions: int = MAX_EMBEDDING_DIMENSIONS,
                 max_response_bytes: int = 2 * 1024 * 1024, max_retries: int = 0) -> None:
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

    def embedding_provider(self, *, model_revision: str = "1", timeout_seconds: float = 30.0,
                           max_batch_size: int = MAX_EMBEDDING_BATCH, max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS,
                           max_dimensions: int = MAX_EMBEDDING_DIMENSIONS, max_response_bytes: int = 2 * 1024 * 1024,
                           max_retries: int = 0) -> EmbeddingProvider:
        try:
            return EmbeddingProviderRegistry(self.provider_id, self.model_id, model_revision=model_revision,
                timeout_seconds=timeout_seconds, max_batch_size=max_batch_size, max_text_chars=max_text_chars,
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
