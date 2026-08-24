from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    add_study_plan_dependency,
    append_study_progress_event,
    archive_knowledge_module,
    create_knowledge_module,
    create_learning_goal,
    create_module_source_link,
    create_plan_item_source_link,
    create_study_plan,
    create_study_plan_item,
    get_study_plan,
    list_study_progress_events,
    refresh_study_source_links,
    transition_study_plan,
    update_study_plan_item,
)
from app.repository import connect


def _seed_project(connection: sqlite3.Connection, project_id: str = "project_9a") -> None:
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (project_id, "Phase 9A", "2026-01-01T00:00:00+00:00"),
    )


def _seed_source(connection: sqlite3.Connection, project_id: str = "project_9a") -> tuple[str, str, str]:
    material_id, extraction_id = "material_source", "extraction_source"
    connection.execute(
        "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (material_id, project_id, "source.txt", "a" * 64, "originals/a", "text/plain", "now", "now"),
    )
    connection.execute(
        "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (extraction_id, material_id, "txt", "1", "success", "A source passage for plans.", "[]", "now"),
    )
    connection.execute(
        "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
        ("span_source", extraction_id, 0, "document", "source.txt", "A source passage for plans."),
    )
    return material_id, extraction_id, "span_source"


def _plan(connection: sqlite3.Connection):
    goal = create_learning_goal(connection, project_id="project_9a", title="Learn SQLite")
    plan = create_study_plan(connection, project_id="project_9a", goal_id=goal["id"], title="Plan")
    first = create_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], title="First")
    second = create_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], title="Second")
    return goal, plan, first, second


def test_plan_lifecycle_and_edit_protection(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        goal, plan, first, _ = _plan(connection)
        assert plan["status"] == "draft"
        confirmed = transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="confirmed")
        assert confirmed["status"] == "confirmed"
        edited = update_study_plan_item(
            connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], title="Edited"
        )
        assert edited["title"] == "Edited"
        assert get_study_plan(connection, project_id="project_9a", plan_id=plan["id"])["status"] == "draft"
        active = transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="confirmed")
        active = transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="active")
        assert active["status"] == "active"
        with pytest.raises(ValueError, match="study_plan_edit_not_allowed"):
            update_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], title="No")
        with pytest.raises(ValueError, match="study_plan_invalid_state"):
            transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="draft")


def test_dependency_rejects_self_and_cycles_atomically(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _, plan, first, second = _plan(connection)
        with pytest.raises(ValueError, match="study_plan_dependency_cycle"):
            add_study_plan_dependency(connection, project_id="project_9a", plan_id=plan["id"], predecessor_item_id=first["id"], successor_item_id=first["id"])
        add_study_plan_dependency(connection, project_id="project_9a", plan_id=plan["id"], predecessor_item_id=first["id"], successor_item_id=second["id"])
        third = create_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], title="Third")
        add_study_plan_dependency(connection, project_id="project_9a", plan_id=plan["id"], predecessor_item_id=second["id"], successor_item_id=third["id"])
        with pytest.raises(ValueError, match="study_plan_dependency_cycle"):
            add_study_plan_dependency(connection, project_id="project_9a", plan_id=plan["id"], predecessor_item_id=third["id"], successor_item_id=first["id"])
        assert connection.execute("SELECT COUNT(*) FROM study_plan_dependencies").fetchone()[0] == 2


def test_progress_is_append_only_and_summary_recomputes(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _, plan, first, _ = _plan(connection)
        with pytest.raises(ValueError, match="study_progress_invalid_event"):
            append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="started")
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="confirmed")
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="active")
        started = append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="started", event_id="progress_one")
        assert started["event_type"] == "started"
        replay = append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="started", event_id="progress_one")
        assert replay["id"] == "progress_one"
        append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="completed")
        reopened = append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="reopened")
        assert reopened["event_type"] == "reopened"
        detail = get_study_plan(connection, project_id="project_9a", plan_id=plan["id"])
        assert detail["progress"]["completed_count"] == 0
        assert detail["progress"]["in_progress_count"] == 1
        assert len(list_study_progress_events(connection, project_id="project_9a", plan_id=plan["id"])) == 3


