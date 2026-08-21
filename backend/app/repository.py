from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters.file_parsers.models import ParseResult
from .chunking import CHUNKING_STRATEGY, CHUNKING_VERSION, SourceSpan, chunk_text
from .migrations.runner import MigrationError, assert_schema_version, migrate

VALID_STATUSES = {"success", "empty", "rejected", "failed"}
SEARCH_SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
RETRIEVAL_POLICY_VERSION = "lexical_fts_v1"
CONTEXT_ASSEMBLER_POLICY_VERSION = "context_assembler_v1"
MAX_CONTEXT_TOKENS = 2000
CITATION_KEY_PREFIX = "ctx-"
MAX_RETRIEVAL_QUERY_LENGTH = 1000
MAX_RETRIEVAL_TOP_K = 50
MAX_QA_QUESTION_LENGTH = 1000
QA_PROMPT_VERSION = "qa_fake_v1"


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


def _delete_chunk_search_rows(connection: sqlite3.Connection, chunk_ids: list[str]) -> None:
    if not chunk_ids:
        return
    placeholders = ",".join("?" for _ in chunk_ids)
    connection.execute(f"DELETE FROM chunks_search WHERE id IN ({placeholders})", chunk_ids)


def _ensure_chunk_search_index(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT c.id, c.text, c.normalized_text FROM chunks c "
        "JOIN materials m ON m.id = c.material_id "
        "JOIN material_revisions r ON r.id = c.revision_id "
        "WHERE c.status = 'ready' AND m.deleted_at IS NULL AND r.is_current = 1 "
        "AND r.material_id = c.material_id AND r.extraction_id = c.extraction_id"
    ).fetchall()
    valid = {str(row["id"]): row for row in rows}
    existing = {str(row[0]) for row in connection.execute("SELECT id FROM chunks_search").fetchall()}
    _delete_chunk_search_rows(connection, sorted(existing - set(valid)))
    missing = [row for chunk_id, row in valid.items() if chunk_id not in existing]
    connection.executemany(
        "INSERT INTO chunks_search (id, text, normalized_text) VALUES (?, ?, ?)",
        [(str(row["id"]), str(row["text"]), str(row["normalized_text"])) for row in missing],
    )


def _sync_chunk_search_for_revision(connection: sqlite3.Connection, revision_id: str) -> None:
    rows = connection.execute(
        "SELECT id, text, normalized_text FROM chunks WHERE revision_id = ? AND status = 'ready' "
        "ORDER BY chunk_index, id", (revision_id,)
    ).fetchall()
    _delete_chunk_search_rows(connection, [str(row["id"]) for row in rows])
    connection.executemany(
        "INSERT INTO chunks_search (id, text, normalized_text) VALUES (?, ?, ?)",
        [(str(row["id"]), str(row["text"]), str(row["normalized_text"])) for row in rows],
    )


def _retrieval_tokens(query: str) -> list[str]:
    return [token for token in query.strip().split() if token]


def _retrieval_preview(text: str, tokens: list[str], limit: int = 240) -> str:
    lowered = text.casefold()
    positions = [lowered.find(token.casefold()) for token in tokens if token.casefold() in lowered]
    start = max(0, min(positions) - 60) if positions else 0
    return text[start:start + limit]


def _create_retrieval_run(connection: sqlite3.Connection, *, query: str, normalized_query: str,
                          project_id: str, status: str, error_code: str | None) -> str:
    run_id = f"retrieval_{uuid.uuid4().hex}"
    connection.execute(
        "INSERT INTO retrieval_runs (id, query, normalized_query, project_id, thread_id, policy_version, "
        "embedding_provider_id, embedding_model_id, status, error_code, created_at) "
        "VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL, ?, ?, ?)",
        (run_id, query, normalized_query, project_id, RETRIEVAL_POLICY_VERSION, status, error_code, utc_now()),
    )
    return run_id


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
        _ensure_chunk_search_index(connection)
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
        connection.execute(
            "UPDATE qa_citations SET status = 'source_unavailable' "
            "WHERE material_id = ? AND status = 'valid'",
            (material_id,),
        )
        connection.execute("DELETE FROM material_search WHERE material_id = ?", (material_id,))
        chunk_ids = [str(value[0]) for value in connection.execute(
            "SELECT id FROM chunks WHERE material_id = ?", (material_id,)
        ).fetchall()]
        _delete_chunk_search_rows(connection, chunk_ids)
        connection.execute("DELETE FROM materials WHERE id = ? AND deleted_at IS NOT NULL", (material_id,))
    return row[0], row[1], row[2]


