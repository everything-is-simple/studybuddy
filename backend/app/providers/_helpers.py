"""Helper functions for provider implementations."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._core import (
    MAX_PROVIDER_RESPONSE_BYTES,
    ProviderError,
    ProviderResult,
)


def _snippet(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


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
    return list(dict.fromkeys(re.findall(r"\[(ctx-[a-zA-Z0-9_-]{1,70})\]", text)))


def _request_json_with_limit(endpoint: str, payload: bytes, headers: dict[str, str], timeout: float, limit: int) -> dict[str, object]:
    try:
        request = Request(endpoint, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ProviderError("embedding_provider_response_too_large")
    except ProviderError:
        raise
    except HTTPError as error:
        code = {401: "embedding_provider_auth_failed", 403: "embedding_provider_forbidden", 429: "embedding_provider_rate_limited"}.get(error.code, "embedding_provider_unavailable" if error.code >= 500 else "embedding_provider_protocol_error")
        raise ProviderError(code) from None
    except TimeoutError:
        raise ProviderError("embedding_provider_timeout") from None
    except URLError as error:
        raise ProviderError("embedding_provider_timeout" if getattr(error, "reason", None).__class__.__name__ == "timeout" else "embedding_provider_connection_failed") from None
    except UnicodeEncodeError:
        raise ProviderError("embedding_provider_invalid_config") from None
    except OSError:
        raise ProviderError("embedding_provider_connection_failed") from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderError("embedding_provider_malformed_response") from None
    if not isinstance(value, dict):
        raise ProviderError("embedding_provider_schema_mismatch")
    return value
