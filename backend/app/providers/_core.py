"""Provider 核心类型、协议和常量定义。

本模块定义了 StudyBuddy 的 AI Provider 抽象层，包括：

1. **LLM Provider**：用于问答生成、卡片生成、练习生成
   - ProviderRequest/ProviderResult：请求和响应数据结构
   - LLMProvider Protocol：LLM 提供商接口

2. **OCR Provider**：用于图像文字识别
   - ImageOcrRequest：OCR 请求
   - ImageOcrProvider Protocol：OCR 提供商接口

3. **Capture Provider**：用于音视频转录（ASR）
   - CaptureTranscriptionRequest/Result：转录请求和结果
   - CaptureTranscriptionProvider Protocol：转录提供商接口

所有 Provider 都遵循统一的协议设计：
- 不依赖具体实现（OpenAI/PaddleOCR/Faster-Whisper）
- 支持 fake provider 用于测试
- 原始数据（bytes）不跨越持久化边界

常量：
- PROVIDER_NOT_CONFIGURED: 未配置错误码
- FAKE_PROVIDER_ID/MODEL_ID: 测试用假 provider
- MAX_PROVIDER_PROMPT_CHARS: 单次请求最大字符数（8000）
- MAX_PROVIDER_RESPONSE_BYTES: 单次响应最大字节数（2MB）

关联模块：
- providers._registry: Provider 注册中心
- providers._openai_llm: OpenAI LLM 实现
- providers._ocr: PaddleOCR 实现
- providers._capture: Faster-Whisper 实现
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

PROVIDER_NOT_CONFIGURED = "provider_not_configured"
FAKE_PROVIDER_ID = "fake"
FAKE_MODEL_ID = "fake-studybuddy-v1"
MAX_PROVIDER_PROMPT_CHARS = 8000
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


class ProviderError(Exception):
    """LLM Provider 通用错误。
    
    Attributes:
        code: 错误代码（如 'provider_not_configured', 'rate_limit_exceeded'）
    """
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderRequest:
    """LLM Provider 请求参数。
    
    Attributes:
        question: 用户问题或生成指令
        context_blocks: 检索到的上下文块列表（每个块包含 text, citation_key 等）
        max_output_tokens: 最大生成 token 数（默认 800）
        max_prompt_chars: 最大 prompt 字符数（默认 30000）
        max_answer_chars: 最大答案字符数（默认 12000）
        generation_kind: 生成类型（'qa', 'card', 'exercise'）
        generation_count: 生成数量（如生成 5 道练习题）
        exercise_type: 练习题类型（'choice', 'blank', 'essay'）
    """
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
    """LLM Provider 响应结果。
    
    Attributes:
        answer_text: 生成的答案或内容
        citation_keys: 引用的上下文块 key 列表
        provider_id: Provider 标识（如 'openai'）
        model_id: 模型标识（如 'gpt-4o-mini'）
        prompt_tokens: prompt token 数
        completion_tokens: 生成 token 数
        provider_request_id: Provider 端请求 ID（用于追踪）
        total_tokens: 总 token 数
        latency_ms: 请求延迟（毫秒）
        finish_reason: 完成原因（'stop', 'length', 'content_filter'）
    """
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
    """LLM Provider 协议（鸭子类型接口）。
    
    任何实现此协议的类都可以作为 LLM Provider 使用。
    
    Attributes:
        provider_id: Provider 标识
        model_id: 模型标识
    
    Methods:
        generate_answer: 根据请求生成答案
    """
    provider_id: str
    model_id: str

    def generate_answer(self, request: ProviderRequest) -> ProviderResult:
        ...


@dataclass(frozen=True)
class CaptureTranscriptionRequest:
    """音视频转录请求（内存输入，原始字节不跨越持久化边界）。
    
    Attributes:
        asset_kind: 资产类型（'audio', 'video'）
        media_type: MIME 类型（如 'audio/wav', 'video/mp4'）
        content_sha256: 内容 SHA256 哈希（用于去重和追踪）
        content: 原始二进制内容（音视频字节）
    
    注意：
        原始字节仅在内存中传递，不会存入数据库。
        转录结果（segments）才会持久化到 captures 表。
    """
    asset_kind: str
    media_type: str
    content_sha256: str
    content: bytes


@dataclass(frozen=True)
class CaptureTranscriptionResult:
    """转录结果。
    
    Attributes:
        segments: 转录片段列表，每个片段包含：
                  - text: 转录文本
                  - start: 开始时间（秒）
                  - end: 结束时间（秒）
                  - confidence: 置信度（可选）
        language: 检测到的语言代码（如 'zh', 'en'）
    """
    segments: list[dict[str, object]]
    language: str | None = None


class CaptureProviderError(Exception):
    """转录 Provider 错误。
    
    Attributes:
        code: 错误代码（如 'unsupported_format', 'transcription_failed'）
    """
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class CaptureTranscriptionProvider(Protocol):
    """转录 Provider 协议（音视频 ASR）。
    
    Attributes:
        provider_id: Provider 标识（如 'faster-whisper'）
        model_id: 模型标识（如 'base', 'large-v3'）
    
    Methods:
        transcribe: 转录音视频
    """
    provider_id: str
    model_id: str

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        ...


@dataclass(frozen=True)
class ImageOcrRequest:
    """图像 OCR 请求（内存输入，原始字节不跨越持久化边界）。
    
    Attributes:
        media_type: MIME 类型（如 'image/png', 'image/jpeg'）
        content_sha256: 内容 SHA256 哈希
        content: 原始图像字节
    
    注意：
        原始字节仅在内存中传递，OCR 结果（segments）才会持久化。
    """
    media_type: str
    content_sha256: str
    content: bytes


class ImageOcrProvider(Protocol):
    """图像 OCR Provider 协议。
    
    Attributes:
        provider_id: Provider 标识（如 'paddleocr'）
        model_id: 模型标识（如 'ch_PP-OCRv4'）
    
    Methods:
        recognize: 识别图像中的文字
    
    注意：
        返回值复用 CaptureTranscriptionResult，因为两者结构相同（segments + language）。
    """
    provider_id: str
    model_id: str

    def recognize(self, request: ImageOcrRequest) -> CaptureTranscriptionResult:
        ...
