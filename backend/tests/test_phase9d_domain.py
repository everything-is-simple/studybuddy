from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    build_report_projection,
    complete_transcription_operation,
    connect,
    create_capture_session,
    create_report_snapshot,
    create_transcription_operation,
    fail_transcription_operation,
    get_capture_session,
    get_report_snapshot,
    list_report_delivery_attempts,
    list_transcription_operations,
    purge_material,
    record_report_delivery_attempt,
    soft_delete_material,
)

PROJECT_ID = "project_9d"
OTHER_PROJECT_ID = "project_other"
NOW = "2026-01-15T08:00:00+00:00"


def _seed_project(connection: sqlite3.Connection, project_id: str = PROJECT_ID) -> None:
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (project_id, "Phase 9D", NOW),
    )


def _seed_capture_material(connection: sqlite3.Connection, *, project_id: str = PROJECT_ID,
                           material_id: str = "material_capture") -> str:
    connection.execute(
        "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (material_id, project_id, "lesson.wav", "a" * 64, "originals/private-path", "audio/wav", NOW, NOW),
    )
    connection.execute(
        "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (f"extraction_{material_id}", material_id, "capture-placeholder", "1", "empty", "", "[]", NOW),
    )
    return material_id


def _capture(connection: sqlite3.Connection, *, project_id: str = PROJECT_ID,
             material_id: str = "material_capture") -> dict[str, object]:
    return create_capture_session(
        connection,
        project_id=project_id,
        asset_kind="audio",
        original_name="ignored.wav",
        media_type="audio/wav",
        material_id=material_id,
    )


def _completed_capture(connection: sqlite3.Connection) -> tuple[dict[str, object], dict[str, object]]:
    capture = _capture(connection)
    operation = create_transcription_operation(
        connection,
        project_id=PROJECT_ID,
        capture_session_id=str(capture["id"]),
        input_fingerprint="a" * 64,
        idempotency_key="capture-key",
    )
    result = complete_transcription_operation(
        connection,
        project_id=PROJECT_ID,
        operation_id=str(operation["id"]),
        language="zh-CN",
        segments=[
            {"text": "clear segment", "confidence": 0.95},
            {"text": "needs review", "confidence": 0.40},
        ],
    )
    connection.execute("UPDATE capture_sessions SET created_at=?,updated_at=? WHERE id=?", (NOW, NOW, capture["id"]))
    connection.execute("UPDATE transcript_drafts SET created_at=?,updated_at=? WHERE id=?", (NOW, NOW, result["draft"]["id"]))
    connection.execute("UPDATE transcript_segments SET created_at=?,updated_at=? WHERE draft_id=?", (NOW, NOW, result["draft"]["id"]))
    return capture, result


