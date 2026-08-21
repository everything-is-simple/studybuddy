from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters.file_parsers.models import ParseResult
from .migrations.runner import MigrationError, assert_schema_version, migrate

VALID_STATUSES = {"success", "empty", "rejected", "failed"}
SEARCH_SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"


def _ensure_search_index(connection: sqlite3.Connection) -> None:
    connection.execute(SEARCH_SCHEMA)
    existing = {row[0] for row in connection.execute("SELECT material_id FROM material_search")}
    rows = connection.execute(
        "SELECT m.id, m.original_name, e.text FROM materials m JOIN extractions e ON e.material_id = m.id"
    ).fetchall()
    source_ids = {row[0] for row in rows}
    for material_id in existing - source_ids:
        connection.execute("DELETE FROM material_search WHERE material_id = ?", (material_id,))
    indexed = {row[0] for row in rows if row[0] in existing}
    for row in rows:
        if row[0] not in indexed:
            connection.execute("INSERT INTO material_search (material_id, original_name, text) VALUES (?, ?, ?)", tuple(row))


def _insert_search_row(connection: sqlite3.Connection, material_id: str, original_name: str, text: str) -> None:
    connection.execute("INSERT INTO material_search (material_id, original_name, text) VALUES (?, ?, ?)",
                       (material_id, original_name, text))


def _replace_search_row(connection: sqlite3.Connection, material_id: str) -> None:
    connection.execute("DELETE FROM material_search WHERE material_id = ?", (material_id,))
    row = connection.execute(
        "SELECT m.id, m.original_name, e.text FROM materials m JOIN extractions e ON e.material_id = m.id WHERE m.id = ?",
        (material_id,),
    ).fetchone()
    if row is not None:
        _insert_search_row(connection, str(row[0]), str(row[1]), str(row[2]))


def _search_tokens(query: str) -> list[str]:
    return [token for token in query.strip().split() if token]


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 2000")
    try:
        migrate(connection)
        assert_schema_version(connection)
        _ensure_search_index(connection)
        connection.commit()
    except MigrationError:
        connection.close()
        raise
    except sqlite3.Error:
        connection.close()
        raise
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
        _insert_search_row(connection, material_id, original_name, result.text)
    return material_id, extraction_id


def _snippet(text: str, tokens: list[str]) -> str:
    lowered = text.casefold()
    positions = [lowered.find(token.casefold()) for token in tokens if token.casefold() in lowered]
    if not positions:
        return ""
    start = max(0, min(positions) - 50)
    end = min(len(text), start + 160)
    return text[start:end]


def _search_rows(connection: sqlite3.Connection, status: str | None, query: str) -> list[sqlite3.Row]:
    tokens = _search_tokens(query)
    if not tokens:
        return []
    query_sql = (
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, e.created_at, m.updated_at, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, e.text AS search_text "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL"
    )
    params: list[str] = []
    if status is not None:
        query_sql += " AND e.status = ?"
        params.append(status)
    if all(token.isascii() and token.replace("_", "").isalnum() for token in tokens):
        match = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
        query_sql += " AND m.id IN (SELECT material_id FROM material_search WHERE material_search MATCH ?)"
        params.append(match)
    else:
        for token in tokens:
            query_sql += " AND (instr(lower(m.original_name), lower(?)) > 0 OR instr(lower(e.text), lower(?)) > 0)"
            params.extend((token, token))
    query_sql += " ORDER BY e.created_at DESC, m.id DESC"
    rows = connection.execute(query_sql, params).fetchall()
    return [row for row in rows if all(
        token.casefold() in str(row[1]).casefold() or token.casefold() in str(row[10]).casefold()
        for token in tokens
    )]


def list_materials(connection: sqlite3.Connection, status: str | None = None,
                   query: str | None = None) -> list[sqlite3.Row | dict[str, object]]:
    normalized = (query or "").strip()
    if normalized:
        results: list[dict[str, object]] = []
        for row in _search_rows(connection, status, normalized):
            payload = dict(row)
            text = str(payload.pop("search_text"))
            tokens = _search_tokens(normalized)
            fields = []
            if any(token.casefold() in str(payload["original_name"]).casefold() for token in tokens):
                fields.append("original_name")
            if any(token.casefold() in text.casefold() for token in tokens):
                fields.append("text")
            payload["match_fields"] = fields
            payload["snippet"] = _snippet(text, tokens)
            results.append(payload)
        return results
    query_sql = (
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id WHERE m.deleted_at IS NULL"
    )
    params: tuple[str, ...] = ()
    if status is not None:
        query_sql += " AND e.status = ?"
        params = (status,)
    query_sql += " ORDER BY e.created_at DESC, m.id DESC"
    return connection.execute(query_sql, params).fetchall()


def list_deleted_materials(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, m.deleted_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NOT NULL ORDER BY m.deleted_at DESC, m.id DESC"
    ).fetchall()


def list_materials_page(connection: sqlite3.Connection, status: str | None = None, query: str | None = None,
                        limit: int = 20, offset: int = 0) -> tuple[list[sqlite3.Row | dict[str, object]], int]:
    rows = list_materials(connection, status, query)
    return rows[offset:offset + limit], len(rows)


def list_deleted_materials_page(connection: sqlite3.Connection, limit: int = 20,
                                offset: int = 0) -> tuple[list[sqlite3.Row], int]:
    rows = list_deleted_materials(connection)
    return rows[offset:offset + limit], len(rows)


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
        _replace_search_row(connection, material_id)
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, e.status, e.error_code, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, m.updated_at "
        "FROM materials m JOIN extractions e ON e.material_id = m.id WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()


def purge_material(connection: sqlite3.Connection, material_id: str) -> tuple[str | None, str | None, str | None]:
    with connection:
        row = connection.execute(
            "SELECT source_sha256, stored_path, original_name FROM materials WHERE id = ? AND deleted_at IS NOT NULL",
            (material_id,),
        ).fetchone()
        if row is None:
            return None, None, None
        connection.execute("DELETE FROM material_search WHERE material_id = ?", (material_id,))
        connection.execute("DELETE FROM materials WHERE id = ? AND deleted_at IS NOT NULL", (material_id,))
    return row[0], row[1], row[2]


def soft_delete_material(connection: sqlite3.Connection, material_id: str) -> bool:
    deleted_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
            (deleted_at, deleted_at, material_id),
        )
    return cursor.rowcount == 1
