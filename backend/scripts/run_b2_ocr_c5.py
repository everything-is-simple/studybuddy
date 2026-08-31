"""Explicit, redacted B2 C5 real-local PaddleOCR acceptance runner."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.providers import ImageOcrRequest, PaddleImageOcrProvider


def main() -> int:
    if os.environ.get("STUDYBUDDY_RUN_REAL_OCR_C5") != "1":
        print(json.dumps({"status": "not_run", "reason": "explicit_opt_in_required"}))
        return 0
    model_root = Path(os.environ.get("STUDYBUDDY_OCR_MODEL_ROOT", ""))
    fixture = Path(os.environ.get("STUDYBUDDY_OCR_FIXTURE", ""))
    if not model_root.is_dir() or not fixture.is_file():
        print(json.dumps({"status": "blocked", "reason": "local_model_or_fixture_missing"}))
        return 2
    content = fixture.read_bytes()
    try:
        provider = PaddleImageOcrProvider(
            model_root,
            timeout_seconds=float(os.environ.get("STUDYBUDDY_OCR_TIMEOUT_SECONDS", "120")),
            max_output_bytes=int(os.environ.get("STUDYBUDDY_OCR_MAX_OUTPUT_BYTES", "524288")),
        )
        result = provider.recognize(ImageOcrRequest(
            media_type=os.environ.get("STUDYBUDDY_OCR_FIXTURE_MIME", "image/png"),
            content_sha256=hashlib.sha256(content).hexdigest(), content=content,
        ))
    except Exception as error:
        code = getattr(error, "code", "ocr_c5_failed")
        print(json.dumps({"status": "failed", "error_code": str(code)}))
        return 1
    qualities = [str(segment.get("quality")) for segment in result.segments]
    confidences = [float(segment.get("confidence", 0)) for segment in result.segments]
    print(json.dumps({
        "status": "real_passed",
        "provider_id": provider.provider_id,
        "model_id": provider.model_id,
        "segment_count": len(result.segments),
        "uncertain_count": qualities.count("uncertain"),
        "confidence_range": [min(confidences), max(confidences)] if confidences else None,
        "input_sha256_prefix": hashlib.sha256(content).hexdigest()[:12],
        "environment": "Windows/Python3.10/CPU/local-model",
        "not_verified": ["general_accuracy", "all_formats", "multilingual", "tables", "concurrency"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
