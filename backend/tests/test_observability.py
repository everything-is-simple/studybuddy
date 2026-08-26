from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backup import BackupError, backup_data, restore_backup, verify_backup
from app.cli import main as cli_main
from app.config import AppConfig
from app.diagnostics import DiagnosticError, collect_diagnostics
from app.main import create_app
from app.repository import claim_operation_task, connect, create_operation_task
from app.startup_preflight import StartupPreflightError
from app.observability import emit_event, metrics_snapshot
from app.task_runner import TaskRunner


def test_request_id_is_generated_and_echoed(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        response = client.get("/api/liveness")
        assert response.status_code == 200
        request_id = response.headers.get("x-request-id")
        assert request_id and len(request_id) <= 128


def test_valid_request_id_is_echoed_and_invalid_is_replaced(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        valid = client.get("/api/liveness", headers={"X-Request-ID": "operator-check-1"})
        assert valid.headers["x-request-id"] == "operator-check-1"
        invalid = client.get("/api/liveness", headers={"X-Request-ID": "bad\nvalue"})
        assert invalid.headers["x-request-id"] != "bad\nvalue"
        assert invalid.headers["x-request-id"]


def test_request_id_is_returned_for_404_and_input_failure(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        missing = client.get("/api/materials/not-found")
        assert missing.status_code == 404 and missing.headers.get("x-request-id")
        invalid = client.get("/api/materials?status=invalid")
        assert invalid.status_code == 400 and invalid.headers.get("x-request-id")


def test_metrics_are_process_scoped_low_cardinality_and_imports_counted(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        assert client.post("/api/materials", files={"file": ("one.txt", b"one", "text/plain")}).status_code == 201
        payload = client.get("/api/metrics").json()
    assert payload["scope"] == "process"
    assert payload["persistent"] is False
    assert any(key.startswith("imports.success") for key in payload["counters"])
    assert all("one.txt" not in key and "material_" not in key.split(".") for key in payload["counters"])


def test_liveness_is_available_but_health_requires_ready(tmp_path: Path):
    app = create_app(AppConfig(data_root=tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/liveness").json() == {"status": "ok"}
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/readiness").json() == {"status": "ready"}
    assert app.state.ready is False


def test_runtime_database_failure_is_degraded_but_liveness_stays_available(tmp_path: Path, monkeypatch):
    from app import main
    app = create_app(AppConfig(data_root=tmp_path))
    with TestClient(app) as client:
        monkeypatch.setattr(main, "collect_diagnostics", lambda root: (_ for _ in ()).throw(DiagnosticError("private-path")))
        assert client.get("/api/liveness").json() == {"status": "ok"}
        assert client.get("/api/health").json() == {"detail": "service_degraded"}
        assert client.get("/api/readiness").json() == {
            "detail": {"status": "degraded", "reason": "database_unavailable"}
        }


def test_task_event_correlation_and_duration_metrics_are_safe(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        connection.execute("INSERT INTO projects VALUES ('project_observe','Observe','now')")
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES ('operation_observe','test','queued','project_observe','safe',0,'now')"
        )
        create_operation_task(
            connection, task_id="task_observe", project_id="project_observe", operation_id="operation_observe",
            task_kind="test", input_fingerprint="safe",
        )
    runner = TaskRunner(database)

    def handler(_context):
        emit_event("task_handler_checkpoint", component="task_runner", outcome="running", retry_count=0)

    runner.register("test", handler)
    with caplog.at_level(logging.INFO, logger="studybuddy.observability"):
        assert runner.run_once() is True
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert '"task_id": "task_observe"' in text
    assert '"operation_id": "operation_observe"' in text
    assert '"project_id": "project_observe"' in text
    assert "safe" not in text
    snapshot = metrics_snapshot()
    assert snapshot["task_duration"]["test.succeeded"]["count"] >= 1
    assert "task_observe" not in snapshot["counters"]


def test_diagnostics_is_read_only_safe_and_reports_stale_task(tmp_path: Path, capsys):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        connection.execute("INSERT INTO projects VALUES ('project_diag','Diagnostic','now')")
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES ('operation_diag','test','queued','project_diag','safe',0,'now')"
        )
        create_operation_task(
            connection, task_id="task_diag", project_id="project_diag", operation_id="operation_diag",
            task_kind="test", input_fingerprint="safe",
        )
        connection.commit()
        claim_operation_task(connection, task_id="task_diag", attempt_id="attempt_diag", lease_seconds=60)
        connection.execute("UPDATE operation_tasks SET status='stale',error_code='task_recovery_required' WHERE id='task_diag'")
        connection.execute("UPDATE operation_task_attempts SET status='stale',error_code='task_recovery_required' WHERE id='attempt_diag'")
        connection.execute("UPDATE ai_operations SET status='stale',error_code='task_recovery_required' WHERE id='operation_diag'")
    before = database.read_bytes()
    result = collect_diagnostics(tmp_path)
    assert result["status"] == "degraded"
    assert result["application_version"] == "local-v1"
    assert result["schema_version"] == 13
    assert result["task_counts"]["stale"] == 1
    assert result["recommended_actions"] == ["review_stale_tasks_before_explicit_retry"]
    assert database.read_bytes() == before
    assert cli_main(["diagnostics", "--data-root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert '"status": "degraded"' in output
    assert str(tmp_path) not in output and "safe" not in output and "traceback" not in output.lower()
    assert metrics_snapshot()["counters"].get("diagnostics.degraded", 0) >= 1


def test_diagnostics_failure_has_stable_output_and_no_path(tmp_path: Path, capsys):
    missing = tmp_path / "missing-root"
    assert cli_main(["diagnostics", "--data-root", str(missing)]) == 1
    output = capsys.readouterr().out
    assert output.strip() == '{"status": "failed", "error_code": "diagnostic_database_unavailable"}'
    assert str(missing) not in output and "traceback" not in output.lower()
    assert metrics_snapshot()["counters"].get("diagnostics.failed", 0) >= 1


def test_startup_failure_emits_stable_redacted_event(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    root = tmp_path / "root-file"
    root.write_text("secret-source-text")
    app = create_app(AppConfig(data_root=root))
    with caplog.at_level(logging.INFO, logger="studybuddy.observability"):
        with pytest.raises(StartupPreflightError, match="data_root_invalid"):
            with TestClient(app):
                pass
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "startup_preflight_failed" in text
    assert "data_root_invalid" in text
    assert "secret-source-text" not in text
    assert str(root) not in text
    assert "traceback" not in text.lower()


def test_restore_confirmation_failure_is_safe_and_counted(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    target = tmp_path / "restore-target"
    with pytest.raises(BackupError, match="restore_confirmation_required"):
        with caplog.at_level(logging.INFO, logger="studybuddy.observability"):
            restore_backup(target, tmp_path / "private-backup", confirm=False)
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert str(target) not in text and "private-backup" not in text
    assert "restore_confirmation_required" in text and "traceback" not in text.lower()
    assert metrics_snapshot()["counters"].get("restore.failed", 0) >= 1


def test_backup_verify_failure_does_not_log_path_or_raw_details(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    source = tmp_path / "source"
    with TestClient(create_app(AppConfig(data_root=source))) as client:
        client.post("/api/materials", files={"file": ("one.txt", b"secret-source-text", "text/plain")})
    backup = tmp_path / "backup"
    backup_data(source, backup)
    database = backup / "database.sqlite3"
    database.write_bytes(database.read_bytes() + b"changed")
    with pytest.raises(BackupError, match="backup_database_hash_mismatch"):
        with caplog.at_level(logging.INFO, logger="studybuddy.observability"):
            verify_backup(backup)
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert str(backup) not in text
    assert "secret-source-text" not in text
    assert "traceback" not in text.lower()
