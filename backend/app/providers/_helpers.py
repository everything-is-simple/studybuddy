"""Provider 实现的辅助函数。

本模块提供 Provider 实现共享的工具函数，包括：

**文本处理**：
- _snippet: 压缩文本为简短摘要
- _prompt_content: 构建包含问题和上下文的完整 prompt
- _extract_citation_keys: 从文本中提取引用标记

**HTTP 请求**：
- _request_json: 发送 JSON POST 请求并验证响应大小
- _request_json_with_limit: 带固定字节限制的 HTTP 请求

**响应解析**：
- _parse_openai_response: 解析 OpenAI API 响应格式
- _optional_int: 安全提取可选整数字段
- _safe_request_id: 验证并清洗请求 ID

**错误处理**：
所有 HTTP 函数统一将异常映射到 ProviderError，包括：
- 401/403 → auth_failed/forbidden
- 429 → rate_limited
- 500+ → unavailable
- 超时 → timeout
- 连接失败 → connection_failed

关联模块：
- providers._openai_llm: 使用 HTTP 和解析函数
- providers._openai_embedding: 使用 HTTP 和解析函数
- providers._core: 提供 ProviderError 和常量
"""

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
    """将文本压缩为简短摘要（去除多余空白）。
    
    Args:
        text: 原始文本
        limit: 最大字符数（默认 180）
        
    Returns:
        压缩后的文本片段，不超过 limit 字符
    """
    compact = " ".join(text.split())
    return compact[:limit]


def _prompt_content(question: str, blocks: list[dict[str, object]]) -> str:
    """构建包含问题和上下文块的完整 prompt 文本。
    
    格式：
    Question:
    {question}
    
    Context:
    [{citation_key}]
    {text}
    
    [{citation_key}]
    {text}
    ...
    
    Args:
        question: 用户问题
        blocks: 上下文块列表，每个块包含 citation_key 和 text
        
    Returns:
        格式化的 prompt 字符串
    """
    parts = [f"Question:\n{question}\n\nContext:"]
    for block in blocks:
        key = str(block.get("citation_key", ""))
        text = str(block.get("text", ""))
        parts.append(f"[{key}]\n{text}")
    return "\n\n".join(parts)


def _request_json(endpoint: str, payload: bytes, headers: dict[str, str], timeout: float) -> dict[str, object]:
    """发送 JSON POST 请求并验证响应大小。
    
    使用 urllib 发送 HTTP POST 请求，自动处理响应大小限制和常见错误。
    
    Args:
        endpoint: API 端点 URL
        payload: JSON 请求体（已编码为 bytes）
        headers: HTTP 请求头字典
        timeout: 请求超时时间（秒）
        
    Returns:
        解析后的 JSON 响应（字典）
        
    Raises:
        ProviderError: 请求失败时抛出，错误码包括：
            - provider_auth_failed: 401 认证失败
            - provider_forbidden: 403 无权限
            - provider_rate_limited: 429 限流
            - provider_unavailable: 500+ 服务不可用
            - provider_timeout: 请求超时
            - provider_connection_failed: 连接失败
            - provider_output_too_large: 响应超过 2MB
            - provider_malformed_response: 响应格式错误
            - provider_schema_mismatch: 响应不是字典
    """
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
    """解析 OpenAI API 响应格式为 ProviderResult。
    
    提取 choices[0].message.content 作为答案文本，自动提取引用标记，
    并收集 token 使用统计。
    
    Args:
        payload: OpenAI API 响应字典
        provider_id: Provider 标识符
        model_id: 模型标识符
        max_answer_chars: 答案最大字符数
        
    Returns:
        标准化的 ProviderResult 对象
        
    Raises:
        ProviderError: 响应格式不符合预期时抛出：
            - provider_schema_mismatch: 缺少必需字段或类型错误
            - provider_malformed_response: 内容为空
            - provider_output_too_large: 内容超过限制
            - provider_refusal: 模型拒绝回答（content_filter/refusal）
    """
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
    """从文本中提取所有引用标记（去重且保持顺序）。
    
    匹配格式：[ctx-xxx]，其中 xxx 为字母、数字、下划线、连字符，长度 1-70。
    
    Args:
        text: 包含引用标记的文本
        
    Returns:
        引用标记列表（已去重，保持首次出现顺序）
        
    Example:
        >>> _extract_citation_keys("参考 [ctx-abc] 和 [ctx-def] 以及 [ctx-abc]")
        ['ctx-abc', 'ctx-def']
    """
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
