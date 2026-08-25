from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.providers import (
    CaptureProviderError,
    CaptureTranscriptionResult,
    DeterministicFakeCaptureProvider,
    LoopbackCaptureProvider,
    provider_registry,
)
from app.repository import (
    connect,
    create_capture_session,
    get_capture_session,
    list_transcription_operations,
    purge_material,
    soft_delete_material,
    transcribe_capture_session,
    upload_capture_asset,
)

PROJECT_ID = "project_9d_capture"
OTHER_PROJECT_ID = "project_other"
NOW = "2026-01-15T08:00:00+00:00"
PNG = b"\x89PNG\r\n\x1a\n" + b"capture-image"
WAV = b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"capture-audio"


def _seed_project(connection: sqlite3.Connection, project_id: str = PROJECT_ID) -> None:
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (project_id, "Capture test", NOW),
    )


def _session(connection: sqlite3.Connection, *, asset_kind: str = "image",
             original_name: str = "lesson.png", media_type: str = "image/png",
             project_id: str = PROJECT_ID) -> dict[str, object]:
    return create_capture_session(
        connection,
        project_id=project_id,
        asset_kind=asset_kind,
        original_name=original_name,
        media_type=media_type,
    )


def _source(tmp_path: Path, content: bytes = PNG) -> Path:
    path = tmp_path / "incoming"
    path.write_bytes(content)
    return path


def _upload(connection: sqlite3.Connection, tmp_path: Path, *, session: dict[str, object],
            content: bytes = PNG, name: str = "lesson.png", media_type: str = "image/png") -> dict[str, object]:
    return upload_capture_asset(
        connection,
        project_id=PROJECT_ID,
        capture_session_id=str(session["id"]),
        source_path=_source(tmp_path, content),
        original_name=name,
        media_type=media_type,
        originals_root=tmp_path / "originals",
        max_upload_bytes=1024,
    )


def test_fake_capture_upload_transcription_is_deterministic_and_uncertain(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session = _session(connection)
        uploaded = _upload(connection, tmp_path, session=session)
        assert uploaded["status"] == "uploaded"
        material_id = str(uploaded["material_id"])
        assert uploaded["source_status"] == "valid"
        assert "stored_path" not in uploaded
        stored = connection.execute(
            "SELECT stored_path,source_sha256,media_type FROM materials WHERE id=?", (material_id,)
        ).fetchone()
        assert stored["media_type"] == "image/png"
        assert Path(stored["stored_path"]).is_file()

        first = transcribe_capture_session(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            provider=DeterministicFakeCaptureProvider(),
            idempotency_key="capture-transcription-1",
        )
        assert first["draft"]["quality_status"] == "uncertain"
        assert first["draft"]["segments"][0]["quality"] == "clear"
        assert first["draft"]["segments"][1]["quality"] == "uncertain"
        assert first["operation"]["provider_id"] == "fake"
        assert first["operation"]["model_id"] == "fake-capture-v1"
        assert first["operation"]["status"] == "succeeded"
        assert get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]))["status"] == "review_required"

        # Same input/key returns the immutable draft and does not add an operation.
        replay = transcribe_capture_session(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            provider=DeterministicFakeCaptureProvider(),
            idempotency_key="capture-transcription-1",
        )
        assert replay["replay"] is True
        assert replay["draft"]["text"] == first["draft"]["text"]
        assert len(list_transcription_operations(connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]))) == 1
        with pytest.raises(ValueError, match="transcription_not_ready"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=DeterministicFakeCaptureProvider(), idempotency_key="new-key",
            )

        database_text = " ".join(
            str(value)
            for table in ("capture_sessions", "transcript_drafts", "transcript_segments", "ai_operations")
            for row in connection.execute(f"SELECT * FROM {table}").fetchall()
            for value in row
            if value is not None
        )
        assert "stored_path" not in database_text
        assert "raw provider response" not in database_text
        assert "Capture test" not in json.dumps(first)


def test_loopback_audio_and_provider_registry_are_local_only(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session = _session(connection, asset_kind="audio", original_name="lesson.wav", media_type="audio/wav")
        _upload(connection, tmp_path, session=session, content=WAV, name="lesson.wav", media_type="audio/wav")
        provider = provider_registry("loopback").capture_provider()
        assert isinstance(provider, LoopbackCaptureProvider)
        result = transcribe_capture_session(
            connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]), provider=provider,
        )
        assert result["operation"]["provider_id"] == "loopback"
        assert result["operation"]["model_id"] == "loopback-capture-v1"
        with pytest.raises(Exception):
            provider_registry("real-ocr-provider", "model").capture_provider()