def get_qa_citation_detail(connection: sqlite3.Connection, citation_key: str) -> dict[str, object] | None:
    citation = connection.execute(
        "SELECT id, citation_key, material_id, revision_id, extraction_id, chunk_id, span_id, status "
        "FROM qa_citations WHERE citation_key = ? ORDER BY position, id LIMIT 1",
        (citation_key,),
    ).fetchone()
    if citation is None:
        return None
    status = str(citation["status"])
    if status == "source_unavailable":
        return {"citation_key": citation_key, "status": "source_unavailable",
                "material_id": citation["material_id"], "revision_id": citation["revision_id"],
                "chunk_id": citation["chunk_id"], "span_ids": [citation["span_id"]] if citation["span_id"] else []}
    material = connection.execute(
        "SELECT deleted_at FROM materials WHERE id = ?", (citation["material_id"],)
    ).fetchone()
    if material is None:
        return {"citation_key": citation_key, "status": "source_unavailable",
                "material_id": citation["material_id"], "revision_id": citation["revision_id"],
                "chunk_id": citation["chunk_id"], "span_ids": [citation["span_id"]] if citation["span_id"] else []}
    if material["deleted_at"] is not None:
        return {"citation_key": citation_key, "status": "source_deleted",
                "material_id": citation["material_id"], "revision_id": citation["revision_id"],
                "chunk_id": citation["chunk_id"], "span_ids": [citation["span_id"]] if citation["span_id"] else []}
    chunk = connection.execute(
        "SELECT c.id, c.material_id, c.revision_id, c.start_offset, c.end_offset, c.text, "
        "r.extraction_id FROM chunks c JOIN material_revisions r ON r.id = c.revision_id "
        "WHERE c.id = ? AND c.material_id = ? AND r.is_current = 1 AND c.status = 'ready'",
        (citation["chunk_id"], citation["material_id"]),
    ).fetchone()
    if chunk is None:
        return {"citation_key": citation_key, "status": "source_unavailable",
                "material_id": citation["material_id"], "revision_id": citation["revision_id"],
                "chunk_id": citation["chunk_id"], "span_ids": [citation["span_id"]] if citation["span_id"] else []}
    excerpt = " ".join(str(chunk["text"]).split())[:240]
    span_ids = [str(row[0]) for row in connection.execute(
        "SELECT span_id FROM chunk_spans WHERE chunk_id = ? ORDER BY span_id", (chunk["id"],)
    ).fetchall()]
    return {"citation_key": citation_key, "status": "valid", "material_id": chunk["material_id"],
            "revision_id": chunk["revision_id"], "chunk_id": chunk["id"],
            "extraction_id": chunk["extraction_id"], "start_offset": chunk["start_offset"],
            "end_offset": chunk["end_offset"], "span_ids": span_ids, "excerpt": excerpt}


