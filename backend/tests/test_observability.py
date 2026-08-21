from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backup import BackupError, backup_data, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.startup_preflight import StartupPreflightError
from app.observability import metrics_snapshot


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
        assert client.get("/api/liveness").status_code == 200
        assert client.get("/api/health").status_code == 200
    assert app.state.ready is False


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
