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
    with sqlite3.connect(source / "studybuddy.sqlite3") as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES ('backup_task_operation','embedding_index','queued','default','backup-input',0,'now')"
        )
        connection.execute(
            "INSERT INTO operation_tasks "
            "(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) "
            "VALUES ('backup_task','default','backup_task_operation','embedding_index','queued','backup-input',0,'queued',0,1,'now','now')"
        )
        connection.execute(
            "INSERT INTO operation_task_attempts "
            "(id,task_id,project_id,attempt_number,status,progress_percent,stage_code,created_at,started_at) "
            "VALUES ('backup_task_attempt','backup_task','default',1,'stale',40,'indexing','now','now')"
        )
    backup = tmp_path / "backup"
    backup_data(source, backup)

    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["database"]["schema_version"] == 13
    with sqlite3.connect(backup / "database.sqlite3") as connection:
        assert assert_schema_version(connection) == 13
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
            (11, "phase9c_exercise_feedback_schema"),
            (12, "phase9d_extended_learning_schema"),
            (13, "phase10_operation_task_schema"),
        ]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13

    assert verify_backup(backup)["status"] == "valid"
    restored = tmp_path / "restored"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert assert_schema_version(connection) == 13
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
            (11, "phase9c_exercise_feedback_schema"),
            (12, "phase9d_extended_learning_schema"),
            (13, "phase10_operation_task_schema"),
        ]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13
        assert tuple(connection.execute(
            "SELECT status,progress_percent,stage_code FROM operation_tasks WHERE id='backup_task'"
        ).fetchone()) == ('queued', 0, 'queued')
        assert tuple(connection.execute(
            "SELECT status,progress_percent,stage_code FROM operation_task_attempts WHERE id='backup_task_attempt'"
        ).fetchone()) == ('stale', 40, 'indexing')

    # Normal startup must not create another history row or downgrade the version.
    with TestClient(create_app(AppConfig(data_root=restored))):
        pass
    with sqlite3.connect(restored / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 13
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13


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