def list_qa_threads(connection: sqlite3.Connection, *, project_id: str, limit: int = 50) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT t.id, t.title, t.created_at, t.updated_at, "
        "(SELECT COUNT(*) FROM qa_messages m WHERE m.thread_id = t.id) AS message_count "
        "FROM qa_threads t WHERE t.project_id = ? AND t.archived_at IS NULL "
        "ORDER BY t.updated_at DESC, t.id DESC LIMIT ?",
        (project_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_qa_thread_history(connection: sqlite3.Connection, *, project_id: str,
                          thread_id: str) -> dict[str, object] | None:
    thread = connection.execute(
        "SELECT id, title, created_at, updated_at FROM qa_threads "
        "WHERE id = ? AND project_id = ? AND archived_at IS NULL",
        (thread_id, project_id),
    ).fetchone()
    if thread is None:
        return None
    messages: list[dict[str, object]] = []
    rows = connection.execute(
        "SELECT m.id, m.role, m.content, m.created_at, a.id AS answer_id, "
        "a.status AS answer_status, a.provider_id, a.model_id "
        "FROM qa_messages m LEFT JOIN qa_answers a ON a.message_id = m.id "
        "WHERE m.thread_id = ? ORDER BY m.rowid",
        (thread_id,),
    ).fetchall()
    for row in rows:
        message = {"id": row["id"], "role": row["role"], "content": row["content"],
                   "created_at": row["created_at"]}
        if row["answer_id"] is not None:
            citations = connection.execute(
                "SELECT citation_key, material_id, revision_id, chunk_id, position "
                "FROM qa_citations WHERE answer_id = ? ORDER BY position, id",
                (row["answer_id"],),
            ).fetchall()
            citation_items: list[dict[str, object]] = []
            for citation in citations:
                detail = get_qa_citation_detail(connection, str(citation["citation_key"])) or {
                    "citation_key": citation["citation_key"], "status": "source_unavailable",
                    "material_id": citation["material_id"], "revision_id": citation["revision_id"],
                    "chunk_id": citation["chunk_id"], "span_ids": [],
                }
                material = connection.execute(
                    "SELECT original_name FROM materials WHERE id = ?", (citation["material_id"],)
                ).fetchone()
                citation_items.append({
                    "citation_key": citation["citation_key"], "position": citation["position"],
                    "material_id": citation["material_id"], "material_name": material[0] if material else None,
                    "revision_id": detail.get("revision_id"), "chunk_id": detail.get("chunk_id"),
                    "span_ids": detail.get("span_ids", []), "status": detail.get("status", "source_unavailable"),
                    "start_offset": detail.get("start_offset"), "end_offset": detail.get("end_offset"),
                    "excerpt": detail.get("excerpt"),
                })
            message["answer_id"] = row["answer_id"]
            message["answer_status"] = row["answer_status"]
            message["provider_id"] = row["provider_id"]
            message["model_id"] = row["model_id"]
            message["citations"] = citation_items
        messages.append(message)
    return {"thread": dict(thread), "messages": messages}


def soft_delete_material(connection: sqlite3.Connection, material_id: str) -> bool:
    deleted_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET deleted_at = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL",
            (deleted_at, deleted_at, material_id),
        )
    return cursor.rowcount == 1


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_payload(connection: sqlite3.Connection, material_id: str, extraction_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT m.id AS material_id, m.source_sha256, e.id AS extraction_id, e.parser_id, "
        "e.parser_version, e.text, e.status FROM materials m JOIN extractions e "
        "ON e.material_id = m.id WHERE m.id = ? AND e.id = ?",
        (material_id, extraction_id),
    ).fetchone()


def _revision_fingerprint(row: sqlite3.Row) -> str:
    values = (str(row["source_sha256"]), _sha256_text(str(row["text"])),
              str(row["parser_id"]), str(row["parser_version"]))
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def create_or_get_revision(connection: sqlite3.Connection, material_id: str,
                            extraction_id: str) -> sqlite3.Row:
    row = _revision_payload(connection, material_id, extraction_id)
    if row is None:
        raise ValueError("material_extraction_mismatch")
    fingerprint = _revision_fingerprint(row)
    existing = connection.execute(
        "SELECT * FROM material_revisions WHERE revision_fingerprint = ?", (fingerprint,)
    ).fetchone()
    if existing is not None:
        if existing["material_id"] != material_id or existing["extraction_id"] != extraction_id:
            raise ValueError("revision_fingerprint_conflict")
        connection.execute(
            "UPDATE material_revisions SET is_current = 1, superseded_at = NULL "
            "WHERE id = ?", (existing["id"],)
        )
        connection.execute(
            "UPDATE material_revisions SET is_current = 0, superseded_at = COALESCE(superseded_at, ?) "
            "WHERE material_id = ? AND id != ? AND is_current = 1",
            (utc_now(), material_id, existing["id"]),
        )
        return connection.execute("SELECT * FROM material_revisions WHERE id = ?", (existing["id"],)).fetchone()
    now = utc_now()
    connection.execute(
        "UPDATE material_revisions SET is_current = 0, superseded_at = COALESCE(superseded_at, ?) "
        "WHERE material_id = ? AND is_current = 1",
        (now, material_id),
    )
    revision_id = f"revision_{uuid.uuid4().hex}"
    connection.execute(
        "INSERT INTO material_revisions "
        "(id, material_id, extraction_id, source_sha256, extraction_sha256, parser_id, parser_version, "
        "revision_fingerprint, is_current, created_at, superseded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, NULL)",
        (revision_id, material_id, extraction_id, row["source_sha256"], _sha256_text(str(row["text"])),
         row["parser_id"], row["parser_version"], fingerprint, now),
    )
    return connection.execute("SELECT * FROM material_revisions WHERE id = ?", (revision_id,)).fetchone()


