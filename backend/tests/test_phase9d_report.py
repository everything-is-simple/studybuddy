from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.repository import (
    build_report_projection,
    connect,
    create_report_snapshot,
    export_report_snapshot,
    get_report_snapshot,
)
from test_phase9d_domain import NOW, PROJECT_ID, _seed_project, _seed_report_facts


def test_all_report_kinds_have_safe_empty_projection_and_export(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        for kind in ("daily", "weekly", "monthly", "exam_alert"):
            report = create_report_snapshot(
                connection,
                project_id=PROJECT_ID,
                report_kind=kind,
                timezone_name="UTC",
                period_start="2026-01-15",
                period_end="2026-01-16",
            )
            assert report["status"] == "ready"
            assert report["safe_payload"]["period"]["report_kind"] == kind
            assert report["safe_payload"]["plan"]["active_goal_count"] == 0
            json_text, json_type = export_report_snapshot(
                connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="json"
            )
            markdown_text, markdown_type = export_report_snapshot(
                connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="markdown"
            )
            assert json_type == "application/json"
            assert markdown_type == "text/markdown"
            assert json.loads(json_text)["period"]["report_kind"] == kind
            assert "stored_path" not in json_text and "answer_key" not in json_text
            assert "stored_path" not in markdown_text and "answer_json" not in markdown_text


def test_report_period_uses_timezone_half_open_boundary(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        connection.executemany(
            "INSERT INTO learning_goals VALUES (?,?,?,?,?,?,?,NULL)",
            [
                ("goal_inside", PROJECT_ID, "private", "private", "active", "2026-01-15T08:00:00+00:00", "2026-01-15T08:00:00+00:00"),
                ("goal_boundary", PROJECT_ID, "private", "private", "active", "2026-01-16T08:00:00+00:00", "2026-01-16T08:00:00+00:00"),
            ],
        )
        projection = build_report_projection(
            connection,
            project_id=PROJECT_ID,
            report_kind="daily",
            timezone_name="America/Los_Angeles",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        assert projection["safe_payload"]["plan"]["active_goal_count"] == 1
        assert projection["safe_payload"]["period"]["timezone"] == "America/Los_Angeles"
        with pytest.raises(ValueError, match="report_invalid_period"):
            build_report_projection(
                connection,
                project_id=PROJECT_ID,
                report_kind="daily",
                timezone_name="not/a-timezone",
                period_start="2026-01-15",
                period_end="2026-01-16",
            )


def test_report_export_and_snapshot_are_read_only_and_redacted(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_report_facts(connection)
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("learning_goals", "study_plans", "study_plan_items", "exercise_attempts", "mistake_cases")
        }
        report = create_report_snapshot(
            connection,
            project_id=PROJECT_ID,
            report_kind="weekly",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-22",
        )
        returned = json.dumps(report, ensure_ascii=False)
        for forbidden in (
            "Private exam title", "private goal text", "Private plan title", "private item body",
            "private question", "private answer key", "private submitted answer", "private explanation",
            "originals/private-path", "safe_payload_json",
        ):
            assert forbidden not in returned
        assert before == {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before
        }
        assert get_report_snapshot(connection, project_id="other-project", report_id=str(report["id"])) is None


def test_degraded_capture_is_counted_without_exposing_source_details(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_report_facts(connection)
        connection.execute(
            "INSERT INTO capture_sessions (id,project_id,status,asset_kind,material_id,original_name,media_type,"
            "source_status,created_at,updated_at,confirmed_at,rejected_at,archived_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
            ("capture_missing", PROJECT_ID, "confirmed", "audio", "missing-material", "private.wav", "audio/wav",
             "valid", NOW, NOW),
        )
        projection = build_report_projection(
            connection,
            project_id=PROJECT_ID,
            report_kind="exam_alert",
            timezone_name="UTC",
            period_start="2026-01-15",
            period_end="2026-01-16",
        )
        payload = projection["safe_payload"]
        assert payload["source_quality"]["source_unavailable_count"] >= 1
        serialized = json.dumps(projection, ensure_ascii=False)
        assert "missing-material" not in serialized
        assert "private.wav" not in serialized