def _seed_report_facts(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO learning_goals VALUES (?,?,?,?,?,?,?,NULL)",
        ("goal_9d", PROJECT_ID, "Private exam title", "private goal text", "active", NOW, NOW),
    )
    connection.execute(
        "INSERT INTO study_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("plan_9d", PROJECT_ID, "goal_9d", "Private plan title", "private plan text", "active", 0,
         NOW, NOW, NOW, NOW, None, None),
    )
    connection.execute(
        "INSERT INTO study_plan_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("item_9d", "plan_9d", PROJECT_ID, None, None, None, "Private item title", "private item body",
         0, "in_progress", 0, NOW, NOW, None, None),
    )
    connection.execute(
        "INSERT INTO rhythm_settings VALUES (?,?,?,?,?,?,?,?,?)",
        ("rhythm_9d", PROJECT_ID, "plan_9d", "daily", "UTC", "2026-01-01", 30, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO rhythm_allocations VALUES (?,?,?,?,?,?,?,?)",
        ("allocation_9d", PROJECT_ID, "plan_9d", "item_9d", "2026-01-15", 45, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO exercise_sets VALUES (?,?,?,?,?,?,?,?)",
        ("set_9d", PROJECT_ID, "Private set", "private set description", "active", NOW, NOW, None),
    )
    connection.execute(
        "INSERT INTO exercises (id,set_id,project_id,exercise_type,prompt,options_json,answer_key_json,explanation,source_revision,status,created_at,updated_at,exercise_kind) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("exercise_9d", "set_9d", PROJECT_ID, "short_answer", "private question", "[]",
         json.dumps("private answer key"), "private explanation", None, "ready", NOW, NOW, "user_created"),
    )
    connection.execute(
        "INSERT INTO exercise_attempts (id,exercise_id,answer_json,score,is_correct,grading_status,submitted_at,reviewed_at,feedback) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("attempt_9d", "exercise_9d", json.dumps("private submitted answer"), None, None,
         "pending_review", NOW, None, "private feedback"),
    )
    connection.execute(
        "INSERT INTO practice_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("practice_9d", PROJECT_ID, "practice", None, "finished", "Private session", 600, "UTC",
         "2026-01-15", NOW, NOW, NOW, NOW, NOW),
    )
    connection.execute(
        "INSERT INTO mistake_cases VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("mistake_9d", PROJECT_ID, "exercise_9d", "revision-private", "open", "user_reported",
         NOW, NOW, None, None),
    )
    connection.execute(
        "INSERT INTO knowledge_modules VALUES (?,?,?,?,?,?,?,NULL)",
        ("module_9d", PROJECT_ID, "Private module", "private module description", "active", NOW, NOW),
    )
    connection.execute(
        "INSERT INTO module_source_links (id,project_id,module_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("source_9d", PROJECT_ID, "module_9d", None, None, None, None, None, None,
         "source_deleted", NOW, NOW),
    )


def test_capture_operation_idempotency_scope_and_append_only_history(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_project(connection, OTHER_PROJECT_ID)
        material_id = _seed_capture_material(connection)
        capture = _capture(connection)
        assert capture["status"] == "uploaded" and capture["source_status"] == "valid"
        assert "stored_path" not in capture

        operation = create_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(capture["id"]),
            input_fingerprint="a" * 64,
            idempotency_key="same-key",
        )
        replay = create_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(capture["id"]),
            input_fingerprint="a" * 64,
            idempotency_key="same-key",
        )
        assert replay["id"] == operation["id"] and replay["replay"] is True
        assert "input_fingerprint" not in replay and "idempotency_key" not in replay
        with pytest.raises(ValueError, match="transcription_idempotency_mismatch"):
            create_transcription_operation(
                connection,
                project_id=PROJECT_ID,
                capture_session_id=str(capture["id"]),
                input_fingerprint="b" * 64,
                idempotency_key="same-key",
            )
        with pytest.raises(ValueError, match="capture_not_found"):
            create_transcription_operation(
                connection,
                project_id=OTHER_PROJECT_ID,
                capture_session_id=str(capture["id"]),
                input_fingerprint="a" * 64,
            )

        completed = complete_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            operation_id=str(operation["id"]),
            segments=[{"text": "uncertain draft", "confidence": 0.25}],
        )
        assert completed["draft"]["quality_status"] == "uncertain"
        assert completed["draft"]["segments"][0]["quality"] == "uncertain"
        completed_replay = complete_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            operation_id=str(operation["id"]),
            segments=[{"text": "must not overwrite", "confidence": 1.0}],
        )
        assert completed_replay["draft"]["text"] == "uncertain draft"
        assert connection.execute("SELECT COUNT(*) FROM transcript_drafts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM ai_operations WHERE capture_session_id=?", (capture["id"],)).fetchone()[0] == 1
        assert len(list_transcription_operations(connection, project_id=PROJECT_ID, capture_session_id=str(capture["id"]))) == 1
        assert connection.execute("SELECT COUNT(*) FROM materials WHERE id=?", (material_id,)).fetchone()[0] == 1