def index_material_revision(connection: sqlite3.Connection, material_id: str,
                            extraction_id: str, *, chunk_size: int = 800,
                            overlap: int = 80) -> sqlite3.Row:
    row = _revision_payload(connection, material_id, extraction_id)
    if row is None:
        raise ValueError("material_extraction_mismatch")
    if connection.execute("SELECT deleted_at FROM materials WHERE id = ?", (material_id,)).fetchone()[0] is not None:
        raise ValueError("source_deleted")
    with connection:
        revision = create_or_get_revision(connection, material_id, extraction_id)
        existing = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE revision_id = ? AND status = 'ready'", (revision["id"],)
        ).fetchone()[0]
        if existing:
            _sync_chunk_search_for_revision(connection, str(revision["id"]))
            return revision
        old_chunk_ids = [str(value[0]) for value in connection.execute(
            "SELECT id FROM chunks WHERE revision_id = ?", (revision["id"],)
        ).fetchall()]
        _delete_chunk_search_rows(connection, old_chunk_ids)
        connection.execute("DELETE FROM chunks WHERE revision_id = ?", (revision["id"],))
        spans = [SourceSpan(str(span["id"]), int(span["ordinal"]), str(span["span_kind"]),
                            str(span["label"]), str(span["text"]))
                 for span in connection.execute(
                     "SELECT id, ordinal, span_kind, label, text FROM text_spans "
                     "WHERE extraction_id = ? ORDER BY ordinal, id", (extraction_id,)).fetchall()]
        drafts = chunk_text(str(row["text"]), spans, chunk_size=chunk_size, overlap=overlap,
                            strategy=CHUNKING_STRATEGY, version=CHUNKING_VERSION)
        for draft in drafts:
            chunk_id = f"chunk_{uuid.uuid4().hex}"
            connection.execute(
                "INSERT INTO chunks (id, project_id, material_id, revision_id, extraction_id, chunk_index, text, "
                "normalized_text, start_offset, end_offset, token_count_estimate, overlap_before, overlap_after, "
                "strategy, chunking_version, status, error_code, created_at, superseded_at) "
                "VALUES (?, (SELECT project_id FROM materials WHERE id = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', NULL, ?, NULL)",
                (chunk_id, material_id, material_id, revision["id"], extraction_id, draft.chunk_index, draft.text,
                 draft.normalized_text, draft.start_offset, draft.end_offset, draft.token_count_estimate,
                 draft.overlap_before, draft.overlap_after, CHUNKING_STRATEGY, CHUNKING_VERSION, utc_now()),
            )
            connection.executemany(
                "INSERT INTO chunk_spans (chunk_id, span_id, overlap_start, overlap_end) VALUES (?, ?, ?, ?)",
                [(chunk_id, span_id, start, end) for span_id, start, end in draft.span_overlaps],
            )
        _sync_chunk_search_for_revision(connection, str(revision["id"]))
        return connection.execute("SELECT * FROM material_revisions WHERE id = ?", (revision["id"],)).fetchone()


