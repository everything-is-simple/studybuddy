from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def _indexed_material(api: TestClient, name: str, text: str) -> str:
    uploaded = api.post("/api/materials", files={"file": (name, text.encode(), "text/plain")})
    assert uploaded.status_code == 201
    material_id = uploaded.json()["material_id"]
    assert api.post(f"/api/materials/{material_id}/ai-index").status_code == 200
    return material_id


def _table_counts(root: Path) -> dict[str, int]:
    tables = (
        "study_decks", "study_cards", "card_citations", "card_reviews",
        "exercise_sets", "exercises", "exercise_citations", "exercise_attempts",
        "ai_operations", "retrieval_runs", "retrieval_hits",
    )
    with connect(root / "studybuddy.sqlite3") as db:
        return {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}


def test_phase8_backup_restore_preserves_artifacts_history_operations_and_source_lifecycle(tmp_path: Path):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    with TestClient(create_app(AppConfig(data_root=source, ai_provider_id="fake"))) as api:
        retained_material = _indexed_material(
            api, "retained.txt", "A retained source supports a valid generated artifact."
        )
        purged_material = _indexed_material(
            api, "purged.txt", "A purged source must remain unavailable after restore."
        )
        deck_id = api.post("/api/study/decks", json={"title": "Backup cards"}).json()["id"]
        exercise_set_id = api.post("/api/study/exercise-sets", json={"title": "Backup exercises"}).json()["id"]

        generated_card = api.post(f"/api/study/decks/{deck_id}/generate", json={
            "topic": "retained source", "material_ids": [retained_material], "count": 1,
        })
        assert generated_card.status_code == 200
        ready_card_id = generated_card.json()["artifacts"][0]["id"]
        assert api.post(f"/api/study/cards/{ready_card_id}/confirm").status_code == 200
        assert api.post(f"/api/study/cards/{ready_card_id}/reviews", json={"result": "good"}).status_code == 201

        rejected_card = api.post(f"/api/study/decks/{deck_id}/cards", json={"front": "Reject", "back": "Later"}).json()
        assert api.post(f"/api/study/cards/{rejected_card['id']}/reject").status_code == 200
        assert api.post(f"/api/study/cards/{rejected_card['id']}/archive").status_code == 200

        unavailable_card = api.post(f"/api/study/decks/{deck_id}/generate", json={
            "topic": "purged source", "material_ids": [purged_material], "count": 1,
        })
        assert unavailable_card.status_code == 200
        unavailable_card_id = unavailable_card.json()["artifacts"][0]["id"]

        generated_exercise = api.post(f"/api/study/exercise-sets/{exercise_set_id}/generate", json={
            "topic": "retained source", "material_ids": [retained_material], "count": 1,
            "exercise_type": "multiple_choice",
        })
        assert generated_exercise.status_code == 200
        ready_exercise_id = generated_exercise.json()["artifacts"][0]["id"]
        assert api.post(f"/api/study/exercises/{ready_exercise_id}/confirm").status_code == 200
        assert api.post(f"/api/study/exercises/{ready_exercise_id}/attempts", json={"answer": 0}).status_code == 201

        short_answer = api.post(f"/api/study/exercise-sets/{exercise_set_id}/exercises", json={
            "exercise_type": "short_answer", "prompt": "Explain", "answer_key": "reference",
        }).json()
        assert api.post(f"/api/study/exercises/{short_answer['id']}/confirm").status_code == 200
        assert api.post(f"/api/study/exercises/{short_answer['id']}/attempts", json={"answer": "student answer"}).json()["grading_status"] == "pending_review"

        rejected_exercise = api.post(f"/api/study/exercise-sets/{exercise_set_id}/exercises", json={
            "exercise_type": "true_false", "prompt": "Reject", "answer_key": True,
        }).json()
        assert api.post(f"/api/study/exercises/{rejected_exercise['id']}/reject").status_code == 200
        assert api.post(f"/api/study/exercises/{rejected_exercise['id']}/archive").status_code == 200

        assert api.delete(f"/api/materials/{purged_material}").status_code == 204
        assert api.post(f"/api/materials/{purged_material}/purge").status_code == 200
        cards = api.get(f"/api/study/decks/{deck_id}").json()["cards"]
        assert next(card for card in cards if card["id"] == unavailable_card_id)["citations"][0]["status"] == "source_unavailable"

    expected_counts = _table_counts(source)
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert _table_counts(restored) == expected_counts

    # Startup and normal reads are diagnostic/read-only for restored Phase 8 data:
    # they neither regenerate artifacts nor repair unavailable citations to valid.
    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as api:
        cards = api.get(f"/api/study/decks/{deck_id}").json()["cards"]
        by_id = {card["id"]: card for card in cards}
        assert by_id[ready_card_id]["status"] == "ready"
        assert by_id[rejected_card["id"]]["status"] == "archived"
        assert by_id[unavailable_card_id]["citations"][0]["status"] == "source_unavailable"

        exercises = api.get(f"/api/study/exercise-sets/{exercise_set_id}").json()["exercises"]
        exercises_by_id = {exercise["id"]: exercise for exercise in exercises}
        assert exercises_by_id[ready_exercise_id]["status"] == "ready"
        assert exercises_by_id[rejected_exercise["id"]]["status"] == "archived"
        assert "answer_key" not in str(exercises)
        assert len(api.get(f"/api/study/exercises/{ready_exercise_id}/attempts").json()) == 1
        pending = api.get(f"/api/study/exercises/{short_answer['id']}/attempts").json()
        assert pending[0]["grading_status"] == "pending_review"
        assert "answer_json" not in str(pending)

    assert _table_counts(restored) == expected_counts
    with connect(restored / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM ai_operations WHERE operation_type LIKE 'generate_%' AND status='succeeded'").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM card_reviews WHERE card_id=?", (ready_card_id,)).fetchone()[0] == 1
