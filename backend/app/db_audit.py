from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .observability import emit_event, increment

logger = logging.getLogger(__name__)
_REQUIRED = {"projects", "materials", "extractions", "text_spans", "material_search"}
_REASON_ORDER = (
    "database_integrity_check_failed", "database_foreign_key_check_failed",
    "database_required_object_missing", "database_required_object_check_error",
    "database_material_extraction_relation_failed", "database_extraction_material_relation_failed",
    "database_span_extraction_relation_failed", "database_search_material_relation_failed",
    "database_search_row_missing", "database_relation_check_error", "database_audit_close_error",
)


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


def _relation_checks(connection: sqlite3.Connection) -> set[str]:
    reasons: set[str] = set()
    checks = (
        ("SELECT 1 FROM materials m LEFT JOIN extractions e ON e.material_id = m.id WHERE e.id IS NULL LIMIT 1", "database_material_extraction_relation_failed"),
        ("SELECT 1 FROM extractions e LEFT JOIN materials m ON m.id = e.material_id WHERE m.id IS NULL LIMIT 1", "database_extraction_material_relation_failed"),
        ("SELECT 1 FROM text_spans s LEFT JOIN extractions e ON e.id = s.extraction_id WHERE e.id IS NULL LIMIT 1", "database_span_extraction_relation_failed"),
        ("SELECT 1 FROM material_search s LEFT JOIN materials m ON m.id = s.material_id WHERE m.id IS NULL LIMIT 1", "database_search_material_relation_failed"),
        ("SELECT 1 FROM materials m LEFT JOIN material_search s ON s.material_id = m.id WHERE s.material_id IS NULL LIMIT 1", "database_search_row_missing"),
    )
    for sql, event in checks:
        if _run(connection, sql, event, expect_rows=True):
            reasons.add(event)
    return reasons


def run_audit(database_path: Path) -> dict[str, object]:
    """Run one-shot diagnostic checks; never migrate, repair, or rebuild indexes."""
    reasons: set[str] = set()
    try:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA query_only = ON")
    except Exception:
        _event("database_audit_connect_error")
        increment("audit", "failed")
        return {"status": "degraded", "reasons": ["database_audit_connect_error"]}
    increment("audit", "started")
    try:
        integrity = _run(connection, "PRAGMA integrity_check", "database_integrity_check_failed")
        if integrity and str(integrity[0][0]).lower() != "ok":
            _event("database_integrity_check_failed")
            reasons.add("database_integrity_check_failed")
        foreign = _run(connection, "PRAGMA foreign_key_check", "database_foreign_key_check_failed", expect_rows=True)
        if foreign:
            _event("database_foreign_key_check_failed")
            reasons.add("database_foreign_key_check_failed")
        try:
            objects = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')").fetchall()}
            if any(required not in objects for required in _REQUIRED):
                _event("database_required_object_missing")
                reasons.add("database_required_object_missing")
        except Exception:
            _event("database_required_object_check_error")
            reasons.add("database_required_object_check_error")
        try:
            reasons.update(_relation_checks(connection))
        except Exception:
            _event("database_relation_check_error")
            reasons.add("database_relation_check_error")
    finally:
        try:
            connection.close()
            increment("audit", "completed")
        except Exception:
            _event("database_audit_close_error")
            reasons.add("database_audit_close_error")
    ordered = sorted(reasons, key=lambda reason: (
        _REASON_ORDER.index(reason) if reason in _REASON_ORDER else len(_REASON_ORDER), reason
    ))
    return {"status": "degraded" if ordered else "ok", "reasons": ordered}