def run_chunk_retrieval(connection: sqlite3.Connection, *, project_id: str, query: str,
                        material_ids: list[str] | None = None, top_k: int = 5) -> dict[str, object]:
    normalized = query.strip()
    tokens = _retrieval_tokens(normalized)
    if not tokens or len(normalized) > MAX_RETRIEVAL_QUERY_LENGTH:
        raise ValueError("retrieval_invalid_query")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_RETRIEVAL_TOP_K:
        raise ValueError("retrieval_invalid_top_k")
    requested = material_ids or []
    if len(set(requested)) != len(requested):
        raise ValueError("retrieval_invalid_materials")
    with connection:
        if requested:
            placeholders = ",".join("?" for _ in requested)
            rows = connection.execute(
                f"SELECT id, deleted_at FROM materials WHERE project_id = ? AND id IN ({placeholders})",
                [project_id, *requested],
            ).fetchall()
            if len(rows) != len(requested):
                raise ValueError("material_not_found")
            if any(row["deleted_at"] is not None for row in rows):
                raise ValueError("source_deleted")
        scope = ""
        params: list[object] = [project_id]
        if requested:
            scope = " AND c.material_id IN (" + ",".join("?" for _ in requested) + ")"
            params.extend(requested)
        ready_count = connection.execute(
            "SELECT COUNT(*) FROM chunks c JOIN materials m ON m.id = c.material_id "
            "JOIN material_revisions r ON r.id = c.revision_id "
            "WHERE c.project_id = ? AND m.deleted_at IS NULL AND r.is_current = 1 "
            "AND c.status = 'ready' AND r.material_id = c.material_id AND r.extraction_id = c.extraction_id" + scope,
            params,
        ).fetchone()[0]
        if not ready_count:
            run_id = _create_retrieval_run(connection, query=query, normalized_query=normalized,
                                           project_id=project_id, status="failed", error_code="retrieval_not_ready")
            return {"run_id": run_id, "status": "failed", "error_code": "retrieval_not_ready", "query": normalized,
                    "policy_version": RETRIEVAL_POLICY_VERSION, "hits": []}
        common = (
            " FROM chunks c JOIN chunks_search s ON s.id = c.id "
            "JOIN materials m ON m.id = c.material_id JOIN material_revisions r ON r.id = c.revision_id "
            "WHERE c.project_id = ? AND m.deleted_at IS NULL AND r.is_current = 1 AND c.status = 'ready' "
            "AND r.material_id = c.material_id AND r.extraction_id = c.extraction_id" + scope
        )
        ascii_tokens = all(token.isascii() and token.replace("_", "").isalnum() for token in tokens)
        if ascii_tokens:
            match = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
            sql = ("SELECT c.id, c.material_id, c.revision_id, c.start_offset, c.end_offset, c.text, "
                   "-bm25(chunks_search) AS lexical_score" + common + " AND chunks_search MATCH ? "
                   "ORDER BY lexical_score DESC, c.start_offset ASC, c.id ASC LIMIT ?")
            rows = connection.execute(sql, [*params, match, top_k]).fetchall()
        else:
            filters = "".join(" AND instr(lower(c.text), lower(?)) > 0" for _ in tokens)
            sql = ("SELECT c.id, c.material_id, c.revision_id, c.start_offset, c.end_offset, c.text, "
                   "1.0 AS lexical_score" + common + filters + " "
                   "ORDER BY lexical_score DESC, c.start_offset ASC, c.id ASC LIMIT ?")
            rows = connection.execute(sql, [*params, *tokens, top_k]).fetchall()
        if not rows:
            run_id = _create_retrieval_run(connection, query=query, normalized_query=normalized,
                                           project_id=project_id, status="empty", error_code="retrieval_empty")
            return {"run_id": run_id, "status": "empty", "error_code": "retrieval_empty", "query": normalized,
                    "policy_version": RETRIEVAL_POLICY_VERSION, "hits": []}
        run_id = _create_retrieval_run(connection, query=query, normalized_query=normalized,
                                       project_id=project_id, status="succeeded", error_code=None)
        hits: list[dict[str, object]] = []
        for rank, row in enumerate(rows, 1):
            score = float(row["lexical_score"])
            connection.execute(
                "INSERT INTO retrieval_hits (run_id, chunk_id, rank, score, lexical_score, vector_score, "
                "rerank_score, selected, citation_label) VALUES (?, ?, ?, ?, ?, NULL, NULL, 1, ?)",
                (run_id, row["id"], rank, score, score, f"chunk-{rank}"),
            )
            span_ids = [str(value[0]) for value in connection.execute(
                "SELECT span_id FROM chunk_spans WHERE chunk_id = ? ORDER BY span_id", (row["id"],)
            ).fetchall()]
            hits.append({"chunk_id": row["id"], "material_id": row["material_id"], "revision_id": row["revision_id"],
                         "rank": rank, "score": score, "lexical_score": score, "citation_label": f"chunk-{rank}",
                         "text_preview": _retrieval_preview(str(row["text"]), tokens),
                         "start_offset": row["start_offset"], "end_offset": row["end_offset"], "span_ids": span_ids})
        return {"run_id": run_id, "status": "succeeded", "error_code": None, "query": normalized,
                "policy_version": RETRIEVAL_POLICY_VERSION, "hits": hits}


