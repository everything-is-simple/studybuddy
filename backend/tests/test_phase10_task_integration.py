from __future__ import annotations

import sys
import threading
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cli import main as cli_main
from app.config import AppConfig
from app.embedding import FakeEmbeddingProvider
from app.main import create_app
from app.repository import claim_operation_task, connect
from app.task_handlers import build_task_runner


def _client(root: Path, *, model_revision: str = "1") -> TestClient:
    return TestClient(create_app(AppConfig(
        data_root=root, max_upload_bytes=4096, embedding_provider_id="fake",
        embedding_model_revision=model_revision,
    )))


def _upload(api: TestClient, body: bytes = b"Phase ten embedding task source.") -> dict[str, object]:
    response = api.post("/api/materials", files={"file": ("source.txt", body, "text/plain")})
    assert response.status_code == 201
    return response.json()


def _queue(api: TestClient, material_id: str, key: str | None = None) -> dict[str, object]:
    headers = {"Idempotency-Key": key} if key else {}
    response = api.post(f"/api/materials/{material_id}/ai-index/tasks", headers=headers)
    assert response.status_code == 202, response.text
    return response.json()


def test_embedding_task_queue_runs_explicitly_and_keeps_legacy_index_synchronous(tmp_path: Path):
    with _client(tmp_path) as api:
        source = _upload(api)
        # Existing endpoint retains its synchronous result contract.
        legacy = api.post(f"/api/materials/{source['material_id']}/ai-index")
        assert legacy.status_code == 200 and legacy.json()["status"] == "ready"

        queued = _queue(api, str(source["material_id"]), "phase10-key")
        assert queued["status"] == "queued"
        assert queued["task_kind"] == "embedding_index"
        assert queued["replay"] is False
        assert {"input_fingerprint", "idempotency_key_fingerprint", "stored_path", "lease_expires_at"}.isdisjoint(queued)
        assert api.get(f"/api/tasks/{queued['task_id']}").json()["status"] == "queued"

        runner = build_task_runner(api.app.state.config)
        assert runner.run_once() is True
        complete = api.get(f"/api/tasks/{queued['task_id']}").json()
        assert complete["status"] == "succeeded"
        assert complete["progress_percent"] == 100
        assert complete["output_artifact_id"] == legacy.json()["revision_id"]
        assert complete["attempt_count"] == 1
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM embeddings WHERE status='ready'").fetchone()[0] >= 1
            assert connection.execute("SELECT COUNT(*) FROM operation_tasks WHERE operation_id=?", (queued["operation_id"],)).fetchone()[0] == 1


def test_embedding_task_idempotency_replay_and_provider_configuration_mismatch(tmp_path: Path):
    with _client(tmp_path) as api:
        source = _upload(api)
        first = _queue(api, str(source["material_id"]), "same-key")
        replay = _queue(api, str(source["material_id"]), "same-key")
        assert replay["task_id"] == first["task_id"] and replay["replay"] is True
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM operation_tasks").fetchone()[0] == 1

    with _client(tmp_path, model_revision="changed") as changed:
        conflict = changed.post(f"/api/materials/{source['material_id']}/ai-index/tasks", headers={"Idempotency-Key": "same-key"})
        assert conflict.status_code == 409
        assert conflict.json() == {"detail": "embedding_index_idempotency_mismatch"}


