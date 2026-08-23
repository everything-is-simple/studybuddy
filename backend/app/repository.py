from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters.file_parsers.models import ParseResult
from .chunking import CHUNKING_STRATEGY, CHUNKING_VERSION, SourceSpan, chunk_text
from .embedding import (EMBEDDING_ENCODING, MAX_EMBEDDING_PAYLOAD_BYTES, EmbeddingError,
                         EmbeddingIdentity, EmbeddingProvider, cosine_similarity, decode_vector,
                         embedding_content_hash, embedding_staleness, encode_vector)
from .migrations.runner import MigrationError, assert_schema_version, migrate

VALID_STATUSES = {"success", "empty", "rejected", "failed"}
RETRIEVAL_POLICY_VERSION = "lexical_fts_v1"
CONTEXT_ASSEMBLER_POLICY_VERSION = "context_assembler_v1"
MAX_CONTEXT_TOKENS = 2000
CITATION_KEY_PREFIX = "ctx-"
MAX_RETRIEVAL_QUERY_LENGTH = 1000
MAX_RETRIEVAL_TOP_K = 50
VECTOR_POLICY_VERSION = "vector_cosine_v1"
HYBRID_POLICY_VERSION = "hybrid_rrf_v1"
FALLBACK_LEXICAL_POLICY_VERSION = "fallback_lexical_v1"
RRF_K = 60
VECTOR_CANDIDATE_POOL = 50
MAX_QA_QUESTION_LENGTH = 1000
QA_PROMPT_VERSION = "qa_fake_v1"
QA_OPERATION_LEASE_SECONDS = 300


