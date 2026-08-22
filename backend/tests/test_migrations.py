from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.backup import BackupError, backup_data, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.migrations.runner import MigrationError, assert_schema_version, migrate
from app.repository import connect
from app.startup_preflight import StartupPreflightError


def test_new_database_has_versioned_schema_and_is_idempotent(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        assert assert_schema_version(connection) == 4
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 4
        ai_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
        assert ai_tables >= {"projects", "materials", "extractions", "text_spans",
                             "material_revisions", "chunks", "chunk_spans", "embeddings",
                             "retrieval_runs", "retrieval_hits", "qa_citations",
                             "ai_operations", "qa_threads", "qa_messages", "qa_answers"}
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 4
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4


def test_legacy_database_is_adopted_without_losing_data(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE materials (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, original_name TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, stored_path TEXT NOT NULL, media_type TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE extractions (id TEXT PRIMARY KEY, material_id TEXT NOT NULL, parser_id TEXT NOT NULL,
            parser_version TEXT NOT NULL, status TEXT NOT NULL, text TEXT NOT NULL, warnings_json TEXT NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE text_spans (id TEXT PRIMARY KEY, extraction_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
            span_kind TEXT NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL);
        INSERT INTO projects VALUES ('p', 'P', '2025-01-01T00:00:00+00:00');
        INSERT INTO materials VALUES ('m', 'p', 'one.txt', 'a', 'originals/a', 'text/plain', '2025-01-01T00:00:00+00:00');
        INSERT INTO extractions VALUES ('e', 'm', 'txt', '1', 'success', 'one', '[]', '2025-01-01T00:00:00+00:00');
        """
    )
    connection.commit(); connection.close()
    with connect(database) as connection:
        assert connection.execute("SELECT original_name FROM materials").fetchone()[0] == "one.txt"
        row = connection.execute("SELECT updated_at, deleted_at FROM materials").fetchone()
        assert row[0] == "2025-01-01T00:00:00+00:00" and row[1] is None
        assert connection.execute("SELECT error_code FROM extractions").fetchone()[0] is None
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 4
        assert connection.execute("SELECT provider_request_id, total_tokens, finish_reason, idempotency_key, retrieval_run_id FROM ai_operations").description is not None
        assert connection.execute("SELECT COUNT(*) FROM material_search").fetchone()[0] == 1
        ai_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
        assert ai_tables >= {"material_revisions", "chunks", "chunk_spans", "embeddings",
                             "retrieval_runs", "retrieval_hits", "qa_citations",
                             "ai_operations", "qa_threads", "qa_messages", "qa_answers"}


def test_unknown_future_version_fails_without_ready(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_migrations VALUES (99, 'future', 'now')")
        connection.execute("PRAGMA user_version = 99")
    app = create_app(AppConfig(data_root=tmp_path))
    with pytest.raises(StartupPreflightError, match="database_schema_version_unknown"):
        with TestClient(app):
            pass
    assert app.state.ready is False


def test_failed_migration_rolls_back_and_uses_stable_error(monkeypatch, tmp_path: Path):
    from app.migrations import runner
    original = runner._MIGRATIONS
    monkeypatch.setattr(runner, "_MIGRATIONS", ((1, "broken", lambda connection: (_ for _ in ()).throw(sqlite3.OperationalError("private"))),))
    database = tmp_path / "studybuddy.sqlite3"
    connection = sqlite3.connect(database)
    with pytest.raises(MigrationError, match="database_migration_failed"):
        migrate(connection)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'schema_migrations'").fetchone() is None
    connection.close()
    monkeypatch.setattr(runner, "_MIGRATIONS", original)


def test_backup_manifest_and_restored_database_retain_version(tmp_path: Path):
    source = tmp_path / "source"
    with TestClient(create_app(AppConfig(data_root=source))) as client:
        assert client.post("/api/materials", files={"file": ("one.txt", b"one", "text/plain")}).status_code == 201
    backup = tmp_path / "backup"
    backup_data(source, backup)
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["database"]["schema_version"] == 4
    assert verify_backup(backup)["status"] == "valid"
    manifest["database"]["schema_version"] = 99
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BackupError, match="backup_schema_version_mismatch"):
        verify_backup(backup)
