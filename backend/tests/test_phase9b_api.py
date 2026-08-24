from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def _client(root: Path, *, project_id: str = "default", provider: str | None = "fake") -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, project_id=project_id, ai_provider_id=provider)))


def _plan(client: TestClient) -> tuple[dict, dict]:
    goal = client.post("/api/study/goals", json={"title": "API goal"})
    assert goal.status_code == 201
    plan = client.post("/api/study/plans", json={"goal_id": goal.json()["id"], "title": "API plan"})
    assert plan.status_code == 201
    item = client.post(f"/api/study/plans/{plan.json()['id']}/items", json={"title": "API item"})
    assert item.status_code == 201
    return plan.json(), item.json()


def _indexed_material(client: TestClient) -> tuple[str, str]:
    uploaded = client.post(
        "/api/materials", files={"file": ("api-source.txt", b"A controlled source supports rhythm and notes.", "text/plain")}
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    indexed = client.post(f"/api/materials/{body['material_id']}/ai-index")
    assert indexed.status_code == 200
    return body["material_id"], indexed.json()["revision_id"]


def test_s1_rhythm_api_round_trip_and_safe_failures(tmp_path: Path):
    with _client(tmp_path) as client:
        plan, item = _plan(client)
        plan_id, item_id = plan["id"], item["id"]

        absent = client.get(f"/api/study/plans/{plan_id}/rhythm")
        assert absent.status_code == 200
        assert absent.json() == {"status": "not_configured", "plan_id": plan_id, "settings": None}

        saved = client.put(
            f"/api/study/plans/{plan_id}/rhythm",
            json={"cadence": "weekly", "timezone": "Asia/Shanghai", "period_start": "2026-01-05", "target_minutes": 120},
        )
        assert saved.status_code == 200
        assert saved.json()["settings"]["timezone"] == "Asia/Shanghai"

        allocation = client.post(
            f"/api/study/plans/{plan_id}/rhythm/allocations",
            json={"item_id": item_id, "local_date": "2026-01-06", "planned_minutes": 30},
        )
        assert allocation.status_code == 201
        allocation_id = allocation.json()["id"]
        duplicate = client.post(
            f"/api/study/plans/{plan_id}/rhythm/allocations",
            json={"item_id": item_id, "local_date": "2026-01-06", "planned_minutes": 30},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "study_rhythm_allocation_duplicate"

        moved = client.patch(
            f"/api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}",
            json={"local_date": "2026-01-07", "planned_minutes": 45},
        )
        assert moved.status_code == 200
        summary = client.get(f"/api/study/plans/{plan_id}/rhythm/summary?local_date=2026-01-05&periods=1")
        assert summary.status_code == 200
        assert summary.json()["buckets"][0]["planned_minutes"] == 45
        assert summary.json()["item_projection"]["pending_count"] == 1
        assert client.get(f"/api/study/plans/{plan_id}/rhythm/export?format=json").status_code == 200
        assert client.delete(f"/api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}").status_code == 204

        invalid = client.put(
            f"/api/study/plans/{plan_id}/rhythm",
            json={"cadence": "daily", "timezone": "GMT+8", "period_start": "2026-02-30", "target_minutes": -1},
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"] in {"study_rhythm_invalid_timezone", "study_rhythm_invalid_date", "study_rhythm_target_out_of_range"}
        assert "traceback" not in invalid.text.lower()
        assert "sql" not in invalid.text.lower()


def test_s2_user_note_api_edit_protection_modules_and_exports(tmp_path: Path):
    with _client(tmp_path) as client:
        module = client.post("/api/study/modules", json={"title": "API module"})
        assert module.status_code == 201
        note = client.post("/api/study/notes", json={"title": "My note", "blocks": [{"content": "Initial"}]})
        assert note.status_code == 201
        note_id = note.json()["id"]
        block_id = note.json()["blocks"][0]["id"]
        assert client.post(f"/api/study/notes/{note_id}/modules/{module.json()['id']}").status_code == 201
        patched = client.patch(
            f"/api/study/notes/{note_id}",
            json={"title": "Edited", "blocks": [{"block_kind": "heading", "content": "Heading"}, {"content": "Body"}]},
        )
        assert patched.status_code == 200
        assert patched.json()["user_edited"] == 1
        assert len(patched.json()["blocks"]) == 2
        assert client.post(f"/api/study/notes/{note_id}/confirm").status_code == 200
        protected = client.patch(f"/api/study/notes/{note_id}", json={"title": "Overwrite"})
        assert protected.status_code == 409
        assert protected.json()["detail"] == "study_note_edit_not_allowed"
        exported = client.get(f"/api/study/notes/{note_id}/export?format=markdown")
        assert exported.status_code == 200
        assert "Overwrite" not in exported.text
        assert "stored_path" not in exported.text
        assert client.delete(f"/api/study/notes/{note_id}/blocks/{block_id}").status_code == 409


def test_s2_note_source_generation_lifecycle_and_provider_safe_failure(tmp_path: Path):
    with _client(tmp_path) as client:
        material_id, revision_id = _indexed_material(client)
        generated = client.post(
            "/api/study/notes/generate",
            headers={"Idempotency-Key": "api-note-1"},
            json={"topic": "controlled source", "material_id": material_id, "source_revision": revision_id},
        )
        assert generated.status_code == 200
        note = generated.json()["note"]
        assert note["provenance"] == "ai_generated"
        assert all(block["sources"] and block["sources"][0]["status"] == "valid" for block in note["blocks"])
        replay = client.post(
            "/api/study/notes/generate",
            headers={"Idempotency-Key": "api-note-1"},
            json={"topic": "controlled source", "material_id": material_id, "source_revision": revision_id},
        )
        assert replay.status_code == 200
        assert replay.json().get("replay") is True
        forged = client.post(
            f"/api/study/notes/{note['id']}/blocks/{note['blocks'][0]['id']}/sources",
            json={"material_id": material_id, "revision_id": revision_id, "extraction_id": "forged", "chunk_id": "forged", "citation_key": "ctx-forged", "context_chunk_ids": []},
        )
        assert forged.status_code == 409
        assert forged.json()["detail"] == "study_note_source_invalid"
        assert client.post(f"/api/materials/{material_id}").status_code == 405
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        detail = client.get(f"/api/study/notes/{note['id']}")
        assert detail.status_code == 200
        assert all(source["status"] == "source_deleted" for block in detail.json()["blocks"] for source in block["sources"])
        assert client.post("/api/study/notes/sources/refresh", json={"note_id": note["id"]}).status_code == 200

    with _client(tmp_path / "unconfigured", provider=None) as client:
        material_id, revision_id = _indexed_material(client)
        failed = client.post(
            "/api/study/notes/generate",
            json={"topic": "controlled source", "material_id": material_id, "source_revision": revision_id},
        )
        assert failed.status_code == 503
        assert failed.json()["detail"] == "study_note_provider_not_configured"
        with connect((tmp_path / "unconfigured") / "studybuddy.sqlite3") as connection:
            operation = connection.execute(
                "SELECT status,error_code FROM ai_operations WHERE operation_type='generate_note' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            assert tuple(operation) == ("failed", "study_note_provider_not_configured")
            assert connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 0


def test_api_project_scope_and_malformed_payload_are_safe(tmp_path: Path):
    with _client(tmp_path, project_id="project_api") as client:
        assert client.post("/api/study/notes", json={"title": "x", "blocks": []}).status_code == 409
        assert client.get("/api/study/notes/note_missing").status_code == 404
        assert client.get("/api/study/plans/plan_missing/rhythm").status_code == 404
        assert client.post("/api/study/notes/sources/refresh", json={"note_id": "../../private"}).status_code == 200
        assert "private" not in client.get("/api/study/notes").text
        malformed = client.put("/api/study/plans/plan_missing/rhythm", json={"cadence": "daily"})
        assert malformed.status_code == 422
        assert "traceback" not in malformed.text.lower()
        assert "stored_path" not in malformed.text