def test_transcription_completion_rolls_back_draft_segments_and_state(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_capture_material(connection)
        capture = _capture(connection)
        operation = create_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(capture["id"]),
            input_fingerprint="a" * 64,
            idempotency_key="retry-key",
        )
        connection.execute(
            "CREATE TRIGGER fail_segment BEFORE INSERT ON transcript_segments "
            "BEGIN SELECT RAISE(ABORT, 'private'); END"
        )
        with pytest.raises(sqlite3.IntegrityError):
            complete_transcription_operation(
                connection,
                project_id=PROJECT_ID,
                operation_id=str(operation["id"]),
                segments=[{"text": "partial", "confidence": 0.9}],
            )
        connection.execute("DROP TRIGGER fail_segment")
        assert connection.execute("SELECT COUNT(*) FROM transcript_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM transcript_segments").fetchone()[0] == 0
        assert connection.execute("SELECT status FROM ai_operations WHERE id=?", (operation["id"],)).fetchone()[0] == "running"
        assert connection.execute("SELECT status FROM capture_sessions WHERE id=?", (capture["id"],)).fetchone()[0] == "transcribing"
        with pytest.raises(ValueError, match="transcription_failed"):
            fail_transcription_operation(
                connection,
                project_id=PROJECT_ID,
                operation_id=str(operation["id"]),
                error_code="raw provider response with secret",
            )
        assert connection.execute("SELECT error_code FROM ai_operations WHERE id=?", (operation["id"],)).fetchone()[0] is None
        failed = fail_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            operation_id=str(operation["id"]),
            error_code="provider_timeout",
        )
        assert failed["status"] == "failed"
        retry = create_transcription_operation(
            connection,
            project_id=PROJECT_ID,
            capture_session_id=str(capture["id"]),
            input_fingerprint="a" * 64,
            idempotency_key="retry-key",
        )
        assert retry["id"] != operation["id"] and retry["retry_count"] == 1
        assert connection.execute("SELECT status FROM ai_operations WHERE id=?", (operation["id"],)).fetchone()[0] == "failed"


def test_capture_source_lifecycle_degrades_without_paths_or_history_loss(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id = _seed_capture_material(connection)
        capture, completed = _completed_capture(connection)
        assert soft_delete_material(connection, material_id) is True
        deleted = get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(capture["id"]))
        assert deleted["source_status"] == "source_deleted"
        assert deleted["transcript_drafts"][0]["text"] == completed["draft"]["text"]
        assert "stored_path" not in json.dumps(deleted)
        purge_material(connection, material_id)
        unavailable = get_capture_session(connection, project_id=PROJECT_ID, capture_session_id=str(capture["id"]))
        assert unavailable["source_status"] == "source_unavailable"
        assert unavailable["status"] == "review_required"
        assert len(unavailable["transcription_operations"]) == 1


