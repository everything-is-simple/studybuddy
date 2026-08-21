from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .observability import emit_event, increment
from .repository import connect

logger = logging.getLogger(__name__)
_REQUIRED = {"projects", "materials", "extractions", "text_spans", "material_search"}


def _event(name: str) -> None:
    # Deliberately no database path, ids, SQL, or exception text.
    increment("audit_events", name)
    emit_event(name, level=logging.WARNING, component="database", outcome="diagnostic")


def _run(connection: sqlite3.Connection, sql: str, event: str, *, expect_rows: bool = False) -> list[sqlite3.Row]:
    try:
        rows = connection.execute(sql).fetchall()
    except Exception:
        _event(event + "_error")
        return []
    if expect_rows and rows:
        _event(event)
    return rows


def _relation_checks(connection: sqlite3.Connection) -> None:
    checks = (
        ("SELECT 1 FROM materials m LEFT JOIN extractions e ON e.material_id = m.id WHERE e.id IS NULL LIMIT 1", "database_material_extraction_relation_failed"),
        ("SELECT 1 FROM extractions e LEFT JOIN materials m ON m.id = e.material_id WHERE m.id IS NULL LIMIT 1", "database_extraction_material_relation_failed"),
        ("SELECT 1 FROM text_spans s LEFT JOIN extractions e ON e.id = s.extraction_id WHERE e.id IS NULL LIMIT 1", "database_span_extraction_relation_failed"),
        ("SELECT 1 FROM material_search s LEFT JOIN materials m ON m.id = s.material_id WHERE m.id IS NULL LIMIT 1", "database_search_material_relation_failed"),
        ("SELECT 1 FROM materials m LEFT JOIN material_search s ON s.material_id = m.id WHERE s.material_id IS NULL LIMIT 1", "database_search_row_missing"),
    )
    for sql, event in checks:
        _run(connection, sql, event, expect_rows=True)


def run_audit(database_path: Path) -> None:
    """Run one-shot diagnostic checks; never repair business rows."""
    try:
        connection = connect(database_path)
    except Exception:
        _event("database_audit_connect_error")
        increment("audit", "failed")
        return
    increment("audit", "started")
    try:
        integrity = _run(connection, "PRAGMA integrity_check", "database_integrity_check_failed")
        if integrity and str(integrity[0][0]).lower() != "ok":
            _event("database_integrity_check_failed")
        foreign = _run(connection, "PRAGMA foreign_key_check", "database_foreign_key_check_failed", expect_rows=True)
        if foreign:
            _event("database_foreign_key_check_failed")
        try:
            objects = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')").fetchall()}
            for required in _REQUIRED:
                if required not in objects:
                    _event("database_required_object_missing")
        except Exception:
            _event("database_required_object_check_error")
        try:
            _relation_checks(connection)
        except Exception:
            _event("database_relation_check_error")
    finally:
        try:
            connection.close()
            increment("audit", "completed")
        except Exception:
            _event("database_audit_close_error")
