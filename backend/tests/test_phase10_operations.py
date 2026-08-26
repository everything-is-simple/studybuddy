from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import BackupError, backup_data, restore_backup, rotate_backups, upgrade_preflight, verify_backup
from app.cli import main as cli_main
from app.config import AppConfig
from app.main import create_app
from app.migrations import runner


def make_data(root: Path) -> None:
    with TestClient(create_app(AppConfig(data_root=root))) as client:
        response = client.post("/api/materials", files={"file": ("one.txt", b"one", "text/plain")})
        assert response.status_code == 201


def test_verify_rejects_tampered_manifest_database_metadata(tmp_path: Path):
    source = tmp_path / "source"
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"]["size"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupError, match="backup_manifest_invalid"):
        verify_backup(backup)


def test_rotation_is_explicit_and_never_deletes_invalid_or_newest_verified(tmp_path: Path):
    source = tmp_path / "source"
    make_data(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    backups = []
    for name, created_at in (("older", "2026-01-01T00:00:00+00:00"), ("newer", "2026-02-01T00:00:00+00:00")):
        target = backup_root / name
        backup_data(source, target)
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = created_at
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        backups.append(target)
    invalid = backup_root / "invalid"
    invalid.mkdir()
    (invalid / "note.txt").write_text("preserve evidence", encoding="utf-8")

    dry_run = rotate_backups(backup_root, retain=1)
    assert dry_run == {"status": "dry_run", "error_code": None, "verified_count": 2, "retain": 1, "delete_count": 1}
    assert all(path.exists() for path in backups) and invalid.exists()

    result = rotate_backups(backup_root, retain=1, confirm=True)
    assert result["status"] == "rotated" and result["deleted_count"] == 1
    assert not (backup_root / "older").exists()
    assert verify_backup(backup_root / "newer")["status"] == "valid"
    assert invalid.exists()


def test_rotation_requires_positive_retention_and_cli_dry_run_is_safe(tmp_path: Path, capsys):
    root = tmp_path / "backups"
    root.mkdir()
    with pytest.raises(BackupError, match="backup_retention_invalid"):
        rotate_backups(root, retain=0)
    assert cli_main(["rotate-backups", "--backup-root", str(root), "--retain", "1"]) == 0
    output = capsys.readouterr().out
    assert output.strip() == '{"status": "dry_run", "error_code": null, "verified_count": 0, "retain": 1, "delete_count": 0}'
    assert str(root) not in output


def test_upgrade_preflight_requires_matching_verified_backup_and_is_non_mutating(tmp_path: Path):
    source = tmp_path / "source"
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    database = source / "studybuddy.sqlite3"
    before = database.read_bytes()

    result = upgrade_preflight(source, backup)
    assert result == {
        "status": "ready", "error_code": None, "database_schema_version": 13,
        "backup_schema_version": 13, "target_schema_version": 13,
        "migration_required": False, "backup_verified": True,
    }
    assert database.read_bytes() == before
    assert cli_main(["upgrade-preflight", "--data-root", str(source), "--backup", str(backup)]) == 0

    other = tmp_path / "other"
    make_data(other)
    other_backup = tmp_path / "other-backup"
    backup_data(other, other_backup)
    with sqlite3.connect(other_backup / "database.sqlite3") as connection:
        connection.execute("PRAGMA user_version = 12")
    with pytest.raises(BackupError, match="backup_schema_version_invalid"):
        upgrade_preflight(source, other_backup)


def test_upgrade_preflight_accepts_verified_pre_upgrade_history_without_migrating(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 12)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:12])
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    assert verify_backup(backup)["status"] == "valid"

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 13)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations)
    before = (source / "studybuddy.sqlite3").read_bytes()
    result = upgrade_preflight(source, backup)
    assert result["database_schema_version"] == 12
    assert result["backup_schema_version"] == 12
    assert result["target_schema_version"] == 13
    assert result["migration_required"] is True
    assert (source / "studybuddy.sqlite3").read_bytes() == before


def test_upgrade_preflight_rejects_known_unwritable_root_without_mutation(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    database = source / "studybuddy.sqlite3"
    before = database.read_bytes()
    monkeypatch.setattr("app.backup.os.access", lambda _path, _mode: False)
    with pytest.raises(BackupError, match="upgrade_data_root_not_writable"):
        upgrade_preflight(source, backup)
    assert database.read_bytes() == before


def test_pre_upgrade_backup_restores_without_migration_then_explicit_startup_upgrades(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 12)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:12])
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)

    restored = tmp_path / "restored"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 12

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 13)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations)
    with TestClient(create_app(AppConfig(data_root=restored))):
        pass
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13


def test_upgrade_preflight_rejects_corrupt_or_missing_original_without_repair(tmp_path: Path):
    source = tmp_path / "source"
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)
    original = next((source / "originals").glob("*/*/original"))
    original.unlink()
    with pytest.raises(BackupError, match="backup_original_missing"):
        upgrade_preflight(source, backup)
    assert not original.exists()
