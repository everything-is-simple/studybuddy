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
        assert assert_schema_version(connection) == 14
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 14
        ai_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
        assert ai_tables >= {"projects", "materials", "extractions", "text_spans",
                             "material_revisions", "chunks", "chunk_spans", "embeddings",
                             "retrieval_runs", "retrieval_hits", "qa_citations",
                             "ai_operations", "qa_threads", "qa_messages", "qa_answers",
                             "study_decks", "study_cards", "card_citations", "card_reviews",
                             "exercise_sets", "exercises", "exercise_citations", "exercise_attempts",
                             "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
                             "study_plan_dependencies", "study_progress_events", "module_source_links",
                             "plan_item_source_links", "notes", "note_blocks", "note_module_links",
                             "note_block_source_links", "rhythm_settings", "rhythm_allocations",
                             "practice_sessions", "practice_session_items", "exercise_attempt_reviews",
                             "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals",
                             "capture_sessions", "transcript_drafts", "transcript_segments",
                             "report_snapshots", "report_delivery_attempts",
                             "operation_tasks", "operation_task_attempts"}
        virtual_tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE sql LIKE 'CREATE VIRTUAL TABLE%'"
        )}
        assert {"material_search", "chunks_search"}.issubset(virtual_tables)


def test_phase9a_schema_has_required_tables_constraints_and_indexes(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
            "study_plan_dependencies", "study_progress_events", "module_source_links",
            "plan_item_source_links",
        }.issubset(tables)
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {
            "learning_goals_project_status_idx", "knowledge_modules_project_status_idx",
            "study_plans_project_status_idx", "study_plans_goal_status_idx",
            "study_plan_items_plan_position_idx", "study_plan_dependencies_successor_idx",
            "study_progress_events_item_time_idx", "module_source_links_source_idx",
            "plan_item_source_links_source_idx",
        }.issubset(indexes)
        connection.execute("INSERT INTO projects VALUES ('project_9a', '9A', '2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO learning_goals VALUES ('goal_1','project_9a','Goal','','active','now','now',NULL)")
        connection.execute("INSERT INTO study_plans VALUES ('plan_1','project_9a','goal_1','Plan','','draft',0,'now','now',NULL,NULL,NULL,NULL)")
        connection.execute("INSERT INTO study_plan_items VALUES ('item_1','plan_1','project_9a',NULL,NULL,NULL,'Item','',0,'pending',0,'now','now',NULL,NULL)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO study_plans VALUES ('plan_bad','project_9a','goal_1','Bad','','invalid',0,'now','now',NULL,NULL,NULL,NULL)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO study_plan_dependencies VALUES ('dep_1','plan_1','project_9a','item_1','item_1','now')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO study_progress_events VALUES ('event_1','plan_1','item_1','project_9a','cancelled','{}','now')")


def test_phase9b_schema_has_required_tables_constraints_and_indexes(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "notes", "note_blocks", "note_module_links", "note_block_source_links",
            "rhythm_settings", "rhythm_allocations",
        }.issubset(tables)
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {
            "notes_project_status_idx", "note_blocks_note_position_idx", "note_module_links_project_idx",
            "note_block_source_links_source_idx", "note_block_source_links_block_idx",
            "rhythm_settings_project_plan_idx", "rhythm_allocations_plan_date_idx",
            "rhythm_allocations_item_date_idx",
        }.issubset(indexes)
        connection.execute("INSERT INTO projects VALUES ('project_9b', '9B', 'now')")
        connection.execute("INSERT INTO learning_goals VALUES ('goal_1','project_9b','Goal','','active','now','now',NULL)")
        connection.execute("INSERT INTO study_plans VALUES ('plan_1','project_9b','goal_1','Plan','','draft',0,'now','now',NULL,NULL,NULL,NULL)")
        connection.execute("INSERT INTO study_plan_items VALUES ('item_1','plan_1','project_9b',NULL,NULL,NULL,'Item','',0,'pending',0,'now','now',NULL,NULL)")
        connection.execute("INSERT INTO notes VALUES ('note_1','project_9b','User note','draft','user_created',0,NULL,'now','now',NULL,NULL)")
        connection.execute("INSERT INTO note_blocks VALUES ('block_1','note_1','project_9b',0,'text','Body','user_created','now','now')")
        connection.execute("INSERT INTO rhythm_settings VALUES ('rhythm_1','project_9b','plan_1','daily','UTC','2026-01-01',0,'now','now')")
        connection.execute("INSERT INTO rhythm_allocations VALUES ('allocation_1','project_9b','plan_1','item_1','2026-01-01',30,'now','now')")
        connection.execute("INSERT INTO note_block_source_links VALUES ('link_1','project_9b','note_1','block_1','purged_material','purged_revision','purged_extraction','purged_chunk',NULL,'ctx-deadbeef-deadbeef','source_unavailable','now','now')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO notes VALUES ('note_bad','project_9b','Bad','draft','user_created',0,'operation_x','now','now',NULL,NULL)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO note_blocks VALUES ('block_bad','note_1','project_9b',0,'html','Body','user_created','now','now')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO rhythm_settings VALUES ('rhythm_bad','project_9b','plan_1','monthly','UTC','2026-01-01',0,'now','now')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO rhythm_allocations VALUES ('allocation_bad','project_9b','plan_1','item_1','2026-01-01',0,'now','now')")
        assert connection.execute("SELECT material_id FROM note_block_source_links WHERE id='link_1'").fetchone()[0] == "purged_material"


