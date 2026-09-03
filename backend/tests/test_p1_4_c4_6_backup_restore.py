from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.restore_acceptance import verify_restored_data


def seed_representative_data(root: Path) -> dict[str, str]:
    with TestClient(create_app(AppConfig(data_root=root, ai_provider_id="fake"))) as client:
        first = client.post("/api/materials", files={"file": ("c4-6.txt", b"C4-6 durable source", "text/plain")})
        assert first.status_code == 201
        second = client.post("/api/materials", files={"file": ("c4-6-copy.txt", b"C4-6 durable source", "text/plain")})
        assert second.status_code == 201
        materials = client.get("/api/materials").json()
        assert len(materials) == 2
        assert client.delete(f"/api/materials/{materials[0]['id']}").status_code == 204
        goal = client.post("/api/study/goals", json={"title": "C4-6 goal"}).json()
        plan = client.post("/api/study/plans", json={"goal_id": goal["id"], "title": "C4-6 plan"}).json()
        item = client.post(f"/api/study/plans/{plan['id']}/items", json={"title": "C4-6 item"}).json()
        assert client.post(f"/api/study/plans/{plan['id']}/confirm").status_code == 200
        assert client.post(f"/api/study/plans/{plan['id']}/activate").status_code == 200
        assert client.post(f"/api/study/plans/{plan['id']}/items/{item['id']}/progress", json={
            "event_type": "started", "metadata": {}
        }).status_code == 201
        assert client.put(f"/api/study/plans/{plan['id']}/rhythm", json={
            "cadence": "daily", "timezone": "Asia/Shanghai", "period_start": "2026-03-01", "target_minutes": 30
        }).status_code == 200
    with sqlite3.connect(root / "studybuddy.sqlite3") as db:
        db.execute(
            "INSERT INTO ai_operations(id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) VALUES (?,?,?,?,?,?,?)",
            ("c4_6_operation", "embedding_index", "queued", "default", "c4-6-fingerprint", 0, "2026-03-01T00:00:00+00:00"),
        )
        db.execute(
            "INSERT INTO operation_tasks(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) VALUES (?,?,?,?,?,?,0,'queued',0,1,?,?)",
            ("c4_6_task", "default", "c4_6_operation", "embedding_index", "queued", "c4-6-fingerprint", "2026-03-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00"),
        )
    return {"plan_id": plan["id"], "item_id": item["id"]}


def snapshot(root: Path, plan_id: str) -> dict[str, object]:
    with sqlite3.connect(root / "studybuddy.sqlite3") as db:
        tables = ("materials", "study_plans", "study_plan_items", "study_progress_events", "rhythm_settings", "operation_tasks")
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        version = db.execute("PRAGMA user_version").fetchone()[0]
    with TestClient(create_app(AppConfig(data_root=root, ai_provider_id="fake"))) as client:
        return {"counts": counts, "version": version,
                "plans": client.get("/api/study/plans").json(),
                "tasks": client.get("/api/tasks").json(),
                "trend": client.get(f"/api/study/plans/{plan_id}/rhythm/weekly-trend?local_date=2026-03-08").json()}


def test_c4_6_backup_verify_restore_new_root_and_two_normal_restarts(tmp_path: Path):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    ids = seed_representative_data(source)
    before = snapshot(source, ids["plan_id"])
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert verify_restored_data(restored)["status"] == "passed"
    after_restore = snapshot(restored, ids["plan_id"])
    assert after_restore == before
    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/readiness").status_code == 200
    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/readiness").status_code == 200
    assert snapshot(restored, ids["plan_id"]) == before
    with sqlite3.connect(restored / "studybuddy.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 14
        assert db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 14
