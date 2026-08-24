from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    append_study_progress_event,
    connect,
    create_knowledge_module,
    create_learning_goal,
    create_module_source_link,
    create_rhythm_allocation,
    create_study_plan,
    create_study_plan_item,
    index_material_revision,
    soft_delete_material,
    delete_rhythm_allocation,
    rhythm_summary,
    save_rhythm_settings,
    transition_study_plan,
    update_rhythm_allocation,
)

PROJECT_ID = "project_9b_rhythm"


def _seed_plan(connection: sqlite3.Connection, *, items: int = 1):
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (PROJECT_ID, "Phase 9B rhythm", "2026-01-01T00:00:00+00:00"),
    )
    goal = create_learning_goal(connection, project_id=PROJECT_ID, title="Rhythm goal")
    plan = create_study_plan(connection, project_id=PROJECT_ID, goal_id=goal["id"], title="Rhythm plan")
    plan_items = [
        create_study_plan_item(connection, project_id=PROJECT_ID, plan_id=plan["id"], title=f"Item {index}")
        for index in range(items)
    ]
    return plan, plan_items


def _activate(connection: sqlite3.Connection, plan_id: str) -> None:
    transition_study_plan(connection, project_id=PROJECT_ID, plan_id=plan_id, target="confirmed")
    transition_study_plan(connection, project_id=PROJECT_ID, plan_id=plan_id, target="active")


def test_rhythm_rejects_invalid_inputs_cross_plan_items_and_no_settings_summary(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        first_plan, [first_item] = _seed_plan(connection)
        second_goal = create_learning_goal(connection, project_id=PROJECT_ID, title="Second goal")
        second_plan = create_study_plan(connection, project_id=PROJECT_ID, goal_id=second_goal["id"], title="Second plan")
        second_item = create_study_plan_item(
            connection, project_id=PROJECT_ID, plan_id=second_plan["id"], title="Other item"
        )

        empty = rhythm_summary(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], local_date="2026-03-01")
        assert empty["settings"] is None
        assert empty["unassigned_item_count"] == 1
        assert empty["item_projection"] == {"pending_count": 1, "in_progress_count": 0, "completed_count": 0, "skipped_count": 0}
        with pytest.raises(ValueError, match="study_rhythm_invalid_date"):
            rhythm_summary(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], local_date="2026-02-30")

        for kwargs, code in (
            ({"cadence": "monthly", "timezone_name": "UTC", "period_start": "2026-03-01", "target_minutes": 1}, "study_rhythm_invalid_cadence"),
            ({"cadence": "daily", "timezone_name": "CST", "period_start": "2026-03-01", "target_minutes": 1}, "study_rhythm_invalid_timezone"),
            ({"cadence": "daily", "timezone_name": "Asia/Shanghai", "period_start": "2026-02-30", "target_minutes": 1}, "study_rhythm_invalid_date"),
            ({"cadence": "daily", "timezone_name": "UTC", "period_start": "2026-03-01", "target_minutes": True}, "study_rhythm_target_out_of_range"),
            ({"cadence": "daily", "timezone_name": "UTC", "period_start": "2026-03-01", "target_minutes": 10081}, "study_rhythm_target_out_of_range"),
        ):
            with pytest.raises(ValueError, match=code):
                save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], **kwargs)

        save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-03-01", target_minutes=30)
        with pytest.raises(ValueError, match="study_rhythm_item_not_found"):
            create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], item_id=second_item["id"], local_date="2026-03-01", planned_minutes=1)
        for local_date, minutes in (("2026-03-01T00:00:00Z", 1), ("2026-02-30", 1), ("2026-03-01", 0), ("2026-03-01", -1), ("2026-03-01", 1441), ("2026-03-01", True)):
            with pytest.raises(ValueError, match="study_rhythm_invalid"):
                create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=first_plan["id"], item_id=first_item["id"], local_date=local_date, planned_minutes=minutes)


def test_rhythm_timeline_is_timezone_explicit_dst_safe_and_never_writes_progress(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        plan, [first, second] = _seed_plan(connection, items=2)
        save_rhythm_settings(
            connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="daily",
            timezone_name="Europe/Berlin", period_start="2026-03-28", target_minutes=60,
        )
        create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=first["id"], local_date="2026-03-29", planned_minutes=45)
        create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=second["id"], local_date="2026-03-30", planned_minutes=75)

        first_read = rhythm_summary(connection, project_id=PROJECT_ID, plan_id=plan["id"], local_date="2026-03-29", periods=2)
        second_read = rhythm_summary(connection, project_id=PROJECT_ID, plan_id=plan["id"], local_date="2026-03-29", periods=2)
        assert first_read == second_read
        assert [bucket["local_date_start"] for bucket in first_read["buckets"]] == ["2026-03-29", "2026-03-30"]
        assert [bucket["planned_minutes"] for bucket in first_read["buckets"]] == [45, 75]
        assert [bucket["remaining_target_minutes"] for bucket in first_read["buckets"]] == [15, 0]
        assert first_read["unassigned_item_count"] == 0
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0


