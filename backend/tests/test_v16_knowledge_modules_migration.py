"""S2 schema upgrade/rollback preserves v9 module identity and existing facts."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.migrations import runner


def test_v16_upgrade_is_consecutive_and_idempotent(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "upgrade.db")
    with monkeypatch.context() as m:
        m.setattr(runner, "CURRENT_SCHEMA_VERSION", 15)
        m.setattr(runner, "_MIGRATIONS", runner._MIGRATIONS[:15])
        runner.migrate(conn)
    conn.execute("INSERT INTO projects VALUES ('p','Test','now')")
    conn.execute("INSERT INTO knowledge_modules(id,project_id,title,description,status,created_at,updated_at) VALUES ('old','p','Original','','active','now','now')")
    conn.commit()
    result = runner.migrate(conn)
    assert result.applied_versions == (16,)
    assert runner.assert_schema_version(conn) == 16
    assert conn.execute("SELECT title FROM knowledge_modules WHERE id='old'").fetchone()[0] == "Original"
    assert conn.execute("SELECT COUNT(*) FROM s2_knowledge_modules").fetchone()[0] == 0
    assert runner.migrate(conn).applied_versions == ()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_v16_failure_rolls_back_ddl_history_and_version(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "rollback.db")
    with monkeypatch.context() as m:
        m.setattr(runner, "CURRENT_SCHEMA_VERSION", 15)
        m.setattr(runner, "_MIGRATIONS", runner._MIGRATIONS[:15])
        runner.migrate(conn)
    body = runner._MIGRATIONS[15][2]
    def fail(c):
        body(c)
        raise sqlite3.OperationalError("synthetic migration failure")
    with monkeypatch.context() as m:
        m.setattr(runner, "_MIGRATIONS", runner._MIGRATIONS[:15] + ((16, runner._MIGRATIONS[15][1], fail),))
        with pytest.raises(runner.MigrationError, match="database_migration_failed"):
            runner.migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 15
    assert conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 's2_%'").fetchall() == []
    assert runner.migrate(conn).applied_versions == (16,)
    conn.close()


def test_v16_rejects_incomplete_schema(tmp_path):
    conn = sqlite3.connect(tmp_path / "incomplete.db")
    runner.migrate(conn)
    conn.execute("DROP TABLE s2_module_exercises")
    conn.commit()
    with pytest.raises(runner.MigrationError, match="database_schema_unsupported"):
        runner.migrate(conn)
    conn.close()