def get_material_index_status(connection: sqlite3.Connection, material_id: str) -> dict[str, object] | None:
    material = connection.execute(
        "SELECT id, deleted_at FROM materials WHERE id = ?", (material_id,)
    ).fetchone()
    if material is None:
        return None
    revision = connection.execute(
        "SELECT * FROM material_revisions WHERE material_id = ? AND is_current = 1 "
        "ORDER BY created_at DESC, id DESC LIMIT 1", (material_id,)
    ).fetchone()
    if revision is None:
        return {"material_id": material_id, "status": "not_indexed", "revision_id": None, "chunk_count": 0}
    count = connection.execute(
        "SELECT COUNT(*) FROM chunks WHERE revision_id = ? AND status = 'ready'", (revision["id"],)
    ).fetchone()[0]
    status = "ready" if count else "empty"
    return {"material_id": material_id, "status": "deleted" if material["deleted_at"] else status,
            "revision_id": revision["id"], "chunk_count": count,
            "is_current": bool(revision["is_current"]), "chunking_version": CHUNKING_VERSION}


def create_qa_request(connection: sqlite3.Connection, *, project_id: str, question: str,
                      material_ids: list[str], thread_id: str | None,
                      request_id: str | None) -> dict[str, str]:
    normalized = question.strip()
    if not normalized or len(normalized) > MAX_QA_QUESTION_LENGTH:
        raise ValueError("qa_invalid_question")
    if not material_ids or len(material_ids) != len(set(material_ids)):
        raise ValueError("qa_invalid_materials")
    created_at = utc_now()
    fingerprint = hashlib.sha256(
        (normalized + "\x1f" + "\x1f".join(sorted(material_ids))).encode("utf-8")
    ).hexdigest()
    with connection:
        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex}"
            title = normalized[:120]
            connection.execute(
                "INSERT INTO qa_threads (id, project_id, title, created_at, updated_at, archived_at) "
                "VALUES (?, ?, ?, ?, ?, NULL)",
                (thread_id, project_id, title, created_at, created_at),
            )
        else:
            thread = connection.execute(
                "SELECT id, archived_at FROM qa_threads WHERE id = ? AND project_id = ?",
                (thread_id, project_id),
            ).fetchone()
            if thread is None:
                raise ValueError("qa_thread_not_found")
            if thread["archived_at"] is not None:
                raise ValueError("qa_thread_archived")
        operation_id = f"operation_{uuid.uuid4().hex}"
        user_message_id = f"message_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO ai_operations (id, operation_type, status, project_id, material_id, thread_id, "
            "input_fingerprint, source_revision, retrieval_policy_version, prompt_version, provider_id, "
            "model_id, request_id, retry_count, error_code, output_artifact_id, prompt_tokens, "
            "completion_tokens, latency_ms, created_at, started_at, finished_at) "
            "VALUES (?, 'qa_answer', 'running', ?, NULL, ?, ?, NULL, ?, ?, NULL, NULL, ?, 0, NULL, "
            "NULL, NULL, NULL, NULL, ?, ?, NULL)",
            (operation_id, project_id, thread_id, fingerprint, RETRIEVAL_POLICY_VERSION,
             QA_PROMPT_VERSION, request_id, created_at, created_at),
        )
        connection.execute(
            "INSERT INTO qa_messages (id, thread_id, role, content, created_at, ai_operation_id) "
            "VALUES (?, ?, 'user', ?, ?, ?)",
            (user_message_id, thread_id, normalized, created_at, operation_id),
        )
        connection.execute("UPDATE qa_threads SET updated_at = ? WHERE id = ?", (created_at, thread_id))
    return {"thread_id": thread_id, "operation_id": operation_id, "user_message_id": user_message_id}


def fail_qa_operation(connection: sqlite3.Connection, operation_id: str, error_code: str) -> None:
    with connection:
        connection.execute(
            "UPDATE ai_operations SET status = 'failed', error_code = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            (error_code, utc_now(), operation_id),
        )


