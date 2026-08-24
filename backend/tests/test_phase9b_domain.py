from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    append_study_progress_event,
    confirm_note,
    connect,
    create_knowledge_module,
    create_learning_goal,
    create_note_source_link,
    create_user_note,
    create_rhythm_allocation,
    create_study_plan,
    create_study_plan_item,
    delete_note_block,
    get_note,
    get_rhythm_settings,
    index_material_revision,
    link_note_module,
    refresh_note_source_links,
    rhythm_summary,
    save_rhythm_settings,
    transition_study_plan,
    update_note,
    update_note_blocks,
    update_rhythm_allocation,
)


def _seed_project(connection: sqlite3.Connection, project_id: str = "project_9b") -> None:
    connection.execute(
        "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
        (project_id, "Phase 9B", "2026-01-01T00:00:00+00:00"),
    )


def _seed_source(connection: sqlite3.Connection, project_id: str = "project_9b") -> tuple[str, str]:
    material_id, extraction_id = "material_0123456789abcdef0123456789abcdef", "extraction_9b_source"
    connection.execute(
        "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (material_id, project_id, "source.txt", "a" * 64, "originals/a", "text/plain", "now", "now"),
    )
    connection.execute(
        "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
        "VALUES (?,?,?,?,?,?,?,?,NULL)",
        (extraction_id, material_id, "txt", "1", "success", "A verified source passage for notes.", "[]", "now"),
    )
    connection.execute(
        "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
        ("span_9b_source", extraction_id, 0, "document", "source.txt", "A verified source passage for notes."),
    )
    revision = index_material_revision(connection, material_id, extraction_id)
    chunk_id = connection.execute(
        "SELECT id FROM chunks WHERE revision_id=? LIMIT 1", (revision["id"],)
    ).fetchone()[0]
    return material_id, str(chunk_id)


def _plan(connection: sqlite3.Connection):
    goal = create_learning_goal(connection, project_id="project_9b", title="Goal")
    plan = create_study_plan(connection, project_id="project_9b", goal_id=goal["id"], title="Plan")
    item = create_study_plan_item(connection, project_id="project_9b", plan_id=plan["id"], title="Read")
    return plan, item


