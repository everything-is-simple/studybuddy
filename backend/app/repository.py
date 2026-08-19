from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters.file_parsers.models import ParseResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS materials (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, original_name TEXT NOT NULL, source_sha256 TEXT NOT NULL, stored_path TEXT NOT NULL, media_type TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT, deleted_at TEXT NULL);
CREATE TABLE IF NOT EXISTS extractions (id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE, parser_id TEXT NOT NULL, parser_version TEXT NOT NULL, status TEXT NOT NULL, text TEXT NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL, error_code TEXT);
CREATE TABLE IF NOT EXISTS text_spans (id TEXT PRIMARY KEY, extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE, ordinal INTEGER NOT NULL, span_kind TEXT NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL);
"""

VALID_STATUSES = {"success", "empty", "rejected", "failed"}


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 2000")
    connection.executescript(SCHEMA)
    material_columns = {row[1] for row in connection.execute("PRAGMA table_info(materials)")}
    if "updated_at" not in material_columns:
        connection.execute("ALTER TABLE materials ADD COLUMN updated_at TEXT")
        connection.execute("UPDATE materials SET updated_at = created_at WHERE updated_at IS NULL")
    if "deleted_at" not in material_columns:
        connection.execute("ALTER TABLE materials ADD COLUMN deleted_at TEXT NULL")
    extraction_columns = {row[1] for row in connection.execute("PRAGMA table_info(extractions)")}
    if "error_code" not in extraction_columns:
        connection.execute("ALTER TABLE extractions ADD COLUMN error_code TEXT")
    return connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_extraction(connection: sqlite3.Connection, material_id: str, result: ParseResult) -> str:
    extraction_id = f"extraction_{uuid.uuid4().hex}"
    with connection:
        connection.execute(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (extraction_id, material_id, result.parser_id, result.parser_version, result.status,
             result.text, json.dumps(result.warnings, ensure_ascii=False), utc_now(), result.error_code),
        )
        connection.executemany(
            "INSERT INTO text_spans VALUES (?, ?, ?, ?, ?, ?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, span.ordinal, span.kind, span.label, span.text)
             for span in result.spans],
        )
    return extraction_id


def save_material_with_extraction(connection: sqlite3.Connection, project_id: str,
                                  original_name: str, source_sha256: str,
                                  stored_path: Path, media_type: str,
                                  result: ParseResult) -> tuple[str, str]:
    material_id = f"material_{uuid.uuid4().hex}"
    extraction_id = f"extraction_{uuid.uuid4().hex}"
    created_at = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?)",
                           (project_id, "Default project", created_at))
        connection.execute(
            "INSERT INTO materials (id, project_id, original_name, source_sha256, stored_path, media_type, created_at, updated_at, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (material_id, project_id, original_name, source_sha256, str(stored_path), media_type, created_at, created_at),
        )
        connection.execute(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (extraction_id, material_id, result.parser_id, result.parser_version, result.status,
             result.text, json.dumps(result.warnings, ensure_ascii=False), created_at, result.error_code),
        )
        connection.executemany(
            "INSERT INTO text_spans VALUES (?, ?, ?, ?, ?, ?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, span.ordinal, span.kind, span.label, span.text)
             for span in result.spans],
        )
    return material_id, extraction_id


def list_materials(connection: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    query = (
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL"
    )
    params: tuple[str, ...] = ()
    if status is not None:
        query += " AND e.status = ?"
        params = (status,)
    query += " ORDER BY e.created_at DESC, m.id DESC"
    return connection.execute(query, params).fetchall()


def list_deleted_materials(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, m.deleted_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NOT NULL ORDER BY m.deleted_at DESC, m.id DESC"
    ).fetchall()


def restore_material(connection: sqlite3.Connection, material_id: str) -> sqlite3.Row | None:
    updated_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET deleted_at = NULL, updated_at = ? WHERE id = ? AND deleted_at IS NOT NULL",
            (updated_at, material_id),
        )
        if cursor.rowcount != 1:
            return None
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, e.status, e.error_code, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, "
        "m.created_at, m.updated_at, m.deleted_at "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()


def material_state(connection: sqlite3.Connection, material_id: str) -> str:
    row = connection.execute("SELECT deleted_at FROM materials WHERE id = ?", (material_id,)).fetchone()
    if row is None:
        return "missing"
    return "deleted" if row[0] is not None else "active"


def get_material(connection: sqlite3.Connection, material_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, m.created_at, m.updated_at, "
        "e.id AS extraction_id, e.parser_id, e.parser_version, e.status, e.text, e.warnings_json, e.created_at AS extraction_created_at, e.error_code "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()


def get_spans(connection: sqlite3.Connection, extraction_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT ordinal, span_kind, label, text FROM text_spans WHERE extraction_id = ? ORDER BY ordinal",
        (extraction_id,),
    ).fetchall()


def rename_material(connection: sqlite3.Connection, material_id: str, original_name: str) -> sqlite3.Row | None:
    updated_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET original_name = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
            (original_name, updated_at, material_id),
        )
        if cursor.rowcount != 1:
            return None
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, e.status, e.error_code, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, m.updated_at "
        "FROM materials m JOIN extractions e ON e.material_id = m.id WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()


def soft_delete_material(connection: sqlite3.Connection, material_id: str) -> bool:
    deleted_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
            (deleted_at, deleted_at, material_id),
        )
    return cursor.rowcount == 1
