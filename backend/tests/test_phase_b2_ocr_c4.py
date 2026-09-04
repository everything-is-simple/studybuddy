from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.providers._ocr as ocr_module
from app.config import AppConfig, config_from_environment
from app.providers import CaptureProviderError, ImageOcrRequest, PaddleImageOcrProvider, provider_registry
from app.main import create_app
from app.repository import connect
from fastapi.testclient import TestClient


class _Page:
    def __init__(self, values: list[str], scores: list[float]) -> None:
        self.json = json.dumps({"res": {"rec_texts": values, "rec_scores": scores}})


def _provider(tmp_path: Path) -> PaddleImageOcrProvider:
    (tmp_path / "PP-OCRv5_server_det").mkdir()
    (tmp_path / "PP-OCRv5_server_rec").mkdir()
    return PaddleImageOcrProvider(tmp_path)


def _request(content: bytes, media_type: str = "image/png") -> ImageOcrRequest:
    return ImageOcrRequest(media_type, hashlib.sha256(content).hexdigest(), content)


def _install_fake_paddle(monkeypatch: pytest.MonkeyPatch, pages: list[_Page]) -> None:
    class FakeOCR:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["device"] == "cpu"
            assert kwargs["enable_mkldnn"] is False
            assert kwargs["text_detection_model_name"] == "PP-OCRv5_server_det"
            assert kwargs["text_recognition_model_name"] == "PP-OCRv5_server_rec"
            assert Path(str(kwargs["text_detection_model_dir"])).is_dir()
            assert Path(str(kwargs["text_recognition_model_dir"])).is_dir()

        def predict(self, image_path: str) -> list[_Page]:
            assert Path(image_path).is_file()
            return pages

    monkeypatch.setitem(sys.modules, "paddleocr", types.SimpleNamespace(PaddleOCR=FakeOCR))


def test_paddle_provider_maps_confidence_and_uncertain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content_path = tmp_path / "fixture.png"
    Image.new("RGB", (80, 40), "white").save(content_path)
    content = content_path.read_bytes()
    _install_fake_paddle(monkeypatch, [_Page(["清晰文本", "待核对"], [0.95, 0.84])])

    result = _provider(tmp_path).recognize(_request(content))

    assert result.language == "ch"
    assert result.segments == [
        {"text": "清晰文本", "confidence": 0.95, "quality": "clear"},
        {"text": "待核对", "confidence": 0.84, "quality": "uncertain"},
    ]


def test_paddle_provider_rejects_bad_input_and_missing_models(tmp_path: Path):
    content = b"not-an-image"
    with pytest.raises(CaptureProviderError, match="transcription_provider_not_configured"):
        PaddleImageOcrProvider(tmp_path / "missing")
    provider = _provider(tmp_path)
    with pytest.raises(CaptureProviderError, match="capture_asset_type_not_supported"):
        provider.recognize(_request(content, "image/gif"))
    with pytest.raises(CaptureProviderError, match="transcription_failed"):
        provider.recognize(ImageOcrRequest("image/png", "0" * 64, content))


def test_registry_keeps_ocr_opt_in_and_capability_safe(tmp_path: Path):
    disabled = AppConfig(data_root=tmp_path)
    assert disabled.ocr_enabled is False
    with pytest.raises(Exception):
        provider_registry("paddleocr", "wrong").capture_provider(ocr_model_root=str(tmp_path))
    with pytest.raises(CaptureProviderError, match="transcription_provider_not_configured"):
        PaddleImageOcrProvider(tmp_path, timeout_seconds=0)


def test_paddle_provider_enforces_output_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    content_path = tmp_path / "fixture.png"
    Image.new("RGB", (80, 40), "white").save(content_path)
    content = content_path.read_bytes()
    (tmp_path / "PP-OCRv5_server_det").mkdir()
    (tmp_path / "PP-OCRv5_server_rec").mkdir()
    _install_fake_paddle(monkeypatch, [_Page(["long text"], [0.95])])
    with pytest.raises(CaptureProviderError, match="payload_too_large"):
        PaddleImageOcrProvider(tmp_path, max_output_bytes=1).recognize(_request(content))


