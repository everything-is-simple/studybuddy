from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app


def client(root: Path, project_id: str = "default") -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, project_id=project_id)))


def exercise(api: TestClient, title: str, prompt: str, kind: str = "true_false") -> dict:
    set_id = api.post("/api/study/exercise-sets", json={"title": title}).json()["id"]
    payload = {"exercise_type": kind, "prompt": prompt, "answer_key": True}
    if kind == "multiple_choice":
        payload = {"exercise_type": kind, "prompt": prompt, "options": ["no", "yes"], "answer_key": 1}
    response = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json=payload)
    assert response.status_code == 201
    result = api.post(f"/api/study/exercises/{response.json()['id']}/confirm")
    assert result.status_code == 200
    return result.json()


def test_recommendations_empty_and_query_boundaries(tmp_path: Path):
    with client(tmp_path) as api:
        empty = api.get("/api/study/practice-recommendations")
        assert empty.status_code == 200
        assert empty.json()["status"] == "empty"
        assert empty.json()["items"] == []
        assert api.get("/api/study/practice-recommendations?limit=0").status_code == 400
        assert api.get("/api/study/practice-recommendations?limit=21").status_code == 400
        assert api.get("/api/study/practice-recommendations?limit=bad").status_code == 422
        assert api.get("/api/study/practice-recommendations?weak_point=").status_code == 400
        assert api.get("/api/study/practice-recommendations?weak_point=" + "x" * 201).status_code == 400
        assert "practice_recommendation_not_found" not in empty.text


def test_recommendations_are_deterministic_and_respect_limit(tmp_path: Path):
    with client(tmp_path) as api:
        first = exercise(api, "first", "unmatched")
        second = exercise(api, "second", "weak algebra")
        third = exercise(api, "third", "unmatched two")
        wrong = api.post(f"/api/study/exercises/{third['id']}/attempts", json={"answer": False})
        assert wrong.status_code == 201
        before = api.get("/api/study/practice-recommendations?limit=20").json()
        again = api.get("/api/study/practice-recommendations?limit=20").json()
        assert {**before, "generated_at": None} == {**again, "generated_at": None}
        ids = [item["exercise_id"] for item in before["items"]]
        assert set(ids[:2]) == {first["id"], second["id"]}
        assert ids[2] == third["id"]
        assert api.get("/api/study/practice-recommendations?limit=2").json()["items"] == before["items"][:2]
        item = next(value for value in before["items"] if value["exercise_id"] == third["id"])
        assert "recent_incorrect" in item["reason_codes"]
        assert "answer_key_json" not in before.__repr__() and "answer_json" not in before.__repr__()


def test_recommendations_weak_point_filter_and_privacy(tmp_path: Path):
    with client(tmp_path) as api:
        matching = exercise(api, "match", "weak algebra concept")
        exercise(api, "other", "different concept")
        response = api.get("/api/study/practice-recommendations?weak_point=algebra")
        assert response.status_code == 200
        assert [item["exercise_id"] for item in response.json()["items"]] == [matching["id"],]
        item = response.json()["items"][0]
        assert item["weak_point"] == "algebra"
        assert item["reason_labels"]
        forbidden = (response.text + repr(response.json())).lower()
        assert "answer_key" not in forbidden
        assert "answer_json" not in forbidden
        assert "stored_path" not in forbidden
        assert "traceback" not in forbidden


def test_recommendations_exclude_invalid_sources_and_isolate_projects(tmp_path: Path):
    with client(tmp_path, project_id="project-a") as api:
        user = exercise(api, "user", "usable")
        material = api.post("/api/materials", files={"file": ("source.txt", b"source", "text/plain")}).json()
        indexed = api.post(f"/api/materials/{material['material_id']}/ai-index").json()
        with sqlite3.connect(tmp_path / "studybuddy.sqlite3") as db:
            chunk = db.execute("SELECT id, text FROM chunks WHERE material_id=?", (material["material_id"],)).fetchone()
        ai_set = api.post("/api/study/exercise-sets", json={"title": "AI"}).json()["id"]
        ai = api.post(f"/api/study/exercise-sets/{ai_set}/exercises", json={
            "exercise_type": "true_false", "prompt": "sourced", "answer_key": True,
            "exercise_kind": "ai_generated", "source_revision": indexed["revision_id"],
            "citations": [{"citation_key": "source", "chunk_id": chunk[0], "quote": chunk[1]}],
        }).json()
        assert api.post(f"/api/study/exercises/{ai['id']}/confirm").status_code == 200
        assert api.delete(f"/api/materials/{material['material_id']}").status_code == 204
        ids = {item["exercise_id"] for item in api.get("/api/study/practice-recommendations").json()["items"]}
        assert user["id"] in ids and ai["id"] not in ids
        with sqlite3.connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM exercise_attempts").fetchone()[0] == 0
    with client(tmp_path, project_id="project-b") as other:
        assert other.get("/api/study/practice-recommendations").json()["items"] == []
