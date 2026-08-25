from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app


def _client(root: Path, *, project_id: str = "default") -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, project_id=project_id)))


def _exercise(client: TestClient, *, kind: str = "true_false") -> dict:
    exercise_set = client.post("/api/study/exercise-sets", json={"title": "API exercises"})
    assert exercise_set.status_code == 201
    if kind == "multiple_choice":
        payload = {"exercise_type": kind, "prompt": "Choose", "options": ["no", "yes"], "answer_key": 1}
    elif kind == "short_answer":
        payload = {"exercise_type": kind, "prompt": "Explain", "answer_key": "because"}
    else:
        payload = {"exercise_type": kind, "prompt": "True?", "answer_key": True}
    created = client.post(f"/api/study/exercise-sets/{exercise_set.json()['id']}/exercises", json=payload)
    assert created.status_code == 201
    confirmed = client.post(f"/api/study/exercises/{created.json()['id']}/confirm")
    assert confirmed.status_code == 200
    return confirmed.json()


def test_s3_api_round_trip_privacy_and_idempotency(tmp_path: Path):
    with _client(tmp_path) as client:
        exercise = _exercise(client, kind="multiple_choice")
        created = client.post(
            "/api/study/practice-sessions",
            json={"title": "Timed API", "exercise_ids": [exercise["id"]], "duration_seconds": 60},
        )
        assert created.status_code == 201
        session = created.json()
        assert session["status"] == "draft"
        assert "answer_key_json" not in str(session)
        assert "answer_json" not in str(session)
        started = client.post(f"/api/study/practice-sessions/{session['id']}/start")
        assert started.status_code == 200
        item_id = started.json()["items"][0]["id"]
        submitted = client.post(
            f"/api/study/practice-sessions/{session['id']}/items/{item_id}/submit",
            headers={"Idempotency-Key": "api-submit-1"}, json={"answer": 0},
        )
        assert submitted.status_code == 200
        assert submitted.json()["is_correct"] is False
        assert "answer_json" not in submitted.text and "answer_key" not in submitted.text
        replay = client.post(
            f"/api/study/practice-sessions/{session['id']}/items/{item_id}/submit",
            headers={"Idempotency-Key": "api-submit-1"}, json={"answer": 0},
        )
        assert replay.status_code == 200 and replay.json()["replay"] is True
        mismatch = client.post(
            f"/api/study/practice-sessions/{session['id']}/items/{item_id}/submit",
            headers={"Idempotency-Key": "api-submit-1"}, json={"answer": 1},
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["detail"] == "practice_submission_idempotency_mismatch"
        result = client.get(f"/api/study/practice-sessions/{session['id']}/result")
        assert result.status_code == 200
        assert result.json()["summary"]["incorrect_count"] == 1
        assert "answer_key_json" not in result.text
        assert client.post(f"/api/study/practice-sessions/{session['id']}/finish").status_code == 200


def test_s4_api_review_mark_feedback_redo_and_scope(tmp_path: Path):
    with _client(tmp_path, project_id="project_api") as client:
        short = _exercise(client, kind="short_answer")
        session = client.post("/api/study/practice-sessions", json={"title": "Review", "exercise_ids": [short["id"]]}).json()
        assert client.post(f"/api/study/practice-sessions/{session['id']}/start").status_code == 200
        item_id = client.get(f"/api/study/practice-sessions/{session['id']}").json()["items"][0]["id"]
        attempt = client.post(f"/api/study/practice-sessions/{session['id']}/items/{item_id}/submit", json={"answer": "private answer"})
        assert attempt.status_code == 200
        review = client.post(f"/api/study/attempts/{attempt.json()['id']}/review", json={"decision": "incorrect", "feedback": "Review safely"})
        assert review.status_code == 200
        assert "answer_json" not in review.text and "answer_key" not in review.text
        mistakes = client.get("/api/study/mistakes")
        assert mistakes.status_code == 200 and len(mistakes.json()) == 1
        mistake_id = mistakes.json()[0]["id"]
        detail = client.get(f"/api/study/mistakes/{mistake_id}")
        assert detail.status_code == 200 and "private answer" not in detail.text
        feedback = client.post(f"/api/study/mistakes/{mistake_id}/feedback", json={"event_kind": "user_correction", "content": "Correction"})
        assert feedback.status_code == 201
        redo = client.post(f"/api/study/mistakes/{mistake_id}/redo")
        assert redo.status_code == 200 and redo.json()["id"] != session["id"]
        assert client.get("/api/study/weak-points").status_code == 200

    with _client(tmp_path / "other", project_id="other") as other:
        assert other.get(f"/api/study/mistakes/{mistake_id}").status_code == 404
        assert other.post(f"/api/study/attempts/{attempt.json()['id']}/review", json={"decision": "correct"}).status_code == 404


def test_s5_api_goal_session_result_and_invalid_boundaries(tmp_path: Path):
    with _client(tmp_path) as client:
        exercise = _exercise(client, kind="true_false")
        goal = client.post("/api/study/cram-goals", json={"title": "Exam", "target_date": "2026-06-01", "target_exercise_count": 1})
        assert goal.status_code == 201
        goal_id = goal.json()["id"]
        invalid = client.post(f"/api/study/cram-goals/{goal_id}/completed")
        assert invalid.status_code == 409
        assert client.post(f"/api/study/cram-goals/{goal_id}/active").status_code == 200
        empty = client.post(f"/api/study/cram-goals/{goal_id}/sessions", json={"title": "Empty", "exercise_ids": []})
        assert empty.status_code == 400
        session = client.post(f"/api/study/cram-goals/{goal_id}/sessions", json={"title": "Cram", "exercise_ids": [exercise["id"]]})
        assert session.status_code == 201
        session_id = session.json()["id"]
        assert client.post(f"/api/study/practice-sessions/{session_id}/start").status_code == 200
        item_id = client.get(f"/api/study/practice-sessions/{session_id}").json()["items"][0]["id"]
        assert client.post(f"/api/study/practice-sessions/{session_id}/items/{item_id}/submit", json={"answer": False}).status_code == 200
        assert client.post(f"/api/study/practice-sessions/{session_id}/finish").status_code == 200
        result = client.get(f"/api/study/cram-goals/{goal_id}/sessions/{session_id}/result")
        assert result.status_code == 200
        assert result.json()["summary"]["mistake_count"] == 1
        assert client.post(f"/api/study/cram-goals/{goal_id}/completed").status_code == 200
        malformed = client.post("/api/study/cram-goals", json={"title": "bad", "target_date": "not-a-date", "target_exercise_count": 1})
        assert malformed.status_code == 400
        assert "traceback" not in malformed.text.lower()
        assert "stored_path" not in malformed.text