def test_source_link_validates_identity_and_tracks_delete_restore(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, extraction_id, span_id = _seed_source(connection)
        revision = __import__("app.repository", fromlist=["index_material_revision"]).index_material_revision(connection, material_id, extraction_id)
        chunk = connection.execute("SELECT id FROM chunks WHERE revision_id=?", (revision["id"],)).fetchone()
        module = create_knowledge_module(connection, project_id="project_9a", title="Source module")
        link = create_module_source_link(connection, project_id="project_9a", module_id=module["id"], payload={
            "material_id": material_id, "revision_id": revision["id"], "extraction_id": extraction_id,
            "chunk_id": chunk[0], "span_id": span_id,
        })
        assert link["status"] == "valid"
        _, plan, first, _ = _plan(connection)
        item_link = create_plan_item_source_link(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], payload={
            "material_id": material_id, "revision_id": revision["id"], "extraction_id": extraction_id,
            "chunk_id": chunk[0], "span_id": span_id,
        })
        assert item_link["status"] == "valid"
        connection.execute("UPDATE materials SET deleted_at='deleted' WHERE id=?", (material_id,))
        refresh_study_source_links(connection, project_id="project_9a")
        assert connection.execute("SELECT status FROM module_source_links").fetchone()[0] == "source_deleted"
        assert connection.execute("SELECT status FROM plan_item_source_links").fetchone()[0] == "source_deleted"
        with pytest.raises(ValueError, match="study_source_invalid"):
            create_module_source_link(connection, project_id="project_9a", module_id=module["id"], payload={
                "material_id": material_id, "revision_id": revision["id"], "extraction_id": extraction_id,
                "chunk_id": "missing", "span_id": span_id,
            })


def test_progress_failure_rolls_back_event_and_item_projection(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _, plan, first, _ = _plan(connection)
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="confirmed")
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="active")
        connection.execute(
            "CREATE TRIGGER fail_progress_projection BEFORE UPDATE OF status ON study_plan_items "
            "BEGIN SELECT RAISE(ABORT, 'private'); END;"
        )
        with pytest.raises(sqlite3.IntegrityError):
            append_study_progress_event(
                connection, project_id="project_9a", plan_id=plan["id"],
                item_id=first["id"], event_type="started",
            )
        connection.execute("DROP TRIGGER fail_progress_projection")
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0
        assert connection.execute("SELECT status FROM study_plan_items WHERE id=?", (first["id"],)).fetchone()[0] == "pending"


def test_cross_project_references_and_completed_item_are_rejected(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection, "project_9a")
        _seed_project(connection, "project_other")
        other_goal = create_learning_goal(connection, project_id="project_other", title="Other")
        _, plan, first, _ = _plan(connection)
        with pytest.raises(ValueError, match="study_plan_goal_invalid"):
            create_study_plan(connection, project_id="project_9a", goal_id=other_goal["id"], title="Cross")
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="confirmed")
        transition_study_plan(connection, project_id="project_9a", plan_id=plan["id"], target="active")
        append_study_progress_event(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], event_type="completed")
        with pytest.raises(ValueError, match="study_plan_edit_not_allowed"):
            update_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], item_id=first["id"], title="Overwrite")


def test_source_stale_and_unavailable_states_are_not_promoted(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, extraction_id, span_id = _seed_source(connection)
        revision = __import__("app.repository", fromlist=["index_material_revision"]).index_material_revision(connection, material_id, extraction_id)
        chunk = connection.execute("SELECT id FROM chunks WHERE revision_id=?", (revision["id"],)).fetchone()[0]
        module = create_knowledge_module(connection, project_id="project_9a", title="Stale module")
        link = create_module_source_link(connection, project_id="project_9a", module_id=module["id"], payload={
            "material_id": material_id, "revision_id": revision["id"], "extraction_id": extraction_id, "chunk_id": chunk, "span_id": span_id,
        })
        connection.execute("UPDATE chunks SET status='stale' WHERE id=?", (chunk,))
        refresh_study_source_links(connection, project_id="project_9a")
        assert connection.execute("SELECT status FROM module_source_links WHERE id=?", (link["id"],)).fetchone()[0] == "stale"
        connection.execute("DELETE FROM materials WHERE id=?", (material_id,))
        refresh_study_source_links(connection, project_id="project_9a")
        assert connection.execute("SELECT status FROM module_source_links WHERE id=?", (link["id"],)).fetchone()[0] == "source_unavailable"


def test_module_archive_keeps_existing_plan_reference_but_blocks_new_reference(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        module = create_knowledge_module(connection, project_id="project_9a", title="Module")
        archive_knowledge_module(connection, project_id="project_9a", module_id=module["id"])
        _, plan, _, _ = _plan(connection)
        with pytest.raises(ValueError, match="study_plan_item_invalid_payload"):
            create_study_plan_item(connection, project_id="project_9a", plan_id=plan["id"], title="Uses archived", module_id=module["id"])
