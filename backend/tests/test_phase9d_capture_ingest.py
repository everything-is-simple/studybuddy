from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.providers import DeterministicFakeCaptureProvider
from app.repository import (
    connect,
    confirm_transcript_draft,
    edit_transcript_draft,
    reject_transcript_draft,
    run_chunk_retrieval,
    transcribe_capture_session,
)
from test_phase9d_capture import PROJECT_ID, _seed_project, _session, _upload


def _transcribed(connection: sqlite3.Connection, tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    session = _session(connection)
    _upload(connection, tmp_path, session=session)
    result = transcribe_capture_session(
        connection,
        project_id=PROJECT_ID,
        capture_session_id=str(session["id"]),
        provider=DeterministicFakeCaptureProvider(),
    )
    return session, result


def test_confirm_ingests_same_capture_material_as_current_s2_revision_and_retrieval(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session, result = _transcribed(connection, tmp_path)
        draft = result["draft"]
        confirmed = confirm_transcript_draft(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            draft_id=str(draft["id"]),
        )
        assert confirmed["capture"]["status"] == "confirmed"
        assert confirmed["draft"]["status"] == "confirmed"
        assert confirmed["capture"]["material_id"]
        material_id = confirmed["capture"]["material_id"]
        assert confirmed["revision"]["extraction_id"]
        assert confirmed["revision"]["citations"]
        assert all(item["status"] == "valid" for item in confirmed["revision"]["citations"])
        assert connection.execute(
            "SELECT COUNT(*) FROM materials WHERE project_id=?", (PROJECT_ID,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT parser_id FROM extractions WHERE id=?", (confirmed["revision"]["extraction_id"],)
        ).fetchone()[0] == "class_capture_transcript"
        assert connection.execute(
            "SELECT COUNT(*) FROM transcript_drafts WHERE status='confirmed'"
        ).fetchone()[0] == 1

        hit = run_chunk_retrieval(
            connection,
            project_id=PROJECT_ID,
            query="Deterministic image capture",
            material_ids=[str(material_id)],
        )
        assert hit["status"] == "succeeded"
        assert hit["hits"]
        assert hit["hits"][0]["revision_id"] == confirmed["revision"]["id"]

        replay = confirm_transcript_draft(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            draft_id=str(draft["id"]),
        )
        assert replay["replay"] is True
        assert replay["revision"]["id"] == confirmed["revision"]["id"]


def test_uncertain_segments_survive_edit_and_confirm_without_provider_overwrite(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session, result = _transcribed(connection, tmp_path)
        draft = result["draft"]
        edited = edit_transcript_draft(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            draft_id=str(draft["id"]),
            text="Teacher explains the lesson\nStudent review marker corrected",
        )
        assert edited["edited_by_user"] is True
        assert edited["text"] == "Teacher explains the lesson\nStudent review marker corrected"
        assert any(segment["quality"] == "uncertain" for segment in edited["segments"])
        with pytest.raises(ValueError, match="transcript_empty_or_invalid"):
            edit_transcript_draft(
                connection,
                project_id=PROJECT_ID,
                capture_session_id=str(session["id"]),
                draft_id=str(draft["id"]),
                text="",
            )
        confirmed = confirm_transcript_draft(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            draft_id=str(draft["id"]),
        )
        extraction = connection.execute(
            "SELECT text FROM extractions WHERE id=?", (confirmed["revision"]["extraction_id"],)
        ).fetchone()
        assert extraction[0] == edited["text"]
        assert "Teacher explains" in extraction[0]
        with pytest.raises(ValueError, match="transcript_user_edit_protected"):
            edit_transcript_draft(
                connection,
                project_id=PROJECT_ID,
                capture_session_id=str(session["id"]),
                draft_id=str(draft["id"]),
                text="Attempted silent overwrite",
            )


def test_reject_keeps_draft_history_and_does_not_create_s2_revision(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session, result = _transcribed(connection, tmp_path)
        draft = result["draft"]
        rejected = reject_transcript_draft(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(session["id"]),
            draft_id=str(draft["id"]),
        )
        assert rejected["capture"]["status"] == "rejected"
        assert rejected["draft"]["status"] == "rejected"
        assert connection.execute(
            "SELECT COUNT(*) FROM material_revisions WHERE material_id=?",
            (session["material_id"],),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT text FROM transcript_drafts WHERE id=?", (draft["id"],)
        ).fetchone()[0] == draft["text"]
        with pytest.raises(ValueError, match="capture_invalid_state"):
            confirm_transcript_draft(
                connection,
                project_id=PROJECT_ID,
                capture_session_id=str(session["id"]),
                draft_id=str(draft["id"]),
            )


def test_confirm_rolls_back_extraction_revision_chunks_and_states_on_failure(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        session, result = _transcribed(connection, tmp_path)
        draft = result["draft"]
        connection.execute(
            "CREATE TRIGGER fail_transcript_revision BEFORE INSERT ON material_revisions "
            "BEGIN SELECT RAISE(ABORT, 'private'); END"
        )
        with pytest.raises(sqlite3.IntegrityError):
            confirm_transcript_draft(
                connection,
                project_id=PROJECT_ID,
                capture_session_id=str(session["id"]),
                draft_id=str(draft["id"]),
            )
        connection.execute("DROP TRIGGER fail_transcript_revision")
        assert connection.execute("SELECT COUNT(*) FROM material_revisions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        assert connection.execute(
            "SELECT status FROM capture_sessions WHERE id=?", (session["id"],)
        ).fetchone()[0] == "review_required"
        assert connection.execute(
            "SELECT status FROM transcript_drafts WHERE id=?", (draft["id"],)
        ).fetchone()[0] == "draft"
