"""P2-USE-4 regression: the transcription endpoint must honor the configured
timeout budget.

Defect found while running the real chain: the endpoint built the provider with
`config.ocr_timeout_seconds` / `config.asr_timeout_seconds` but did not pass a
budget to `transcribe_capture_session`, so the repository default of 30 seconds
silently overrode it. A cold local PaddleOCR model load takes longer than that,
so real OCR always returned 504 provider_timeout even though the provider had a
120 second budget and the recognition itself succeeded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app.api.study_capture_reports as capture_routes
from app.config import AppConfig
from app.main import create_app
from app.repository import connect

PROJECT_ID = "default"
NOW = "2026-01-15T08:00:00+00:00"
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6360000002000154a24f7d0000000049454e44ae426082"
)
WAV = b"RIFF" + (20).to_bytes(4, "little") + b"WAVE" + b"studybuddy-capture"


def _config(tmp_path: Path, **overrides: object) -> AppConfig:
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    with connect(root / "studybuddy.sqlite3") as connection:
        connection.execute("INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
                           (PROJECT_ID, "timeout project", NOW))
    return AppConfig(data_root=root, project_id=PROJECT_ID, **overrides)


def _ready_capture(client: TestClient, *, kind: str) -> str:
    audio = kind == "audio"
    created = client.post("/api/study/capture-sessions", json={
        "asset_kind": kind,
        "original_name": "lesson.wav" if audio else "board.png",
        "media_type": "audio/wav" if audio else "image/png",
    })
    assert created.status_code == 201, created.text
    capture_id = str(created.json()["id"])
    uploaded = client.post(
        f"/api/study/capture-sessions/{capture_id}/upload",
        files={"file": ("lesson.wav" if audio else "board.png",
                        WAV if audio else PNG,
                        "audio/wav" if audio else "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    return capture_id


@pytest.fixture()
def recorder(monkeypatch: pytest.MonkeyPatch):
    """Capture the keyword arguments the endpoint hands to the repository.

    The patch has to be installed after `create_app`, because route registration
    injects the real repository function into the route module globals.
    """
    seen: dict[str, object] = {}

    def _record(_connection: object, **kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {"operation": {"status": "succeeded"}, "draft": {"id": "draft_stub"},
                "replay": False}

    def _install() -> dict[str, object]:
        monkeypatch.setattr(capture_routes, "transcribe_capture_session", _record)
        return seen

    return _install


def test_audio_transcription_uses_the_configured_asr_budget(tmp_path: Path, recorder) -> None:
    config = _config(tmp_path, asr_provider_id="whisper-cpp", asr_model_id="ggml-large-v3-turbo",
                     asr_runtime_path=tmp_path / "main.exe", asr_model_path=tmp_path / "model.bin",
                     asr_timeout_seconds=180.0)
    (tmp_path / "main.exe").write_bytes(b"stub")
    (tmp_path / "model.bin").write_bytes(b"stub")
    application = create_app(config)
    seen = recorder()
    with TestClient(application) as client:
        capture_id = _ready_capture(client, kind="audio")
        response = client.post(f"/api/study/capture-sessions/{capture_id}/transcribe")

    assert response.status_code == 200, response.text
    assert seen["timeout_seconds"] == 180.0


def test_image_transcription_uses_the_configured_ocr_budget(tmp_path: Path, recorder) -> None:
    model_root = tmp_path / "models"
    for name in ("PP-OCRv5_server_det", "PP-OCRv5_server_rec"):
        (model_root / name).mkdir(parents=True)
    config = _config(tmp_path, ocr_enabled=True, ocr_provider_id="paddleocr",
                     ocr_model_root=model_root, ocr_timeout_seconds=240.0)
    application = create_app(config)
    seen = recorder()
    with TestClient(application) as client:
        capture_id = _ready_capture(client, kind="image")
        response = client.post(f"/api/study/capture-sessions/{capture_id}/transcribe")

    assert response.status_code == 200, response.text
    # Previously this silently used 30.0, shorter than a cold local model load.
    assert seen["timeout_seconds"] == 240.0


def test_budget_is_not_the_repository_default_when_configuration_raises_it(
        tmp_path: Path, recorder) -> None:
    config = _config(tmp_path, asr_provider_id="whisper-cpp", asr_model_id="ggml-large-v3-turbo",
                     asr_runtime_path=tmp_path / "main.exe", asr_model_path=tmp_path / "model.bin")
    (tmp_path / "main.exe").write_bytes(b"stub")
    (tmp_path / "model.bin").write_bytes(b"stub")
    application = create_app(config)
    seen = recorder()
    with TestClient(application) as client:
        capture_id = _ready_capture(client, kind="audio")
        client.post(f"/api/study/capture-sessions/{capture_id}/transcribe")

    assert seen["timeout_seconds"] == config.asr_timeout_seconds
    assert seen["timeout_seconds"] > 30.0
