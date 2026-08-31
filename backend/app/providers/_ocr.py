"""Explicit local PaddleOCR adapter for the B2 Formal scope."""
from __future__ import annotations

import hashlib
import json
import os
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


class PaddleImageOcrProvider:
    """Offline, explicitly configured PaddleOCR provider; no model downloads."""

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
            input_path = temporary_root / "input.image"
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