def test_user_note_blocks_modules_and_confirm_protect_user_state(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        module = create_knowledge_module(connection, project_id="project_9b", title="Topic")
        note = create_user_note(connection, project_id="project_9b", title="My note", blocks=[
            {"block_kind": "heading", "content": "Heading"},
            {"block_kind": "text", "content": "User observation"},
        ])
        assert note["status"] == "draft" and len(note["blocks"]) == 2
        link_note_module(connection, project_id="project_9b", note_id=note["id"], module_id=module["id"])
        update_note(connection, project_id="project_9b", note_id=note["id"], title="Edited note")
        updated = update_note_blocks(connection, project_id="project_9b", note_id=note["id"], blocks=[
            {"block_kind": "bullet", "content": "Rewritten"},
        ])
        assert updated["user_edited"] == 1 and len(updated["blocks"]) == 1
        confirmed = confirm_note(connection, project_id="project_9b", note_id=note["id"])
        assert confirmed["status"] == "confirmed"
        with pytest.raises(ValueError, match="study_note_edit_not_allowed"):
            update_note(connection, project_id="project_9b", note_id=note["id"], title="Overwrite")
        with pytest.raises(ValueError, match="study_note_block_edit_not_allowed"):
            delete_note_block(connection, project_id="project_9b", note_id=note["id"], block_id=confirmed["blocks"][0]["id"])


def test_note_source_requires_server_valid_citation_and_refreshes_lifecycle(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        material_id, chunk_id = _seed_source(connection)
        chunk = connection.execute(
            "SELECT revision_id,extraction_id FROM chunks WHERE id=?", (chunk_id,)
        ).fetchone()
        # Use the exact key produced by context assembly, never a client-authored quote.
        from app.repository import assemble_context
        context = assemble_context(connection, project_id="project_9b", hits=[{"chunk_id": chunk_id, "rank": 1}])
        citation_key = context["context_blocks"][0]["citation_key"]
        note = create_user_note(connection, project_id="project_9b", title="Evidence", blocks=[{"content": "Evidence"}])
        bad_payload = {
            "material_id": material_id, "revision_id": chunk["revision_id"],
            "extraction_id": chunk["extraction_id"], "chunk_id": chunk_id, "citation_key": "ctx-forged-key",
        }
        with pytest.raises(ValueError, match="study_note_source_invalid"):
            create_note_source_link(connection, project_id="project_9b", note_id=note["id"], block_id=note["blocks"][0]["id"], payload=bad_payload, context_chunk_ids=[chunk_id])
        with pytest.raises(ValueError, match="study_note_source_invalid"):
            create_note_source_link(connection, project_id="project_9b", note_id=note["id"], block_id=note["blocks"][0]["id"], payload={
                **bad_payload, "citation_key": citation_key,
            }, context_chunk_ids=["chunk_missing"])
        link = create_note_source_link(connection, project_id="project_9b", note_id=note["id"], block_id=note["blocks"][0]["id"], payload={
            **bad_payload, "citation_key": citation_key,
        }, context_chunk_ids=[chunk_id])
        assert link["status"] == "valid"
        connection.execute("UPDATE materials SET deleted_at='deleted' WHERE id=?", (material_id,))
        assert refresh_note_source_links(connection, project_id="project_9b") == 1
        assert connection.execute("SELECT status FROM note_block_source_links WHERE id=?", (link["id"],)).fetchone()[0] == "source_deleted"
        connection.execute("UPDATE materials SET deleted_at=NULL WHERE id=?", (material_id,))
        # Restore/read does not promote. Explicit refresh does, after full identity validation.
        assert connection.execute("SELECT status FROM note_block_source_links WHERE id=?", (link["id"],)).fetchone()[0] == "source_deleted"
        assert refresh_note_source_links(connection, project_id="project_9b") == 1
        assert connection.execute("SELECT status FROM note_block_source_links WHERE id=?", (link["id"],)).fetchone()[0] == "valid"


def test_rhythm_is_deterministic_and_does_not_write_progress(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        plan, item = _plan(connection)
        settings = save_rhythm_settings(connection, project_id="project_9b", plan_id=plan["id"], cadence="weekly", timezone_name="UTC", period_start="2026-01-05", target_minutes=120)
        allocation = create_rhythm_allocation(connection, project_id="project_9b", plan_id=plan["id"], item_id=item["id"], local_date="2026-01-06", planned_minutes=30)
        summary = rhythm_summary(connection, project_id="project_9b", plan_id=plan["id"], local_date="2026-01-05")
        assert summary["buckets"][0]["planned_minutes"] == 30
        assert summary["buckets"][0]["remaining_target_minutes"] == 90
        assert summary["unassigned_item_count"] == 0
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0
        update_rhythm_allocation(connection, project_id="project_9b", plan_id=plan["id"], allocation_id=allocation["id"], planned_minutes=45)
        assert get_rhythm_settings(connection, project_id="project_9b", plan_id=plan["id"])["target_minutes"] == 120
        with pytest.raises(ValueError, match="study_rhythm_allocation_duplicate"):
            create_rhythm_allocation(connection, project_id="project_9b", plan_id=plan["id"], item_id=item["id"], local_date="2026-01-06", planned_minutes=10)
        with pytest.raises(ValueError, match="study_rhythm_invalid_timezone"):
            save_rhythm_settings(connection, project_id="project_9b", plan_id=plan["id"], cadence="daily", timezone_name="GMT+8", period_start="2026-01-01", target_minutes=1)


def test_locked_note_write_rolls_back_without_partial_artifact(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        _seed_project(connection)
    holder = sqlite3.connect(database, timeout=0)
    holder.execute("PRAGMA foreign_keys=ON")
    holder.execute("BEGIN IMMEDIATE")
    try:
        with connect(database) as connection:
            with pytest.raises(sqlite3.OperationalError):
                create_user_note(connection, project_id="project_9b", title="Locked", blocks=[{"content": "Body"}])
    finally:
        holder.rollback()
        holder.close()
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_completed_item_rhythm_is_read_only_and_failed_note_write_rolls_back(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        plan, item = _plan(connection)
        save_rhythm_settings(connection, project_id="project_9b", plan_id=plan["id"], cadence="daily", timezone_name="UTC", period_start="2026-01-01", target_minutes=10)
        transition_study_plan(connection, project_id="project_9b", plan_id=plan["id"], target="confirmed")
        transition_study_plan(connection, project_id="project_9b", plan_id=plan["id"], target="active")
        append_study_progress_event(connection, project_id="project_9b", plan_id=plan["id"], item_id=item["id"], event_type="completed")
        with pytest.raises(ValueError, match="study_rhythm_edit_not_allowed"):
            create_rhythm_allocation(connection, project_id="project_9b", plan_id=plan["id"], item_id=item["id"], local_date="2026-01-01", planned_minutes=10)
        note = create_user_note(connection, project_id="project_9b", title="Rollback", blocks=[{"content": "Before"}])
        connection.execute("CREATE TRIGGER fail_note_block BEFORE UPDATE OF content ON note_blocks BEGIN SELECT RAISE(ABORT, 'private'); END")
        with pytest.raises(sqlite3.IntegrityError):
            update_note_blocks(connection, project_id="project_9b", note_id=note["id"], blocks=[{"content": "After"}])
        connection.execute("DROP TRIGGER fail_note_block")
        assert get_note(connection, project_id="project_9b", note_id=note["id"])["blocks"][0]["content"] == "Before"