def test_capture_upload_rejects_type_signature_size_and_repeated_upload(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session = _session(connection)
        with pytest.raises(ValueError, match="capture_asset_type_not_supported"):
            _upload(connection, tmp_path, session=session, content=b"not-png")
        assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0
        with pytest.raises(ValueError, match="capture_asset_too_large"):
            upload_capture_asset(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                source_path=_source(tmp_path, PNG + b"too-large"), original_name="lesson.png",
                media_type="image/png", originals_root=tmp_path / "originals", max_upload_bytes=4,
            )
        assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0
        uploaded = _upload(connection, tmp_path, session=session)
        with pytest.raises(ValueError, match="capture_invalid_state"):
            _upload(connection, tmp_path, session=session)
        assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 1
        assert uploaded["status"] == "uploaded"


def test_transcription_failure_timeout_invalid_output_and_retry_are_safe(tmp_path: Path):
    class FailingProvider:
        provider_id = "fake"
        model_id = "fake-capture-v1"

        def transcribe(self, request):
            raise CaptureProviderError("provider_timeout")

    class InvalidProvider:
        provider_id = "fake"
        model_id = "fake-capture-v1"

        def transcribe(self, request):
            return CaptureTranscriptionResult(segments=[{"text": "", "confidence": 1.0}])

    class HugeProvider:
        provider_id = "fake"
        model_id = "fake-capture-v1"

        def transcribe(self, request):
            return CaptureTranscriptionResult(
                segments=[{"text": "x" * 20000, "confidence": 0.9} for _ in range(11)]
            )

    class SlowProvider:
        provider_id = "fake"
        model_id = "fake-capture-v1"

        def transcribe(self, request):
            time.sleep(0.01)
            return CaptureTranscriptionResult(segments=[{"text": "too late", "confidence": 0.9}])

    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session = _session(connection)
        _upload(connection, tmp_path, session=session)
        with pytest.raises(ValueError, match="provider_timeout"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=FailingProvider(), idempotency_key="failed-key",
            )
        assert connection.execute("SELECT COUNT(*) FROM transcript_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT status FROM capture_sessions WHERE id=?", (session["id"],)).fetchone()[0] == "failed"
        failed = connection.execute("SELECT error_code,status FROM ai_operations").fetchone()
        assert tuple(failed) == ("provider_timeout", "failed")

        retry_session = get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]))
        # The domain retry creates a new operation only after explicit session retry state is restored.
        connection.execute("UPDATE capture_sessions SET status='uploaded' WHERE id=?", (session["id"],))
        with pytest.raises(ValueError, match="transcript_empty_or_invalid"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=InvalidProvider(), idempotency_key="invalid-key",
            )
        assert connection.execute("SELECT COUNT(*) FROM transcript_drafts").fetchone()[0] == 0
        connection.execute("UPDATE capture_sessions SET status='uploaded' WHERE id=?", (session["id"],))
        with pytest.raises(ValueError, match="payload_too_large"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=HugeProvider(), idempotency_key="huge-key",
            )
        connection.execute("UPDATE capture_sessions SET status='uploaded' WHERE id=?", (session["id"],))
        with pytest.raises(ValueError, match="provider_timeout"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=SlowProvider(), idempotency_key="slow-key", timeout_seconds=0.001,
            )
        assert connection.execute("SELECT COUNT(*) FROM transcript_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 4


def test_capture_source_delete_and_purge_keep_transcript_but_degrade_read_path(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session = _session(connection)
        uploaded = _upload(connection, tmp_path, session=session)
        transcribe_capture_session(
            connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
            provider=DeterministicFakeCaptureProvider(),
        )
        material_id = str(uploaded["material_id"])
        assert soft_delete_material(connection, material_id) is True
        deleted = get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]))
        assert deleted["source_status"] == "source_deleted"
        assert deleted["transcript_drafts"][0]["text"]
        assert "stored_path" not in json.dumps(deleted)
        assert purge_material(connection, material_id)[0] is not None
        unavailable = get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]))
        assert unavailable["source_status"] == "source_unavailable"
        assert unavailable["transcript_drafts"][0]["text"]
        with pytest.raises(ValueError, match="capture_source_unavailable"):
            transcribe_capture_session(
                connection, project_id=PROJECT_ID, capture_session_id=str(session["id"]),
                provider=DeterministicFakeCaptureProvider(),
            )


def test_capture_upload_scope_and_cleanup_on_database_failure(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_project(connection, OTHER_PROJECT_ID)
        session = _session(connection)
        source = _source(tmp_path)
        with pytest.raises(ValueError, match="capture_not_found"):
            upload_capture_asset(
                connection, project_id=OTHER_PROJECT_ID, capture_session_id=str(session["id"]),
                source_path=source, original_name="lesson.png", media_type="image/png",
                originals_root=tmp_path / "other-originals", max_upload_bytes=1024,
            )
        assert not list((tmp_path / "other-originals").rglob("original")) if (tmp_path / "other-originals").exists() else True

        connection.execute(
            "CREATE TRIGGER fail_capture_material BEFORE INSERT ON materials "
            "BEGIN SELECT RAISE(ABORT, 'private'); END"
        )
        with pytest.raises(ValueError, match="capture_upload_failed"):
            _upload(connection, tmp_path, session=session)
        connection.execute("DROP TRIGGER fail_capture_material")
        assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0
        assert not list((tmp_path / "originals").rglob("original")) if (tmp_path / "originals").exists() else True