def _ensure_search_index(connection: sqlite3.Connection) -> None:
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
                          project_id: str, status: str, error_code: str | None,
                          embedding_provider_id: str | None = None,
                          embedding_model_id: str | None = None,
                          policy_version: str | None = None) -> str:
    run_id = f"retrieval_{uuid.uuid4().hex}"
    connection.execute(
        "INSERT INTO retrieval_runs (id, query, normalized_query, project_id, thread_id, policy_version, "
        "embedding_provider_id, embedding_model_id, status, error_code, created_at) "
        "VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)",
        (run_id, query, normalized_query, project_id, policy_version or RETRIEVAL_POLICY_VERSION,
         embedding_provider_id, embedding_model_id, status, error_code, utc_now()),
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


def _search_rows(connection: sqlite3.Connection, status: str | None, query: str,
                 *, limit: int | None = None, offset: int = 0) -> list[sqlite3.Row]:
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
    if limit is not None:
        query_sql += " LIMIT ? OFFSET ?"
        params.extend((str(limit), str(offset)))
    rows = connection.execute(query_sql, params).fetchall()
    return [row for row in rows if all(
        token.casefold() in str(row[1]).casefold() or token.casefold() in str(row[10]).casefold()
        for token in tokens
    )]


def _search_count(connection: sqlite3.Connection, status: str | None, query: str) -> int:
    tokens = _search_tokens(query)
    if not tokens:
        return 0
    query_sql = (
        "SELECT COUNT(*) FROM materials m JOIN extractions e ON e.material_id = m.id "
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
    return int(connection.execute(query_sql, params).fetchone()[0])


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
    normalized = (query or "").strip()
    if normalized:
        # Keep the same filtering contract as list_materials while applying the
        # page window in SQLite rather than materializing every match.
        total = _search_count(connection, status, normalized)
        rows = _search_rows(connection, status, normalized, limit=limit, offset=offset)
        tokens = _search_tokens(normalized)
        results: list[dict[str, object]] = []
        for row in rows:
            payload = dict(row)
            text = str(payload.pop("search_text"))
            payload["match_fields"] = [field for field, value in (
                ("original_name", payload["original_name"]), ("text", text)
            ) if any(token.casefold() in str(value).casefold() for token in tokens)]
            payload["snippet"] = _snippet(text, tokens)
            results.append(payload)
        return results, total
    base = (
        " FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL"
    )
    params: list[str] = []
    if status is not None:
        base += " AND e.status = ?"
        params.append(status)
    total = int(connection.execute("SELECT COUNT(*)" + base, params).fetchone()[0])
    rows = connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count" + base +
        " ORDER BY e.created_at DESC, m.id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return rows, total


def list_deleted_materials_page(connection: sqlite3.Connection, limit: int = 20,
                                offset: int = 0) -> tuple[list[sqlite3.Row], int]:
    base = (
        " FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NOT NULL"
    )
    total = int(connection.execute("SELECT COUNT(*)" + base).fetchone()[0])
    rows = connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, m.deleted_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count" + base +
        " ORDER BY m.deleted_at DESC, m.id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return rows, total


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
    material_name_row = connection.execute(
        "SELECT original_name, deleted_at FROM materials WHERE id = ?", (citation["material_id"],)
    ).fetchone()
    material_name = material_name_row["original_name"] if material_name_row else None
    base = {"citation_key": citation_key, "material_id": citation["material_id"],
            "material_name": material_name, "revision_id": citation["revision_id"],
            "chunk_id": citation["chunk_id"],
            "span_ids": [citation["span_id"]] if citation["span_id"] else []}
    status = str(citation["status"])
    if status == "source_unavailable":
        return {**base, "status": "source_unavailable"}
    material = material_name_row
    if material is None:
        return {**base, "status": "source_unavailable"}
    if material["deleted_at"] is not None:
        return {**base, "status": "source_deleted"}
    chunk = connection.execute(
        "SELECT c.id, c.material_id, c.revision_id, c.start_offset, c.end_offset, c.text, "
        "r.extraction_id FROM chunks c JOIN material_revisions r ON r.id = c.revision_id "
        "WHERE c.id = ? AND c.material_id = ? AND r.is_current = 1 AND c.status = 'ready'",
        (citation["chunk_id"], citation["material_id"]),
    ).fetchone()
    if chunk is None:
        return {**base, "status": "source_unavailable"}
    excerpt = " ".join(str(chunk["text"]).split())[:240]
    span_ids = [str(row[0]) for row in connection.execute(
        "SELECT span_id FROM chunk_spans WHERE chunk_id = ? ORDER BY span_id", (chunk["id"],)
    ).fetchall()]
    return {**base, "status": "valid", "material_id": chunk["material_id"],
            "material_name": material_name, "revision_id": chunk["revision_id"], "chunk_id": chunk["id"],
            "extraction_id": chunk["extraction_id"], "start_offset": chunk["start_offset"],
            "end_offset": chunk["end_offset"], "span_ids": span_ids, "excerpt": excerpt}


def list_qa_threads(connection: sqlite3.Connection, *, project_id: str, limit: int = 50) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT t.id, t.title, t.created_at, t.updated_at, "
        "(SELECT COUNT(*) FROM qa_messages m WHERE m.thread_id = t.id) AS message_count, "
        "CASE WHEN (SELECT COUNT(*) FROM qa_messages m WHERE m.thread_id = t.id) = 0 THEN 'empty' "
        "WHEN EXISTS (SELECT 1 FROM ai_operations o WHERE o.thread_id = t.id AND o.status = 'failed' "
        "AND o.created_at = (SELECT MAX(o2.created_at) FROM ai_operations o2 WHERE o2.thread_id = t.id)) THEN 'failed' "
        "ELSE 'active' END AS status "
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


def reclaim_stale_embedding_operations(connection: sqlite3.Connection, *, project_id: str,
                                       lease_seconds: int = QA_OPERATION_LEASE_SECONDS) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - lease_seconds
    stale_ids = []
    for row in connection.execute(
        "SELECT id, started_at FROM ai_operations WHERE project_id=? AND operation_type='embedding_index' AND status='running'",
        (project_id,),
    ).fetchall():
        try:
            started = datetime.fromisoformat(str(row["started_at"])).timestamp()
        except (TypeError, ValueError, OverflowError):
            continue
        if started <= cutoff:
            stale_ids.append(str(row["id"]))
    if stale_ids:
        with connection:
            connection.executemany(
                "UPDATE ai_operations SET status='stale', error_code='embedding_index_lease_expired', finished_at=? WHERE id=? AND status='running'",
                [(utc_now(), operation_id) for operation_id in stale_ids],
            )
    return len(stale_ids)


def create_embedding_index_operation(connection: sqlite3.Connection, *, project_id: str,
                                     material_id: str, source_revision: str,
                                     retry_count: int = 0) -> str:
    operation_id = f"embedding_index_{uuid.uuid4().hex}"
    now = utc_now()
    fingerprint = hashlib.sha256(f"{material_id}:{source_revision}".encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,retry_count,created_at,started_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (operation_id, "embedding_index", "running", project_id, material_id, fingerprint, source_revision, retry_count, now, now),
    )
    return operation_id


def finish_embedding_index_operation(connection: sqlite3.Connection, operation_id: str, *, status: str,
                                      error_code: str | None = None) -> None:
    if status not in {"succeeded", "failed", "stale"}:
        raise ValueError("embedding_operation_invalid_status")
    with connection:
        connection.execute(
            "UPDATE ai_operations SET status=?, error_code=?, finished_at=? WHERE id=? AND status='running'",
            (status, error_code, utc_now(), operation_id),
        )


def index_embeddings_for_material(connection: sqlite3.Connection, *, material_id: str,
                                  provider: EmbeddingProvider, rebuild: bool = False,
                                  retry_failed: bool = False, operation_id: str | None = None) -> dict[str, object]:
    """Explicit, synchronous SQLite-first indexing; never called during startup."""
    if getattr(provider, "dimensions", 0) == 0:
        probe = connection.execute(
            "SELECT text FROM chunks WHERE material_id=? AND status='ready' ORDER BY chunk_index, id LIMIT 1",
            (material_id,),
        ).fetchone()
        if probe is not None:
            provider.embed([str(probe["text"])])
    with connection:
        rows = connection.execute(
            "SELECT c.id, c.text, c.revision_id FROM chunks c JOIN materials m ON m.id=c.material_id "
            "JOIN material_revisions r ON r.id=c.revision_id WHERE c.material_id=? AND m.deleted_at IS NULL "
            "AND r.is_current=1 AND c.status='ready' ORDER BY c.chunk_index, c.id", (material_id,)
        ).fetchall()
        if not rows:
            return {"status": "empty", "material_id": material_id, "embedded_count": 0, "skipped_count": 0}
        embedded = skipped = 0
        for start in range(0, len(rows), 32):
            batch = rows[start:start + 32]
            todo = []
            for row in batch:
                content_hash = embedding_content_hash(str(row["text"]))
                encoding = getattr(provider, "encoding", EMBEDDING_ENCODING)
                identity = EmbeddingIdentity(
                    chunk_id=str(row["id"]), source_revision=str(row["revision_id"]),
                    content_hash=content_hash, provider_id=str(provider.provider_id),
                    model_id=str(provider.model_id), model_revision=str(provider.model_revision),
                    dimensions=provider.dimensions, vector_encoding=encoding,
                ).validate()
                existing = connection.execute(
                    "SELECT id,status FROM embeddings WHERE chunk_id=? AND source_revision=? AND content_hash=? "
                    "AND provider_id=? AND model_id=? AND model_revision=? AND dimensions=? AND vector_encoding=?",
                    (row["id"], row["revision_id"], content_hash, provider.provider_id, provider.model_id,
                     provider.model_revision, provider.dimensions, encoding),
                ).fetchone()
                if existing and existing["status"] == "ready":
                    skipped += 1
                elif existing and existing["status"] in {"stale", "failed", "running"} and not (rebuild or retry_failed):
                    skipped += 1
                else:
                    todo.append((row, content_hash))
            if not todo:
                continue
            try:
                vectors = provider.embed([str(row["text"]) for row, _ in todo])
                if len(vectors) != len(todo):
                    raise EmbeddingError("embedding_invalid_response")
                for (row, content_hash), vector in zip(todo, vectors):
                    payload = encode_vector(vector, encoding=encoding)
                    if len(vector) != provider.dimensions:
                        raise EmbeddingError("embedding_dimension_mismatch")
                    now = utc_now()
                    connection.execute("""INSERT INTO embeddings
                        (id,chunk_id,provider_id,model_id,model_revision,dimensions,vector_encoding,vector_payload,
                         content_hash,source_revision,status,error_code,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?, 'ready',NULL,?,?)
                        ON CONFLICT(chunk_id,source_revision,content_hash,provider_id,model_id,model_revision,dimensions,vector_encoding)
                        DO UPDATE SET vector_payload=excluded.vector_payload,status='ready',error_code=NULL,updated_at=excluded.updated_at""",
                        (f"embedding_{uuid.uuid4().hex}", row["id"], provider.provider_id, provider.model_id,
                         provider.model_revision, provider.dimensions, encoding, payload, content_hash,
                         row["revision_id"], now, now))
                    embedded += 1
            except EmbeddingError as error:
                for row, content_hash in todo:
                    now = utc_now()
                    connection.execute("""INSERT INTO embeddings
                        (id,chunk_id,provider_id,model_id,model_revision,dimensions,vector_encoding,vector_payload,
                         content_hash,source_revision,status,error_code,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?, 'failed',?,?,?,?)
                        ON CONFLICT(chunk_id,source_revision,content_hash,provider_id,model_id,model_revision,dimensions,vector_encoding)
                        DO UPDATE SET vector_payload=NULL,status='failed',error_code=excluded.error_code,updated_at=excluded.updated_at""",
                        (f"embedding_{uuid.uuid4().hex}", row["id"], provider.provider_id, provider.model_id,
                         provider.model_revision, provider.dimensions, encoding, None, content_hash,
                         row["revision_id"], error.code, now, now))
                raise
            except Exception:
                error = EmbeddingError("embedding_provider_failed")
                for row, content_hash in todo:
                    now = utc_now()
                    connection.execute("""INSERT INTO embeddings
                        (id,chunk_id,provider_id,model_id,model_revision,dimensions,vector_encoding,vector_payload,
                         content_hash,source_revision,status,error_code,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?, 'failed',?,?,?,?)
                        ON CONFLICT(chunk_id,source_revision,content_hash,provider_id,model_id,model_revision,dimensions,vector_encoding)
                        DO UPDATE SET vector_payload=NULL,status='failed',error_code=excluded.error_code,updated_at=excluded.updated_at""",
                        (f"embedding_{uuid.uuid4().hex}", row["id"], provider.provider_id, provider.model_id,
                         provider.model_revision, provider.dimensions, encoding, None, content_hash,
                         row["revision_id"], error.code, now, now))
                raise error
        return {"status": "ready", "material_id": material_id, "embedded_count": embedded, "skipped_count": skipped,
                "provider_id": provider.provider_id, "model_id": provider.model_id, "dimensions": provider.dimensions,
                "rebuild": rebuild, "retry_failed": retry_failed}


def verify_embeddings(connection: sqlite3.Connection, *, project_id: str | None = None,
                      material_id: str | None = None, revision_id: str | None = None) -> dict[str, object]:
    """Read-only, deterministic embedding integrity report; never rebuilds or mutates rows."""
    if sum(value is not None for value in (project_id, material_id, revision_id)) > 1:
        raise ValueError("embedding_verify_ambiguous_scope")
    where, params = [], []
    if project_id is not None:
        where.append("m.project_id=?"); params.append(project_id)
    if material_id is not None:
        where.append("m.id=?"); params.append(material_id)
    if revision_id is not None:
        where.append("r.id=?"); params.append(revision_id)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = connection.execute(
        "SELECT e.*, c.text, c.status AS chunk_status, c.revision_id AS chunk_revision_id, "
        "m.deleted_at, r.is_current, r.material_id AS revision_material_id "
        "FROM embeddings e LEFT JOIN chunks c ON c.id=e.chunk_id "
        "LEFT JOIN materials m ON m.id=c.material_id LEFT JOIN material_revisions r ON r.id=e.source_revision" + clause,
        params).fetchall()
    counts = {"checked": 0, "ready_valid": 0, "ready_invalid": 0, "stale": 0,
              "failed": 0, "running": 0, "orphan": 0}
    issue_counts: dict[str, int] = {}
    for row in rows:
        counts["checked"] += 1
        status = str(row["status"])
        if status in {"stale", "failed", "running"}:
            counts[status] += 1
        if row["chunk_id"] is None or row["deleted_at"] is None and row["revision_material_id"] is None:
            counts["orphan"] += 1
            issue_counts["embedding_orphan"] = issue_counts.get("embedding_orphan", 0) + 1
            if status == "ready": counts["ready_invalid"] += 1
            continue
        try:
            expected = EmbeddingIdentity(str(row["chunk_id"]), str(row["source_revision"]),
                embedding_content_hash(str(row["text"])), str(row["provider_id"]), str(row["model_id"]),
                str(row["model_revision"]), int(row["dimensions"]), str(row["vector_encoding"]))
            expected.validate()
            reason = embedding_staleness(row, expected_identity=expected, payload_valid=True,
                                     source_state=("deleted" if row["deleted_at"] is not None else
                                                   "not_current" if row["is_current"] != 1 else
                                                   "not_ready" if row["chunk_status"] != "ready" else "ready"))
        except (EmbeddingError, TypeError, ValueError) as error:
            reason = error.code if isinstance(error, EmbeddingError) else "embedding_identity_invalid"
        if reason is None and status == "ready":
            try:
                decode_vector(row["vector_payload"], int(row["dimensions"]), encoding=str(row["vector_encoding"]))
            except EmbeddingError as error:
                reason = error.code
        if reason is not None:
            issue_counts[reason] = issue_counts.get(reason, 0) + 1
            if status == "ready": counts["ready_invalid"] += 1
        elif status == "ready":
            counts["ready_valid"] += 1
    invalid = counts["ready_invalid"] > 0 or counts["orphan"] > 0
    return {"status": "invalid" if invalid else ("empty" if not rows else "valid"),
            "scope": {"project_id": project_id, "material_id": material_id, "revision_id": revision_id},
            "counts": counts, "issues": [{"code": code, "count": issue_counts[code]} for code in sorted(issue_counts)],
            "policy_version": "embedding_verify_v1"}


def rebuild_embeddings_for_material(connection: sqlite3.Connection, *, material_id: str,
                                    provider: EmbeddingProvider, retry_failed: bool = True) -> dict[str, object]:
    """Explicit synchronous rebuild; callers must provide a bounded material scope."""
    if not isinstance(material_id, str) or not material_id:
        raise ValueError("embedding_rebuild_scope_required")
    return index_embeddings_for_material(connection, material_id=material_id, provider=provider,
                                         rebuild=True, retry_failed=retry_failed)


def _lexical_candidates(connection: sqlite3.Connection, *, project_id: str, query: str,
                         material_ids: list[str] | None, limit: int) -> tuple[str, list[sqlite3.Row]]:
    normalized = query.strip()
    tokens = _retrieval_tokens(normalized)
    if not tokens or len(normalized) > MAX_RETRIEVAL_QUERY_LENGTH:
        raise ValueError("retrieval_invalid_query")
    requested = material_ids or []
    if len(set(requested)) != len(requested):
        raise ValueError("retrieval_invalid_materials")
    if requested:
        placeholders = ",".join("?" for _ in requested)
        rows = connection.execute(f"SELECT id, deleted_at FROM materials WHERE project_id=? AND id IN ({placeholders})",
                                   [project_id, *requested]).fetchall()
        if len(rows) != len(requested):
            raise ValueError("material_not_found")
        if any(row["deleted_at"] is not None for row in rows):
            raise ValueError("source_deleted")
    scope = ""
    params: list[object] = [project_id]
    if requested:
        scope = " AND c.material_id IN (" + ",".join("?" for _ in requested) + ")"
        params.extend(requested)
    common = (" FROM chunks c JOIN chunks_search s ON s.id=c.id JOIN materials m ON m.id=c.material_id "
              "JOIN material_revisions r ON r.id=c.revision_id WHERE c.project_id=? AND m.deleted_at IS NULL "
              "AND r.is_current=1 AND c.status='ready' AND r.material_id=c.material_id AND r.extraction_id=c.extraction_id" + scope)
    ready = connection.execute("SELECT COUNT(*)" + common, params).fetchone()[0]
    if not ready:
        return "retrieval_not_ready", []
    ascii_tokens = all(token.isascii() and token.replace("_", "").isalnum() for token in tokens)
    if ascii_tokens:
        match = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
        sql = "SELECT c.id,c.material_id,c.revision_id,c.start_offset,c.end_offset,c.text,-bm25(chunks_search) AS lexical_score" + common + " AND chunks_search MATCH ? ORDER BY lexical_score DESC,c.start_offset ASC,c.id ASC LIMIT ?"
        rows = connection.execute(sql, [*params, match, limit]).fetchall()
    else:
        filters = "".join(" AND instr(lower(c.text),lower(?))>0" for _ in tokens)
        sql = "SELECT c.id,c.material_id,c.revision_id,c.start_offset,c.end_offset,c.text,1.0 AS lexical_score" + common + filters + " ORDER BY lexical_score DESC,c.start_offset ASC,c.id ASC LIMIT ?"
        rows = connection.execute(sql, [*params, *tokens, limit]).fetchall()
    return ("succeeded" if rows else "empty"), list(rows)


def _hydrate_provider_dimensions(connection: sqlite3.Connection, *, project_id: str,
                                  provider: EmbeddingProvider) -> None:
    if getattr(provider, "dimensions", 0):
        return
    row = connection.execute(
        "SELECT dimensions FROM embeddings e JOIN chunks c ON c.id=e.chunk_id "
        "JOIN materials m ON m.id=c.material_id WHERE c.project_id=? AND e.provider_id=? "
        "AND e.model_id=? AND e.model_revision=? AND e.status='ready' ORDER BY e.updated_at DESC LIMIT 1",
        (project_id, provider.provider_id, provider.model_id, provider.model_revision),
    ).fetchone()
    if row is not None:
        setattr(provider, "dimensions", int(row["dimensions"]))


def _vector_candidates(connection: sqlite3.Connection, *, project_id: str, query: str,
                       provider: EmbeddingProvider, material_ids: list[str] | None,
                       limit: int) -> tuple[str, list[dict[str, object]]]:
    _hydrate_provider_dimensions(connection, project_id=project_id, provider=provider)
    query_vector = provider.embed([query.strip()])[0]
    requested = material_ids or []
    scope = ""
    params: list[object] = [project_id, provider.provider_id, provider.model_id, provider.model_revision,
                            provider.dimensions, getattr(provider, "encoding", EMBEDDING_ENCODING)]
    if requested:
        scope = " AND c.material_id IN (" + ",".join("?" for _ in requested) + ")"; params.extend(requested)
    rows = connection.execute("""SELECT e.*,c.material_id,c.revision_id,c.text,c.start_offset,c.end_offset
        FROM embeddings e JOIN chunks c ON c.id=e.chunk_id JOIN materials m ON m.id=c.material_id
        JOIN material_revisions r ON r.id=c.revision_id WHERE c.project_id=? AND e.provider_id=?
        AND e.model_id=? AND e.model_revision=? AND e.dimensions=? AND e.vector_encoding=?
        AND e.status='ready' AND m.deleted_at IS NULL AND r.is_current=1 AND c.status='ready'
        AND r.material_id=c.material_id""" + scope, params).fetchall()
    scored = []
    for row in rows:
        try:
            identity = EmbeddingIdentity(str(row["chunk_id"]), str(row["revision_id"]), embedding_content_hash(str(row["text"])),
                provider.provider_id, provider.model_id, provider.model_revision, provider.dimensions,
                getattr(provider, "encoding", EMBEDDING_ENCODING))
            if embedding_staleness(row, expected_identity=identity, payload_valid=True) is not None:
                continue
            score = cosine_similarity(query_vector, decode_vector(row["vector_payload"], row["dimensions"], encoding=row["vector_encoding"]))
            scored.append((score, row))
        except EmbeddingError:
            continue
    scored.sort(key=lambda item: (-round(item[0], 12), str(item[1]["id"])))
    return ("succeeded" if scored else "empty"), [{**dict(row), "id": str(row["chunk_id"]), "vector_score": score} for score, row in scored[:limit]]


def _persist_ranked_retrieval(connection: sqlite3.Connection, *, project_id: str, query: str,
                              policy: str, status: str, error_code: str | None,
                              ranked: list[dict[str, object]], provider: EmbeddingProvider | None = None) -> dict[str, object]:
    run_id = _create_retrieval_run(connection, query=query, normalized_query=query.strip(), project_id=project_id,
                                    status=status, error_code=error_code, policy_version=policy,
                                    embedding_provider_id=provider.provider_id if provider else None,
                                    embedding_model_id=provider.model_id if provider else None)
    hits = []
    with connection:
        for rank, row in enumerate(ranked, 1):
            final = float(row["score"]); lexical = row.get("lexical_score"); vector = row.get("vector_score")
            connection.execute("INSERT INTO retrieval_hits (run_id,chunk_id,rank,score,lexical_score,vector_score,rerank_score,selected,citation_label) VALUES (?,?,?,?,?,?,NULL,1,?)",
                (run_id, row["id"], rank, final, lexical, vector, f"chunk-{rank}"))
            hits.append({"chunk_id":row["id"], "material_id":row["material_id"], "revision_id":row["revision_id"],
                         "rank":rank, "score":final, "lexical_score":lexical, "vector_score":vector,
                         "lexical_rank":row.get("lexical_rank"), "vector_rank":row.get("vector_rank"),
                         "citation_label":f"chunk-{rank}", "text_preview":_retrieval_preview(str(row["text"]), _retrieval_tokens(query))})
    return {"run_id":run_id, "status":status, "error_code":error_code, "query":query.strip(), "policy_version":policy, "hits":hits}


def run_hybrid_retrieval(connection: sqlite3.Connection, *, project_id: str, query: str,
                         provider: EmbeddingProvider | None, material_ids: list[str] | None = None,
                         top_k: int = 5, allow_fallback: bool = True,
                         embedding_error_code: str = "embedding_provider_not_configured") -> dict[str, object]:
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_RETRIEVAL_TOP_K:
        raise ValueError("retrieval_invalid_top_k")
    try:
        lexical_status, lexical_rows = _lexical_candidates(connection, project_id=project_id, query=query,
                                                            material_ids=material_ids, limit=VECTOR_CANDIDATE_POOL)
        if provider is None:
            raise EmbeddingError(embedding_error_code)
        vector_status, vector_rows = _vector_candidates(connection, project_id=project_id, query=query,
                                                        provider=provider, material_ids=material_ids, limit=VECTOR_CANDIDATE_POOL)
    except EmbeddingError as error:
        code = getattr(error, "code", "embedding_index_unavailable")
        if not allow_fallback:
            raise
        lexical_status, lexical_rows = _lexical_candidates(connection, project_id=project_id, query=query,
                                                            material_ids=material_ids, limit=top_k)
        ranked = [{**dict(row), "score": float(row["lexical_score"]), "lexical_score": float(row["lexical_score"]), "vector_score": None,
                   "lexical_rank": index + 1, "vector_rank": None} for index, row in enumerate(lexical_rows)]
        result = _persist_ranked_retrieval(connection, project_id=project_id, query=query,
                                           policy=FALLBACK_LEXICAL_POLICY_VERSION, status=lexical_status,
                                           error_code=code, ranked=ranked)
        result.update({"fallback": True, "fallback_reason": code})
        return result
    merged: dict[str, dict[str, object]] = {}
    for index, row in enumerate(lexical_rows, 1):
        item = merged.setdefault(str(row["id"]), {**dict(row), "lexical_rank": index, "vector_rank": None,
                                                   "lexical_score": float(row["lexical_score"]), "vector_score": None})
        item["rrf"] = 1.0 / (RRF_K + index)
    for index, row in enumerate(vector_rows, 1):
        item = merged.setdefault(str(row["id"]), {**row, "lexical_rank": None, "vector_rank": index,
                                                   "lexical_score": None, "vector_score": float(row["vector_score"])})
        item["vector_rank"] = index; item["vector_score"] = float(row["vector_score"])
        item["rrf"] = float(item.get("rrf", 0.0)) + 1.0 / (RRF_K + index)
    ranked = [{**item, "score": float(item.get("rrf", 0.0))} for item in merged.values()]
    ranked.sort(key=lambda item: (-round(item["score"], 12), str(item["id"]))); ranked = ranked[:top_k]
    status = "succeeded" if ranked else ("failed" if lexical_status == "retrieval_not_ready" else "empty")
    code = "retrieval_not_ready" if status == "failed" else ("retrieval_empty" if not ranked else None)
    result = _persist_ranked_retrieval(connection, project_id=project_id, query=query, policy=HYBRID_POLICY_VERSION,
                                       status=status, error_code=code, ranked=ranked, provider=provider)
    result["fallback"] = False
    return result


def run_vector_retrieval(connection: sqlite3.Connection, *, project_id: str, query: str,
                         provider: EmbeddingProvider, material_ids: list[str] | None = None,
                         top_k: int = 5) -> dict[str, object]:
    if not query.strip() or len(query.strip()) > MAX_RETRIEVAL_QUERY_LENGTH or not 1 <= top_k <= MAX_RETRIEVAL_TOP_K:
        raise ValueError("retrieval_invalid_query" if not query.strip() else "retrieval_invalid_top_k")
    _hydrate_provider_dimensions(connection, project_id=project_id, provider=provider)
    vectors = provider.embed([query.strip()])
    query_vector = vectors[0]
    requested = material_ids or []
    scope = ""; params: list[object] = [project_id, provider.provider_id, provider.model_id, provider.model_revision, provider.dimensions, EMBEDDING_ENCODING]
    if requested:
        scope = " AND c.material_id IN (" + ",".join("?" for _ in requested) + ")"; params.extend(requested)
    rows = connection.execute("""SELECT e.*,c.material_id,c.revision_id,c.text,c.start_offset,c.end_offset FROM embeddings e
        JOIN chunks c ON c.id=e.chunk_id JOIN materials m ON m.id=c.material_id JOIN material_revisions r ON r.id=c.revision_id
        WHERE c.project_id=? AND e.provider_id=? AND e.model_id=? AND e.model_revision=? AND e.dimensions=? AND e.vector_encoding=?
        AND e.status='ready' AND m.deleted_at IS NULL AND r.is_current=1 AND c.status='ready' AND r.material_id=c.material_id""" + scope, params).fetchall()
    scored = []
    for row in rows:
        try:
            identity = EmbeddingIdentity(
                chunk_id=str(row["chunk_id"]), source_revision=str(row["revision_id"]),
                content_hash=embedding_content_hash(str(row["text"])),
                provider_id=provider.provider_id, model_id=provider.model_id,
                model_revision=provider.model_revision, dimensions=provider.dimensions,
                vector_encoding=EMBEDDING_ENCODING,
            )
            reason = embedding_staleness(row, expected_identity=identity, payload_valid=True)
            if reason is not None:
                continue
            score = cosine_similarity(query_vector, decode_vector(row["vector_payload"], row["dimensions"], encoding=row["vector_encoding"]))
        except EmbeddingError: continue
        scored.append((score, row))
    scored.sort(key=lambda item: (-round(item[0], 12), str(item[1]["id"])))
    selected = scored[:top_k]
    run_id = _create_retrieval_run(connection, query=query, normalized_query=query.strip(), project_id=project_id,
                                    status="succeeded" if selected else "empty", error_code=None if selected else "retrieval_empty",
                                    policy_version=VECTOR_POLICY_VERSION,
                                    embedding_provider_id=provider.provider_id,
                                    embedding_model_id=provider.model_id)
    hits = []
    with connection:
        for rank, (score, row) in enumerate(selected, 1):
            connection.execute("INSERT INTO retrieval_hits (run_id,chunk_id,rank,score,lexical_score,vector_score,rerank_score,selected,citation_label) VALUES (?,?,?,?,NULL,?,NULL,1,?)",
                               (run_id,row["chunk_id"],rank,score,score,f"chunk-{rank}"))
            hits.append({"chunk_id":row["chunk_id"],"material_id":row["material_id"],"revision_id":row["revision_id"],"rank":rank,"score":score,"vector_score":score,"citation_label":f"chunk-{rank}","text_preview":_retrieval_preview(str(row["text"]),[query])})
    return {"run_id":run_id,"status":"succeeded" if selected else "empty","error_code":None if selected else "retrieval_empty","query":query.strip(),"policy_version":VECTOR_POLICY_VERSION,"hits":hits}


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


def reclaim_stale_qa_operations(connection: sqlite3.Connection, *, project_id: str,
                                 lease_seconds: int = QA_OPERATION_LEASE_SECONDS) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - lease_seconds
    stale_ids: list[str] = []
    for row in connection.execute(
        "SELECT id, started_at FROM ai_operations "
        "WHERE project_id = ? AND operation_type = 'qa_answer' AND status = 'running'",
        (project_id,),
    ).fetchall():
        try:
            started = datetime.fromisoformat(str(row["started_at"])).timestamp()
        except (TypeError, ValueError, OverflowError):
            continue
        if started <= cutoff:
            stale_ids.append(str(row["id"]))
    if not stale_ids:
        return 0
    with connection:
        connection.executemany(
            "UPDATE ai_operations SET status = 'stale', error_code = ?, finished_at = ? "
            "WHERE id = ? AND status = 'running'",
            [("qa_operation_stale", utc_now(), operation_id) for operation_id in stale_ids],
        )
    return len(stale_ids)


def get_idempotent_qa_response(connection: sqlite3.Connection, *, project_id: str,
                                idempotency_key: str, retrieval_mode: str = "lexical",
                                expected_fingerprint: str | None = None) -> dict[str, object] | None:
    operation = connection.execute(
        "SELECT id, status, thread_id, retrieval_run_id, output_artifact_id, error_code, input_fingerprint "
        "FROM ai_operations WHERE project_id = ? AND idempotency_key = ?",
        (project_id, idempotency_key),
    ).fetchone()
    if operation is None:
        return None
    if expected_fingerprint is not None and str(operation["input_fingerprint"]) != expected_fingerprint:
        raise ValueError("qa_idempotency_key_mismatch")
    if operation["status"] == "running":
        raise ValueError("qa_operation_in_progress")
    run = connection.execute(
        "SELECT policy_version FROM retrieval_runs WHERE id = ?",
        (operation["retrieval_run_id"],),
    ).fetchone()
    actual_mode = {"lexical_fts_v1": "lexical", "vector_cosine_v1": "vector",
                   "hybrid_rrf_v1": "hybrid", "fallback_lexical_v1": "hybrid"}.get(
                       str(run["policy_version"]) if run else "", "lexical")
    if actual_mode != retrieval_mode:
        raise ValueError("qa_idempotency_mode_mismatch")
    if operation["status"] != "succeeded" or not operation["output_artifact_id"]:
        return None
    answer = connection.execute(
        "SELECT a.answer_text, a.provider_id, a.model_id, m.id AS assistant_message_id "
        "FROM qa_answers a JOIN qa_messages m ON m.id = a.message_id "
        "WHERE a.id = ? AND a.ai_operation_id = ?",
        (operation["output_artifact_id"], operation["id"]),
    ).fetchone()
    if answer is None:
        return None
    citations = []
    for row in connection.execute(
        "SELECT citation_key, material_id, revision_id, chunk_id, span_id, position, status "
        "FROM qa_citations WHERE answer_id = ? ORDER BY position",
        (operation["output_artifact_id"],),
    ).fetchall():
        citation = dict(row)
        citation["span_ids"] = [citation.pop("span_id")] if citation.get("span_id") else []
        citations.append(citation)
    retrieval = connection.execute(
        "SELECT policy_version, error_code FROM retrieval_runs WHERE id = ?",
        (operation["retrieval_run_id"],),
    ).fetchone()
    retrieval_mode = {
        "lexical_fts_v1": "lexical", "vector_cosine_v1": "vector", "hybrid_rrf_v1": "hybrid",
        "fallback_lexical_v1": "hybrid",
    }.get(str(retrieval["policy_version"]) if retrieval else "", "lexical")
    return {
        "status": "succeeded", "thread_id": operation["thread_id"],
        "user_message_id": connection.execute(
            "SELECT id FROM qa_messages WHERE ai_operation_id = ? AND role = 'user'",
            (operation["id"],),
        ).fetchone()[0],
        "assistant_message_id": answer["assistant_message_id"],
        "answer_id": operation["output_artifact_id"], "operation_id": operation["id"],
        "answer_text": answer["answer_text"], "provider_id": answer["provider_id"],
        "model_id": answer["model_id"], "retrieval_run_id": operation["retrieval_run_id"],
        "retrieval": {
            "mode": retrieval_mode,
            "policy_version": retrieval["policy_version"] if retrieval else RETRIEVAL_POLICY_VERSION,
            "fallback": bool(retrieval and retrieval["policy_version"] == FALLBACK_LEXICAL_POLICY_VERSION),
            "fallback_reason": retrieval["error_code"] if retrieval and retrieval["policy_version"] == FALLBACK_LEXICAL_POLICY_VERSION else None,
            "run_id": operation["retrieval_run_id"],
        },
        "citations": citations,
    }


def qa_request_fingerprint(*, question: str, material_ids: list[str], thread_id: str | None,
                           retrieval_mode: str, allow_retrieval_fallback: bool) -> str:
    normalized = question.strip()
    payload = "\x1f".join((normalized, "\x1e".join(sorted(material_ids)), thread_id or "",
                           retrieval_mode, str(int(allow_retrieval_fallback))))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_qa_request(connection: sqlite3.Connection, *, project_id: str, question: str,
                      material_ids: list[str], thread_id: str | None,
                      request_id: str | None, idempotency_key: str | None = None,
                      retrieval_mode: str = "lexical", allow_retrieval_fallback: bool = True) -> dict[str, object]:
    normalized = question.strip()
    if not normalized or len(normalized) > MAX_QA_QUESTION_LENGTH:
        raise ValueError("qa_invalid_question")
    if not material_ids or len(material_ids) != len(set(material_ids)):
        raise ValueError("qa_invalid_materials")
    if retrieval_mode not in {"lexical", "vector", "hybrid"}:
        raise ValueError("retrieval_invalid_mode")
    if not isinstance(allow_retrieval_fallback, bool):
        raise ValueError("retrieval_invalid_fallback")
    created_at = utc_now()
    fingerprint = qa_request_fingerprint(
        question=normalized, material_ids=material_ids, thread_id=thread_id,
        retrieval_mode=retrieval_mode, allow_retrieval_fallback=allow_retrieval_fallback,
    )
    with connection:
        if idempotency_key:
            existing = connection.execute(
                "SELECT status FROM ai_operations WHERE project_id = ? AND idempotency_key = ?",
                (project_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["status"] == "running":
                    raise ValueError("qa_operation_in_progress")
                if existing["status"] == "succeeded":
                    return {"replay": True, "idempotency_key": idempotency_key}
                connection.execute(
                    "UPDATE ai_operations SET idempotency_key = NULL WHERE project_id = ? AND idempotency_key = ?",
                    (project_id, idempotency_key),
                )
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
            "completion_tokens, latency_ms, created_at, started_at, finished_at, idempotency_key) "
            "VALUES (?, 'qa_answer', 'running', ?, NULL, ?, ?, NULL, ?, ?, NULL, NULL, ?, 0, NULL, "
            "NULL, NULL, NULL, NULL, ?, ?, NULL, ?)",
            (operation_id, project_id, thread_id, fingerprint,
             {"lexical": RETRIEVAL_POLICY_VERSION, "vector": VECTOR_POLICY_VERSION,
              "hybrid": HYBRID_POLICY_VERSION}[retrieval_mode],
             QA_PROMPT_VERSION, request_id, created_at, created_at, idempotency_key),
        )
        connection.execute(
            "INSERT INTO qa_messages (id, thread_id, role, content, created_at, ai_operation_id) "
            "VALUES (?, ?, 'user', ?, ?, ?)",
            (user_message_id, thread_id, normalized, created_at, operation_id),
        )
        connection.execute("UPDATE qa_threads SET updated_at = ? WHERE id = ?", (created_at, thread_id))
    return {"thread_id": thread_id, "operation_id": operation_id, "user_message_id": user_message_id,
            "replay": False, "idempotency_key": idempotency_key}


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
                      prompt_tokens: int | None, completion_tokens: int | None, latency_ms: int,
                      provider_request_id: str | None = None, total_tokens: int | None = None,
                      finish_reason: str | None = None, retrieval_run_id: str | None = None) -> dict[str, object]:
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
            "provider_request_id = ?, total_tokens = ?, finish_reason = ?, "
            "finished_at = ?, retrieval_run_id = ? WHERE id = ? AND project_id = ? AND status = 'running'",
            (provider_id, model_id, answer_id, prompt_tokens, completion_tokens, latency_ms,
             provider_request_id, total_tokens, finish_reason, created_at, retrieval_run_id, operation_id, project_id),
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