def test_v8_database_upgrades_to_phase9a_v9_once(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 8)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:8])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 8
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='learning_goals'").fetchone() is None
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 9)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:9])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 9
        row = connection.execute("SELECT version, name FROM schema_migrations WHERE version=9").fetchone()
        assert tuple(row) == (9, "phase9a_learning_plan_schema")
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='study_progress_events'").fetchone() is not None
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=9").fetchone()[0] == 1


def test_v9_database_upgrades_to_phase9b_v10_once(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 9)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:9])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 9
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='notes'").fetchone() is None
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 10)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:10])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 10
        assert tuple(connection.execute("SELECT version, name FROM schema_migrations WHERE version=10").fetchone()) == (
            10, "phase9b_material_learning_schema",
        )
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='notes'").fetchone() is not None
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=10").fetchone()[0] == 1


def test_phase9a_migration_failure_rolls_back_v9_to_existing_v8(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 8)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:8])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 8

    original = runner._migration_v9
    def broken(connection: sqlite3.Connection) -> None:
        original(connection)
        raise sqlite3.OperationalError("private")

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 9)
    monkeypatch.setattr(runner, "_MIGRATIONS", tuple(
        (version, name, broken if version == 9 else function)
        for version, name, function in migrations
    ))
    connection = sqlite3.connect(database)
    with pytest.raises(MigrationError, match="database_migration_failed"):
        migrate(connection)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='learning_goals'").fetchone() is None
    assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 8
    assert connection.execute("SELECT 1 FROM schema_migrations WHERE version=9").fetchone() is None
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
    connection.close()


def test_phase9b_migration_failure_rolls_back_v10_to_existing_v9(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 9)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:9])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 9

    original = runner._migration_v10

    def broken(connection: sqlite3.Connection) -> None:
        original(connection)
        raise sqlite3.OperationalError("private")

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 10)
    monkeypatch.setattr(runner, "_MIGRATIONS", tuple(
        (version, name, broken if version == 10 else function)
        for version, name, function in migrations
    ))
    connection = sqlite3.connect(database)
    with pytest.raises(MigrationError, match="database_migration_failed"):
        migrate(connection)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='notes'").fetchone() is None
    assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 9
    assert connection.execute("SELECT 1 FROM schema_migrations WHERE version=10").fetchone() is None
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
    connection.close()