def test_embedding_task_failure_retry_cancel_and_source_lifecycle_are_safe(tmp_path: Path, monkeypatch):
    with _client(tmp_path) as api:
        source = _upload(api)
        queued = _queue(api, str(source["material_id"]))

        def unavailable(_config):
            from app.embedding import EmbeddingError
            raise EmbeddingError("embedding_provider_timeout")

        monkeypatch.setattr("app.task_handlers._embedding_provider", unavailable)
        runner = build_task_runner(api.app.state.config)
        assert runner.run_once() is True
        failed = api.get(f"/api/tasks/{queued['task_id']}").json()
        assert failed["status"] == "failed" and failed["error_code"] == "embedding_provider_timeout"
        monkeypatch.undo()
        retried = api.post(f"/api/tasks/{queued['task_id']}/retry")
        assert retried.status_code == 200 and retried.json()["status"] == "queued"
        assert build_task_runner(api.app.state.config).run_once() is True
        assert api.get(f"/api/tasks/{queued['task_id']}").json()["attempt_count"] == 2

        cancel_source = _upload(api, b"cancel source")
        cancel_task = _queue(api, str(cancel_source["material_id"]))
        cancelled = api.post(f"/api/tasks/{cancel_task['task_id']}/cancel")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        assert build_task_runner(api.app.state.config).run_once() is False

        lifecycle_source = _upload(api, b"source lifecycle task")
        lifecycle_task = _queue(api, str(lifecycle_source["material_id"]))
        entered, release = threading.Event(), threading.Event()
        provider = FakeEmbeddingProvider()

        class BlockingProvider:
            provider_id = provider.provider_id
            model_id = provider.model_id
            model_revision = provider.model_revision
            dimensions = provider.dimensions
            encoding = provider.encoding

            def embed(self, texts):
                entered.set()
                assert release.wait(3)
                return provider.embed(texts)

        monkeypatch.setattr("app.task_handlers._embedding_provider", lambda _config: BlockingProvider())
        running = build_task_runner(api.app.state.config)
        thread = threading.Thread(target=running.run_once)
        thread.start()
        assert entered.wait(3)
        assert api.delete(f"/api/materials/{lifecycle_source['material_id']}").status_code == 204
        release.set()
        thread.join(3)
        stale = api.get(f"/api/tasks/{lifecycle_task['task_id']}").json()
        assert stale["status"] == "failed" and stale["error_code"] == "source_stale"
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM embeddings e JOIN chunks c ON c.id=e.chunk_id WHERE c.material_id=? AND e.status='ready'",
                (lifecycle_source["material_id"],),
            ).fetchone()[0] == 0


def test_operator_cli_marks_inherited_active_embedding_task_stale_without_execution(tmp_path: Path):
    with _client(tmp_path) as api:
        source = _upload(api, b"stale cli source")
        queued = _queue(api, str(source["material_id"]))
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        claim_operation_task(
            connection, task_id=str(queued["task_id"]), attempt_id="attempt_cli_recovery", lease_seconds=60,
        )
    assert cli_main(["run-tasks", "--data-root", str(tmp_path), "--once"]) == 0
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        assert tuple(connection.execute(
            "SELECT status,error_code FROM operation_tasks WHERE id=?", (queued["task_id"],)
        ).fetchone()) == ("stale", "task_recovery_required")
        assert connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0


def test_embedding_task_running_cancel_and_operator_cli_are_explicit(tmp_path: Path, monkeypatch):
    with _client(tmp_path) as api:
        source = _upload(api, b"running cancellation source")
        queued = _queue(api, str(source["material_id"]))
        entered, release = threading.Event(), threading.Event()
        provider = FakeEmbeddingProvider()

        class BlockingProvider:
            provider_id = provider.provider_id
            model_id = provider.model_id
            model_revision = provider.model_revision
            dimensions = provider.dimensions
            encoding = provider.encoding

            def embed(self, texts):
                entered.set()
                assert release.wait(3)
                return provider.embed(texts)

        monkeypatch.setattr("app.task_handlers._embedding_provider", lambda _config: BlockingProvider())
        runner = build_task_runner(api.app.state.config)
        thread = threading.Thread(target=runner.run_once)
        thread.start()
        assert entered.wait(3)
        assert api.post(f"/api/tasks/{queued['task_id']}/cancel").json()["status"] == "cancel_requested"
        release.set()
        thread.join(3)
        assert api.get(f"/api/tasks/{queued['task_id']}").json()["status"] == "cancelled"
        monkeypatch.undo()

        cli_source = _upload(api, b"cli source")
        cli_task = _queue(api, str(cli_source["material_id"]))
    assert cli_main(["run-tasks", "--data-root", str(tmp_path), "--once"]) == 0
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT status FROM operation_tasks WHERE id=?", (cli_task["task_id"],)).fetchone()[0] == "succeeded"