def test_report_projection_is_whitelisted_recomputable_and_read_only(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_capture_material(connection)
        _completed_capture(connection)
        _seed_report_facts(connection)
        fact_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("study_progress_events", "exercise_attempts", "mistake_cases", "notes", "rhythm_allocations")
        }
        projection = build_report_projection(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        payload = projection["safe_payload"]
        assert payload["plan"]["active_goal_count"] == 1
        assert payload["plan"]["planned_minutes_total"] == 45
        assert payload["rhythm"]["overload_day_count"] == 1
        assert payload["practice"]["pending_review_count"] == 1
        assert payload["feedback"]["open_mistake_count"] == 1
        assert payload["source_quality"]["uncertain_transcript_segment_count"] == 1
        assert payload["quality_flags"]["has_uncertain_capture"] is True
        serialized = json.dumps(projection, ensure_ascii=False)
        for forbidden in (
            "Private exam title", "private goal text", "Private plan title", "private item body",
            "private question", "private answer key", "private submitted answer", "private explanation",
            "originals/private-path", "clear segment", "needs review",
        ):
            assert forbidden not in serialized
        assert fact_counts == {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in fact_counts
        }

        report = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        replay = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        assert replay["id"] == report["id"] and replay["replay"] is True
        assert "aggregation_fingerprint" not in report
        assert get_report_snapshot(connection, project_id=OTHER_PROJECT_ID, report_id=str(report["id"])) is None
        assert connection.execute("SELECT COUNT(*) FROM report_snapshots").fetchone()[0] == 1


def test_report_snapshot_rolls_back_and_new_fact_creates_new_projection(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        connection.execute(
            "CREATE TRIGGER fail_report BEFORE INSERT ON report_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'private'); END"
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            create_report_snapshot(
                connection,
                project_id=PROJECT_ID,
                report_kind="daily",
                timezone_name="UTC",
                period_start="2026-01-15",
                period_end="2026-01-16",
            )
        connection.execute("DROP TRIGGER fail_report")
        assert connection.execute("SELECT COUNT(*) FROM report_snapshots").fetchone()[0] == 0
        first = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        connection.execute(
            "INSERT INTO learning_goals VALUES (?,?,?,?,?,?,?,NULL)",
            ("goal_new", PROJECT_ID, "Never expose", "Never expose", "active", NOW, NOW),
        )
        second = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        assert second["id"] != first["id"]
        assert first["safe_payload"]["plan"]["active_goal_count"] == 0
        assert second["safe_payload"]["plan"]["active_goal_count"] == 1
        assert connection.execute("SELECT COUNT(*) FROM report_snapshots").fetchone()[0] == 2


def test_delivery_audit_is_append_only_idempotent_and_secret_free(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        dry_run = record_report_delivery_attempt(
            connection,
            project_id=PROJECT_ID,
            report_id=str(report["id"]),
            channel="smtp",
            mode="dry_run",
            target_label="guardian-primary",
            idempotency_key="delivery-key",
        )
        replay = record_report_delivery_attempt(
            connection,
            project_id=PROJECT_ID,
            report_id=str(report["id"]),
            channel="smtp",
            mode="dry_run",
            target_label="guardian-primary",
            idempotency_key="delivery-key",
        )
        assert replay["id"] == dry_run["id"] and replay["replay"] is True
        assert dry_run["status"] == "dry_run" and dry_run["error_code"] is None
        with pytest.raises(ValueError, match="delivery_idempotency_mismatch"):
            record_report_delivery_attempt(
                connection,
                project_id=PROJECT_ID,
                report_id=str(report["id"]),
                channel="smtp",
                mode="dry_run",
                target_label="different-target",
                idempotency_key="delivery-key",
            )
        with pytest.raises(ValueError, match="delivery_idempotency_mismatch"):
            record_report_delivery_attempt(
                connection,
                project_id=PROJECT_ID,
                report_id=str(report["id"]),
                channel="smtp",
                mode="off",
                target_label="guardian-primary",
                idempotency_key="delivery-key",
            )
        blocked = record_report_delivery_attempt(
            connection,
            project_id=PROJECT_ID,
            report_id=str(report["id"]),
            channel="feishu",
            mode="live",
            target_label="guardian-primary",
        )
        assert blocked["status"] == "blocked" and blocked["error_code"] == "delivery_live_not_approved"
        attempts = list_report_delivery_attempts(
            connection, project_id=PROJECT_ID, report_id=str(report["id"])
        )
        assert {attempt["id"] for attempt in attempts} == {dry_run["id"], blocked["id"]}
        database_text = " ".join(
            str(value)
            for row in connection.execute("SELECT * FROM report_delivery_attempts").fetchall()
            for value in row
            if value is not None
        )
        returned = json.dumps(attempts)
        for forbidden in ("delivery-key", "smtp-password", "webhook-secret", "safe_payload_json"):
            assert forbidden not in database_text
            assert forbidden not in returned
        assert connection.execute("SELECT COUNT(*) FROM report_delivery_attempts").fetchone()[0] == 2