def test_missing_search_schema_is_not_repaired_at_runtime(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        connection.execute("DROP TABLE material_search")
        connection.commit()
    with pytest.raises(MigrationError, match="database_schema_unsupported"):
        connect(database)


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
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 14
        assert connection.execute("SELECT provider_request_id, total_tokens, finish_reason, idempotency_key, retrieval_run_id FROM ai_operations").description is not None
        assert connection.execute("SELECT id,operation_id,status,progress_percent FROM operation_tasks").description is not None
        assert connection.execute("SELECT id,task_id,attempt_number,lease_expires_at FROM operation_task_attempts").description is not None
        assert connection.execute("SELECT id, goal_id, status, user_edited FROM study_plans").description is not None
        assert connection.execute("SELECT id, provenance, generation_operation_id FROM notes").description is not None
        assert connection.execute("SELECT id, cadence, target_minutes FROM rhythm_settings").description is not None
        assert connection.execute("SELECT COUNT(*) FROM material_search").fetchone()[0] == 1
        ai_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
        assert ai_tables >= {"material_revisions", "chunks", "chunk_spans", "embeddings",
                             "retrieval_runs", "retrieval_hits", "qa_citations",
                             "ai_operations", "qa_threads", "qa_messages", "qa_answers"}


def test_phase9d_schema_has_required_tables_constraints_and_indexes(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "capture_sessions", "transcript_drafts", "transcript_segments",
            "report_snapshots", "report_delivery_attempts",
        }.issubset(tables)
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {
            "capture_sessions_project_status_idx", "transcript_drafts_session_status_idx",
            "transcript_segments_draft_ordinal_idx", "report_snapshots_project_period_idx",
            "report_delivery_attempts_report_time_idx", "ai_operations_capture_session_idx",
        }.issubset(indexes)
        connection.execute("INSERT INTO projects VALUES ('project_9d','9D','now')")
        connection.execute(
            "INSERT INTO capture_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('capture_1', 'project_9d', 'draft', 'audio', None, 'lesson.wav', 'audio/wav', None,
             'now', 'now', None, None, None),
        )
        connection.execute(
            "INSERT INTO transcript_drafts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ('draft_1', 'project_9d', 'capture_1', None, 'draft', 'draft text', 'zh-CN', 'uncertain', 0, 'now', 'now'),
        )
        connection.execute(
            "INSERT INTO transcript_segments VALUES (?,?,?,?,?,?,?,?,?)",
            ('segment_1', 'draft_1', 'project_9d', 0, 'uncertain text', 0.25, 'uncertain', 'now', 'now'),
        )
        connection.execute(
            "INSERT INTO report_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('report_1', 'project_9d', 'daily', 'UTC', '2026-01-01', '2026-01-02', 'ready', 'v1',
             'fingerprint_1', '{}', '', None, 'now', 'now', 'now', None),
        )
        connection.execute(
            "INSERT INTO report_delivery_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ('delivery_1', 'project_9d', 'report_1', 'smtp', 'dry_run', 'parent-a', 'content_1',
             'key_1', 'dry_run', None, None, 'now', 'now'),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO transcript_segments VALUES (?,?,?,?,?,?,?,?,?)",
                ('segment_bad', 'draft_1', 'project_9d', 1, 'bad', 1.1, 'clear', 'now', 'now'),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO capture_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ('capture_bad', 'project_9d', 'draft', 'video', None, 'lesson.mp4', 'video/mp4', None,
                 'now', 'now', None, None, None),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO report_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ('report_bad', 'project_9d', 'daily', 'UTC', '2026-01-02', '2026-01-01', 'draft', 'v1',
                 'fingerprint_2', '{}', '', None, 'now', 'now', None, None),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO report_delivery_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ('delivery_bad', 'project_9d', 'report_1', 'smtp', 'dry_run', 'parent-a', 'content_1',
                 'key_1', 'dry_run', None, None, 'now', 'now'),
            )


def test_phase10_task_schema_constraints_and_scope_are_enforced(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        connection.execute("INSERT INTO projects VALUES ('project_task_a','Task A','now')")
        connection.execute("INSERT INTO projects VALUES ('project_task_b','Task B','now')")
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES ('operation_task_a','embedding_index','queued','project_task_a','input-a',0,'now')"
        )
        connection.execute(
            "INSERT INTO operation_tasks "
            "(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) "
            "VALUES ('task_a','project_task_a','operation_task_a','embedding_index','queued','input-a',0,'queued',0,2,'now','now')"
        )
        connection.execute(
            "INSERT INTO operation_task_attempts "
            "(id,task_id,project_id,attempt_number,status,progress_percent,stage_code,created_at,started_at) "
            "VALUES ('attempt_a_1','task_a','project_task_a',1,'running',0,'reading_source','now','now')"
        )
        assert tuple(connection.execute(
            "SELECT status,progress_percent,stage_code,retry_count,max_retries FROM operation_tasks WHERE id='task_a'"
        ).fetchone()) == ('queued', 0, 'queued', 0, 2)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO operation_tasks "
                "(id,project_id,operation_id,task_kind,status,input_fingerprint,retry_count,max_retries,created_at,updated_at) "
                "VALUES ('task_scope_bad','project_task_b','operation_task_a','embedding_index','queued','input-a',0,0,'now','now')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO operation_task_attempts "
                "(id,task_id,project_id,attempt_number,status,created_at) "
                "VALUES ('attempt_scope_bad','task_a','project_task_b',2,'running','now')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO operation_tasks "
                "(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,retry_count,max_retries,created_at,updated_at) "
                "VALUES ('task_progress_bad','project_task_a','operation_task_a','embedding_index','invalid','input-a',101,0,0,'now','now')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO operation_task_attempts "
                "(id,task_id,project_id,attempt_number,status,created_at) "
                "VALUES ('attempt_duplicate_running','task_a','project_task_a',2,'running','now')"
            )


