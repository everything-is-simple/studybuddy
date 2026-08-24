from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backup import BackupError, backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.migrations.runner import assert_schema_version
from fastapi.testclient import TestClient


def make_data(root: Path) -> None:
    with TestClient(create_app(AppConfig(data_root=root))) as client:
        assert client.post('/api/materials', files={'file': ('one.txt', b'one', 'text/plain')}).status_code == 201
        assert client.post('/api/materials', files={'file': ('two.txt', b'one', 'text/plain')}).status_code == 201
        items = client.get('/api/materials').json()
        assert client.delete('/api/materials/' + items[0]['id']).status_code == 204


def test_backup_verify_and_restore_preserves_shared_and_deleted(tmp_path: Path):
    source = tmp_path / 'source'
    make_data(source)
    backup = tmp_path / 'backup'
    result = backup_data(source, backup)
    assert result['status'] == 'complete'
    manifest = json.loads((backup / 'manifest.json').read_text())
    assert manifest['originals']['count'] == 1
    assert str(source) not in (backup / 'manifest.json').read_text()
    assert verify_backup(backup)['status'] == 'valid'
    restored = tmp_path / 'restored'
    assert restore_backup(restored, backup, confirm=True)['status'] == 'restored'
    with TestClient(create_app(AppConfig(data_root=restored))) as client:
        assert len(client.get('/api/materials').json()) == 1
        assert len(client.get('/api/materials/deleted').json()) == 1


def test_backup_restore_preserves_schema_version_and_history(tmp_path: Path):
    source = tmp_path / "source"
    make_data(source)
    backup = tmp_path / "backup"
    backup_data(source, backup)

    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["database"]["schema_version"] == 10
    with sqlite3.connect(backup / "database.sqlite3") as connection:
        assert assert_schema_version(connection) == 10
        assert connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall() == [
            (1, "canonical_material_schema"),
            (2, "ai_phase0_schema"),
            (3, "phase5_provider_metadata"),
            (4, "qa_operation_idempotency"),
            (5, "phase7_embedding_schema"),
            (6, "search_index_schema_contract"),
            (7, "phase8_cards_exercises_schema"),
            (8, "phase8_exercise_provenance"),
            (9, "phase9a_learning_plan_schema"),
            (10, "phase9b_material_learning_schema"),
        ]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10

    assert verify_backup(backup)["status"] == "valid"
    restored = tmp_path / "restored"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert assert_schema_version(connection) == 10
        assert connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall() == [
            (1, "canonical_material_schema"),
            (2, "ai_phase0_schema"),
            (3, "phase5_provider_metadata"),
            (4, "qa_operation_idempotency"),
            (5, "phase7_embedding_schema"),
            (6, "search_index_schema_contract"),
            (7, "phase8_cards_exercises_schema"),
            (8, "phase8_exercise_provenance"),
            (9, "phase9a_learning_plan_schema"),
            (10, "phase9b_material_learning_schema"),
        ]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10

    # Normal startup must not create another history row or downgrade the version.
    with TestClient(create_app(AppConfig(data_root=restored))):
        pass
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 10
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10


def test_restore_requires_confirm_and_nonempty_target_unchanged(tmp_path: Path):
    source = tmp_path / 'source'
    make_data(source)
    backup = tmp_path / 'backup'
    backup_data(source, backup)
    target = tmp_path / 'target'
    target.mkdir(); (target / 'keep').write_text('keep')
    with pytest.raises(BackupError, match='restore_confirmation_required'):
        restore_backup(target, backup)
    assert (target / 'keep').read_text() == 'keep'
    with pytest.raises(BackupError, match='restore_target_not_empty'):
        restore_backup(target, backup, confirm=True)
    assert (target / 'keep').read_text() == 'keep'


def test_verify_hash_mismatch_does_not_repair(tmp_path: Path):
    source = tmp_path / 'source'
    make_data(source)
    backup = tmp_path / 'backup'
    backup_data(source, backup)
    database = backup / 'database.sqlite3'
    original = database.read_bytes()
    database.write_bytes(original + b'changed')
    with pytest.raises(BackupError, match='backup_database_hash_mismatch'):
        verify_backup(backup)
    assert database.read_bytes() == original + b'changed'


def test_backup_rejects_output_inside_data_root(tmp_path: Path):
    source = tmp_path / 'source'
    make_data(source)
    with pytest.raises(BackupError, match='backup_output_inside_data_root'):
        backup_data(source, source / 'backup')
