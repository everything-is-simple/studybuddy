from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

CURRENT_SCHEMA_VERSION = 1
HISTORY_TABLE = "schema_migrations"


class MigrationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MigrationResult:
    current_version: int
    applied_versions: tuple[int, ...]
    adopted_legacy: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _objects(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    )}


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _create_history(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )


def _baseline_complete(connection: sqlite3.Connection) -> bool:
    objects = _objects(connection)
    required = {"projects", "materials", "extractions", "text_spans"}
    if not required.issubset(objects):
        return False
    return {
        "id", "project_id", "original_name", "source_sha256", "stored_path",
        "media_type", "created_at", "updated_at", "deleted_at",
    }.issubset(_columns(connection, "materials")) and {
        "id", "material_id", "parser_id", "parser_version", "status", "text",
        "warnings_json", "created_at", "error_code",
    }.issubset(_columns(connection, "extractions"))


def _create_canonical_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            stored_path TEXT NOT NULL, media_type TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT, deleted_at TEXT NULL
        );
        CREATE TABLE IF NOT EXISTS extractions (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            parser_id TEXT NOT NULL, parser_version TEXT NOT NULL,
            status TEXT NOT NULL, text TEXT NOT NULL, warnings_json TEXT NOT NULL,
            created_at TEXT NOT NULL, error_code TEXT
        );
        CREATE TABLE IF NOT EXISTS text_spans (
            id TEXT PRIMARY KEY,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL, span_kind TEXT NOT NULL,
            label TEXT NOT NULL, text TEXT NOT NULL
        );
        """
    )
    columns = _columns(connection, "materials")
    if "updated_at" not in columns:
        connection.execute("ALTER TABLE materials ADD COLUMN updated_at TEXT")
        connection.execute("UPDATE materials SET updated_at = created_at WHERE updated_at IS NULL")
    if "deleted_at" not in columns:
        connection.execute("ALTER TABLE materials ADD COLUMN deleted_at TEXT NULL")
    extraction_columns = _columns(connection, "extractions")
    if "error_code" not in extraction_columns:
        connection.execute("ALTER TABLE extractions ADD COLUMN error_code TEXT")
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING "
        "fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
    )


def _migration_v1(connection: sqlite3.Connection) -> None:
    _create_canonical_schema(connection)


_MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
    (1, "canonical_material_schema", _migration_v1),
)


def schema_version(connection: sqlite3.Connection) -> int:
    try:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchall()
    except sqlite3.Error as exc:
        raise MigrationError("database_schema_version_unknown") from exc
    return int(rows[0][0]) if rows else 0


def _check_history(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()
    expected = [version for version, _, _ in _MIGRATIONS]
    actual = [int(row[0]) for row in rows]
    if actual != expected[:len(actual)] or any(version < 1 for version in actual):
        raise MigrationError("database_schema_version_unknown")
    for row, migration in zip(rows, _MIGRATIONS):
        if row[1] != migration[1]:
            raise MigrationError("database_migration_history_mismatch")
    current = actual[-1] if actual else 0
    if current > CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return current


def migrate(connection: sqlite3.Connection) -> MigrationResult:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 2000")
    adopted = False
    applied: list[int] = []
    try:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (HISTORY_TABLE,)
        ).fetchone() is not None:
            current = _check_history(connection)
            pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current == CURRENT_SCHEMA_VERSION and pragma == CURRENT_SCHEMA_VERSION:
                if not _baseline_complete(connection):
                    raise MigrationError("database_schema_unsupported")
                return MigrationResult(current, ())
        connection.execute("BEGIN IMMEDIATE")
        _create_history(connection)
        current = _check_history(connection)
        if current == 0 and _baseline_complete(connection):
            migration = _MIGRATIONS[0]
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (migration[0], migration[1], _now()),
            )
            current = CURRENT_SCHEMA_VERSION
            adopted = True
        elif current == 0 and _objects(connection) - {HISTORY_TABLE}:
            # Existing pre-runner databases may have the core tables but lack
            # columns added by the old implicit schema upgrade path.
            known = {"sqlite_sequence", "projects", "materials", "extractions",
                     "text_spans", "material_search"}
            if not (_objects(connection) - {HISTORY_TABLE}).issubset(known):
                raise MigrationError("database_schema_unsupported")
        for version, name, function in _MIGRATIONS:
            if version <= current:
                continue
            if version != current + 1:
                raise MigrationError("database_migration_incomplete")
            function(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _now()),
            )
            applied.append(version)
            current = version
        if current != CURRENT_SCHEMA_VERSION:
            raise MigrationError("database_migration_incomplete")
        if not _baseline_complete(connection):
            raise MigrationError("database_schema_unsupported")
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.commit()
        return MigrationResult(current, tuple(applied), adopted)
    except MigrationError:
        connection.rollback()
        raise
    except (sqlite3.Error, OSError) as exc:
        connection.rollback()
        raise MigrationError("database_migration_failed") from exc


def assert_schema_version(connection: sqlite3.Connection) -> int:
    version = schema_version(connection)
    pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != CURRENT_SCHEMA_VERSION or pragma != CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return version
