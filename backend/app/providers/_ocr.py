"""PaddleOCR 和 RapidOCR 图像文字识别 Provider。

本模块提供本地离线的 OCR（光学字符识别）能力，支持中文图像文字提取。
实现了三个 Provider：

1. **PaddleImageOcrProvider** - 主要 OCR 引擎
   - 使用 PaddlePaddle 的 PP-OCRv5 模型
   - 需要预先下载模型文件到本地
   - 精度高，但初始化较慢

2. **RapidImageOcrProvider** - 快速备用引擎
   - 使用 RapidOCR（基于 ONNX 推理）
   - 模型更小，初始化更快
   - 精度略低于 PaddleOCR

3. **OcrFallbackProvider** - 降级策略包装器
   - 优先使用 PaddleOCR
   - 失败时自动降级到 RapidOCR
   - 记录降级原因用于诊断

支持的图像格式：
- image/png
- image/jpeg
- image/webp

性能限制：
- 单图最大 50 MiB
- 分辨率最大 12,000,000 像素（约 4000×3000）
- OCR 结果最大 524 KiB（防止超长文本 OOM）

关联模块：
- _core: CaptureProvider 协议定义
- api.study_capture_reports: OCR API 调用方

Note:
    所有 Provider 都是本地离线运行，不发起网络请求。
    模型文件需要手动下载到 model_root 目录。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from ._core import CaptureProviderError, CaptureTranscriptionRequest, CaptureTranscriptionResult, ImageOcrRequest

PADDLE_PROVIDER_ID = "paddleocr"
PADDLE_MODEL_ID = "PP-OCRv5_server_det+PP-OCRv5_server_rec"
PADDLE_OCR_VERSION = "3.7.0"
PADDLEPADDLE_VERSION = "3.3.1"
PADDLE_UNCERTAIN_THRESHOLD = 0.85
MAX_OCR_PIXELS = 12_000_000
SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class RapidImageOcrProvider:
    """离线 RapidOCR ONNX Provider（备用方案）。

    使用 RapidOCR（基于 ONNX Runtime）进行图像文字识别。
    作为 PaddleOCR 的备用引擎，初始化更快但精度略低。

    Attributes:
        provider_id: "rapidocr"
        model_id: "ch_PP-OCRv4_det_infer+ch_PP-OCRv4_rec_infer"
        model_root: 模型文件根目录（可选）
        timeout_seconds: 识别超时时间（秒）
        max_output_bytes: 输出结果最大字节数
    """

    provider_id = "rapidocr"
    model_id = "ch_PP-OCRv4_det_infer+ch_PP-OCRv4_rec_infer"

    def __init__(self, model_root: Path | str | None = None, *, timeout_seconds: float = 120.0,
                 max_output_bytes: int = 524288) -> None:
        self.model_root = Path(model_root) if model_root else None
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        if timeout_seconds <= 0 or max_output_bytes < 1:
            raise CaptureProviderError("transcription_provider_not_configured")

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind != "image":
            raise CaptureProviderError("capture_asset_type_not_supported")
        return self.recognize(ImageOcrRequest(request.media_type, request.content_sha256, request.content))

    def recognize(self, request: ImageOcrRequest) -> CaptureTranscriptionResult:
        if request.media_type not in SUPPORTED_IMAGE_TYPES or not request.content:
            raise CaptureProviderError("capture_asset_type_not_supported")
        if len(request.content) > 50 * 1024 * 1024:
            raise CaptureProviderError("capture_asset_too_large")
        if hashlib.sha256(request.content).hexdigest() != request.content_sha256:
            raise CaptureProviderError("transcription_failed")
        temporary_root = Path(tempfile.mkdtemp(prefix="studybuddy-rapidocr-"))
        try:
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[request.media_type]
            input_path = temporary_root / f"input{suffix}"
            input_path.write_bytes(request.content)
            PaddleImageOcrProvider._validate_image(input_path)
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            result, _ = engine(str(input_path))
            segments: list[dict[str, object]] = []
            for item in result or []:
                if len(item) < 3:
                    continue
                text = str(item[1]).strip()
                if not text:
                    continue
                confidence = max(0.0, min(1.0, float(item[2])))
                segments.append({"text": text, "confidence": confidence,
                                 "quality": "clear" if confidence >= PADDLE_UNCERTAIN_THRESHOLD else "uncertain"})
            if not segments:
                raise CaptureProviderError("transcript_empty_or_invalid")
            if len(json.dumps(segments, ensure_ascii=False).encode("utf-8")) > self.max_output_bytes:
                raise CaptureProviderError("payload_too_large")
            return CaptureTranscriptionResult(segments=segments, language="ch")
        except CaptureProviderError:
            raise
        except TimeoutError:
            raise CaptureProviderError("provider_timeout") from None
        except Exception:
            raise CaptureProviderError("transcription_failed") from None
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)


class OcrFallbackProvider:
    """PaddleOCR + RapidOCR 降级策略包装器。

    优先使用 PaddleOCR（精度高），失败时自动降级到 RapidOCR（速度快）。
    仅在明确允许的错误场景下降级，其他错误直接上抛。

    允许降级的错误：
    - transcription_provider_not_configured: 主引擎未配置
    - provider_unavailable: 主引擎不可用
    - provider_timeout: 主引擎超时
    - transcript_empty_or_invalid: 主引擎返回空结果
    - transcription_failed: 主引擎识别失败

    Attributes:
        provider_id: "ocr-fallback"
        model_id: "paddleocr+rapidocr"
        primary: 主 OCR Provider（通常是 PaddleOCR）
        fallback: 备用 OCR Provider（通常是 RapidOCR）
        last_fallback_reason: 最近一次降级原因
        last_primary_error: 最近一次主引擎错误码
    """

    provider_id = "ocr-fallback"
    model_id = "paddleocr+rapidocr"

    _FALLBACK_ERRORS = {
        "transcription_provider_not_configured", "provider_unavailable", "provider_timeout",
        "transcript_empty_or_invalid", "transcription_failed",
    }

    def __init__(self, primary: ImageOcrProvider, fallback: ImageOcrProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_fallback_reason: str | None = None
        self.last_primary_error: str | None = None

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind != "image":
            raise CaptureProviderError("capture_asset_type_not_supported")
        try:
            result = self.primary.transcribe(request)
            self.last_fallback_reason = None
            self.last_primary_error = None
            return result
        except CaptureProviderError as error:
            if error.code not in self._FALLBACK_ERRORS:
                raise
            self.last_primary_error = error.code
            self.last_fallback_reason = {
                "transcription_provider_not_configured": "primary_unavailable",
                "provider_unavailable": "primary_unavailable",
                "provider_timeout": "primary_timeout",
                "transcript_empty_or_invalid": "primary_empty_result",
                "transcription_failed": "primary_failed",
            }[error.code]
        try:
            return self.fallback.transcribe(request)
        except CaptureProviderError as error:
            raise CaptureProviderError(
                "payload_too_large" if error.code == "payload_too_large" else
                "provider_timeout" if error.code == "provider_timeout" else "transcription_failed"
            ) from None


class PaddleImageOcrProvider:
    """PaddleOCR 本地离线 Provider（主引擎）。

    使用 PaddlePaddle 的 PP-OCRv5 Server 模型进行高精度 OCR。
    需要预先下载模型文件到本地目录，不自动下载模型。

    模型要求：
    - PP-OCRv5_server_det: 文本检测模型
    - PP-OCRv5_server_rec: 文本识别模型
    - 两者都需要放在 model_root 目录下

    依赖版本：
    - paddleocr==3.7.0
    - paddlepaddle==3.3.1

    Attributes:
        provider_id: "paddleocr"
        model_id: "PP-OCRv5_server_det+PP-OCRv5_server_rec"
        model_root: 模型文件根目录
        timeout_seconds: 识别超时时间（秒）
        max_output_bytes: 输出结果最大字节数

    Note:
        首次调用时懒加载 PaddleOCR 引擎（_ocr 字段）。
        初始化较慢（约 3-5 秒），但后续识别速度快。
    """

    provider_id = PADDLE_PROVIDER_ID
    model_id = PADDLE_MODEL_ID

    def __init__(self, model_root: Path | str, *, timeout_seconds: float = 120.0,
                 max_output_bytes: int = 524288) -> None:
        self.model_root = Path(model_root)
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self._ocr = None
        if timeout_seconds <= 0 or max_output_bytes < 1:
            raise CaptureProviderError("transcription_provider_not_configured")
        if not self.model_root.is_dir():
            raise CaptureProviderError("transcription_provider_not_configured")
        if not all((self.model_root / name).is_dir() for name in ("PP-OCRv5_server_det", "PP-OCRv5_server_rec")):
            raise CaptureProviderError("transcription_provider_not_configured")

    def transcribe(self, request: CaptureTranscriptionRequest) -> CaptureTranscriptionResult:
        if request.asset_kind != "image":
            raise CaptureProviderError("capture_asset_type_not_supported")
        return self.recognize(ImageOcrRequest(
            media_type=request.media_type, content_sha256=request.content_sha256, content=request.content
        ))

    def recognize(self, request: ImageOcrRequest) -> CaptureTranscriptionResult:
        if request.media_type not in SUPPORTED_IMAGE_TYPES or not request.content:
            raise CaptureProviderError("capture_asset_type_not_supported")
        if len(request.content) > 50 * 1024 * 1024:
            raise CaptureProviderError("capture_asset_too_large")
        if hashlib.sha256(request.content).hexdigest() != request.content_sha256:
            raise CaptureProviderError("transcription_failed")
        temporary_root = Path(tempfile.mkdtemp(prefix="studybuddy-ocr-"))
        try:
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[request.media_type]
            input_path = temporary_root / f"input{suffix}"
            input_path.write_bytes(request.content)
            self._validate_image(input_path)
            result = self._load().predict(str(input_path))
            segments: list[dict[str, object]] = []
            for page in result or []:
                data = page.json if hasattr(page, "json") else page
                if isinstance(data, str):
                    data = json.loads(data)
                values = data.get("res", {})
                texts = values.get("rec_texts", [])
                scores = values.get("rec_scores", [])
                for ordinal, value in enumerate(texts):
                    text = str(value).strip()
                    if not text:
                        continue
                    confidence = float(scores[ordinal]) if ordinal < len(scores) else 0.0
                    confidence = max(0.0, min(1.0, confidence))
                    segments.append({"text": text, "confidence": confidence,
                                     "quality": "clear" if confidence >= PADDLE_UNCERTAIN_THRESHOLD else "uncertain"})
            if not segments:
                raise CaptureProviderError("transcript_empty_or_invalid")
            if len(json.dumps(segments, ensure_ascii=False).encode("utf-8")) > self.max_output_bytes:
                raise CaptureProviderError("payload_too_large")
            return CaptureTranscriptionResult(segments=segments, language="ch")
        except CaptureProviderError:
            raise
        except TimeoutError:
            raise CaptureProviderError("provider_timeout") from None
        except Exception:
            raise CaptureProviderError("transcription_failed") from None
        finally:
            import shutil
            shutil.rmtree(temporary_root, ignore_errors=True)

    def _load(self):
        if self._ocr is None:
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                device="cpu", enable_mkldnn=False, lang="ch",
                use_doc_orientation_classify=False, use_doc_unwarping=False,
                use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                text_detection_model_dir=str(self.model_root / "PP-OCRv5_server_det"),
                text_recognition_model_dir=str(self.model_root / "PP-OCRv5_server_rec"),
            )
        return self._ocr

    @staticmethod
    def _validate_image(path: Path) -> None:
        from PIL import Image
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.width * image.height > MAX_OCR_PIXELS:
                raise CaptureProviderError("capture_asset_too_large")
