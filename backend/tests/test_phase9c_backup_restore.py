from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import BackupError, backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.repository import connect
from app.restore_acceptance import verify_restored_data


def _client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, ai_provider_id="fake")))


def _fixture(root: Path) -> dict[str, str]:
    with _client(root) as api:
        exercise_set = api.post("/api/study/exercise-sets", json={"title": "Restore 9C"}).json()
        exercise = api.post(f"/api/study/exercise-sets/{exercise_set['id']}/exercises", json={
            "exercise_type": "multiple_choice", "prompt": "Choose", "options": ["wrong", "right"], "answer_key": 1,
        }).json()
        assert api.post(f"/api/study/exercises/{exercise['id']}/confirm").status_code == 200
        practice = api.post("/api/study/practice-sessions", json={
            "title": "Restore practice", "exercise_ids": [exercise["id"]], "duration_seconds": 60,
        }).json()
        assert api.post(f"/api/study/practice-sessions/{practice['id']}/start").status_code == 200
        item_id = api.get(f"/api/study/practice-sessions/{practice['id']}").json()["items"][0]["id"]
        attempt = api.post(f"/api/study/practice-sessions/{practice['id']}/items/{item_id}/submit", json={"answer": 0}).json()
        assert api.post(f"/api/study/practice-sessions/{practice['id']}/finish").status_code == 200
        goal = api.post("/api/study/cram-goals", json={
            "title": "Restore cram", "target_date": "2026-06-01", "target_exercise_count": 1,
        }).json()
        assert api.post(f"/api/study/cram-goals/{goal['id']}/active").status_code == 200
        cram = api.post(f"/api/study/cram-goals/{goal['id']}/sessions", json={
            "title": "Restore cram session", "exercise_ids": [exercise["id"]],
        }).json()
        with connect(root / "studybuddy.sqlite3") as connection:
            connection.execute("UPDATE practice_session_items SET citation_status='stale' WHERE session_id=?", (cram["id"],))
            connection.commit()
        return {"practice": practice["id"], "cram": cram["id"], "goal": goal["id"], "attempt": attempt["id"]}


def _ensure_original_fixture(root: Path) -> None:
    root.joinpath("originals").mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root / "studybuddy.sqlite3") as connection:
        rows = connection.execute("SELECT source_sha256,stored_path FROM materials").fetchall()
    fixture = b"retained 9C original fixture"
    fixture_hash = hashlib.sha256(fixture).hexdigest()
    with sqlite3.connect(root / "studybuddy.sqlite3") as connection:
        for digest, stored_path in rows:
            target = Path(stored_path)
            if not target.is_absolute():
                target = root / target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fixture)
            connection.execute("UPDATE materials SET source_sha256=? WHERE stored_path=?", (fixture_hash, str(stored_path)))
        connection.commit()


def _counts(database: Path) -> dict[str, int]:
    tables = ("practice_sessions", "practice_session_items", "exercise_attempts", "exercise_attempt_reviews",
              "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals")
    with sqlite3.connect(database) as connection:
        return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}


def test_phase9c_backup_restore_preserves_facts_statuses_and_non_repair(tmp_path: Path, monkeypatch):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    ids = _fixture(source)
    _ensure_original_fixture(source)
    before = _counts(source / "studybuddy.sqlite3")
    before_bytes = (source / "studybuddy.sqlite3").read_bytes()
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    manifest = (backup / "manifest.json").read_text(encoding="utf-8")
    assert json.loads(manifest)["database"]["schema_version"] == 13
    assert str(source) not in manifest and "stored_path" not in manifest

    def forbidden(*_args, **_kwargs):
        raise AssertionError("provider_or_repair_called_during_restore")

    monkeypatch.setattr("app.main.provider_registry", forbidden)
    monkeypatch.setattr("app.main.index_material_revision", forbidden)
    monkeypatch.setattr("app.repository.index_material_revision", forbidden)
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    acceptance = verify_restored_data(restored)
    assert acceptance["status"] == "passed"
    assert acceptance["checks"]["study"]["counts"]["practice_sessions"] == before["practice_sessions"]
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM exercise_attempts").fetchone()[0] == before["exercise_attempts"]
    assert _counts(restored / "studybuddy.sqlite3") == before
    assert (source / "studybuddy.sqlite3").read_bytes() == before_bytes

    with _client(restored) as api:
        practice = api.get(f"/api/study/practice-sessions/{ids['practice']}")
        assert practice.status_code == 200
        assert practice.json()["status"] == "finished"
        cram = api.get(f"/api/study/practice-sessions/{ids['cram']}")
        assert cram.status_code == 200
        assert cram.json()["items"][0]["citation_status"] == "stale"
        assert "answer_key_json" not in cram.text and "answer_json" not in cram.text
        assert api.get(f"/api/study/cram-goals/{ids['goal']}/sessions/{ids['cram']}/result").status_code == 200

    assert _counts(restored / "studybuddy.sqlite3") == before


def test_phase9c_backup_restore_failure_and_target_boundaries(tmp_path: Path):
    source = tmp_path / "source"
    _fixture(source)
    _ensure_original_fixture(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    target = tmp_path / "target"
    target.mkdir()
    (target / "existing").write_text("occupied", encoding="utf-8")
    with pytest.raises(BackupError, match="restore_target_not_empty"): 
        restore_backup(target, backup, confirm=True)
    with pytest.raises(BackupError, match="restore_confirmation_required"):
        restore_backup(tmp_path / "unconfirmed", backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"]["schema_version"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupError, match="backup_schema_version_mismatch"):
        verify_backup(backup)
