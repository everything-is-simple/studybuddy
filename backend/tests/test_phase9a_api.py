from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def client_for(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, project_id="default")))


def test_phase9a_api_minimal_plan_and_progress_path(tmp_path: Path):
    with client_for(tmp_path) as client:
        goal = client.post("/api/study/goals", json={"title": "Learn SQLite", "description": "Core"})
        assert goal.status_code == 201
        goal_body = goal.json()
        assert goal_body["status"] == "active"
        assert "stored_path" not in goal_body

        module = client.post("/api/study/modules", json={"title": "Transactions"})
        assert module.status_code == 201
        plan = client.post("/api/study/plans", json={"goal_id": goal_body["id"], "title": "Plan"})
        assert plan.status_code == 201
        plan_body = plan.json()
        item = client.post(f"/api/study/plans/{plan_body['id']}/items", json={"title": "Understand WAL"})
        assert item.status_code == 201
        item_body = item.json()
        assert item_body["status"] == "pending"
        assert client.post(f"/api/study/plans/{plan_body['id']}/confirm").status_code == 200
        assert client.post(f"/api/study/plans/{plan_body['id']}/activate").status_code == 200
        progress = client.post(
            f"/api/study/plans/{plan_body['id']}/items/{item_body['id']}/progress",
            headers={"Idempotency-Key": "unused"},
            json={"event_type": "started", "event_id": "progress_api_1", "metadata": {"source": "ui"}},
        )
        assert progress.status_code == 201
        assert progress.json()["event"]["event_type"] == "started"
        replay = client.post(
            f"/api/study/plans/{plan_body['id']}/items/{item_body['id']}/progress",
            json={"event_type": "started", "event_id": "progress_api_1"},
        )
        assert replay.status_code == 201
        conflict = client.post(
            f"/api/study/plans/{plan_body['id']}/items/{item_body['id']}/progress",
            json={"event_type": "completed", "event_id": "progress_api_1"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"] == "study_progress_event_duplicate"
        detail = client.get(f"/api/study/plans/{plan_body['id']}")
        assert detail.status_code == 200
        assert detail.json()["progress"]["in_progress_count"] == 1
        assert "raw" not in detail.text.lower()


def test_phase9a_api_boundary_and_project_scope(tmp_path: Path):
    with client_for(tmp_path) as client:
        assert client.post("/api/study/goals", json={"title": "   "}).status_code == 400
        assert client.get("/api/study/goals/not-an-id-that-is-too-long-" * 10).status_code == 404
        missing = client.post("/api/study/plans", json={"goal_id": "goal_missing", "title": "Plan"})
        assert missing.status_code == 409
        assert missing.json()["detail"] == "study_plan_goal_invalid"
        assert client.post("/api/study/sources/refresh", json={"path": "private"}).status_code == 200
        assert "private" not in client.get("/api/study/sources").text
        assert client.get("/api/study/sources?module_id=m&plan_id=p").status_code == 400
        assert client.post("/api/study/plans/plan_missing/confirm").status_code == 404
        assert client.post("/api/study/plans/plan_missing/items/item_missing/progress", json={"event_type": "cancelled"}).status_code == 404


def test_phase9a_api_dependency_cycle_and_state_errors(tmp_path: Path):
    with client_for(tmp_path) as client:
        goal = client.post("/api/study/goals", json={"title": "Goal"}).json()
        plan = client.post("/api/study/plans", json={"goal_id": goal["id"], "title": "Plan"}).json()
        first = client.post(f"/api/study/plans/{plan['id']}/items", json={"title": "First"}).json()
        second = client.post(f"/api/study/plans/{plan['id']}/items", json={"title": "Second"}).json()
        assert client.post(
            f"/api/study/plans/{plan['id']}/dependencies",
            json={"predecessor_item_id": first["id"], "successor_item_id": second["id"]},
        ).status_code == 201
        cycle = client.post(
            f"/api/study/plans/{plan['id']}/dependencies",
            json={"predecessor_item_id": second["id"], "successor_item_id": first["id"]},
        )
        assert cycle.status_code == 409
        assert cycle.json()["detail"] == "study_plan_dependency_cycle"
        active_before_confirm = client.post(f"/api/study/plans/{plan['id']}/activate")
        assert active_before_confirm.status_code == 409
        assert active_before_confirm.json()["detail"] == "study_plan_confirm_required"
        malformed = client.post(f"/api/study/plans/{plan['id']}/items", json={"title": "x", "position": -1})
        assert malformed.status_code == 400
        assert "traceback" not in malformed.text.lower()


def test_phase9a_api_source_unavailable_is_safe(tmp_path: Path):
    with client_for(tmp_path) as client:
        goal = client.post("/api/study/goals", json={"title": "Goal"}).json()
        plan = client.post("/api/study/plans", json={"goal_id": goal["id"], "title": "Plan"}).json()
        item = client.post(f"/api/study/plans/{plan['id']}/items", json={"title": "Item"}).json()
        bad = client.post(
            f"/api/study/plans/{plan['id']}/items/{item['id']}/sources",
            json={"material_id": "missing", "revision_id": "revision_missing", "chunk_id": "chunk_missing"},
        )
        assert bad.status_code == 409
        assert bad.json()["detail"] == "study_source_invalid"
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM plan_item_source_links").fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0
