"""Provider 实现模块 - LLM、Embedding 和转录服务。

本模块是 StudyBuddy 的 AI Provider 层入口，提供统一的接口访问各种 AI 服务：

**核心 Provider 类型**：
1. LLM Provider: 大语言模型（问答、卡片生成、练习生成）
   - OpenAICompatibleLLMProvider: OpenAI/DeepSeek/兼容接口
   - FakeLLMProvider: 测试用假 Provider

2. Embedding Provider: 文本向量化（语义检索）
   - OpenAICompatibleEmbeddingProvider: OpenAI Embedding API

3. Capture Provider: 语音/图像转录（OCR/ASR）
   - PaddleImageOcrProvider: PaddleOCR 图像文字识别
   - WhisperCliCaptureProvider: Faster-Whisper 语音转录
   - FakeCaptureProvider: 测试用假转录
   - LoopbackCaptureProvider: 回环测试
   - DeterministicFakeCaptureProvider: 确定性假转录

**注册与工厂**：
- ProviderRegistry: LLM Provider 注册表
- EmbeddingProviderRegistry: Embedding Provider 注册表
- provider_registry(): 工厂函数，根据配置实例化 Provider

**使用示例**：
```python
from app.providers import provider_registry, ProviderRequest

# 获取 LLM Provider 实例
provider = provider_registry(
    provider_id='openai',
    api_key='sk-...',
    model='gpt-4o-mini'
)

# 生成答案
request = ProviderRequest(
    question='什么是机器学习？',
    context_blocks=[...],
    max_output_tokens=500
)
result = provider.generate_answer(request)
print(result.answer_text)
```

**模块初始化**：
- 自动初始化 SSL 上下文（修复 Windows 证书存储问题）
- 导出所有公共类型、常量和实现

关联模块：
- api.ai_retrieval_qa: 使用 LLM Provider 生成答案
- repositories.ai: 使用 Embedding Provider 存储向量
- api.study_capture_reports: 使用 Capture Provider 转录
"""

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
