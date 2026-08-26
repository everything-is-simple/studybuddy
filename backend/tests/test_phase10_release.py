from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cli import main as cli_main
from app.config import AppConfig, config_from_environment
from app.instance_lock import InstanceLock, InstanceLockError
from app.main import create_app
from app.startup_preflight import StartupPreflightError


def clear_release_env(monkeypatch):
    for name in (
        "STUDYBUDDY_DATA_ROOT", "STUDYBUDDY_HOST", "STUDYBUDDY_PORT",
        "STUDYBUDDY_TASK_MAX_CONCURRENCY", "STUDYBUDDY_LOG_LEVEL",
        "STUDYBUDDY_BACKUP_ROOT", "STUDYBUDDY_DEMO_MODE", "STUDYBUDDY_AI_PROVIDER",
        "STUDYBUDDY_AI_MODEL", "STUDYBUDDY_AI_BASE_URL", "STUDYBUDDY_AI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_cli_version_is_stable_and_safe(capsys):
    assert cli_main(["version"]) == 0
    assert capsys.readouterr().out.strip() == '{"application_version": "local-v1", "schema_version": 13}'


def test_default_release_configuration_is_local_safe_and_secret_is_not_repr(monkeypatch):
    clear_release_env(monkeypatch)
    config = config_from_environment()
    assert config.host == "127.0.0.1"
    assert config.port == 8787
    assert config.task_max_concurrency == 1
    assert config.log_level == "INFO"
    assert config.report_delivery_mode == "off"
    assert config.report_delivery_enabled is False
    assert config.ai_provider_id is None
    monkeypatch.setenv("STUDYBUDDY_AI_API_KEY", "private-key")
    config = config_from_environment()
    assert "private-key" not in repr(config)


@pytest.mark.parametrize(
    ("name", "value", "error"),
    [
        ("STUDYBUDDY_HOST", "0.0.0.0", "invalid_host"),
        ("STUDYBUDDY_PORT", "80", "invalid_studybuddy_port"),
        ("STUDYBUDDY_PORT", "70000", "invalid_studybuddy_port"),
        ("STUDYBUDDY_TASK_MAX_CONCURRENCY", "2", "invalid_studybuddy_task_max_concurrency"),
        ("STUDYBUDDY_LOG_LEVEL", "TRACE", "invalid_log_level"),
    ],
)
def test_invalid_release_configuration_fails_before_start(monkeypatch, name, value, error):
    clear_release_env(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=error):
        config_from_environment()


def test_demo_mode_is_explicit_and_cannot_include_real_provider_settings(monkeypatch):
    clear_release_env(monkeypatch)
    monkeypatch.setenv("STUDYBUDDY_DEMO_MODE", "true")
    config = config_from_environment()
    assert config.demo_mode is True and config.ai_provider_id == "fake"
    monkeypatch.setenv("STUDYBUDDY_AI_API_KEY", "secret")
    with pytest.raises(ValueError, match="invalid_demo_configuration"):
        config_from_environment()


def test_backup_root_must_be_outside_data_root(tmp_path: Path):
    with pytest.raises(StartupPreflightError, match="backup_root_inside_data_root"):
        with TestClient(create_app(AppConfig(data_root=tmp_path, backup_root=tmp_path / "backups"))):
            pass


def test_instance_lock_rejects_another_process_and_releases(tmp_path: Path):
    path = tmp_path / ".studybuddy-instance.lock"
    code = (
        "import sys; from app.instance_lock import InstanceLock; "
        "lock=InstanceLock(sys.argv[1]); lock.acquire(); print('locked', flush=True); "
        "sys.stdin.read(); lock.release()"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"
        second = InstanceLock(path)
        with pytest.raises(InstanceLockError, match="data_root_in_use"):
            second.acquire()
    finally:
        if child.stdin is not None:
            child.stdin.close()
        child.wait(timeout=10)
    assert child.returncode == 0


def test_instance_lock_rejects_same_process_and_releases(tmp_path: Path):
    path = tmp_path / ".studybuddy-instance.lock"
    first = InstanceLock(path)
    second = InstanceLock(path)
    first.acquire()
    try:
        with pytest.raises(InstanceLockError, match="data_root_in_use"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_startup_lock_is_released_after_database_failure(tmp_path: Path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "connect", lambda _path: (_ for _ in ()).throw(OSError("private")))
    app = create_app(AppConfig(data_root=tmp_path))
    with pytest.raises(StartupPreflightError, match="database_startup_failed"):
        with TestClient(app):
            pass
    monkeypatch.undo()
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        assert client.get("/api/health").status_code == 200


def test_same_data_root_cannot_have_two_live_app_instances(tmp_path: Path):
    first = TestClient(create_app(AppConfig(data_root=tmp_path)))
    second = TestClient(create_app(AppConfig(data_root=tmp_path)))
    with first:
        assert first.get("/api/liveness").status_code == 200
        with pytest.raises(StartupPreflightError, match="data_root_in_use"):
            with second:
                pass
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as restarted:
        assert restarted.get("/api/health").status_code == 200


def test_operator_scripts_are_local_single_process_and_do_not_accept_secrets():
    start = (ROOT / "scripts" / "start-studybuddy.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "scripts" / "stop-studybuddy.ps1").read_text(encoding="utf-8")
    health = (ROOT / "scripts" / "health-studybuddy.ps1").read_text(encoding="utf-8")
    assert "127.0.0.1" in start and "backend.app" in start and "serve" in start
    assert "--workers" not in start and "--reload" not in start and "-m backend.app serve" in start
    assert "API_KEY" not in start and "API_KEY" not in stop
    assert "api/liveness" in health and "api/health" in health and "api/readiness" in health
