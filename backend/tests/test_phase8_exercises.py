from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def test_exercise_types_deterministic_grading_and_answer_key_privacy(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        exercise_set = api.post("/api/study/exercise-sets", json={"title": "Practice"})
        assert exercise_set.status_code == 201
        set_id = exercise_set.json()["id"]
        multiple = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "2+2?", "options": ["3", "4"], "answer_key": 1
        })
        assert multiple.status_code == 201
        item = multiple.json()
        assert item["status"] == "draft"
        assert "answer_key" not in item and "answer_key_json" not in item
        assert api.post(f"/api/study/exercises/{item['id']}/confirm").status_code == 200
        correct = api.post(f"/api/study/exercises/{item['id']}/attempts", json={"answer": 1})
        wrong = api.post(f"/api/study/exercises/{item['id']}/attempts", json={"answer": 0})
        assert correct.json()["is_correct"] is True and correct.json()["grading_status"] == "deterministic"
        assert wrong.json()["is_correct"] is False
        true_false = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "true_false", "prompt": "Sky is blue", "answer_key": True
        }).json()
        assert api.post(f"/api/study/exercises/{true_false['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/exercises/{true_false['id']}/attempts", json={"answer": True}).json()["is_correct"] is True
        short = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "short_answer", "prompt": "Explain", "answer_key": "reference"
        }).json()
        assert api.post(f"/api/study/exercises/{short['id']}/confirm").status_code == 200
        pending = api.post(f"/api/study/exercises/{short['id']}/attempts", json={"answer": "my answer"})
        assert pending.json()["grading_status"] == "pending_review" and pending.json()["score"] is None
        assert "answer_key" not in api.get(f"/api/study/exercise-sets/{set_id}").text
        history = api.get(f"/api/study/exercises/{item['id']}/attempts")
        assert history.status_code == 200
        assert [entry["is_correct"] for entry in history.json()] == [True, False]
        assert "answer_json" not in history.text


def test_exercise_schema_and_state_boundaries(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        set_id = api.post("/api/study/exercise-sets", json={"title": "Boundaries"}).json()["id"]
        bad = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "bad", "options": ["one"], "answer_key": 0
        })
        assert bad.status_code == 400 and bad.json()["detail"] == "invalid_exercise_schema"
        valid = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "true_false", "prompt": "T", "answer_key": True
        }).json()
        assert api.post(f"/api/study/exercises/{valid['id']}/attempts", json={"answer": True}).status_code == 404
        assert api.post(f"/api/study/exercises/{valid['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/exercises/{valid['id']}/attempts", json={"answer": "bad"}).status_code == 400


def test_exercise_edit_transitions_and_ai_source_lifecycle(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        set_id = api.post("/api/study/exercise-sets", json={"title": "Lifecycle"}).json()["id"]
        draft = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "Q", "options": ["A", "B"], "answer_key": 0,
        }).json()
        changed = api.patch(f"/api/study/exercises/{draft['id']}", json={
            "prompt": "Changed", "options": ["A", "B"], "answer_key": 1,
        })
        assert changed.status_code == 200 and changed.json()["edited_by_user"] is True
        assert api.post(f"/api/study/exercises/{draft['id']}/reject").status_code == 200
        assert api.post(f"/api/study/exercises/{draft['id']}/confirm").status_code == 409
        assert api.post(f"/api/study/exercises/{draft['id']}/archive").status_code == 200

        material = api.post("/api/materials", files={"file": ("source.txt", b"trusted exercise source", "text/plain")}).json()
        material_id = material["material_id"]
        indexed = api.post(f"/api/materials/{material_id}/ai-index").json()
        revision_id = indexed["revision_id"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            chunk = db.execute("SELECT id, text FROM chunks WHERE material_id=?", (material_id,)).fetchone()
        ai = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "true_false", "prompt": "Trusted?", "answer_key": True,
            "exercise_kind": "ai_generated", "source_revision": revision_id,
            "citations": [{"citation_key": "exercise-source", "chunk_id": chunk["id"], "quote": chunk["text"]}],
        })
        assert ai.status_code == 201
        exercise_id = ai.json()["id"]
        assert api.delete(f"/api/materials/{material_id}").status_code == 204
        assert api.post(f"/api/study/exercises/{exercise_id}/confirm").status_code == 409
        lifecycle = api.get(f"/api/study/exercise-sets/{set_id}").json()["exercises"]
        sourced = next(item for item in lifecycle if item["id"] == exercise_id)
        assert sourced["citations"][0]["status"] == "source_deleted"
        assert api.post(f"/api/materials/{material_id}/restore").status_code == 200
        assert api.post(f"/api/study/exercises/{exercise_id}/confirm").status_code == 200


