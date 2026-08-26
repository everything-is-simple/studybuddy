from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.migrations.runner import CURRENT_SCHEMA_VERSION, assert_schema_version
from app.repository import connect
from app.task_handlers import build_task_runner


def _config(data_root: Path) -> AppConfig:
    return AppConfig(
        data_root=data_root,
        max_upload_bytes=1_000_000,
        ai_provider_id="fake",
        embedding_provider_id="fake",
        embedding_model_id="fake-embedding-v1",
    )


def _upload(client: TestClient, body: bytes = b"Local release candidate study material.") -> dict[str, object]:
    response = client.post("/api/materials", files={"file": ("release.txt", body, "text/plain")})
    assert response.status_code == 201
    return response.json()


def _exercise(client: TestClient) -> dict[str, object]:
    exercise_set = client.post("/api/study/exercise-sets", json={"title": "Release exercises"})
    assert exercise_set.status_code == 201
    created = client.post(
        f"/api/study/exercise-sets/{exercise_set.json()['id']}/exercises",
        json={"exercise_type": "true_false", "prompt": "Release check", "answer_key": True},
    )
    assert created.status_code == 201
    confirmed = client.post(f"/api/study/exercises/{created.json()['id']}/confirm")
    assert confirmed.status_code == 200
    return confirmed.json()


def _schema_snapshot(data_root: Path) -> tuple[int, list[tuple[int, str]]]:
    with connect(data_root / "studybuddy.sqlite3") as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        history = [tuple(row) for row in connection.execute(
            "SELECT version,name FROM schema_migrations ORDER BY version"
        ).fetchall()]
        assert assert_schema_version(connection) == CURRENT_SCHEMA_VERSION
    return version, history