def persist_qa_answer(connection: sqlite3.Connection, *, project_id: str, operation_id: str,
                      thread_id: str, provider_id: str, model_id: str, answer_text: str,
                      citation_keys: list[str], context_blocks: list[dict[str, object]],
                      prompt_tokens: int, completion_tokens: int, latency_ms: int) -> dict[str, object]:
    allowed = {str(block.get("citation_key")): block for block in context_blocks}
    verified: list[tuple[str, dict[str, object], dict[str, object]]] = []
    for key in citation_keys:
        if key not in allowed or any(key == existing[0] for existing in verified):
            continue
        validation = validate_citation_key(connection, key)
        block = allowed[key]
        source = block.get("source_info", {})
        if (validation.get("status") == "valid" and isinstance(source, dict)
                and validation["material_id"] == source.get("material_id")
                and validation["revision_id"] == source.get("revision_id")):
            verified.append((key, validation, block))
    if not verified:
        raise ValueError("citation_verification_failed")
    created_at = utc_now()
    assistant_message_id = f"message_{uuid.uuid4().hex}"
    answer_id = f"answer_{uuid.uuid4().hex}"
    with connection:
        extraction_rows = {
            str(row["id"]): str(row["extraction_id"])
            for row in connection.execute(
                "SELECT id, extraction_id FROM material_revisions WHERE id IN ({})".format(
                    ",".join("?" for _key, validation, _block in verified)
                ),
                [validation["revision_id"] for _key, validation, _block in verified],
            ).fetchall()
        }
        connection.execute(
            "INSERT INTO qa_messages (id, thread_id, role, content, created_at, ai_operation_id) "
            "VALUES (?, ?, 'assistant', ?, ?, ?)",
            (assistant_message_id, thread_id, answer_text, created_at, operation_id),
        )
        connection.execute(
            "INSERT INTO qa_answers (id, message_id, ai_operation_id, answer_text, answer_format, "
            "source_coverage, status, prompt_version, provider_id, model_id, generated_at) "
            "VALUES (?, ?, ?, ?, 'plain_text', 'cited', 'ready', ?, ?, ?, ?)",
            (answer_id, assistant_message_id, operation_id, answer_text, QA_PROMPT_VERSION,
             provider_id, model_id, created_at),
        )
        for position, (key, validation, block) in enumerate(verified, 1):
            span_ids = block.get("span_ids", [])
            span_id = str(span_ids[0]) if isinstance(span_ids, list) and span_ids else None
            revision_id = str(validation["revision_id"])
            connection.execute(
                "INSERT INTO qa_citations (id, answer_id, citation_key, material_id, revision_id, extraction_id, "
                "chunk_id, span_id, quote, position, source_revision, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, 'valid')",
                (f"citation_{uuid.uuid4().hex}", answer_id, key, validation["material_id"], revision_id,
                 extraction_rows.get(revision_id), validation["chunk_id"], span_id, position, revision_id),
            )
        connection.execute(
            "UPDATE ai_operations SET status = 'succeeded', provider_id = ?, model_id = ?, "
            "output_artifact_id = ?, prompt_tokens = ?, completion_tokens = ?, latency_ms = ?, "
            "finished_at = ? WHERE id = ? AND project_id = ? AND status = 'running'",
            (provider_id, model_id, answer_id, prompt_tokens, completion_tokens, latency_ms,
             created_at, operation_id, project_id),
        )
        connection.execute("UPDATE qa_threads SET updated_at = ? WHERE id = ?", (created_at, thread_id))
    return {
        "assistant_message_id": assistant_message_id,
        "answer_id": answer_id,
        "citations": [
            {"citation_key": key, "material_id": validation["material_id"],
             "revision_id": validation["revision_id"], "chunk_id": validation["chunk_id"],
             "span_ids": block.get("span_ids", []), "position": position, "status": "valid"}
            for position, (key, validation, block) in enumerate(verified, 1)
        ],
    }


def _citation_key(material_id: str, chunk_id: str) -> str:
    # IDs are prefixed (material_xxx / chunk_xxx); use the UUID portion only
    mid = material_id.split("_", 1)[1] if "_" in material_id else material_id
    cid = chunk_id.split("_", 1)[1] if "_" in chunk_id else chunk_id
    return f"{CITATION_KEY_PREFIX}{mid[:8]}-{cid[:8]}"


def _parse_citation_key(key: str) -> tuple[str, str] | None:
    if not key.startswith(CITATION_KEY_PREFIX):
        return None
    parts = key[len(CITATION_KEY_PREFIX):].split("-", 1)
    if len(parts) != 2 or len(parts[0]) != 8 or len(parts[1]) != 8:
        return None
    # Verify each part is a valid hex string (UUID prefix, not full UUID)
    for part in parts:
        try:
            int(part, 16)
        except ValueError:
            return None
    return parts[0], parts[1]