def test_v11_database_upgrades_to_phase9d_v12_once(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 11)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:11])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 11
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='capture_sessions'").fetchone() is None
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 12)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:12])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 12
        assert tuple(connection.execute("SELECT version, name FROM schema_migrations WHERE version=12").fetchone()) == (
            12, "phase9d_extended_learning_schema",
        )
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='capture_sessions'").fetchone() is not None
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=12").fetchone()[0] == 1


def test_v13_database_upgrades_to_v14_once(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 13)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:13])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 13
        # Add test data to verify fingerprint recalculation
        connection.execute("INSERT INTO projects VALUES ('fp_project','FP','now')")
        connection.execute(
            "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at) "
            "VALUES ('fp_mat','fp_project','test.txt','sha','originals/sha','text/plain','now','now')"
        )
        connection.execute(
            "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at) "
            "VALUES ('fp_ext','fp_mat','text','1.0.0','success','test','[]','now')"
        )
        connection.execute(
            "INSERT INTO material_revisions (id,material_id,extraction_id,source_sha256,extraction_sha256,"
            "parser_id,parser_version,revision_fingerprint,is_current,created_at) "
            "VALUES ('fp_rev','fp_mat','fp_ext','sha','esha','text','1.0.0','old_fp',1,'now')"
        )
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 14)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations)
    with connect(database) as connection:
        assert assert_schema_version(connection) == 14
        assert tuple(connection.execute("SELECT version, name FROM schema_migrations WHERE version=14").fetchone()) == (
            14, "fix_revision_fingerprint_material_id",
        )
        # Verify fingerprint was updated
        fp = connection.execute("SELECT revision_fingerprint FROM material_revisions WHERE id='fp_rev'").fetchone()[0]
        assert fp != 'old_fp'
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations WHERE version=14").fetchone()[0] == 1


def test_phase10_migration_failure_rolls_back_v13_to_existing_v12(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 12)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:12])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 12

    original = runner._migration_v13
    def broken(connection: sqlite3.Connection) -> None:
        original(connection)
        raise sqlite3.OperationalError("private")

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 13)
    monkeypatch.setattr(runner, "_MIGRATIONS", tuple(
        (version, name, broken if version == 13 else function)
        for version, name, function in migrations
    ))
    connection = sqlite3.connect(database)
    with pytest.raises(MigrationError, match="database_migration_failed"):
        migrate(connection)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='operation_tasks'").fetchone() is None
    assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 12
    assert connection.execute("SELECT 1 FROM schema_migrations WHERE version=13").fetchone() is None
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 12
    connection.close()


def test_phase9d_migration_failure_rolls_back_v12_to_existing_v11(monkeypatch, tmp_path: Path):
    from app.migrations import runner

    database = tmp_path / "studybuddy.sqlite3"
    migrations = runner._MIGRATIONS
    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 11)
    monkeypatch.setattr(runner, "_MIGRATIONS", migrations[:11])
    with connect(database) as connection:
        assert assert_schema_version(connection) == 11

    original = runner._migration_v12
    def broken(connection: sqlite3.Connection) -> None:
        original(connection)
        raise sqlite3.OperationalError("private")

    monkeypatch.setattr(runner, "CURRENT_SCHEMA_VERSION", 12)
    monkeypatch.setattr(runner, "_MIGRATIONS", tuple(
        (version, name, broken if version == 12 else function)
        for version, name, function in migrations
    ))
    connection = sqlite3.connect(database)
    with pytest.raises(MigrationError, match="database_migration_failed"):
        migrate(connection)
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='capture_sessions'").fetchone() is None
    assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 11
    assert connection.execute("SELECT 1 FROM schema_migrations WHERE version=12").fetchone() is None
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 11
    connection.close()


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
    assert manifest["database"]["schema_version"] == 14
    assert verify_backup(backup)["status"] == "valid"
    manifest["database"]["schema_version"] = 99
    (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BackupError, match="backup_schema_version_mismatch"):
        verify_backup(backup)
