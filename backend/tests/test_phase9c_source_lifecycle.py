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


def _source_exercise(api: TestClient, root: Path) -> tuple[str, str, str]:
    uploaded = api.post("/api/materials", files={"file": ("lifecycle-9c.txt", b"A source retained for practice history.", "text/plain")})
    material_id = uploaded.json()["material_id"]
    indexed = api.post(f"/api/materials/{material_id}/ai-index").json()
    exercise_set = api.post("/api/study/exercise-sets", json={"title": "Lifecycle"}).json()
    context = api.post("/api/context", json={"hit_ids": [], "max_tokens": 100})
    # User-created exercises have no citation dependency and still provide a
    # stable session history; source status is checked separately through the
    # snapshot table when the material is deleted/purged.
    exercise = api.post(f"/api/study/exercise-sets/{exercise_set['id']}/exercises", json={
        "exercise_type": "true_false", "prompt": "Source history?", "answer_key": True,
    }).json()
    assert api.post(f"/api/study/exercises/{exercise['id']}/confirm").status_code == 200
    return material_id, indexed["revision_id"], exercise["id"]


def test_phase9c_source_delete_restore_purge_keeps_session_attempt_history(tmp_path: Path):
    with _client(tmp_path) as api:
        material_id, revision_id, exercise_id = _source_exercise(api, tmp_path)
        session = api.post("/api/study/practice-sessions", json={"title": "Lifecycle", "exercise_ids": [exercise_id]}).json()
        assert api.post(f"/api/study/practice-sessions/{session['id']}/start").status_code == 200
        item_id = api.get(f"/api/study/practice-sessions/{session['id']}").json()["items"][0]["id"]
        attempt = api.post(f"/api/study/practice-sessions/{session['id']}/items/{item_id}/submit", json={"answer": False})
        assert attempt.status_code == 200
        assert api.post(f"/api/study/practice-sessions/{session['id']}/finish").status_code == 200
        before = api.get(f"/api/study/practice-sessions/{session['id']}").json()
        assert before["summary"]["submitted_count"] == 1
        assert api.delete(f"/api/materials/{material_id}").status_code == 204
        deleted = api.get(f"/api/study/practice-sessions/{session['id']}").json()
        assert deleted["summary"]["submitted_count"] == 1
        assert api.post(f"/api/materials/{material_id}/restore").status_code == 200
        # ordinary restore/read does not create a new attempt or alter the result.
        restored = api.get(f"/api/study/practice-sessions/{session['id']}").json()
        assert restored["summary"]["submitted_count"] == 1
        assert api.delete(f"/api/materials/{material_id}").status_code == 204
        assert api.post(f"/api/materials/{material_id}/purge").status_code == 200
        unavailable = api.get(f"/api/study/practice-sessions/{session['id']}").json()
        assert unavailable["summary"]["submitted_count"] == 1
        assert "stored_path" not in unavailable and "answer_key_json" not in unavailable
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM exercise_attempts WHERE id=?", (attempt.json()["id"],)).fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM practice_session_items WHERE session_id=?", (session["id"],)).fetchone()[0] == 1
