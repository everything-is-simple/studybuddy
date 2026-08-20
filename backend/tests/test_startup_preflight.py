from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig, DEFAULT_MAX_UPLOAD_BYTES, config_from_environment
from app.main import create_app
from app.startup_preflight import StartupPreflightError


def test_normal_and_missing_root_start_safely(tmp_path: Path):
    root = tmp_path / "missing"
    with TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=8))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/materials", files={"file": ("x.txt", b"12345678", "text/plain")}).status_code == 201
    assert root.is_dir() and (root / "studybuddy.sqlite3").is_file()


def test_data_root_regular_file_rejected(tmp_path: Path):
    root = tmp_path / "root-file"
    root.write_bytes(b"keep")
    with pytest.raises(StartupPreflightError, match="data_root_invalid"):
        with TestClient(create_app(AppConfig(data_root=root))):
            pass
    assert root.read_bytes() == b"keep"


def test_originals_root_symlink_rejected_when_supported(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "originals").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(StartupPreflightError, match="originals_root_symlink"):
        with TestClient(create_app(AppConfig(data_root=root))):
            pass
    assert not (outside / "studybuddy.sqlite3").exists()


def test_database_directory_rejected(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "studybuddy.sqlite3").mkdir()
    with pytest.raises(StartupPreflightError, match="database_path_invalid"):
        with TestClient(create_app(AppConfig(data_root=root))):
            pass


def test_invalid_environment_limits_rejected(monkeypatch):
    for value in ("", "0", "-1", "abc", "1.5"):
        monkeypatch.setenv("STUDYBUDDY_MAX_UPLOAD_BYTES", value)
        with pytest.raises(ValueError, match="invalid_max_upload_bytes"):
            config_from_environment()
    monkeypatch.delenv("STUDYBUDDY_MAX_UPLOAD_BYTES", raising=False)
    assert config_from_environment().max_upload_bytes == DEFAULT_MAX_UPLOAD_BYTES
    monkeypatch.setenv("STUDYBUDDY_MAX_UPLOAD_BYTES", "8")
    assert config_from_environment().max_upload_bytes == 8


def test_preflight_order(monkeypatch, tmp_path: Path):
    from app import main
    events: list[str] = []
    monkeypatch.setattr(main, "preflight", lambda config: events.append("preflight"))
    monkeypatch.setattr(main, "connect", lambda path: events.append("connect") or __import__("contextlib").nullcontext())
    monkeypatch.setattr(main, "run_audit", lambda path: events.append("audit"))
    monkeypatch.setattr(main, "reconcile", lambda config: events.append("recovery"))
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        assert client.get("/api/health").status_code == 200
    assert events == ["preflight", "connect", "audit", "recovery"]