def validate_citation_key(connection: sqlite3.Connection, key: str) -> dict[str, object] | None:
    parsed = _parse_citation_key(key)
    if parsed is None:
        return {"status": "invalid_format"}
    material_id_hint, chunk_id_hint = parsed
    # IDs are prefixed (material_xxx / chunk_xxx); search with prefix included
    material = connection.execute(
        "SELECT id, deleted_at FROM materials WHERE id LIKE ?",
        (f"material_{material_id_hint}%",),
    ).fetchone()
    if material is None:
        return {"status": "source_purged"}
    if material["deleted_at"] is not None:
        return {"status": "source_deleted", "material_id": material["id"]}
    # Verify chunk exists and links to active current revision
    chunk = connection.execute(
        "SELECT c.id, c.status, c.revision_id, m.id AS material_id "
        "FROM chunks c JOIN materials m ON m.id = c.material_id "
        "JOIN material_revisions r ON r.id = c.revision_id "
        "WHERE c.id LIKE ? AND m.deleted_at IS NULL AND r.is_current = 1 "
        "AND r.material_id = c.material_id AND r.extraction_id = c.extraction_id",
        (f"chunk_{chunk_id_hint}%",),
    ).fetchone()
    if chunk is None:
        return {"status": "source_purged"}
    return {
        "status": "valid",
        "material_id": chunk["material_id"],
        "chunk_id": chunk["id"],
        "revision_id": chunk["revision_id"],
    }


def assemble_context(connection: sqlite3.Connection, *, project_id: str, hits: list[dict[str, object]],
                     max_tokens: int = MAX_CONTEXT_TOKENS) -> dict[str, object]:
    if not isinstance(hits, list) or max_tokens <= 0:
        raise ValueError("context_invalid_input")
    if not hits:
        return {"context_blocks": [], "total_tokens_estimate": 0,
                "policy_version": CONTEXT_ASSEMBLER_POLICY_VERSION, "truncated": False}
    seen_chunks: set[str] = set()
    ordered: list[tuple[str, int]] = []
    for h in hits:
        cid = str(h.get("chunk_id", ""))
        if cid in seen_chunks or not cid:
            continue
        seen_chunks.add(cid)
        ordered.append((cid, h.get("rank", 0)))
    placeholders = ",".join("?" for _ in ordered)
    sql = ("SELECT c.id, c.material_id, c.revision_id, c.start_offset, c.end_offset, c.text, "
           "m.original_name FROM chunks c JOIN materials m ON m.id = c.material_id "
           "JOIN material_revisions r ON r.id = c.revision_id "
           "WHERE c.project_id = ? AND m.project_id = ? AND m.deleted_at IS NULL "
           "AND r.is_current = 1 AND c.status = 'ready' "
           "AND r.material_id = c.material_id AND r.extraction_id = c.extraction_id "
           "AND c.id IN ({})".format(placeholders))
    chunk_params = [project_id, project_id] + [cid for cid, _ in ordered]
    rows_by_id: dict[str, sqlite3.Row] = {}
    for row in connection.execute(sql, chunk_params).fetchall():
        rows_by_id[str(row["id"])] = row
    blocks: list[dict[str, object]] = []
    total_chars = 0
    truncated = False
    for cid, _rank in ordered:
        row = rows_by_id.get(cid)
        if row is None:
            continue
        text = str(row["text"])
        token_estimate = len(text)
        if total_chars + token_estimate > max_tokens * 4:
            truncated = True
            break
        total_chars += token_estimate
        span_ids = [str(s["span_id"]) for s in connection.execute(
            "SELECT span_id FROM chunk_spans WHERE chunk_id = ? ORDER BY span_id", (row["id"],)
        ).fetchall()]
        blocks.append({
            "citation_key": _citation_key(str(row["material_id"]), str(row["id"])),
            "material_name": str(row["original_name"]),
            "text": text,
            "source_info": {
                "material_id": str(row["material_id"]),
                "revision_id": str(row["revision_id"]),
                "start_offset": row["start_offset"],
                "end_offset": row["end_offset"],
            },
            "span_ids": span_ids,
        })
    return {"context_blocks": blocks, "total_tokens_estimate": total_chars // 4,
            "policy_version": CONTEXT_ASSEMBLER_POLICY_VERSION, "truncated": truncated}