def test_phase10_gate_j_release_candidate_drill_isolated_and_safe(tmp_path: Path, monkeypatch):
    """Exercise the approved local-v1 release path without real network actions."""
    workspace = Path(tempfile.mkdtemp(prefix="studybuddy-phase10-gatej-", dir=tmp_path))
    data_root = workspace / "data"
    backup_root = workspace / "backup"
    restored_root = workspace / "restored"
    try:
        with TestClient(create_app(_config(data_root))) as client:
            assert client.get("/api/liveness").json() == {"status": "ok"}
            assert client.get("/api/health").json() == {"status": "ok"}
            assert client.get("/api/readiness").json() == {"status": "ready"}

            material = _upload(client)
            material_id = str(material["material_id"])
            assert client.get(f"/api/materials/{material_id}").status_code == 200
            assert client.get("/api/materials", params={"q": "release"}).status_code == 200
            assert client.get(f"/api/materials/{material_id}/original").status_code == 200
            assert client.get(f"/api/materials/{material_id}/text").status_code == 200

            indexed = client.post(f"/api/materials/{material_id}/ai-index")
            assert indexed.status_code == 200
            assert indexed.json()["status"] == "ready"

            answer = client.post(
                "/api/qa/ask",
                json={"question": "release candidate", "material_ids": [material_id]},
            )
            assert answer.status_code == 200
            answer_body = answer.json()
            assert answer_body["status"] == "succeeded"
            citation = answer_body["citations"][0]
            detail = client.get(f"/api/qa/citations/{citation['citation_key']}")
            assert detail.status_code == 200
            assert detail.json()["status"] == "valid"

            deck = client.post("/api/study/decks", json={"title": "Release deck"})
            assert deck.status_code == 201
            card = client.post(
                f"/api/study/decks/{deck.json()['id']}/cards",
                json={"front": "Question", "back": "Answer"},
            )
            assert card.status_code == 201
            exercise = _exercise(client)

            goal = client.post("/api/study/goals", json={"title": "Release goal"})
            assert goal.status_code == 201
            plan = client.post(
                "/api/study/plans", json={"goal_id": goal.json()["id"], "title": "Release plan"}
            )
            assert plan.status_code == 201
            item = client.post(f"/api/study/plans/{plan.json()['id']}/items", json={"title": "Release item"})
            assert item.status_code == 201
            assert client.post(f"/api/study/plans/{plan.json()['id']}/confirm").status_code == 200
            assert client.post(f"/api/study/plans/{plan.json()['id']}/activate").status_code == 200
            assert client.post(
                f"/api/study/plans/{plan.json()['id']}/items/{item.json()['id']}/progress",
                json={"event_type": "started", "event_id": "gate_j_progress"},
            ).status_code == 201

            practice = client.post(
                "/api/study/practice-sessions",
                json={"title": "Release practice", "exercise_ids": [exercise["id"]], "duration_seconds": 60},
            )
            assert practice.status_code == 201
            assert client.post(f"/api/study/practice-sessions/{practice.json()['id']}/start").status_code == 200

            capture = client.post(
                "/api/study/capture-sessions",
                json={"asset_kind": "audio", "original_name": "release.wav", "media_type": "audio/wav"},
            )
            assert capture.status_code == 201
            report = client.post(
                "/api/study/reports",
                json={
                    "report_kind": "daily", "timezone": "UTC",
                    "period_start": "2026-01-01", "period_end": "2026-01-02",
                },
            )
            assert report.status_code == 201
            assert client.get(f"/api/study/reports/{report.json()['id']}/export?format=json").status_code == 200

            queued = client.post(f"/api/materials/{material_id}/ai-index/tasks")
            assert queued.status_code == 202
            queued_body = queued.json()
            assert {"input_fingerprint", "idempotency_key_fingerprint", "stored_path", "lease_expires_at"}.isdisjoint(queued_body)
            runner = build_task_runner(client.app.state.config)
            assert runner.run_once() is True
            complete = client.get(f"/api/tasks/{queued_body['task_id']}").json()
            assert complete["status"] == "succeeded"
            assert complete["progress_percent"] == 100

            retry_material = _upload(client, b"Retryable local release material.")
            retry_task = client.post(f"/api/materials/{retry_material['material_id']}/ai-index/tasks")
            assert retry_task.status_code == 202

            def unavailable(_config: AppConfig):
                from app.embedding import EmbeddingError
                raise EmbeddingError("embedding_provider_timeout")

            monkeypatch.setattr("app.task_handlers._embedding_provider", unavailable)
            assert runner.run_once() is True
            failed = client.get(f"/api/tasks/{retry_task.json()['task_id']}").json()
            assert failed["status"] == "failed"
            assert failed["error_code"] == "embedding_provider_timeout"
            monkeypatch.undo()
            assert client.post(f"/api/tasks/{retry_task.json()['task_id']}/retry").status_code == 200
            assert runner.run_once() is True
            retried = client.get(f"/api/tasks/{retry_task.json()['task_id']}").json()
            assert retried["status"] == "succeeded"
            assert retried["attempt_count"] == 2

            cancelled_material = _upload(client, b"Queued cancellation material.")
            cancelled_task = client.post(f"/api/materials/{cancelled_material['material_id']}/ai-index/tasks")
            assert cancelled_task.status_code == 202
            cancelled = client.post(f"/api/tasks/{cancelled_task.json()['task_id']}/cancel")
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"

            schema_before = _schema_snapshot(data_root)
            assert backup_data(data_root, backup_root)["status"] == "complete"
            assert verify_backup(backup_root)["status"] == "valid"

        assert restore_backup(restored_root, backup_root, confirm=True)["status"] == "restored"
        assert _schema_snapshot(restored_root) == schema_before

        with TestClient(create_app(_config(restored_root))) as restored:
            assert restored.get("/api/health").json() == {"status": "ok"}
            assert restored.get("/api/readiness").json() == {"status": "ready"}
            assert restored.get(f"/api/materials/{material_id}").status_code == 200
            assert restored.get(f"/api/materials/{material_id}/original").status_code == 200
            assert restored.get(f"/api/qa/citations/{citation['citation_key']}").json()["status"] == "valid"
            assert restored.get(f"/api/study/exercises/{exercise['id']}/attempts").status_code == 200
            assert restored.get(f"/api/tasks/{queued_body['task_id']}").json()["status"] == "succeeded"
            assert restored.get(f"/api/tasks/{retry_task.json()['task_id']}").json()["attempt_count"] == 2
            assert restored.get(f"/api/tasks/{cancelled_task.json()['task_id']}").json()["status"] == "cancelled"

        # A second startup proves normal lock release and no automatic task execution.
        with TestClient(create_app(_config(restored_root))) as restarted:
            assert restarted.get("/api/readiness").json() == {"status": "ready"}
            assert restarted.get(f"/api/tasks/{queued_body['task_id']}").json()["status"] == "succeeded"

        environment = {**os.environ, "PYTHONPATH": str(ROOT.parent)}
        diagnostics = subprocess.run(
            [sys.executable, "-m", "backend.app", "diagnostics", "--data-root", str(restored_root)],
            cwd=ROOT.parent, env=environment, text=True, capture_output=True, timeout=30, check=False,
        )
        assert diagnostics.returncode == 0
        diagnostic_body = json.loads(diagnostics.stdout)
        assert diagnostic_body["status"] == "ok"
        assert diagnostic_body["schema_version"] == CURRENT_SCHEMA_VERSION
        assert diagnostic_body["task_counts"]["succeeded"] >= 2
        assert str(workspace) not in diagnostics.stdout
        assert "traceback" not in diagnostics.stdout.lower()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
