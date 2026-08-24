from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect, index_material_revision


def _client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, ai_provider_id="fake")))


def _ready_material(api: TestClient, name: str = "lifecycle-note.txt") -> tuple[str, str]:
    response = api.post(
        "/api/materials",
        files={"file": (name, b"A controlled lifecycle source establishes cited note evidence.", "text/plain")},
    )
    assert response.status_code == 201
    material = response.json()
    indexed = api.post(f"/api/materials/{material['material_id']}/ai-index")
    assert indexed.status_code == 200
    return material["material_id"], material["extraction_id"]


def _active_rhythm_plan(api: TestClient) -> tuple[str, str]:
    goal = api.post("/api/study/goals", json={"title": "Lifecycle goal"}).json()
    plan = api.post("/api/study/plans", json={"goal_id": goal["id"], "title": "Lifecycle rhythm"}).json()
    item = api.post(f"/api/study/plans/{plan['id']}/items", json={"title": "Keep completed history"}).json()
    assert api.post(f"/api/study/plans/{plan['id']}/confirm").status_code == 200
    assert api.post(f"/api/study/plans/{plan['id']}/activate").status_code == 200
    assert api.put(f"/api/study/plans/{plan['id']}/rhythm", json={
        "cadence": "weekly", "timezone": "UTC", "period_start": "2026-01-05", "target_minutes": 120,
    }).status_code == 200
    assert api.post(f"/api/study/plans/{plan['id']}/rhythm/allocations", json={
        "item_id": item["id"], "local_date": "2026-01-06", "planned_minutes": 30,
    }).status_code == 201
    assert api.post(f"/api/study/plans/{plan['id']}/items/{item['id']}/progress", json={"event_type": "completed"}).status_code == 201
    return plan["id"], item["id"]


def _generated_confirmed_note(api: TestClient, material_id: str) -> tuple[str, str]:
    module = api.post("/api/study/modules", json={"title": "Lifecycle note module"}).json()
    generated = api.post("/api/study/notes/generate", headers={"Idempotency-Key": "lifecycle-note"}, json={
        "topic": "controlled lifecycle source", "material_id": material_id,
    })
    assert generated.status_code == 200
    note = generated.json()["note"]
    assert api.post(f"/api/study/notes/{note['id']}/modules/{module['id']}").status_code == 201
    edited = api.patch(f"/api/study/notes/{note['id']}", json={
        "title": "User edited cited history",
        "blocks": [{"block_kind": block["block_kind"], "content": block["content"] + " edited"} for block in note["blocks"]],
    })
    assert edited.status_code == 200 and edited.json()["user_edited"] == 1
    assert api.post(f"/api/study/notes/{note['id']}/confirm").status_code == 200
    return note["id"], module["id"]


def _statuses(note: dict[str, object]) -> set[str]:
    return {source["status"] for block in note["blocks"] for source in block["sources"]}


def test_phase9b_note_rhythm_lifecycle_requires_explicit_refresh_and_keeps_history(tmp_path: Path):
    with _client(tmp_path) as api:
        material_id, extraction_id = _ready_material(api)
        plan_id, item_id = _active_rhythm_plan(api)
        note_id, module_id = _generated_confirmed_note(api, material_id)
        before = api.get(f"/api/study/notes/{note_id}").json()
        assert before["status"] == "confirmed" and before["user_edited"] == 1
        assert _statuses(before) == {"valid"}

        assert api.delete(f"/api/materials/{material_id}").status_code == 204
        deleted = api.get(f"/api/study/notes/{note_id}").json()
        assert deleted["status"] == "confirmed" and deleted["user_edited"] == 1
        assert _statuses(deleted) == {"source_deleted"}
        plan = api.get(f"/api/study/plans/{plan_id}").json()
        assert plan["status"] == "active" and plan["progress"]["completed_count"] == 1
        assert api.get(f"/api/study/plans/{plan_id}/rhythm/summary?local_date=2026-01-05").json()["buckets"][0]["planned_minutes"] == 30

        assert api.post(f"/api/materials/{material_id}/restore").status_code == 200
        # Read/startup-equivalent requests do not promote a deleted source.
        assert _statuses(api.get(f"/api/study/notes/{note_id}").json()) == {"source_deleted"}
        assert api.post("/api/study/notes/sources/refresh", json={"note_id": note_id}).status_code == 200
        assert _statuses(api.get(f"/api/study/notes/{note_id}").json()) == {"valid"}

        # A new current revision makes the retained identity stale; it is never rewritten.
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            connection.execute(
                "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
                "SELECT 'extraction_9b_lifecycle_new',material_id,parser_id,parser_version,status,text || ' revised','[]',created_at,NULL "
                "FROM extractions WHERE id=?", (extraction_id,)
            )
            connection.execute(
                "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) "
                "SELECT 'span_9b_lifecycle_new','extraction_9b_lifecycle_new',ordinal,span_kind,label,text || ' revised' "
                "FROM text_spans WHERE extraction_id=?", (extraction_id,)
            )
            assert connection.execute(
                "SELECT COUNT(*) FROM extractions WHERE id=? AND material_id=?",
                ("extraction_9b_lifecycle_new", material_id),
            ).fetchone()[0] == 1
            index_material_revision(connection, material_id, "extraction_9b_lifecycle_new")
        stale = api.get(f"/api/study/notes/{note_id}").json()
        assert stale["status"] == "confirmed" and _statuses(stale) == {"stale"}
        assert api.post(f"/api/study/modules/{module_id}/archive").status_code == 200
        assert api.get(f"/api/study/notes/{note_id}").json()["archived_module_warning_count"] == 1
        assert api.post(f"/api/study/notes/{note_id}/archive").status_code == 200

        assert api.delete(f"/api/materials/{material_id}").status_code == 204
        assert api.post(f"/api/materials/{material_id}/purge").status_code == 200
        unavailable = api.get(f"/api/study/notes/{note_id}").json()
        assert unavailable["status"] == "archived" and unavailable["user_edited"] == 1
        assert _statuses(unavailable) == {"source_unavailable"}
        assert unavailable["modules"][0]["id"] == module_id
        exported = api.get(f"/api/study/notes/{note_id}/export?format=json")
        assert exported.status_code == 200
        assert "lifecycle-note.txt" not in exported.text
        assert "stored_path" not in exported.text and "original_name" not in exported.text
        exported_note = exported.json()["note"]
        assert all("text" not in source and "material_name" not in source
                   for block in exported_note["blocks"] for source in block["sources"])
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM study_progress_events WHERE item_id=?", (item_id,)).fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM rhythm_allocations WHERE plan_id=?", (plan_id,)).fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM note_block_source_links WHERE note_id=?", (note_id,)).fetchone()[0] == len(unavailable["blocks"])
