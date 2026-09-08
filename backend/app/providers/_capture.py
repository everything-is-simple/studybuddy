"""语音/图像转录 Provider。

本模块提供三种转录 Provider：
1. DeterministicFakeCaptureProvider - 确定性假 Provider，用于测试
2. LoopbackCaptureProvider - 本地回环 Provider，无网络 I/O
3. WhisperCliCaptureProvider - Whisper.cpp CLI 适配器，本地语音识别

支持的资产类型：
- audio: 音频文件 (通过 Whisper)
- image: 图像文件 (通过 OCR，见 _ocr.py)

Provider 选择：
- 测试环境: 使用 fake 或 loopback
- 生产环境: 使用 whisper-cpp (需要显式配置可执行文件和模型路径)

依赖项：
- whisper.cpp: 本地 Whisper 运行时 (https://github.com/ggerganov/whisper.cpp)
- 模型文件: ggml-*.bin 格式的量化模型
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


from ._core import (
    CaptureProviderError,
    CaptureTranscriptionProvider,
    CaptureTranscriptionRequest,
    CaptureTranscriptionResult,
)


class DeterministicFakeCaptureProvider:
    """确定性假转录 Provider。
    
    用途：
        - 单元测试和集成测试
        - 演示模式
        - 不依赖外部模型的开发环境
    
    行为：
        - 根据输入内容的 SHA256 哈希生成确定性输出
        - 总是返回固定格式的两段文本
        - 不执行真实的 OCR 或 ASR
        - 第一段置信度 0.94，第二段 0.62
    
    注意：
        这不是精度声明，仅用于可重复的测试场景。
    """

    provider_id = "fake"
    model_id = "fake-capture-v1"

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind not in {"audio", "image"} or not request.content:
            raise CaptureProviderError("transcription_failed")
        digest = hashlib.sha256(request.content).hexdigest()
        label = "audio" if request.asset_kind == "audio" else "image"
        return CaptureTranscriptionResult(
            language="en",
            segments=[
                {"text": f"Deterministic {label} capture {digest[:12]}", "confidence": 0.94},
                {"text": f"Review marker {digest[12:20]}", "confidence": 0.62},
            ],
        )


class LoopbackCaptureProvider(DeterministicFakeCaptureProvider):
    """本地回环转录 Provider。
    
    特性：
        - 继承 DeterministicFakeCaptureProvider 的所有行为
        - 明确标识为 loopback 而非 fake
        - 零网络 I/O
    
    用途：
        - 离线开发环境
        - 网络隔离测试
        - 快速原型验证
    """

    provider_id = "loopback"
    model_id = "loopback-capture-v1"


class WhisperCliCaptureProvider:
    """Whisper.cpp CLI 适配器。
    
    要求：
        - 显式配置的 whisper.cpp 可执行文件路径
        - 显式配置的 ggml 模型文件路径
        - 本地文件系统访问权限
    
    支持的模型：
        - ggml-large-v3-turbo (默认)
        - ggml-base, ggml-small, ggml-medium, ggml-large 等
    
    输出格式：
        - 纯文本 (.txt): 完整转录文本
        - SRT 字幕 (.srt): 带时间戳的分段文本
    
    限制：
        - 仅支持音频 (asset_kind='audio')
        - 仅支持 WAV 格式输入
        - 超时后会抛出 provider_timeout
    
    安全：
        - 不下载模型（需要预先配置）
        - 不发送数据到网络
        - 使用临时目录处理，完成后清理
    """

    provider_id = "whisper-cpp"

    def __init__(self, executable: Path | str, model_path: Path | str, *,
                 model_id: str = "ggml-large-v3-turbo", timeout_seconds: float = 120.0,
                 max_output_bytes: int = 262144) -> None:
        self.executable = Path(executable)
        self.model_path = Path(model_path)
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind != "audio" or not request.content:
            raise CaptureProviderError("transcription_failed")
        if not self.executable.is_file() or not self.model_path.is_file():
            raise CaptureProviderError("provider_unavailable")
        if self.timeout_seconds <= 0 or self.max_output_bytes < 1:
            raise CaptureProviderError("transcription_failed")
        temporary_root = Path(tempfile.mkdtemp(prefix="studybuddy-asr-"))
        try:
            input_path = temporary_root / "input.wav"
            input_path.write_bytes(request.content)
            command = [str(self.executable), "-f", str(input_path), "-m", str(self.model_path),
                       "--language", "en", "-otxt", "-osrt", "-nc"]
            try:
                subprocess.run(command, cwd=temporary_root, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=self.timeout_seconds, check=False)
            except subprocess.TimeoutExpired:
                raise CaptureProviderError("provider_timeout") from None
            output_files = [*temporary_root.glob("*.txt"), *temporary_root.glob("*.srt")]
            if sum(path.stat().st_size for path in output_files if path.is_file()) > self.max_output_bytes:
                raise CaptureProviderError("payload_too_large")
            txt_path = temporary_root / "input.txt"
            srt_path = temporary_root / "input.srt"
            text = txt_path.read_text(encoding="utf-8", errors="replace").strip() if txt_path.is_file() else ""
            segments = _parse_srt(srt_path.read_text(encoding="utf-8", errors="replace")) if srt_path.is_file() else []
            if not segments and text:
                segments = [{"text": line.strip(), "confidence": None} for line in text.splitlines() if line.strip()]
            if not segments:
                raise CaptureProviderError("transcript_empty_or_invalid")
            return CaptureTranscriptionResult(segments=segments, language="en")
        except OSError:
            raise CaptureProviderError("provider_unavailable") from None
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)


def _parse_srt(value: str) -> list[dict[str, object]]:
    """解析 SRT 字幕格式。
    
    SRT 格式：
        1
        00:00:00,000 --> 00:00:02,500
        First subtitle text
        
        2
        00:00:02,500 --> 00:00:05,000
        Second subtitle text
    
    Args:
        value: SRT 格式的字幕文本
    
    Returns:
        包含以下字段的字典列表：
        - text: 字幕文本
        - start: 开始时间戳
        - end: 结束时间戳
        - confidence: 固定为 0.95
    """
    segments: list[dict[str, object]] = []
    for block in value.replace("\r\n", "\n").split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = (part.strip() for part in lines[1].split("-->", 1))
        text = " ".join(lines[2:]).strip()
        if text:
            segments.append({"text": text, "start": start, "end": end, "confidence": 0.95})
    return segments


# Short aliases keep the capture surface discoverable for later provider gates.
FakeCaptureProvider = DeterministicFakeCaptureProvider
