from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.repository import (
    add_study_plan_dependency,
    append_study_progress_event,
    connect,
    create_knowledge_module,
    create_learning_goal,
    create_module_source_link,
    create_plan_item_source_link,
    create_study_plan,
    create_study_plan_item,
    index_material_revision,
    refresh_study_source_links,
    transition_study_plan,
    update_study_plan,
)
from app.restore_acceptance import verify_restored_data


STUDY_TABLES = (
    "learning_goals",
    "knowledge_modules",
    "study_plans",
    "study_plan_items",
    "study_plan_dependencies",
    "study_progress_events",
    "module_source_links",
    "plan_item_source_links",
)
PERSISTED_TABLES = STUDY_TABLES + (
    "material_revisions",
    "chunks",
    "chunk_spans",
    "embeddings",
    "ai_operations",
)


def _upload(client: TestClient, name: str, text: bytes) -> dict[str, object]:
    response = client.post(
        "/api/materials",
        files={"file": (name, text, "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


def _index(connection: sqlite3.Connection, material: dict[str, object]) -> dict[str, object]:
    revision = index_material_revision(
        connection,
        str(material["material_id"]),
        str(material["extraction_id"]),
    )
    chunk = connection.execute(
        "SELECT id FROM chunks WHERE revision_id=? ORDER BY chunk_index,id LIMIT 1",
        (revision["id"],),
    ).fetchone()
    assert chunk is not None
    return {"revision_id": str(revision["id"]), "chunk_id": str(chunk[0])}


def _rows(database: Path, table: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(database) as connection:
        return [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]


def _snapshot(database: Path, tables: tuple[str, ...] = PERSISTED_TABLES) -> dict[str, list[tuple[object, ...]]]:
    return {table: _rows(database, table) for table in tables}


def _plan_details(client: TestClient, plan_ids: list[str]) -> dict[str, dict[str, object]]:
    return {
        plan_id: client.get(f"/api/study/plans/{plan_id}").json()
        for plan_id in plan_ids
    }


def _create_plan(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    goal_id: str,
    title: str,
    status: str,
    module_id: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    plan = create_study_plan(
        connection,
        project_id=project_id,
        goal_id=goal_id,
        title=title,
    )
    item = create_study_plan_item(
        connection,
        project_id=project_id,
        plan_id=str(plan["id"]),
        title=f"{title} item",
        module_id=module_id,
    )
    if status == "draft":
        update_study_plan(
            connection,
            project_id=project_id,
            plan_id=str(plan["id"]),
            title=f"{title} edited",
        )
    elif status == "confirmed":
        plan = transition_study_plan(
            connection,
            project_id=project_id,
            plan_id=str(plan["id"]),
            target="confirmed",
        )
    else:
        transition_study_plan(
            connection,
            project_id=project_id,
            plan_id=str(plan["id"]),
            target="confirmed",
        )
        plan = transition_study_plan(
            connection,
            project_id=project_id,
            plan_id=str(plan["id"]),
            target="active",
        )
        if status == "paused":
            plan = transition_study_plan(
                connection,
                project_id=project_id,
                plan_id=str(plan["id"]),
                target="paused",
            )
        elif status == "completed":
            plan = transition_study_plan(
                connection,
                project_id=project_id,
                plan_id=str(plan["id"]),
                target="completed",
            )
            plan = transition_study_plan(
                connection,
                project_id=project_id,
                plan_id=str(plan["id"]),
                target="archived",
            ) if status == "archived" else plan
    if status == "archived":
        if plan["status"] == "draft":
            plan = transition_study_plan(
                connection,
                project_id=project_id,
                plan_id=str(plan["id"]),
                target="archived",
            )
        else:
            plan = transition_study_plan(
                connection,
                project_id=project_id,
                plan_id=str(plan["id"]),
                target="archived",
            )
    return plan, item


def _build_learning_fixture(root: Path) -> tuple[list[str], dict[str, object]]:
    client = TestClient(create_app(AppConfig(data_root=root, project_id="default")))
    client.__enter__()
    materials = {
        "valid": _upload(client, "valid-source.txt", b"Valid source for a restored study plan."),
        "stale": _upload(client, "stale-source.txt", b"Stale source for a restored study plan."),
        "unavailable": _upload(client, "unavailable-source.txt", b"Unavailable source for a restored study plan."),
    }
    with connect(root / "studybuddy.sqlite3") as connection:
        goal = create_learning_goal(connection, project_id="default", title="Backup goal")
        valid_module = create_knowledge_module(connection, project_id="default", title="Valid module")
        stale_module = create_knowledge_module(connection, project_id="default", title="Stale module")
        unavailable_module = create_knowledge_module(connection, project_id="default", title="Unavailable module")
        valid_source = _index(connection, materials["valid"])
        stale_source = _index(connection, materials["stale"])
        unavailable_source = _index(connection, materials["unavailable"])
        active = create_study_plan(connection, project_id="default", goal_id=goal["id"], title="Active plan")
        first = create_study_plan_item(
            connection, project_id="default", plan_id=active["id"], title="Pending item", module_id=valid_module["id"]
        )
        second = create_study_plan_item(
            connection, project_id="default", plan_id=active["id"], title="Started item", module_id=stale_module["id"]
        )
        third = create_study_plan_item(
            connection, project_id="default", plan_id=active["id"], title="Completed item", module_id=unavailable_module["id"]
        )
        add_study_plan_dependency(
            connection,
            project_id="default",
            plan_id=active["id"],
            predecessor_item_id=first["id"],
            successor_item_id=second["id"],
        )
        create_module_source_link(
            connection, project_id="default", module_id=valid_module["id"],
            payload={"material_id": materials["valid"]["material_id"], **valid_source},
        )
        create_plan_item_source_link(
            connection, project_id="default", plan_id=active["id"], item_id=first["id"],
            payload={"material_id": materials["valid"]["material_id"], **valid_source},
        )
        create_module_source_link(
            connection, project_id="default", module_id=stale_module["id"],
            payload={"material_id": materials["stale"]["material_id"], **stale_source},
        )
        create_module_source_link(
            connection, project_id="default", module_id=unavailable_module["id"],
            payload={"material_id": materials["unavailable"]["material_id"], **unavailable_source},
        )
        transition_study_plan(connection, project_id="default", plan_id=active["id"], target="confirmed")
        transition_study_plan(connection, project_id="default", plan_id=active["id"], target="active")
        append_study_progress_event(
            connection, project_id="default", plan_id=active["id"], item_id=second["id"], event_type="started",
        )
        append_study_progress_event(
            connection, project_id="default", plan_id=active["id"], item_id=third["id"], event_type="completed",
        )
        connection.execute("UPDATE chunks SET status='stale' WHERE revision_id=?", (stale_source["revision_id"],))
        refresh_study_source_links(connection, project_id="default")
        draft, _ = _create_plan(
            connection, project_id="default", goal_id=goal["id"], title="Draft plan", status="draft",
        )
        confirmed, _ = _create_plan(
            connection, project_id="default", goal_id=goal["id"], title="Confirmed plan", status="confirmed",
        )
        paused, _ = _create_plan(
            connection, project_id="default", goal_id=goal["id"], title="Paused plan", status="paused",
        )
        completed, _ = _create_plan(
            connection, project_id="default", goal_id=goal["id"], title="Completed plan", status="completed",
        )
        archived, _ = _create_plan(
            connection, project_id="default", goal_id=goal["id"], title="Archived plan", status="archived",
        )
        plan_ids = [str(active["id"]), str(draft["id"]), str(confirmed["id"]), str(paused["id"]), str(completed["id"]), str(archived["id"])]
        expected = {
            "goal_id": str(goal["id"]),
            "active_plan_id": str(active["id"]),
            "active_item_ids": [str(first["id"]), str(second["id"]), str(third["id"])],
            "plan_ids": plan_ids,
        }
    assert client.delete(f"/api/materials/{materials['unavailable']['material_id']}").status_code == 204
    assert client.post(f"/api/materials/{materials['unavailable']['material_id']}/purge").status_code == 200
    client.__exit__(None, None, None)
    return plan_ids, expected


def test_phase9a_backup_restore_preserves_all_plan_state_and_history(tmp_path: Path):
    source = tmp_path / "source"
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"
    plan_ids, expected = _build_learning_fixture(source)
    database = source / "studybuddy.sqlite3"
    before = _snapshot(database)
    with TestClient(create_app(AppConfig(data_root=source, project_id="default"))) as client:
        before_details = _plan_details(client, plan_ids)
        assert before_details[expected["active_plan_id"]]["status"] == "active"
        assert before_details[expected["active_plan_id"]]["progress"]["completed_count"] == 1
        assert before_details[expected["active_plan_id"]]["progress"]["in_progress_count"] == 1
        assert before_details[expected["active_plan_id"]]["progress"]["source_warning_count"] == 2
        assert {link["status"] for link in before_details[expected["active_plan_id"]]["source_links"]} == {
            "valid", "stale", "source_unavailable",
        }
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert _snapshot(database) == before
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["database"]["schema_version"] == 11
    assert str(source) not in (backup / "manifest.json").read_text(encoding="utf-8")
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert verify_restored_data(restored)["status"] == "passed"
    assert _snapshot(restored / "studybuddy.sqlite3") == before
    with TestClient(create_app(AppConfig(data_root=restored, project_id="default"))) as client:
        after_details = _plan_details(client, plan_ids)
    assert after_details == before_details
    assert after_details[expected["active_plan_id"]]["source_links"]
    assert {link["status"] for link in after_details[expected["active_plan_id"]]["source_links"]} == {
        "valid", "stale", "source_unavailable",
    }


def test_phase9a_restore_verify_and_startup_do_not_repair_or_generate(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"
    plan_ids, expected = _build_learning_fixture(source)
    database = source / "studybuddy.sqlite3"
    before = _snapshot(database)
    before_bytes = database.read_bytes()
    backup_data(source, backup)
    assert verify_backup(backup)["status"] == "valid"
    assert database.read_bytes() == before_bytes

    def fail_provider(*_args, **_kwargs):
        raise AssertionError("provider_called_during_restore_acceptance")

    monkeypatch.setattr("app.main.provider_registry", fail_provider)
    monkeypatch.setattr("app.main.index_material_revision", fail_provider)
    monkeypatch.setattr("app.repository.index_material_revision", fail_provider)
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert verify_restored_data(restored)["status"] == "passed"
    assert _snapshot(restored / "studybuddy.sqlite3") == before
    with TestClient(create_app(AppConfig(data_root=restored, project_id="default"))) as client:
        assert client.get(f"/api/study/plans/{expected['active_plan_id']}").status_code == 200
        assert client.get(f"/api/study/sources?plan_id={expected['active_plan_id']}").status_code == 200
        assert client.get(f"/api/study/plans/{expected['active_plan_id']}/progress").status_code == 200
    assert _snapshot(restored / "studybuddy.sqlite3") == before
    with connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_operations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM plan_item_source_links WHERE status='valid' AND material_id IS NULL"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM module_source_links WHERE status='source_unavailable'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM study_progress_events"
        ).fetchone()[0] == 2