def test_rhythm_limits_settings_rollback_and_manual_move_delete(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        plan, [item, other_item] = _seed_plan(connection, items=2)
        save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-01-01", target_minutes=0)
        allocations = [
            create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date=f"2026-01-0{day}", planned_minutes=1440)
            for day in range(1, 8)
        ]
        assert len(allocations) == 7
        with pytest.raises(ValueError, match="study_rhythm_allocation_limit_exceeded"):
            create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date="2026-01-08", planned_minutes=1)
        # This is valid under daily buckets but would overload one weekly bucket.
        create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=other_item["id"], local_date="2026-01-01", planned_minutes=1)
        # Preserved allocations are not silently moved, but a cadence edit that makes
        # them exceed the weekly contract must roll back atomically.
        with pytest.raises(ValueError, match="study_rhythm_allocation_limit_exceeded"):
            save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="weekly", timezone_name="UTC", period_start="2026-01-01", target_minutes=0)
        assert rhythm_summary(connection, project_id=PROJECT_ID, plan_id=plan["id"], local_date="2026-01-01")["settings"]["cadence"] == "daily"

        moved = update_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], allocation_id=allocations[0]["id"], local_date="2026-02-01", planned_minutes=30)
        assert moved["local_date"] == "2026-02-01" and moved["planned_minutes"] == 30
        assert delete_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], allocation_id=moved["id"]) is True
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0


def test_completed_item_and_terminal_plan_protect_allocations_until_explicit_reopen(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        plan, [item] = _seed_plan(connection)
        save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="weekly", timezone_name="UTC", period_start="2026-01-05", target_minutes=120)
        allocation = create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date="2026-01-06", planned_minutes=30)
        _activate(connection, plan["id"])
        append_study_progress_event(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], event_type="completed")
        with pytest.raises(ValueError, match="study_rhythm_edit_not_allowed"):
            update_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], allocation_id=allocation["id"], planned_minutes=60)
        with pytest.raises(ValueError, match="study_rhythm_edit_not_allowed"):
            delete_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], allocation_id=allocation["id"])

        append_study_progress_event(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], event_type="reopened")
        assert update_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], allocation_id=allocation["id"], planned_minutes=60)["planned_minutes"] == 60
        transition_study_plan(connection, project_id=PROJECT_ID, plan_id=plan["id"], target="completed")
        with pytest.raises(ValueError, match="study_rhythm_edit_not_allowed"):
            save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-01-01", target_minutes=1)
        assert connection.execute("SELECT event_type FROM study_progress_events ORDER BY created_at,id").fetchall()


def test_rhythm_summary_keeps_plan_projection_and_reports_unavailable_source_warning(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        connection.execute(
            "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
            (PROJECT_ID, "Phase 9B rhythm", "2026-01-01T00:00:00+00:00"),
        )
        material_id, extraction_id = "material_9b_rhythm_source", "extraction_9b_rhythm_source"
        connection.execute(
            "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)",
            (material_id, PROJECT_ID, "source.txt", "d" * 64, "originals/d", "text/plain", "now", "now"),
        )
        connection.execute(
            "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)",
            (extraction_id, material_id, "txt", "1", "success", "Rhythm evidence", "[]", "now"),
        )
        connection.execute(
            "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
            ("span_9b_rhythm_source", extraction_id, 0, "document", "source.txt", "Rhythm evidence"),
        )
        module = create_knowledge_module(connection, project_id=PROJECT_ID, title="Source module")
        goal = create_learning_goal(connection, project_id=PROJECT_ID, title="Source goal")
        plan = create_study_plan(connection, project_id=PROJECT_ID, goal_id=goal["id"], title="Source plan")
        item = create_study_plan_item(connection, project_id=PROJECT_ID, plan_id=plan["id"], title="Read", module_id=module["id"])
        revision = index_material_revision(connection, material_id, extraction_id)
        chunk_id = connection.execute("SELECT id FROM chunks WHERE revision_id=?", (revision["id"],)).fetchone()[0]
        create_module_source_link(connection, project_id=PROJECT_ID, module_id=module["id"], payload={
            "material_id": material_id, "revision_id": revision["id"], "extraction_id": extraction_id, "chunk_id": chunk_id,
        })
        save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-01-01", target_minutes=30)
        create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date="2026-01-01", planned_minutes=30)
        _activate(connection, plan["id"])
        append_study_progress_event(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], event_type="started")
        assert soft_delete_material(connection, material_id) is True

        summary = rhythm_summary(connection, project_id=PROJECT_ID, plan_id=plan["id"], local_date="2026-01-01")
        assert summary["source_warning_count"] == 1
        assert summary["item_projection"] == {"pending_count": 0, "in_progress_count": 1, "completed_count": 0, "skipped_count": 0}
        assert summary["buckets"][0]["planned_minutes"] == 30
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 1


def test_rhythm_write_lock_fails_without_partial_state_and_succeeds_after_retry(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        plan, [item] = _seed_plan(connection)
        save_rhythm_settings(connection, project_id=PROJECT_ID, plan_id=plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-01-01", target_minutes=20)

    holder = sqlite3.connect(database, timeout=0)
    holder.execute("PRAGMA foreign_keys=ON")
    holder.execute("BEGIN IMMEDIATE")
    try:
        with connect(database) as blocked:
            with pytest.raises(sqlite3.OperationalError):
                create_rhythm_allocation(blocked, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date="2026-01-01", planned_minutes=20)
    finally:
        holder.rollback()
        holder.close()

    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM rhythm_allocations").fetchone()[0] == 0
        retried = create_rhythm_allocation(connection, project_id=PROJECT_ID, plan_id=plan["id"], item_id=item["id"], local_date="2026-01-01", planned_minutes=20)
        assert retried["planned_minutes"] == 20
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0
