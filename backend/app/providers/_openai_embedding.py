"""OpenAI 兼容的 Embedding Provider 实现。

本模块实现了 OpenAI Embedding API 的客户端，用于将文本转换为向量表示，
支持批量处理和自动重试。

**支持的后端**：
- OpenAI 官方 API (text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002)
- Azure OpenAI Service
- 其他 OpenAI 兼容的 Embedding 服务

**主要功能**：
- 批量文本向量化（最多 MAX_EMBEDDING_BATCH 条）
- 自动维度检测和验证
- 网络故障重试机制
- 响应大小限制（防止 OOM）

**配置参数**：
- provider_id: Provider 标识符
- model_id: 模型名称（如 text-embedding-3-small）
- base_url: API 端点（如 https://api.openai.com/v1）
- api_key: 认证密钥
- timeout_seconds: 请求超时（默认 30 秒）
- max_retries: 最大重试次数（默认 0）

**错误处理**：
所有网络和协议错误都通过 ProviderError 抛出，最终转换为 EmbeddingError。
支持的错误码包括认证失败、限流、超时、连接失败等。

关联模块：
- embedding: Embedding 核心类型和验证逻辑
- _helpers: HTTP 请求工具
- _core: Provider 错误类型
"""

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
        """初始化 OpenAI 兼容的 Embedding Provider。

        Args:
            provider_id: Provider 标识符（如 "openai"）
            model_id: 模型名称（如 "text-embedding-3-small"）
            model_revision: 模型版本（用于缓存失效，默认 "1"）
            base_url: API 基础 URL（如 "https://api.openai.com/v1"）
            api_key: 认证密钥
            timeout_seconds: 请求超时时间（秒，默认 30.0）
            max_batch_size: 单批次最大文本数（默认 MAX_EMBEDDING_BATCH）
            max_text_chars: 单条文本最大字符数（默认 MAX_EMBEDDING_TEXT_CHARS）
            max_dimensions: 向量最大维度（默认 MAX_EMBEDDING_DIMENSIONS）
            max_response_bytes: 响应最大字节数（默认 2 MiB）
            max_retries: 网络错误最大重试次数（默认 0）

        Raises:
            ProviderError: 当必需参数缺失时抛出 "embedding_provider_not_configured"

        Note:
            dimensions 字段在首次调用 embed() 时自动检测并缓存。
        """
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
        """返回 Provider 的能力描述。

        Returns:
            包含以下字段的字典：
            - status: 总是 "configured"
            - configured: 总是 True
            - runtime_kind: "openai_compatible"
            - verification_status: "unverified"（未实际调用 API）
            - network_required: True（需要网络连接）
            - provider_id, model_id, model_revision: 配置参数
            - encoding: 文本编码方式（总是 "utf-8"）
            - supports: {"embeddings": True, "batch": True}
        """
        return {"status": "configured", "configured": True, "runtime_kind": "openai_compatible",
                "verification_status": "unverified", "network_required": True,
                "provider_id": self.provider_id, "model_id": self.model_id,
                "model_revision": self.model_revision, "encoding": self.encoding,
                "supports": {"embeddings": True, "batch": True}}

    def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为向量表示。

        Args:
            texts: 待向量化的文本列表（每条文本会自动 strip）

        Returns:
            浮点向量列表，顺序与输入 texts 对应，每个向量维度为 self.dimensions。

        Raises:
            EmbeddingError:
                - "embedding_batch_too_large": texts 为空或超过 max_batch_size
                - "embedding_invalid_request": texts 包含空字符串或非字符串
                - "embedding_text_too_long": 某条文本超过 max_text_chars
                - "embedding_schema_mismatch": API 响应格式不匹配
                - "embedding_invalid_dimensions": 向量维度 < 1 或 > 65535
                - "embedding_provider_*": 网络、认证、限流等错误

        Side Effects:
            - 首次调用时自动检测并设置 self.dimensions
            - 网络错误时会根据 max_retries 自动重试

        Note:
            重试仅针对临时性错误（连接失败、服务不可用、超时、限流），
            认证失败、协议错误等不会重试。
        """
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
