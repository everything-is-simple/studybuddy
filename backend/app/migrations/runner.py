"""Migration execution engine and registry."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from ._helpers import (
    _now,
    _objects,
    _columns,
    _create_history,
    _baseline_complete,
)
from ._canonical import _create_canonical_schema
from . import (
    _v01_canonical_material as v01,
    _v02_ai_phase0 as v02,
    _v03_phase5_provider as v03,
    _v04_qa_idempotency as v04,
    _v05_phase7_embedding as v05,
    _v06_search_index as v06,
    _v07_phase8_cards as v07,
    _v08_exercise_provenance as v08,
    _v09_phase9a_learning_plan as v09,
    _v10_phase9b_material_learning as v10,
    _v11_phase9c_feedback as v11,
    _v12_phase9d_extended as v12,
    _v13_phase10_tasks as v13,
)

CURRENT_SCHEMA_VERSION = 13
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


_MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
    (1, "canonical_material_schema", v01.migrate),
    (2, "ai_phase0_schema", v02.migrate),
    (3, "phase5_provider_metadata", v03.migrate),
    (4, "qa_operation_idempotency", v04.migrate),
    (5, "phase7_embedding_schema", v05.migrate),
    (6, "search_index_schema_contract", v06.migrate),
    (7, "phase8_cards_exercises_schema", v07.migrate),
    (8, "phase8_exercise_provenance", v08.migrate),
    (9, "phase9a_learning_plan_schema", v09.migrate),
    (10, "phase9b_material_learning_schema", v10.migrate),
    (11, "phase9c_exercise_feedback_schema", v11.migrate),
    (12, "phase9d_extended_learning_schema", v12.migrate),
    (13, "phase10_operation_task_schema", v13.migrate),
)

# Compatibility aliases for tests that monkeypatch migration functions
_migration_v9 = v09.migrate
_migration_v10 = v10.migrate
_migration_v11 = v11.migrate
_migration_v12 = v12.migrate
_migration_v13 = v13.migrate


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
                if not _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
                    raise MigrationError("database_schema_unsupported")
                return MigrationResult(current, ())
        connection.execute("BEGIN IMMEDIATE")
        _create_history(connection)
        current = _check_history(connection)
        if current == 0 and _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
            # A complete pre-runner database already has the current schema.
            # Adopt it with the full consecutive history; do not replay ALTERs.
            connection.executemany(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                [(version, name, _now()) for version, name, _function in _MIGRATIONS],
            )
            current = CURRENT_SCHEMA_VERSION
            adopted = True
        elif current == 0 and _objects(connection) - {HISTORY_TABLE}:
            # Existing pre-runner databases may have the core tables but lack
            # columns added by the old implicit schema upgrade path.
            known = {"sqlite_sequence", "projects", "materials", "extractions",
                     "text_spans", "material_search",
                     "material_revisions", "chunks", "chunk_spans", "embeddings",
                     "retrieval_runs", "retrieval_hits", "qa_citations",
                     "ai_operations", "qa_threads", "qa_messages", "qa_answers",
                     "chunks_search"}
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
        if not _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
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


def inspect_schema_version(connection: sqlite3.Connection) -> int:
    """Validate recorded history without applying a migration or changing the database."""
    version = _check_history(connection)
    pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1 or pragma != version:
        raise MigrationError("database_schema_version_unknown")
    return version


def assert_schema_version(connection: sqlite3.Connection) -> int:
    version = inspect_schema_version(connection)
    if version != CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return version