def test_exercise_create_rolls_back_when_citation_write_fails(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as api:
        set_id = api.post("/api/study/exercise-sets", json={"title": "Rollback"}).json()["id"]
        material = api.post("/api/materials", files={"file": ("citation.txt", b"transaction source", "text/plain")}).json()
        indexed = api.post(f"/api/materials/{material['material_id']}/ai-index").json()
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            chunk = db.execute("SELECT id, text FROM chunks WHERE material_id=?", (material["material_id"],)).fetchone()
            db.execute("CREATE TRIGGER exercise_citation_abort BEFORE INSERT ON exercise_citations BEGIN SELECT RAISE(ABORT, 'test'); END")
            db.commit()
        failed = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "true_false", "prompt": "Transaction?", "answer_key": True,
            "exercise_kind": "ai_generated", "source_revision": indexed["revision_id"],
            "citations": [{"citation_key": "transaction", "chunk_id": chunk["id"], "quote": chunk["text"]}],
        })
        assert failed.status_code == 500 and failed.json()["detail"] == "exercise_create_failed"
        assert api.get(f"/api/study/exercise-sets/{set_id}").json()["exercises"] == []


def test_exercise_schema_provenance_and_backup_restart(tmp_path: Path):
    from app.backup import backup_data, restore_backup

    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    with TestClient(create_app(AppConfig(data_root=source))) as api:
        material = api.post("/api/materials", files={"file": ("backup.txt", b"backup source", "text/plain")})
        assert material.status_code == 201
        set_id = api.post("/api/study/exercise-sets", json={"title": "Persist"}).json()["id"]
        duplicate = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "Duplicate", "options": ["same", "Same"], "answer_key": 0,
        })
        assert duplicate.status_code == 400 and duplicate.json()["detail"] == "invalid_exercise_schema"
        ai_without_source = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "short_answer", "prompt": "Why?", "answer_key": "because", "exercise_kind": "ai_generated",
        })
        assert ai_without_source.status_code == 400 and ai_without_source.json()["detail"] == "citation_invalid"
        user_citation_without_revision = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "short_answer", "prompt": "Source?", "answer_key": "reference",
            "citations": [{"citation_key": "bad", "chunk_id": "chunk_missing", "quote": "x"}],
        })
        assert user_citation_without_revision.status_code == 400
        exercise = api.post(f"/api/study/exercise-sets/{set_id}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "Persist?", "options": ["yes", "no"], "answer_key": 0,
        }).json()
        assert api.post(f"/api/study/exercises/{exercise['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/exercises/{exercise['id']}/attempts", json={"answer": 0}).status_code == 201
    assert backup_data(source, backup)["status"] == "complete"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with TestClient(create_app(AppConfig(data_root=restored))) as api:
        restored_exercise = api.get(f"/api/study/exercise-sets/{set_id}").json()["exercises"][0]
        assert restored_exercise["id"] == exercise["id"] and "answer_key" not in str(restored_exercise)
        assert len(api.get(f"/api/study/exercises/{exercise['id']}/attempts").json()) == 1
