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
from app.repository import connect, index_material_revision
from app.restore_acceptance import verify_restored_data


SNAPSHOT_TABLES = (
    "learning_goals", "knowledge_modules", "study_plans", "study_plan_items", "study_progress_events",
    "notes", "note_blocks", "note_module_links", "note_block_source_links",
    "rhythm_settings", "rhythm_allocations", "ai_operations", "retrieval_runs", "retrieval_hits",
)


def _rows(database: Path, table: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(database) as connection:
        return [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()]


def _snapshot(database: Path) -> dict[str, list[tuple[object, ...]]]:
    return {table: _rows(database, table) for table in SNAPSHOT_TABLES}


def _upload_index(api: TestClient, name: str, text: str) -> tuple[str, str]:
    uploaded = api.post("/api/materials", files={"file": (name, text.encode(), "text/plain")})
    assert uploaded.status_code == 201
    material = uploaded.json()
    indexed = api.post(f"/api/materials/{material['material_id']}/ai-index")
    assert indexed.status_code == 200
    return material["material_id"], material["extraction_id"]


def _generated_note(api: TestClient, material_id: str, topic: str, key: str) -> dict[str, object]:
    result = api.post("/api/study/notes/generate", headers={"Idempotency-Key": key}, json={
        "topic": topic, "material_id": material_id,
    })
    assert result.status_code == 200
    return result.json()["note"]


def _build_fixture(root: Path) -> dict[str, str]:
    with TestClient(create_app(AppConfig(data_root=root, ai_provider_id="fake"))) as api:
        valid_material, _ = _upload_index(api, "valid-9b.txt", "Valid 9B source for history and restore.")
        stale_material, stale_extraction = _upload_index(api, "stale-9b.txt", "Stale 9B source for revision history.")
        unavailable_material, _ = _upload_index(api, "unavailable-9b.txt", "Unavailable 9B source for tombstone history.")

        module = api.post("/api/study/modules", json={"title": "Restored note module"}).json()
        valid_note = _generated_note(api, valid_material, "valid 9B source", "restore-valid-note")
        assert api.post(f"/api/study/notes/{valid_note['id']}/modules/{module['id']}").status_code == 201
        edited = api.patch(f"/api/study/notes/{valid_note['id']}", json={
            "title": "User edited restored note",
            "blocks": [{"block_kind": block["block_kind"], "content": block["content"] + " user edit"}
                       for block in valid_note["blocks"]],
        })
        assert edited.status_code == 200 and edited.json()["user_edited"] == 1
        assert api.post(f"/api/study/notes/{valid_note['id']}/confirm").status_code == 200

        stale_note = _generated_note(api, stale_material, "stale 9B source", "restore-stale-note")
        assert api.post(f"/api/study/notes/{stale_note['id']}/confirm").status_code == 200
        with connect(root / "studybuddy.sqlite3") as connection:
            connection.execute(
                "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
                "SELECT 'extraction_9b_restore_new',material_id,parser_id,parser_version,status,text || ' revised','[]',created_at,NULL "
                "FROM extractions WHERE id=?", (stale_extraction,)
            )
            connection.execute(
                "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) "
                "SELECT 'span_9b_restore_new','extraction_9b_restore_new',ordinal,span_kind,label,text || ' revised' "
                "FROM text_spans WHERE extraction_id=?", (stale_extraction,)
            )
            index_material_revision(connection, stale_material, "extraction_9b_restore_new")
        assert api.get(f"/api/study/notes/{stale_note['id']}").json()["blocks"][0]["sources"][0]["status"] == "stale"
        assert api.post(f"/api/study/notes/{stale_note['id']}/archive").status_code == 200

        unavailable_note = _generated_note(api, unavailable_material, "unavailable 9B source", "restore-unavailable-note")
        assert api.post(f"/api/study/notes/{unavailable_note['id']}/confirm").status_code == 200
        assert api.delete(f"/api/materials/{unavailable_material}").status_code == 204
        assert api.post(f"/api/materials/{unavailable_material}/purge").status_code == 200
        unavailable = api.get(f"/api/study/notes/{unavailable_note['id']}").json()
        assert {source["status"] for block in unavailable["blocks"] for source in block["sources"]} == {"source_unavailable"}

        user_draft = api.post("/api/study/notes", json={
            "title": "User draft survives restore", "blocks": [{"content": "No source is required for this user draft."}],
        }).json()
        goal = api.post("/api/study/goals", json={"title": "Restore rhythm goal"}).json()
        plan = api.post("/api/study/plans", json={"goal_id": goal["id"], "title": "Restore rhythm plan"}).json()
        item = api.post(f"/api/study/plans/{plan['id']}/items", json={"title": "Completed scheduled item"}).json()
        assert api.post(f"/api/study/plans/{plan['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/plans/{plan['id']}/activate").status_code == 200
        assert api.put(f"/api/study/plans/{plan['id']}/rhythm", json={
            "cadence": "weekly", "timezone": "UTC", "period_start": "2026-01-05", "target_minutes": 180,
        }).status_code == 200
        assert api.post(f"/api/study/plans/{plan['id']}/rhythm/allocations", json={
            "item_id": item["id"], "local_date": "2026-01-06", "planned_minutes": 45,
        }).status_code == 201
        assert api.post(f"/api/study/plans/{plan['id']}/items/{item['id']}/progress", json={"event_type": "completed"}).status_code == 201
        return {"valid_note": valid_note["id"], "stale_note": stale_note["id"],
                "unavailable_note": unavailable_note["id"], "user_draft": user_draft["id"],
                "plan": plan["id"], "item": item["id"]}


def test_phase9b_backup_restore_preserves_notes_rhythm_tombstones_and_non_repair(tmp_path: Path, monkeypatch):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    ids = _build_fixture(source)
    before = _snapshot(source / "studybuddy.sqlite3")
    before_bytes = (source / "studybuddy.sqlite3").read_bytes()

    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert (source / "studybuddy.sqlite3").read_bytes() == before_bytes
    manifest_text = (backup / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["database"]["schema_version"] == 12
    assert str(source) not in manifest_text
    assert "Valid 9B source" not in manifest_text and "stored_path" not in manifest_text

    def forbidden(*_args, **_kwargs):
        raise AssertionError("provider_or_index_called_during_restore")

    monkeypatch.setattr("app.main.provider_registry", forbidden)
    monkeypatch.setattr("app.main.index_material_revision", forbidden)
    monkeypatch.setattr("app.repository.index_material_revision", forbidden)
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    acceptance = verify_restored_data(restored)
    assert acceptance["status"] == "passed"
    assert acceptance["checks"]["study"]["counts"]["notes"] == 4
    assert acceptance["checks"]["study"]["rhythm_settings_count"] == 1
    assert acceptance["checks"]["study"]["rhythm_allocations_count"] == 1
    assert _snapshot(restored / "studybuddy.sqlite3") == before

    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as api:
        valid = api.get(f"/api/study/notes/{ids['valid_note']}").json()
        stale = api.get(f"/api/study/notes/{ids['stale_note']}").json()
        unavailable = api.get(f"/api/study/notes/{ids['unavailable_note']}").json()
        draft = api.get(f"/api/study/notes/{ids['user_draft']}").json()
        assert valid["status"] == "confirmed" and valid["user_edited"] == 1
        assert stale["status"] == "archived"
        assert {source["status"] for block in stale["blocks"] for source in block["sources"]} == {"stale"}
        assert {source["status"] for block in unavailable["blocks"] for source in block["sources"]} == {"source_unavailable"}
        assert draft["status"] == "draft" and draft["provenance"] == "user_created"
        summary = api.get(f"/api/study/plans/{ids['plan']}/rhythm/summary?local_date=2026-01-05").json()
        assert summary["buckets"][0]["planned_minutes"] == 45
        assert summary["item_projection"]["completed_count"] == 1
        assert api.get(f"/api/study/plans/{ids['plan']}/progress").json()["events"][0]["event_type"] == "completed"
        assert "stored_path" not in api.get(f"/api/study/notes/{ids['unavailable_note']}/export?format=json").text

    # Startup, ordinary reads, and offline verification did not generate, refresh, or promote retained history.
    assert _snapshot(restored / "studybuddy.sqlite3") == before
    with connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_operations WHERE operation_type='generate_note'").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events WHERE item_id=?", (ids["item"],)).fetchone()[0] == 1