def test_p1_6_2_accepts_png_jpeg_and_webp_after_real_image_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    provider = _provider(tmp_path)
    _install_fake_paddle(monkeypatch, [_Page(["decoded text"], [0.95])])
    for media_type, suffix in (("image/png", "png"), ("image/jpeg", "jpg"), ("image/webp", "webp")):
        content_path = tmp_path / f"fixture.{suffix}"
        Image.new("RGB", (80, 40), "white").save(content_path, format="JPEG" if suffix == "jpg" else suffix.upper())
        result = provider.recognize(_request(content_path.read_bytes(), media_type))
        assert result.segments[0]["text"] == "decoded text"
        assert result.language == "ch"


def test_p1_6_2_rejects_empty_and_corrupt_supported_images(tmp_path: Path):
    provider = _provider(tmp_path)
    for content in (b"", b"not-a-real-image"):
        with pytest.raises(CaptureProviderError) as error:
            provider.recognize(_request(content, "image/png"))
        assert error.value.code in {"capture_asset_type_not_supported", "transcription_failed"}


def test_p1_6_2_pixel_and_byte_limits_fail_before_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    provider = _provider(tmp_path)
    content_path = tmp_path / "large.png"
    Image.new("RGB", (80, 40), "white").save(content_path)
    content = content_path.read_bytes()
    monkeypatch.setattr(ocr_module, "MAX_OCR_PIXELS", 10)
    _install_fake_paddle(monkeypatch, [_Page(["must not run"], [0.95])])
    with pytest.raises(CaptureProviderError, match="capture_asset_too_large"):
        provider.recognize(_request(content))

    oversized = b"x" * (50 * 1024 * 1024 + 1)
    with pytest.raises(CaptureProviderError, match="capture_asset_too_large"):
        provider.recognize(_request(oversized))


def test_p1_6_2_timeout_cleans_temp_root_and_maps_stable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    provider = _provider(tmp_path,)
    content_path = tmp_path / "fixture.png"
    Image.new("RGB", (80, 40), "white").save(content_path)
    temp_root = tmp_path / "controlled-ocr-temp"

    def make_temp_root(*_args: object, **_kwargs: object) -> str:
        temp_root.mkdir()
        return str(temp_root)

    class TimeoutOCR:
        def predict(self, _image_path: str) -> list[object]:
            raise TimeoutError("bounded timeout")

    monkeypatch.setattr(ocr_module.tempfile, "mkdtemp", make_temp_root)
    monkeypatch.setattr(provider, "_load", lambda: TimeoutOCR())
    with pytest.raises(CaptureProviderError, match="provider_timeout"):
        provider.recognize(_request(content_path.read_bytes()))
    assert not temp_root.exists()


def test_image_api_does_not_fallback_when_ocr_is_disabled(tmp_path: Path):
    root = tmp_path / "data"
    root.mkdir()
    with connect(root / "studybuddy.sqlite3") as connection:
        connection.execute("INSERT INTO projects (id,name,created_at) VALUES (?,?,?)", ("p", "P", "2026-01-01"))
    with TestClient(create_app(AppConfig(data_root=root, project_id="p"))) as client:
        created = client.post("/api/study/capture-sessions", json={
            "asset_kind": "image", "original_name": "slide.png", "media_type": "image/png"})
        assert created.status_code == 201
        response = client.post(f"/api/study/capture-sessions/{created.json()['id']}/transcribe")
        assert response.status_code == 503
        assert response.json()["detail"] == "transcription_provider_not_configured"


def test_environment_ocr_gate_is_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("STUDYBUDDY_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("STUDYBUDDY_OCR_ENABLED", raising=False)
    assert config_from_environment().ocr_enabled is False
    monkeypatch.setenv("STUDYBUDDY_OCR_ENABLED", "true")
    monkeypatch.setenv("STUDYBUDDY_OCR_PROVIDER", "paddleocr")
    monkeypatch.setenv("STUDYBUDDY_OCR_MODEL_ROOT", str(tmp_path))
    config = config_from_environment()
    assert config.ocr_enabled is True
    assert config.ocr_provider_id == "paddleocr"
    assert config.ocr_model_root == tmp_path
