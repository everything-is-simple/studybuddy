from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.providers._capture as capture_module
from app.providers import (
    CaptureProviderError,
    CaptureTranscriptionRequest,
    WhisperCliCaptureProvider,
    provider_registry,
)
from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.repository import connect, create_capture_session, get_capture_session, transcribe_capture_session, upload_capture_asset
from app.restore_acceptance import verify_restored_data

REAL_ASR_SMOKE = os.environ.get("STUDYBUDDY_RUN_REAL_ASR_SMOKE") == "1"
REAL_ASR_RUNTIME = Path(os.environ.get("STUDYBUDDY_ASR_RUNTIME", "H:/Whisper/cli/main.exe"))
REAL_ASR_MODEL = Path(os.environ.get("STUDYBUDDY_ASR_MODEL_PATH", "H:/Whisper/Models/ggml-large-v3-turbo.bin"))
REAL_ASR_FIXTURE = Path(os.environ.get("STUDYBUDDY_ASR_FIXTURE", "H:/Whisper/Whisper-1.12.0/SampleClips/jfk.wav"))

PROJECT = "formal_asr"
WAV = b"RIFF" + (20).to_bytes(4, "little") + b"WAVE" + b"formal-asr"


def _runtime(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "main.exe"
    executable.write_bytes(b"runtime")
    model = tmp_path / "model.bin"
    model.write_bytes(b"model")
    return executable, model


def _request() -> CaptureTranscriptionRequest:
    return CaptureTranscriptionRequest(
        asset_kind="audio", media_type="audio/wav", content_sha256="a" * 64, content=WAV
    )


def test_whisper_cli_adapter_parses_outputs_and_removes_temporary_files(tmp_path: Path, monkeypatch):
    executable, model = _runtime(tmp_path)

    def run(_command, *, cwd, stdout, stderr, timeout, check):
        Path(cwd, "input.txt").write_text("First line\nSecond line\n", encoding="utf-8")
        Path(cwd, "input.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nFirst line\n", encoding="utf-8"
        )

    monkeypatch.setattr(capture_module.subprocess, "run", run)
    result = WhisperCliCaptureProvider(executable, model, model_id="test-model").transcribe(_request())
    assert result.language == "en"
    assert result.segments[0]["text"] == "First line"
    assert not list(tmp_path.glob("studybuddy-asr-*"))


def test_whisper_cli_adapter_timeout_and_output_limit_are_safe(tmp_path: Path, monkeypatch):
    executable, model = _runtime(tmp_path)

    def timeout(*_args, **_kwargs):
        raise capture_module.subprocess.TimeoutExpired("main.exe", 0.01)

    monkeypatch.setattr(capture_module.subprocess, "run", timeout)
    with pytest.raises(CaptureProviderError, match="provider_timeout"):
        WhisperCliCaptureProvider(executable, model).transcribe(_request())

    def huge(_command, *, cwd, stdout, stderr, timeout, check):
        Path(cwd, "input.txt").write_text("x" * 100, encoding="utf-8")

    monkeypatch.setattr(capture_module.subprocess, "run", huge)
    with pytest.raises(CaptureProviderError, match="payload_too_large"):
        WhisperCliCaptureProvider(executable, model, max_output_bytes=10).transcribe(_request())


def test_formal_registry_requires_explicit_runtime_and_model(tmp_path: Path):
    with pytest.raises(Exception, match="transcription_provider_not_configured"):
        provider_registry("whisper-cpp", "ggml-large-v3-turbo").capture_provider()
    executable, model = _runtime(tmp_path)
    provider = provider_registry("whisper-cpp", "ggml-large-v3-turbo").capture_provider(
        runtime_path=str(executable), model_path=str(model)
    )
    assert isinstance(provider, WhisperCliCaptureProvider)


def test_formal_provider_is_draft_first_and_idempotent(tmp_path: Path, monkeypatch):
    executable, model = _runtime(tmp_path)

    def run(_command, *, cwd, stdout, stderr, timeout, check):
        Path(cwd, "input.txt").write_text("Formal transcript", encoding="utf-8")
        Path(cwd, "input.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nFormal transcript\n", encoding="utf-8"
        )

    monkeypatch.setattr(capture_module.subprocess, "run", run)
    provider = WhisperCliCaptureProvider(executable, model, model_id="ggml-large-v3-turbo")
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        connection.execute("INSERT INTO projects (id,name,created_at) VALUES (?,?,?)", (PROJECT, PROJECT, "now"))
        session = create_capture_session(connection, project_id=PROJECT, asset_kind="audio",
                                         original_name="lesson.wav", media_type="audio/wav")
        source = tmp_path / "lesson.wav"
        source.write_bytes(WAV)
        upload_capture_asset(connection, project_id=PROJECT, capture_session_id=session["id"],
                             source_path=source, original_name="lesson.wav", media_type="audio/wav",
                             originals_root=tmp_path / "originals", max_upload_bytes=4096)
        result = transcribe_capture_session(connection, project_id=PROJECT, capture_session_id=session["id"],
                                            provider=provider, idempotency_key="formal-key")
        assert result["draft"]["status"] == "draft"
        assert connection.execute("SELECT COUNT(*) FROM material_revisions").fetchone()[0] == 0
        replay = transcribe_capture_session(connection, project_id=PROJECT, capture_session_id=session["id"],
                                            provider=provider, idempotency_key="formal-key")
        assert replay["replay"] is True
        assert replay["draft"]["id"] == result["draft"]["id"]
        assert "Formal transcript" in json.dumps(result)


@pytest.mark.skipif(not REAL_ASR_SMOKE, reason="opt-in real ASR smoke")
def test_real_asr_api_lifecycle_and_backup_restore_are_scoped(tmp_path: Path, monkeypatch):
    assert REAL_ASR_RUNTIME.is_file()
    assert REAL_ASR_MODEL.is_file()
    assert REAL_ASR_FIXTURE.is_file()
    source = tmp_path / "source"
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"
    config = AppConfig(
        data_root=source,
        asr_provider_id="whisper-cpp",
        asr_model_id="ggml-large-v3-turbo",
        asr_runtime_path=REAL_ASR_RUNTIME,
        asr_model_path=REAL_ASR_MODEL,
        asr_timeout_seconds=120.0,
    )
    with TestClient(create_app(config)) as client:
        created = client.post("/api/study/capture-sessions", json={
            "asset_kind": "audio", "original_name": "fixture.wav", "media_type": "audio/wav",
        })
        assert created.status_code == 201
        capture_id = str(created.json()["id"])
        uploaded = client.post(
            f"/api/study/capture-sessions/{capture_id}/upload",
            files={"file": ("fixture.wav", REAL_ASR_FIXTURE.read_bytes(), "audio/wav")},
        )
        assert uploaded.status_code == 200
        first = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcribe",
            headers={"Idempotency-Key": "formal-real-asr-api"},
        )
        assert first.status_code == 200
        draft = first.json()["draft"]
        assert draft["status"] == "draft"
        assert draft["segments"]
        replay = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcribe",
            headers={"Idempotency-Key": "formal-real-asr-api"},
        )
        assert replay.status_code == 200
        assert replay.json()["replay"] is True
        assert replay.json()["draft"]["id"] == draft["id"]
        edited = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcript/edit",
            json={"draft_id": draft["id"], "text": "User-reviewed transcript."},
        )
        assert edited.status_code == 200
        confirmed = client.post(
            f"/api/study/capture-sessions/{capture_id}/confirm",
            json={"draft_id": draft["id"]},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["capture"]["status"] == "confirmed"
        assert confirmed.json()["revision"]["citations"]
        public_payload = json.dumps({"first": first.json(), "confirmed": confirmed.json()})
        assert "stored_path" not in public_payload
        assert str(REAL_ASR_RUNTIME) not in public_payload
        assert str(REAL_ASR_MODEL) not in public_payload

    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"

    def provider_called(*_args, **_kwargs):
        raise AssertionError("provider_called_during_restore")

    monkeypatch.setattr("app.main.provider_registry", provider_called)
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert verify_restored_data(restored)["status"] == "passed"
    with connect(restored / "studybuddy.sqlite3") as connection:
        restored_capture = get_capture_session(
            connection, project_id="default", capture_session_id=capture_id,
        )
    assert restored_capture is not None
    assert restored_capture["status"] == "confirmed"
    assert len(restored_capture["transcript_drafts"]) == 1
