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
        _refresh_exercise_citations_for_material(connection, material_id)
        _refresh_card_citations_for_material(connection, material_id)
        _refresh_study_source_links_for_material(connection, material_id)
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, e.status, e.error_code, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, "
        "m.created_at, m.updated_at, m.deleted_at "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()


MAX_CARD_TEXT_LENGTH = 4000
MAX_CARD_TAGS = 20
MAX_CARD_CITATIONS = 20
MAX_DECK_TITLE_LENGTH = 200
MAX_EXERCISE_PROMPT_LENGTH = 4000
MAX_EXERCISE_OPTIONS = 10


def _validate_text(value: object, *, code: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(code)
    return value.strip()


def _validate_card_payload(payload: dict[str, object]) -> tuple[str, str, str, list[str]]:
    front = _validate_text(payload.get("front"), code="invalid_card_payload", maximum=MAX_CARD_TEXT_LENGTH)
    back = _validate_text(payload.get("back"), code="invalid_card_payload", maximum=MAX_CARD_TEXT_LENGTH)
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str) or len(explanation) > MAX_CARD_TEXT_LENGTH:
        raise ValueError("invalid_card_payload")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or len(tags) > MAX_CARD_TAGS or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 50 for tag in tags):
        raise ValueError("invalid_card_payload")
    return front, back, explanation, [tag.strip() for tag in tags]


def _citation_rows(connection: sqlite3.Connection, citations: object, *, code: str,
                   artifact_id: str, table: str) -> list[tuple[object, ...]]:
    if not isinstance(citations, list) or len(citations) > MAX_CARD_CITATIONS:
        raise ValueError(code)
    result: list[tuple[object, ...]] = []
    seen: set[str] = set()
    for position, item in enumerate(citations):
        if not isinstance(item, dict):
            raise ValueError("citation_invalid")
        key = item.get("citation_key")
        if not isinstance(key, str) or not key or len(key) > 100 or key in seen:
            raise ValueError("citation_invalid")
        seen.add(key)
        chunk_id = item.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("citation_invalid")
        chunk = connection.execute(
            "SELECT c.material_id, c.revision_id, c.extraction_id, c.text, c.status, r.is_current, m.deleted_at "
            "FROM chunks c JOIN material_revisions r ON r.id=c.revision_id JOIN materials m ON m.id=c.material_id "
            "WHERE c.id=?", (chunk_id,)
        ).fetchone()
        quote = item.get("quote", "")
        if chunk is None or not isinstance(quote, str) or not quote.strip() or len(quote) > 500:
            raise ValueError("citation_invalid")
        if chunk["status"] != "ready" or not chunk["is_current"] or chunk["deleted_at"] is not None or quote.strip() not in str(chunk["text"]):
            raise ValueError("citation_invalid")
        span_id = item.get("span_id")
        if span_id is not None and (not isinstance(span_id, str) or connection.execute(
                "SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id, span_id)).fetchone() is None):
            raise ValueError("citation_invalid")
        result.append((f"{table}_citation_{uuid.uuid4().hex}", artifact_id, key,
                       chunk["material_id"], chunk["revision_id"], chunk["extraction_id"], chunk_id,
                       span_id, quote.strip(), position, "valid"))
    return result


def create_deck(connection: sqlite3.Connection, *, project_id: str, title: str,
                description: str = "") -> dict[str, object]:
    title = _validate_text(title, code="invalid_deck_payload", maximum=MAX_DECK_TITLE_LENGTH)
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("invalid_deck_payload")
    deck_id = f"deck_{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (?, ?, ?)",
                           (project_id, "Default project", now))
        connection.execute("INSERT INTO study_decks VALUES (?,?,?,?,?,?,?,?)",
                           (deck_id, project_id, title, description, "active", now, now, None))
    return get_deck(connection, project_id=project_id, deck_id=deck_id) or {}


def get_deck(connection: sqlite3.Connection, *, project_id: str, deck_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM study_decks WHERE id=? AND project_id=?", (deck_id, project_id)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["cards"] = list_cards(connection, project_id=project_id, deck_id=deck_id)
    return result


def list_decks(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM study_decks WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()]


def list_cards(connection: sqlite3.Connection, *, project_id: str, deck_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    where = "c.project_id=?"
    if deck_id is not None:
        where += " AND c.deck_id=?"; params.append(deck_id)
    with connection:
        rows = connection.execute("SELECT c.id,c.deck_id,c.card_type,c.status,c.front,c.back,c.explanation,c.tags_json,c.source_revision,c.edited_by_user,c.created_at,c.updated_at,c.confirmed_at,c.archived_at FROM study_cards c WHERE " + where + " ORDER BY c.updated_at DESC,c.id DESC", params).fetchall()
        for row in rows:
            _refresh_card_citations(connection, str(row["id"]))
    return [{**dict(row), "tags": json.loads(row["tags_json"]), "citations": list_card_citations(connection, str(row["id"]))} for row in rows]


def list_card_citations(connection: sqlite3.Connection, card_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute("SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,quote,position,status FROM card_citations WHERE card_id=? ORDER BY position,id", (card_id,)).fetchall()]


def _refresh_card_citations(connection: sqlite3.Connection, card_id: str) -> list[str]:
    statuses: list[str] = []
    for citation in connection.execute("SELECT * FROM card_citations WHERE card_id=?", (card_id,)).fetchall():
        status = "source_unavailable"
        if citation["material_id"] is not None:
            material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (citation["material_id"],)).fetchone()
            if material is not None and material["deleted_at"] is not None:
                status = "source_deleted"
            elif material is not None and citation["chunk_id"] is not None:
                chunk = connection.execute(
                    "SELECT c.status,c.revision_id,c.extraction_id,r.is_current FROM chunks c JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                    (citation["chunk_id"], citation["material_id"]),
                ).fetchone()
                if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                    status = "valid" if chunk["revision_id"] == citation["revision_id"] and chunk["extraction_id"] == citation["extraction_id"] else "stale"
                elif chunk is not None:
                    status = "stale"
        connection.execute("UPDATE card_citations SET status=? WHERE id=?", (status, citation["id"]))
        statuses.append(status)
    return statuses


def _refresh_card_citations_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    for row in connection.execute("SELECT DISTINCT card_id FROM card_citations WHERE material_id=?", (material_id,)).fetchall():
        _refresh_card_citations(connection, str(row["card_id"]))


def create_card(connection: sqlite3.Connection, *, project_id: str, deck_id: str, payload: dict[str, object], card_type: str = "user_created", source_revision: str | None = None) -> dict[str, object]:
    if card_type not in {"user_created", "ai_generated"}:
        raise ValueError("invalid_card_payload")
    if connection.execute("SELECT 1 FROM study_decks WHERE id=? AND project_id=? AND status='active'", (deck_id, project_id)).fetchone() is None:
        raise ValueError("deck_not_found")
    front, back, explanation, tags = _validate_card_payload(payload)
    card_id = f"card_{uuid.uuid4().hex}"
    now = utc_now()
    citations = _citation_rows(connection, payload.get("citations", []), code="invalid_card_payload", artifact_id=card_id, table="card")
    with connection:
        connection.execute("INSERT INTO study_cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (card_id, deck_id, project_id, card_type, "draft", front, back, explanation, json.dumps(tags, ensure_ascii=False), source_revision, 0, None, now, now, None, None))
        connection.executemany("INSERT INTO card_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=deck_id) if item["id"] == card_id)


def update_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, payload: dict[str, object]) -> dict[str, object]:
    row = connection.execute("SELECT * FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None: raise ValueError("card_not_found")
    if row["status"] in {"ready", "archived"}: raise ValueError("card_edit_not_allowed")
    front, back, explanation, tags = _validate_card_payload(payload)
    with connection:
        connection.execute("UPDATE study_cards SET front=?,back=?,explanation=?,tags_json=?,edited_by_user=1,updated_at=? WHERE id=? AND status='draft'", (front, back, explanation, json.dumps(tags, ensure_ascii=False), utc_now(), card_id))
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=row["deck_id"]) if item["id"] == card_id)


def confirm_card(connection: sqlite3.Connection, *, project_id: str, card_id: str) -> dict[str, object]:
    row = connection.execute("SELECT deck_id,status FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None: raise ValueError("card_not_found")
    if row["status"] != "draft": raise ValueError("card_invalid_state")
    with connection:
        _refresh_card_citations(connection, card_id)
    if connection.execute("SELECT 1 FROM card_citations WHERE card_id=? AND status='valid'", (card_id,)).fetchone() is None:
        if connection.execute("SELECT card_type FROM study_cards WHERE id=?", (card_id,)).fetchone()[0] == "ai_generated": raise ValueError("citation_invalid")
    with connection: connection.execute("UPDATE study_cards SET status='ready',confirmed_at=?,updated_at=? WHERE id=?", (utc_now(), utc_now(), card_id))
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=row["deck_id"]) if item["id"] == card_id)


def transition_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, target: str) -> dict[str, object]:
    row = connection.execute("SELECT deck_id,status FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None:
        raise ValueError("card_not_found")
    allowed = {"rejected": {"draft"}, "archived": {"draft", "ready", "rejected", "stale"}}
    if target not in allowed or row["status"] not in allowed[target]:
        raise ValueError("card_invalid_state")
    now = utc_now()
    with connection:
        connection.execute("UPDATE study_cards SET status=?,updated_at=?,archived_at=? WHERE id=?", (target, now, now if target == "archived" else None, card_id))
    result = connection.execute("SELECT * FROM study_cards WHERE id=?", (card_id,)).fetchone()
    return _card_public(connection, result)


def review_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, result: str) -> dict[str, object]:
    if result not in {"again", "hard", "good", "easy"}: raise ValueError("invalid_card_review")
    if connection.execute("SELECT 1 FROM study_cards WHERE id=? AND project_id=? AND status='ready'", (card_id, project_id)).fetchone() is None: raise ValueError("card_not_ready")
    review_id = f"review_{uuid.uuid4().hex}"
    with connection: connection.execute("INSERT INTO card_reviews VALUES (?,?,?,?,?)", (review_id, card_id, result, utc_now(), "{}"))
    return {"id": review_id, "card_id": card_id, "result": result}


MAX_EXERCISE_EXPLANATION_LENGTH = 4000
MAX_EXERCISE_ANSWER_LENGTH = 1000
MAX_GENERATION_TOPIC_LENGTH = 500
MAX_GENERATION_COUNT = 10
GENERATION_PROMPT_VERSION = "phase8_draft_generation_v1"


def _exercise_payload(payload: dict[str, object], exercise_type: str) -> tuple[str, list[str], object, str]:
    if exercise_type not in {"multiple_choice", "true_false", "short_answer"}:
        raise ValueError("invalid_exercise_schema")
    prompt = _validate_text(payload.get("prompt"), code="invalid_exercise_schema", maximum=MAX_EXERCISE_PROMPT_LENGTH)
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str) or len(explanation) > MAX_EXERCISE_EXPLANATION_LENGTH:
        raise ValueError("invalid_exercise_schema")
    options = payload.get("options", [])
    if (not isinstance(options, list) or len(options) > MAX_EXERCISE_OPTIONS or
            any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in options)):
        raise ValueError("invalid_exercise_schema")
    options = [item.strip() for item in options]
    if len({item.casefold() for item in options}) != len(options):
        raise ValueError("invalid_exercise_schema")
    answer_key = payload.get("answer_key")
    if exercise_type == "multiple_choice":
        if len(options) < 2 or not isinstance(answer_key, int) or isinstance(answer_key, bool) or not 0 <= answer_key < len(options):
            raise ValueError("invalid_exercise_schema")
    elif exercise_type == "true_false":
        if (options and options != ["True", "False"]) or not isinstance(answer_key, bool):
            raise ValueError("invalid_exercise_schema")
        options = ["True", "False"]
    else:
        if options or not isinstance(answer_key, str) or not answer_key.strip() or len(answer_key) > MAX_EXERCISE_ANSWER_LENGTH:
            raise ValueError("invalid_exercise_schema")
        answer_key = answer_key.strip()
    return prompt, options, answer_key, explanation


def _exercise_citations(connection: sqlite3.Connection, citations: object, exercise_id: str) -> list[tuple[object, ...]]:
    return _citation_rows(connection, citations, code="invalid_exercise_schema", artifact_id=exercise_id, table="exercise")


def _refresh_exercise_citations(connection: sqlite3.Connection, exercise_id: str) -> list[str]:
    """Persist the current source lifecycle without trusting saved citation state."""
    statuses: list[str] = []
    for citation in connection.execute("SELECT * FROM exercise_citations WHERE exercise_id=?", (exercise_id,)).fetchall():
        status = "source_unavailable"
        if citation["material_id"] is not None:
            material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (citation["material_id"],)).fetchone()
            if material is not None and material["deleted_at"] is not None:
                status = "source_deleted"
            elif material is not None and citation["chunk_id"] is not None:
                chunk = connection.execute(
                    "SELECT c.status, c.revision_id, c.extraction_id, r.is_current FROM chunks c "
                    "JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                    (citation["chunk_id"], citation["material_id"]),
                ).fetchone()
                if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                    status = "valid" if (chunk["revision_id"] == citation["revision_id"] and
                                            chunk["extraction_id"] == citation["extraction_id"]) else "stale"
                elif chunk is not None:
                    status = "stale"
        connection.execute("UPDATE exercise_citations SET status=? WHERE id=?", (status, citation["id"]))
        statuses.append(status)
    return statuses


def _refresh_exercise_citations_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    for row in connection.execute(
            "SELECT DISTINCT exercise_id FROM exercise_citations WHERE material_id=?", (material_id,)).fetchall():
        _refresh_exercise_citations(connection, str(row["exercise_id"]))


def _validate_exercise_source_revision(connection: sqlite3.Connection, source_revision: str | None,
                                        citations: list[tuple[object, ...]], exercise_kind: str) -> None:
    if source_revision is not None:
        source = connection.execute(
            "SELECT r.id FROM material_revisions r JOIN materials m ON m.id=r.material_id "
            "WHERE r.id=? AND r.is_current=1 AND m.deleted_at IS NULL", (source_revision,)
        ).fetchone()
        if source is None:
            raise ValueError("citation_invalid")
    if citations and (source_revision is None or any(row[4] != source_revision for row in citations)):
        raise ValueError("citation_invalid")
    if exercise_kind == "ai_generated" and (not citations or source_revision is None):
        raise ValueError("citation_invalid")


def _exercise_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    result = {"id": row["id"], "set_id": row["set_id"], "exercise_type": row["exercise_type"],
              "exercise_kind": row["exercise_kind"], "status": row["status"], "prompt": row["prompt"],
              "options": json.loads(row["options_json"]), "explanation": row["explanation"],
              "source_revision": row["source_revision"], "edited_by_user": bool(row["edited_by_user"]),
              "created_at": row["created_at"], "updated_at": row["updated_at"],
              "confirmed_at": row["confirmed_at"], "archived_at": row["archived_at"]}
    result["citations"] = [dict(item) for item in connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,quote,position,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id", (row["id"],)).fetchall()]
    return result


def list_exercise_sets(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM exercise_sets WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [{**dict(row), "exercise_count": connection.execute("SELECT COUNT(*) FROM exercises WHERE set_id=?", (row["id"],)).fetchone()[0]} for row in rows]


def get_exercise_set(connection: sqlite3.Connection, *, project_id: str, set_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM exercise_sets WHERE id=? AND project_id=?", (set_id, project_id)).fetchone()
    if row is None:
        return None
    return {**dict(row), "exercises": list_exercises(connection, project_id=project_id, set_id=set_id)}


def create_exercise_set(connection: sqlite3.Connection, *, project_id: str, title: str, description: str = "") -> dict[str, object]:
    title = _validate_text(title, code="invalid_exercise_set_payload", maximum=MAX_DECK_TITLE_LENGTH)
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("invalid_exercise_set_payload")
    now, set_id = utc_now(), f"exercise_set_{uuid.uuid4().hex}"
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)", (project_id, "Default project", now))
        connection.execute("INSERT INTO exercise_sets VALUES (?,?,?,?,?,?,?,?)", (set_id, project_id, title, description, "active", now, now, None))
    return get_exercise_set(connection, project_id=project_id, set_id=set_id) or {}


def _generation_fingerprint(*, artifact_kind: str, container_id: str, topic: str, material_ids: list[str],
                            retrieval_mode: str, allow_fallback: bool, count: int,
                            exercise_type: str | None, source_revision: str | None) -> str:
    payload = "\x1f".join((artifact_kind, container_id, topic.strip(), "\x1e".join(sorted(material_ids)),
                            retrieval_mode, str(int(allow_fallback)), str(count), exercise_type or "", source_revision or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generation_public(connection: sqlite3.Connection, operation: sqlite3.Row) -> dict[str, object] | None:
    if operation["status"] != "succeeded" or not operation["output_artifact_id"]:
        return None
    artifact_kind = str(operation["operation_type"]).removeprefix("generate_")
    if artifact_kind == "card":
        rows = connection.execute("SELECT * FROM study_cards WHERE generation_operation_id=? ORDER BY created_at,id", (operation["id"],)).fetchall()
        artifacts = [_card_public(connection, row) for row in rows]
    else:
        rows = connection.execute("SELECT * FROM exercises WHERE generation_operation_id=? ORDER BY created_at,id", (operation["id"],)).fetchall()
        artifacts = [_exercise_public(connection, row) for row in rows]
    if not artifacts:
        return None
    return {"status": "succeeded", "operation_id": operation["id"], "retrieval_run_id": operation["retrieval_run_id"],
            "artifacts": artifacts}


def _card_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    return {**dict(row), "tags": json.loads(row["tags_json"]),
            "citations": list_card_citations(connection, str(row["id"]))}


def create_generation_operation(connection: sqlite3.Connection, *, project_id: str, artifact_kind: str,
                                container_id: str, topic: str, material_ids: list[str], retrieval_mode: str,
                                allow_fallback: bool, count: int, exercise_type: str | None,
                                source_revision: str | None, request_id: str | None,
                                idempotency_key: str | None) -> dict[str, object]:
    if artifact_kind not in {"card", "exercise"} or not isinstance(topic, str) or not topic.strip() or len(topic.strip()) > MAX_GENERATION_TOPIC_LENGTH:
        raise ValueError("generation_invalid_request")
    if (not material_ids or len(material_ids) != len(set(material_ids)) or len(material_ids) > 200 or
            retrieval_mode not in {"lexical", "vector", "hybrid"} or not isinstance(allow_fallback, bool) or
            not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_GENERATION_COUNT):
        raise ValueError("generation_invalid_request")
    if artifact_kind == "card":
        if exercise_type is not None or connection.execute("SELECT 1 FROM study_decks WHERE id=? AND project_id=? AND status='active'", (container_id, project_id)).fetchone() is None:
            raise ValueError("deck_not_found" if exercise_type is None else "generation_invalid_request")
    elif exercise_type not in {"multiple_choice", "true_false", "short_answer"} or connection.execute("SELECT 1 FROM exercise_sets WHERE id=? AND project_id=? AND status='active'", (container_id, project_id)).fetchone() is None:
        raise ValueError("exercise_set_not_found" if exercise_type in {"multiple_choice", "true_false", "short_answer"} else "generation_invalid_request")
    rows = connection.execute(
        "SELECT m.id, r.id AS revision_id FROM materials m LEFT JOIN material_revisions r ON r.material_id=m.id AND r.is_current=1 "
        "WHERE m.project_id=? AND m.id IN ({})".format(",".join("?" for _ in material_ids)),
        [project_id, *material_ids],
    ).fetchall()
    if len(rows) != len(material_ids):
        raise ValueError("material_not_found")
    if len(material_ids) != 1:
        raise ValueError("generation_invalid_request")
    material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_ids[0],)).fetchone()
    if material is None:
        raise ValueError("material_not_found")
    if material["deleted_at"] is not None:
        raise ValueError("source_deleted")
    current_revision = str(rows[0]["revision_id"]) if len(rows) == 1 and rows[0]["revision_id"] is not None else None
    if source_revision is not None and source_revision != current_revision:
        raise ValueError("generation_stale_source")
    if any(row["revision_id"] is None for row in rows) or connection.execute(
            "SELECT COUNT(*) FROM chunks c JOIN material_revisions r ON r.id=c.revision_id JOIN materials m ON m.id=c.material_id "
            "WHERE m.project_id=? AND m.deleted_at IS NULL AND r.is_current=1 AND c.status='ready' "
            "AND c.material_id IN ({})".format(",".join("?" for _ in material_ids)), [project_id, *material_ids]).fetchone()[0] == 0:
        raise ValueError("retrieval_not_ready")
    fingerprint = _generation_fingerprint(artifact_kind=artifact_kind, container_id=container_id, topic=topic,
                                          material_ids=material_ids, retrieval_mode=retrieval_mode,
                                          allow_fallback=allow_fallback, count=count, exercise_type=exercise_type,
                                          source_revision=current_revision)
    with connection:
        if idempotency_key:
            existing = connection.execute("SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, idempotency_key)).fetchone()
            if existing is not None:
                if existing["input_fingerprint"] != fingerprint:
                    raise ValueError("generation_idempotency_key_mismatch")
                if existing["status"] == "running":
                    raise ValueError("generation_in_progress")
                replay = _generation_public(connection, existing)
                if replay is not None:
                    return {**replay, "replay": True}
                connection.execute("UPDATE ai_operations SET idempotency_key=NULL WHERE id=?", (existing["id"],))
        operation_id, now = f"operation_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
            "retrieval_policy_version,prompt_version,request_id,retry_count,created_at,started_at,idempotency_key) "
            "VALUES (?,?,'running',?,?,?, ?,?,?,?,0,?,?,?)",
            (operation_id, f"generate_{artifact_kind}", project_id, material_ids[0] if len(material_ids) == 1 else None,
             fingerprint, current_revision, {"lexical": RETRIEVAL_POLICY_VERSION, "vector": VECTOR_POLICY_VERSION, "hybrid": HYBRID_POLICY_VERSION}[retrieval_mode],
             GENERATION_PROMPT_VERSION, request_id, now, now, idempotency_key),
        )
    return {"operation_id": operation_id, "replay": False, "source_revision": current_revision}


def fail_generation_operation(connection: sqlite3.Connection, operation_id: str, error_code: str) -> None:
    with connection:
        connection.execute("UPDATE ai_operations SET status='failed',error_code=?,finished_at=? WHERE id=? AND status='running'", (error_code, utc_now(), operation_id))


def persist_generated_draft(connection: sqlite3.Connection, *, project_id: str, operation_id: str,
                            artifact_kind: str, container_id: str, source_revision: str,
                            items: list[dict[str, object]], citation_groups: list[list[str]],
                            context_blocks: list[dict[str, object]], provider_id: str, model_id: str,
                            prompt_tokens: int | None, completion_tokens: int | None, latency_ms: int,
                            provider_request_id: str | None, total_tokens: int | None,
                            finish_reason: str | None) -> list[dict[str, object]]:
    if not items or len(items) != len(citation_groups) or any(not isinstance(item, dict) for item in items):
        raise ValueError("generation_schema_invalid")
    with connection:
        operation = connection.execute("SELECT status,source_revision FROM ai_operations WHERE id=? AND project_id=?", (operation_id, project_id)).fetchone()
    if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
        raise ValueError("generation_stale_source")
    allowed = {str(block.get("citation_key")): block for block in context_blocks}
    prepared: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    for item, citation_keys in zip(items, citation_groups):
        if not isinstance(citation_keys, list) or not citation_keys:
            raise ValueError("generation_schema_invalid")
        citations_payload: list[dict[str, object]] = []
        for key in citation_keys:
            block = allowed.get(key)
            source = block.get("source_info") if isinstance(block, dict) else None
            if not isinstance(source, dict) or source.get("revision_id") != source_revision:
                raise ValueError("citation_verification_failed")
            validation = validate_citation_key(connection, key)
            if validation.get("status") != "valid" or validation.get("revision_id") != source_revision:
                raise ValueError("citation_verification_failed")
            citations_payload.append({"citation_key": key, "chunk_id": validation["chunk_id"], "quote": str(block["text"])[:500]})
        if len({entry["citation_key"] for entry in citations_payload}) != len(citations_payload):
            raise ValueError("citation_verification_failed")
        prepared.append((item, citations_payload))
    artifact_ids: list[str] = []
    with connection:
        operation = connection.execute("SELECT status,source_revision FROM ai_operations WHERE id=? AND project_id=?", (operation_id, project_id)).fetchone()
        if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
            raise ValueError("generation_stale_source")
        for item, citations_payload in prepared:
            if artifact_kind == "card":
                front, back, explanation, tags = _validate_card_payload(item)
                artifact_id = f"card_{uuid.uuid4().hex}"
                citation_rows = _citation_rows(connection, citations_payload, code="generation_schema_invalid", artifact_id=artifact_id, table="card")
                connection.execute("INSERT INTO study_cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (artifact_id, container_id, project_id, "ai_generated", "draft", front, back, explanation, json.dumps(tags, ensure_ascii=False), source_revision, 0, operation_id, utc_now(), utc_now(), None, None))
                connection.executemany("INSERT INTO card_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citation_rows)
            else:
                exercise_type = item.get("exercise_type")
                if not isinstance(exercise_type, str):
                    raise ValueError("generation_schema_invalid")
                prompt, options, answer_key, explanation = _exercise_payload(item, exercise_type)
                artifact_id = f"exercise_{uuid.uuid4().hex}"
                citation_rows = _exercise_citations(connection, citations_payload, artifact_id)
                _validate_exercise_source_revision(connection, source_revision, citation_rows, "ai_generated")
                connection.execute(
                    "INSERT INTO exercises (id,set_id,project_id,exercise_type,exercise_kind,status,prompt,options_json,answer_key_json,"
                    "explanation,source_revision,edited_by_user,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
                    "VALUES (?,?,?,?,?,'draft',?,?,?,?,?,0,?,?,?,NULL,NULL)",
                    (artifact_id, container_id, project_id, exercise_type, "ai_generated", prompt, json.dumps(options, ensure_ascii=False),
                     json.dumps(answer_key, ensure_ascii=False), explanation, source_revision, operation_id, utc_now(), utc_now()),
                )
                connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citation_rows)
            artifact_ids.append(artifact_id)
        connection.execute(
            "UPDATE ai_operations SET status='succeeded',output_artifact_id=?,provider_id=?,model_id=?,provider_request_id=?,"
            "prompt_tokens=?,completion_tokens=?,total_tokens=?,latency_ms=?,finish_reason=?,finished_at=? WHERE id=? AND status='running'",
            (artifact_ids[0], provider_id, model_id, provider_request_id, prompt_tokens, completion_tokens, total_tokens,
             latency_ms, finish_reason, utc_now(), operation_id),
        )
    rows = [connection.execute("SELECT * FROM study_cards WHERE id=?" if artifact_kind == "card" else "SELECT * FROM exercises WHERE id=?", (artifact_id,)).fetchone() for artifact_id in artifact_ids]
    return [_card_public(connection, row) if artifact_kind == "card" else _exercise_public(connection, row) for row in rows]


def list_exercises(connection: sqlite3.Connection, *, project_id: str, set_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    where = "project_id=?"
    if set_id is not None:
        where += " AND set_id=?"
        params.append(set_id)
    with connection:
        rows = connection.execute("SELECT * FROM exercises WHERE " + where + " ORDER BY updated_at DESC,id DESC", params).fetchall()
        for row in rows:
            _refresh_exercise_citations(connection, str(row["id"]))
    return [_exercise_public(connection, row) for row in rows]


def create_exercise(connection: sqlite3.Connection, *, project_id: str, set_id: str, exercise_type: str,
                    payload: dict[str, object], source_revision: str | None = None,
                    exercise_kind: str = "user_created") -> dict[str, object]:
    if exercise_kind not in {"user_created", "ai_generated"}:
        raise ValueError("invalid_exercise_schema")
    if connection.execute("SELECT 1 FROM exercise_sets WHERE id=? AND project_id=? AND status='active'", (set_id, project_id)).fetchone() is None:
        raise ValueError("exercise_set_not_found")
    prompt, options, answer_key, explanation = _exercise_payload(payload, exercise_type)
    exercise_id, now = f"exercise_{uuid.uuid4().hex}", utc_now()
    citations = _exercise_citations(connection, payload.get("citations", []), exercise_id)
    _validate_exercise_source_revision(connection, source_revision, citations, exercise_kind)
    with connection:
        connection.execute(
            "INSERT INTO exercises (id,set_id,project_id,exercise_type,exercise_kind,status,prompt,options_json,answer_key_json,"
            "explanation,source_revision,edited_by_user,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
            "VALUES (?,?,?,?,?,'draft',?,?,?,?,?,0,NULL,?,?,NULL,NULL)",
            (exercise_id, set_id, project_id, exercise_type, exercise_kind, prompt, json.dumps(options, ensure_ascii=False),
             json.dumps(answer_key, ensure_ascii=False), explanation, source_revision, now, now),
        )
        connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=set_id) if item["id"] == exercise_id)


def update_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                    payload: dict[str, object]) -> dict[str, object]:
    row = connection.execute("SELECT * FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    if row["status"] != "draft":
        raise ValueError("exercise_edit_not_allowed")
    if payload.get("answer_key") is None:
        payload = {**payload, "answer_key": json.loads(row["answer_key_json"])}
    prompt, options, answer_key, explanation = _exercise_payload(payload, str(row["exercise_type"]))
    citation_input = payload.get("citations", [])
    if not citation_input and row["exercise_kind"] == "ai_generated":
        citation_input = [dict(item) for item in connection.execute(
            "SELECT citation_key,chunk_id,quote FROM exercise_citations WHERE exercise_id=? ORDER BY position,id", (exercise_id,)
        ).fetchall()]
    citations = _exercise_citations(connection, citation_input, exercise_id)
    _validate_exercise_source_revision(connection, row["source_revision"], citations, str(row["exercise_kind"]))
    with connection:
        connection.execute("DELETE FROM exercise_citations WHERE exercise_id=?", (exercise_id,))
        connection.execute("UPDATE exercises SET prompt=?,options_json=?,answer_key_json=?,explanation=?,edited_by_user=1,updated_at=? WHERE id=?", (prompt, json.dumps(options, ensure_ascii=False), json.dumps(answer_key, ensure_ascii=False), explanation, utc_now(), exercise_id))
        connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)


def confirm_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str) -> dict[str, object]:
    row = connection.execute("SELECT set_id,status,exercise_kind,source_revision FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    if row["status"] != "draft":
        raise ValueError("exercise_invalid_state")
    with connection:
        statuses = _refresh_exercise_citations(connection, exercise_id)
        if any(status != "valid" for status in statuses):
            raise ValueError("citation_invalid")
        if row["exercise_kind"] == "ai_generated" and (not statuses or row["source_revision"] is None):
            raise ValueError("citation_invalid")
        now = utc_now()
        connection.execute("UPDATE exercises SET status='ready',confirmed_at=?,updated_at=? WHERE id=?", (now, now, exercise_id))
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)


def transition_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                        target: str) -> dict[str, object]:
    row = connection.execute("SELECT set_id,status FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    allowed = {"rejected": {"draft"}, "archived": {"draft", "ready", "rejected", "stale"}}
    if target not in allowed or row["status"] not in allowed[target]:
        raise ValueError("exercise_invalid_state")
    now = utc_now()
    with connection:
        connection.execute("UPDATE exercises SET status=?,updated_at=?,archived_at=? WHERE id=?", (target, now, now if target == "archived" else None, exercise_id))
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)


def list_exercise_attempts(connection: sqlite3.Connection, *, project_id: str, exercise_id: str) -> list[dict[str, object]]:
    if connection.execute("SELECT 1 FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone() is None:
        raise ValueError("exercise_not_found")
    rows = connection.execute(
        "SELECT id,exercise_id,score,is_correct,grading_status,submitted_at,reviewed_at,feedback "
        "FROM exercise_attempts WHERE exercise_id=? ORDER BY rowid", (exercise_id,)
    ).fetchall()
    return [{**dict(row), "is_correct": (None if row["is_correct"] is None else bool(row["is_correct"]))}
            for row in rows]


def submit_exercise_attempt(connection: sqlite3.Connection, *, project_id: str, exercise_id: str, answer: object) -> dict[str, object]:
    row = connection.execute("SELECT * FROM exercises WHERE id=? AND project_id=? AND status='ready'", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_ready")
    if isinstance(answer, str) and len(answer) > MAX_EXERCISE_ANSWER_LENGTH:
        raise ValueError("invalid_exercise_answer")
    expected, correct, score, grading = json.loads(row["answer_key_json"]), None, None, "deterministic"
    if row["exercise_type"] == "multiple_choice":
        if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(json.loads(row["options_json"])):
            raise ValueError("invalid_exercise_answer")
        correct, score = answer == expected, 1.0 if answer == expected else 0.0
    elif row["exercise_type"] == "true_false":
        if not isinstance(answer, bool):
            raise ValueError("invalid_exercise_answer")
        correct, score = answer == expected, 1.0 if answer == expected else 0.0
    else:
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("invalid_exercise_answer")
        grading = "pending_review"
    attempt_id = f"attempt_{uuid.uuid4().hex}"
    with connection:
        connection.execute("INSERT INTO exercise_attempts VALUES (?,?,?,?,?,?,?,?,?)", (attempt_id, exercise_id, json.dumps(answer, ensure_ascii=False), score, int(correct) if correct is not None else None, grading, utc_now(), None, ""))
    return {"id": attempt_id, "exercise_id": exercise_id, "score": score, "is_correct": correct, "grading_status": grading}


# Phase 9A domain repository. These functions own SQLite transactions and
# leave HTTP serialization to the later API task.
STUDY_TEXT_MAX = 4000
STUDY_DESCRIPTION_MAX = 10000
STUDY_METADATA_MAX = 10000
STUDY_GOAL_PREFIX = "goal_"
STUDY_MODULE_PREFIX = "module_"
STUDY_PLAN_PREFIX = "plan_"
STUDY_ITEM_PREFIX = "plan_item_"
STUDY_DEPENDENCY_PREFIX = "plan_dependency_"
STUDY_PROGRESS_PREFIX = "progress_"
STUDY_SOURCE_PREFIX = "study_source_"
STUDY_PLAN_STATUSES = {"draft", "confirmed", "active", "paused", "completed", "archived"}
STUDY_ITEM_STATUSES = {"pending", "in_progress", "completed", "skipped", "archived"}
STUDY_PROGRESS_EVENTS = {"started", "completed", "skipped", "reopened"}
STUDY_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}


def _study_text(value: object, *, code: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(code)
    result = value.strip()
    if not allow_empty and not result:
        raise ValueError(code)
    return result


def _study_description(value: object, *, code: str = "study_plan_invalid_payload") -> str:
    return _study_text(value, code=code, maximum=STUDY_DESCRIPTION_MAX, allow_empty=True)


def _study_project_exists(connection: sqlite3.Connection, project_id: str) -> bool:
    return connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is not None


def _study_goal_row(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM learning_goals WHERE id = ? AND project_id = ?", (goal_id, project_id)
    ).fetchone()


def _study_module_row(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM knowledge_modules WHERE id = ? AND project_id = ?", (module_id, project_id)
    ).fetchone()


def create_learning_goal(connection: sqlite3.Connection, *, project_id: str, title: object,
                         description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_goal_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description, code="study_goal_invalid_payload")
    if not _study_project_exists(connection, project_id):
        raise ValueError("project_not_found")
    goal_id = f"{STUDY_GOAL_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO learning_goals (id,project_id,title,description,status,created_at,updated_at,archived_at) "
            "VALUES (?,?,?,?,?,?,?,NULL)",
            (goal_id, project_id, title_value, description_value, "active", now, now),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))


def list_learning_goals(connection: sqlite3.Connection, *, project_id: str,
                        include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id = ?" if include_archived else "project_id = ? AND status = 'active'"
    return [dict(row) for row in connection.execute(
        "SELECT * FROM learning_goals WHERE " + where + " ORDER BY updated_at DESC, id DESC", (project_id,)
    ).fetchall()]


def get_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object] | None:
    row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
    return dict(row) if row is not None else None


def archive_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
        if row is None:
            raise ValueError("learning_goal_not_found")
        if row["status"] == "archived":
            return dict(row)
        connection.execute(
            "UPDATE learning_goals SET status='archived', archived_at=?, updated_at=? WHERE id=? AND project_id=?",
            (now, now, goal_id, project_id),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))


def update_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                         title: object | None = None, description: object | None = None) -> dict[str, object]:
    with connection:
        row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
        if row is None:
            raise ValueError("learning_goal_not_found")
        if row["status"] == "archived":
            raise ValueError("learning_goal_archived")
        next_title = str(row["title"]) if title is None else _study_text(title, code="study_goal_invalid_payload", maximum=STUDY_TEXT_MAX)
        next_description = str(row["description"]) if description is None else _study_description(description, code="study_goal_invalid_payload")
        connection.execute(
            "UPDATE learning_goals SET title=?,description=?,updated_at=? WHERE id=? AND project_id=?",
            (next_title, next_description, utc_now(), goal_id, project_id),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))


def create_knowledge_module(connection: sqlite3.Connection, *, project_id: str, title: object,
                            description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_module_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description, code="study_module_invalid_payload")
    if not _study_project_exists(connection, project_id):
        raise ValueError("project_not_found")
    module_id = f"{STUDY_MODULE_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO knowledge_modules (id,project_id,title,description,status,created_at,updated_at,archived_at) "
            "VALUES (?,?,?,?,?,?,?,NULL)",
            (module_id, project_id, title_value, description_value, "active", now, now),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))


def list_knowledge_modules(connection: sqlite3.Connection, *, project_id: str,
                           include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id = ?" if include_archived else "project_id = ? AND status = 'active'"
    return [dict(row) for row in connection.execute(
        "SELECT * FROM knowledge_modules WHERE " + where + " ORDER BY updated_at DESC, id DESC", (project_id,)
    ).fetchall()]


def get_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> dict[str, object] | None:
    row = _study_module_row(connection, project_id=project_id, module_id=module_id)
    return dict(row) if row is not None else None


def update_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str,
                            title: object | None = None, description: object | None = None) -> dict[str, object]:
    with connection:
        row = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if row is None:
            raise ValueError("knowledge_module_not_found")
        if row["status"] == "archived":
            raise ValueError("knowledge_module_archived")
        next_title = str(row["title"]) if title is None else _study_text(title, code="study_module_invalid_payload", maximum=STUDY_TEXT_MAX)
        next_description = str(row["description"]) if description is None else _study_description(description, code="study_module_invalid_payload")
        connection.execute(
            "UPDATE knowledge_modules SET title=?,description=?,updated_at=? WHERE id=? AND project_id=?",
            (next_title, next_description, utc_now(), module_id, project_id),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))


def archive_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if row is None:
            raise ValueError("knowledge_module_not_found")
        if row["status"] == "archived":
            return dict(row)
        connection.execute(
            "UPDATE knowledge_modules SET status='archived', archived_at=?, updated_at=? WHERE id=? AND project_id=?",
            (now, now, module_id, project_id),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))


def _study_plan_row(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM study_plans WHERE id = ? AND project_id = ?", (plan_id, project_id)
    ).fetchone()


def _study_plan_items(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM study_plan_items WHERE plan_id=? AND project_id=? ORDER BY position,id",
        (plan_id, project_id),
    ).fetchall()]


def _study_dependencies(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM study_plan_dependencies WHERE plan_id=? AND project_id=? ORDER BY created_at,id",
        (plan_id, project_id),
    ).fetchall()]


def _study_source_links(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT l.* FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
        "WHERE i.plan_id=? AND l.project_id=? ORDER BY l.created_at,l.id", (plan_id, project_id)
    ).fetchall()]


def study_progress_summary(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> dict[str, object]:
    rows = connection.execute(
        "SELECT status, COUNT(*) AS count FROM study_plan_items WHERE plan_id=? AND project_id=? "
        "GROUP BY status", (plan_id, project_id)
    ).fetchall()
    counts = {status: int(row["count"]) for status, row in ((str(row["status"]), row) for row in rows)}
    item_count = sum(count for status, count in counts.items() if status != "archived")
    completed = counts.get("completed", 0)
    last_event = connection.execute(
        "SELECT created_at FROM study_progress_events WHERE plan_id=? AND project_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        (plan_id, project_id),
    ).fetchone()
    warnings = connection.execute(
        "SELECT COUNT(*) FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
        "WHERE i.plan_id=? AND l.project_id=? AND l.status != 'valid'", (plan_id, project_id)
    ).fetchone()[0]
    return {
        "item_count": item_count,
        "completed_count": completed,
        "skipped_count": counts.get("skipped", 0),
        "in_progress_count": counts.get("in_progress", 0),
        "pending_count": counts.get("pending", 0),
        "archived_count": counts.get("archived", 0),
        "completion_ratio": (completed / item_count) if item_count else 0.0,
        "last_event_at": last_event[0] if last_event else None,
        "source_warning_count": int(warnings),
    }


def _study_plan_public(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object]:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_plan_not_found")
    return {
        **dict(row),
        "items": _study_plan_items(connection, plan_id=plan_id, project_id=project_id),
        "dependencies": _study_dependencies(connection, plan_id=plan_id, project_id=project_id),
        "source_links": _study_source_links(connection, plan_id=plan_id, project_id=project_id),
        "progress": study_progress_summary(connection, plan_id=plan_id, project_id=project_id),
    }


def create_study_plan(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                      title: object, description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_plan_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description)
    goal = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
    if goal is None:
        raise ValueError("study_plan_goal_invalid")
    if goal["status"] != "active":
        raise ValueError("learning_goal_archived")
    plan_id = f"{STUDY_PLAN_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO study_plans (id,project_id,goal_id,title,description,status,user_edited,created_at,updated_at,"
            "confirmed_at,activated_at,completed_at,archived_at) VALUES (?,?,?,?,?,'draft',0,?,?,NULL,NULL,NULL,NULL)",
            (plan_id, project_id, goal_id, title_value, description_value, now, now),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)


def list_study_plans(connection: sqlite3.Connection, *, project_id: str,
                      include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id=?" if include_archived else "project_id=? AND status!='archived'"
    rows = connection.execute("SELECT id FROM study_plans WHERE " + where + " ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [_study_plan_public(connection, project_id=project_id, plan_id=str(row[0])) for row in rows]


def get_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object] | None:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id) if row is not None else None


def _study_plan_for_edit(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_plan_not_found")
    if row["status"] not in {"draft", "confirmed"}:
        raise ValueError("study_plan_edit_not_allowed")
    return row


def update_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                      title: object | None = None, description: object | None = None) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_plan_for_edit(connection, project_id=project_id, plan_id=plan_id)
        title_value = str(row["title"]) if title is None else _study_text(title, code="study_plan_invalid_payload", maximum=STUDY_TEXT_MAX)
        description_value = str(row["description"]) if description is None else _study_description(description)
        next_status = "draft" if row["status"] == "confirmed" else row["status"]
        connection.execute(
            "UPDATE study_plans SET title=?,description=?,status=?,user_edited=1,updated_at=?,confirmed_at=? WHERE id=? AND project_id=?",
            (title_value, description_value, next_status, now, None if next_status == "draft" else row["confirmed_at"], plan_id, project_id),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)


def transition_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                          target: str) -> dict[str, object]:
    allowed = {
        "draft": {"confirmed", "archived"}, "confirmed": {"draft", "active", "archived"},
        "active": {"paused", "completed", "archived"}, "paused": {"active", "completed", "archived"},
        "completed": {"archived"}, "archived": set(),
    }
    now = utc_now()
    with connection:
        row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
        if row is None:
            raise ValueError("study_plan_not_found")
        if target not in allowed.get(str(row["status"]), set()):
            raise ValueError("study_plan_invalid_state")
        if target == "active" and row["status"] != "confirmed":
            raise ValueError("study_plan_confirm_required")
        confirmed_at = now if target == "confirmed" else row["confirmed_at"]
        activated_at = now if target == "active" else row["activated_at"]
        completed_at = now if target == "completed" else row["completed_at"]
        archived_at = now if target == "archived" else row["archived_at"]
        connection.execute(
            "UPDATE study_plans SET status=?,confirmed_at=?,activated_at=?,completed_at=?,archived_at=?,updated_at=? WHERE id=? AND project_id=?",
            (target, confirmed_at, activated_at, completed_at, archived_at, now, plan_id, project_id),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)


def _study_item_row(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM study_plan_items WHERE id=? AND project_id=? AND plan_id=?", (item_id, project_id, plan_id)
    ).fetchone()


def _study_item_edit_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row:
    row = _study_plan_for_edit(connection, project_id=project_id, plan_id=plan_id)
    if row["status"] == "confirmed":
        now = utc_now()
        connection.execute("UPDATE study_plans SET status='draft',confirmed_at=NULL,updated_at=? WHERE id=?", (now, plan_id))
        row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    return row


def _study_optional_reference(connection: sqlite3.Connection, *, table: str, value: str | None,
                              project_id: str, archived_allowed: bool = False) -> None:
    if value is None:
        return
    row = connection.execute(f"SELECT project_id,status FROM {table} WHERE id=?", (value,)).fetchone()
    if row is None or row["project_id"] != project_id or (not archived_allowed and row["status"] != "active"):
        raise ValueError("study_plan_item_invalid_payload")


def create_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                           title: object, description: object = "", position: int | None = None,
                           module_id: str | None = None, deck_id: str | None = None,
                           exercise_set_id: str | None = None) -> dict[str, object]:
    title_value = _study_text(title, code="study_plan_item_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description)
    with connection:
        plan = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        _study_optional_reference(connection, table="knowledge_modules", value=module_id, project_id=project_id)
        _study_optional_reference(connection, table="study_decks", value=deck_id, project_id=project_id)
        _study_optional_reference(connection, table="exercise_sets", value=exercise_set_id, project_id=project_id)
        max_position = connection.execute("SELECT COALESCE(MAX(position), -1) FROM study_plan_items WHERE plan_id=?", (plan_id,)).fetchone()[0]
        item_position = max_position + 1 if position is None else position
        if not isinstance(item_position, int) or item_position < 0:
            raise ValueError("study_plan_item_invalid_payload")
        item_id = f"{STUDY_ITEM_PREFIX}{uuid.uuid4().hex}"
        now = utc_now()
        try:
            connection.execute(
                "INSERT INTO study_plan_items (id,plan_id,project_id,module_id,deck_id,exercise_set_id,title,description,position,status,user_edited,created_at,updated_at,completed_at,archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,'pending',1,?,?,NULL,NULL)",
                (item_id, plan_id, project_id, module_id, deck_id, exercise_set_id, title_value, description_value, item_position, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_plan_item_invalid_payload") from exc
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))


def update_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str,
                           title: object | None = None, description: object | None = None,
                           position: int | None = None, module_id: str | None = None,
                           deck_id: str | None = None, exercise_set_id: str | None = None) -> dict[str, object]:
    with connection:
        row = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if row is None:
            raise ValueError("study_plan_item_not_found")
        self_status = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        if row["status"] in {"completed", "skipped", "archived"}:
            raise ValueError("study_plan_item_edit_not_allowed")
        _study_optional_reference(connection, table="knowledge_modules", value=module_id, project_id=project_id)
        _study_optional_reference(connection, table="study_decks", value=deck_id, project_id=project_id)
        _study_optional_reference(connection, table="exercise_sets", value=exercise_set_id, project_id=project_id)
        next_position = row["position"] if position is None else position
        if not isinstance(next_position, int) or next_position < 0:
            raise ValueError("study_plan_item_invalid_payload")
        connection.execute(
            "UPDATE study_plan_items SET title=?,description=?,position=?,module_id=?,deck_id=?,exercise_set_id=?,user_edited=1,updated_at=? WHERE id=? AND plan_id=? AND project_id=?",
            (str(row["title"]) if title is None else _study_text(title, code="study_plan_item_invalid_payload", maximum=STUDY_TEXT_MAX),
             str(row["description"]) if description is None else _study_description(description), next_position,
             row["module_id"] if module_id is None else module_id, row["deck_id"] if deck_id is None else deck_id,
             row["exercise_set_id"] if exercise_set_id is None else exercise_set_id, utc_now(), item_id, plan_id, project_id),
        )
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))


def archive_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str) -> dict[str, object]:
    with connection:
        row = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if row is None:
            raise ValueError("study_plan_item_not_found")
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        if row["status"] == "archived":
            return dict(row)
        if connection.execute("SELECT 1 FROM study_progress_events WHERE item_id=?", (item_id,)).fetchone() is not None:
            raise ValueError("study_plan_item_edit_not_allowed")
        now = utc_now()
        connection.execute("UPDATE study_plan_items SET status='archived',archived_at=?,updated_at=? WHERE id=?", (now, now, item_id))
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))


def _study_dependency_cycle(connection: sqlite3.Connection, *, plan_id: str, predecessor: str, successor: str) -> bool:
    graph: dict[str, list[str]] = {}
    for row in connection.execute("SELECT predecessor_item_id,successor_item_id FROM study_plan_dependencies WHERE plan_id=?", (plan_id,)).fetchall():
        graph.setdefault(str(row[0]), []).append(str(row[1]))
    graph.setdefault(predecessor, []).append(successor)
    stack = [successor]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == predecessor:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, []))
    return False


def add_study_plan_dependency(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                              predecessor_item_id: str, successor_item_id: str) -> dict[str, object]:
    with connection:
        plan = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        left = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=predecessor_item_id)
        right = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=successor_item_id)
        if left is None or right is None or left["status"] == "archived" or right["status"] == "archived":
            raise ValueError("study_plan_dependency_invalid")
        if _study_dependency_cycle(connection, plan_id=plan_id, predecessor=predecessor_item_id, successor=successor_item_id):
            raise ValueError("study_plan_dependency_cycle")
        dependency_id = f"{STUDY_DEPENDENCY_PREFIX}{uuid.uuid4().hex}"
        try:
            connection.execute(
                "INSERT INTO study_plan_dependencies (id,plan_id,project_id,predecessor_item_id,successor_item_id,created_at) VALUES (?,?,?,?,?,?)",
                (dependency_id, plan_id, project_id, predecessor_item_id, successor_item_id, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_plan_dependency_invalid") from exc
    return dict(connection.execute("SELECT * FROM study_plan_dependencies WHERE id=?", (dependency_id,)).fetchone())


def remove_study_plan_dependency(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                                 dependency_id: str) -> bool:
    with connection:
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        cursor = connection.execute("DELETE FROM study_plan_dependencies WHERE id=? AND plan_id=? AND project_id=?", (dependency_id, plan_id, project_id))
    if cursor.rowcount == 0:
        raise ValueError("study_plan_dependency_invalid")
    return True


def append_study_progress_event(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                                item_id: str, event_type: str, metadata: object | None = None,
                                event_id: str | None = None) -> dict[str, object]:
    if event_type not in STUDY_PROGRESS_EVENTS:
        raise ValueError("study_progress_invalid_event")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict) or len(json.dumps(metadata, ensure_ascii=False)) > STUDY_METADATA_MAX:
        raise ValueError("study_progress_invalid_event")
    with connection:
        plan = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if plan is None or item is None:
            raise ValueError("study_plan_item_not_found")
        if plan["status"] != "active" or item["status"] == "archived":
            raise ValueError("study_progress_invalid_event")
        if event_id is not None:
            existing = connection.execute("SELECT * FROM study_progress_events WHERE id=?", (event_id,)).fetchone()
            if existing is not None:
                if existing["plan_id"] == plan_id and existing["item_id"] == item_id and existing["event_type"] == event_type:
                    return dict(existing)
                raise ValueError("study_progress_event_duplicate")
        progress_id = event_id or f"{STUDY_PROGRESS_PREFIX}{uuid.uuid4().hex}"
        next_status = {"started": "in_progress", "completed": "completed", "skipped": "skipped", "reopened": "in_progress"}[event_type]
        completed_at = utc_now() if event_type == "completed" else None
        now = utc_now()
        connection.execute(
            "INSERT INTO study_progress_events (id,plan_id,item_id,project_id,event_type,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (progress_id, plan_id, item_id, project_id, event_type, json.dumps(metadata, ensure_ascii=False, separators=(",", ":")), now),
        )
        connection.execute("UPDATE study_plan_items SET status=?,completed_at=?,updated_at=? WHERE id=? AND plan_id=?", (next_status, completed_at, now, item_id, plan_id))
    return dict(connection.execute("SELECT * FROM study_progress_events WHERE id=?", (progress_id,)).fetchone())


def list_study_progress_events(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                               item_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id, plan_id]
    where = "project_id=? AND plan_id=?"
    if item_id is not None:
        where += " AND item_id=?"
        params.append(item_id)
    rows = connection.execute("SELECT * FROM study_progress_events WHERE " + where + " ORDER BY created_at,id", params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(str(item.pop("metadata_json")))
        result.append(item)
    return result


def _study_source_status(connection: sqlite3.Connection, *, material_id: str | None, revision_id: str | None,
                         extraction_id: str | None, chunk_id: str | None, span_id: str | None,
                         citation_key: str | None) -> str:
    if not material_id or not revision_id or not chunk_id:
        raise ValueError("study_source_invalid")
    material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None:
        return "source_unavailable"
    if material["deleted_at"] is not None:
        return "source_deleted"
    chunk = connection.execute(
        "SELECT c.revision_id,c.extraction_id,c.status,r.is_current FROM chunks c JOIN material_revisions r ON r.id=c.revision_id "
        "WHERE c.id=? AND c.material_id=?", (chunk_id, material_id)
    ).fetchone()
    if chunk is None or chunk["revision_id"] != revision_id or (extraction_id is not None and chunk["extraction_id"] != extraction_id):
        return "stale"
    if chunk["status"] != "ready" or not chunk["is_current"]:
        return "stale"
    if span_id is not None and connection.execute("SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id, span_id)).fetchone() is None:
        raise ValueError("study_source_invalid")
    if citation_key is not None:
        validation = validate_citation_key(connection, citation_key)
        if validation is None or validation.get("chunk_id") != chunk_id:
            raise ValueError("study_source_invalid")
    return "valid"


def _study_source_payload(connection: sqlite3.Connection, *, project_id: str, payload: dict[str, object],
                          owner_type: str) -> tuple[object, ...]:
    required = ("material_id", "revision_id", "chunk_id")
    if any(not isinstance(payload.get(key), str) or not str(payload[key]) for key in required):
        raise ValueError("study_source_invalid")
    material_id = str(payload["material_id"]); revision_id = str(payload["revision_id"]); chunk_id = str(payload["chunk_id"])
    extraction_id = payload.get("extraction_id"); span_id = payload.get("span_id"); citation_key = payload.get("citation_key")
    for value in (extraction_id, span_id, citation_key):
        if value is not None and (not isinstance(value, str) or len(value) > 200):
            raise ValueError("study_source_invalid")
    status = _study_source_status(connection, material_id=material_id, revision_id=revision_id,
                                  extraction_id=extraction_id, chunk_id=chunk_id, span_id=span_id,
                                  citation_key=citation_key)
    if status != "valid":
        raise ValueError("study_source_invalid")
    prefix = "module_source" if owner_type == "module" else "plan_item_source"
    return (f"{prefix}_{uuid.uuid4().hex}", project_id, material_id, revision_id, extraction_id, chunk_id,
            span_id, citation_key, status, utc_now(), utc_now())


def create_module_source_link(connection: sqlite3.Connection, *, project_id: str, module_id: str,
                              payload: dict[str, object]) -> dict[str, object]:
    with connection:
        module = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if module is None:
            raise ValueError("knowledge_module_not_found")
        if module["status"] != "active":
            raise ValueError("knowledge_module_archived")
        row = _study_source_payload(connection, project_id=project_id, payload=payload, owner_type="module")
        link_id = row[0]
        try:
            connection.execute("INSERT INTO module_source_links (id,project_id,module_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (link_id, project_id, module_id, *row[2:]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_source_invalid") from exc
    return dict(connection.execute("SELECT * FROM module_source_links WHERE id=?", (link_id,)).fetchone())


def create_plan_item_source_link(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str,
                                 payload: dict[str, object]) -> dict[str, object]:
    with connection:
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if item is None:
            raise ValueError("study_plan_item_not_found")
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        row = _study_source_payload(connection, project_id=project_id, payload=payload, owner_type="item")
        link_id = row[0]
        try:
            connection.execute("INSERT INTO plan_item_source_links (id,project_id,plan_item_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (link_id, project_id, item_id, *row[2:]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_source_invalid") from exc
    return dict(connection.execute("SELECT * FROM plan_item_source_links WHERE id=?", (link_id,)).fetchone())


def _refresh_study_source_links_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    for table, owner in (("module_source_links", "module_id"), ("plan_item_source_links", "plan_item_id")):
        rows = connection.execute(
            f"SELECT id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key FROM {table} WHERE material_id=?", (material_id,)
        ).fetchall()
        for row in rows:
            status = "source_deleted" if connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()["deleted_at"] is not None else _study_source_status(connection, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"])
            connection.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE id=?", (status, utc_now(), row["id"]))


def refresh_study_source_links(connection: sqlite3.Connection, *, project_id: str, plan_id: str | None = None) -> int:
    with connection:
        changed = 0
        for table in ("module_source_links", "plan_item_source_links"):
            if table == "plan_item_source_links" and plan_id is not None:
                rows = connection.execute(
                    "SELECT l.id,l.material_id,l.revision_id,l.extraction_id,l.chunk_id,l.span_id,l.citation_key "
                    "FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
                    "WHERE l.project_id=? AND i.plan_id=?", (project_id, plan_id)
                ).fetchall()
            elif table == "module_source_links" and plan_id is not None:
                rows = connection.execute(
                    "SELECT l.id,l.material_id,l.revision_id,l.extraction_id,l.chunk_id,l.span_id,l.citation_key "
                    "FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
                    "WHERE l.project_id=? AND i.plan_id=?", (project_id, plan_id)
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key FROM {table} WHERE project_id=?",
                    (project_id,),
                ).fetchall()
            for row in rows:
                material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (row["material_id"],)).fetchone()
                status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(connection, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"])
                changed += connection.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE id=? AND status!=?", (status, utc_now(), row["id"], status)).rowcount
    return changed


def get_study_source_links(connection: sqlite3.Connection, *, project_id: str, plan_id: str | None = None,
                           module_id: str | None = None, item_id: str | None = None) -> list[dict[str, object]]:
    if module_id is not None:
        return [dict(row) for row in connection.execute("SELECT * FROM module_source_links WHERE project_id=? AND module_id=? ORDER BY created_at,id", (project_id, module_id)).fetchall()]
    query = "SELECT l.* FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id WHERE l.project_id=?"
    params: list[object] = [project_id]
    if plan_id is not None:
        query += " AND i.plan_id=?"; params.append(plan_id)
    if item_id is not None:
        query += " AND l.plan_item_id=?"; params.append(item_id)
    return [dict(row) for row in connection.execute(query + " ORDER BY l.created_at,l.id", params).fetchall()]


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
        connection.execute(
            "UPDATE exercise_citations SET status = 'source_unavailable' WHERE material_id = ?",
            (material_id,),
        )
        connection.execute(
            "UPDATE card_citations SET status = 'source_unavailable' WHERE material_id = ?",
            (material_id,),
        )
        _refresh_study_source_links_for_material(connection, material_id)
        connection.execute(
            "UPDATE module_source_links SET status = 'source_unavailable', updated_at = ? WHERE material_id = ?",
            (utc_now(), material_id),
        )
        connection.execute(
            "UPDATE plan_item_source_links SET status = 'source_unavailable', updated_at = ? WHERE material_id = ?",
            (utc_now(), material_id),
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
        if cursor.rowcount == 1:
            _refresh_exercise_citations_for_material(connection, material_id)
            _refresh_card_citations_for_material(connection, material_id)
            _refresh_study_source_links_for_material(connection, material_id)
    return cursor.rowcount == 1


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_payload(connection: sqlite3.Connection, material_id: str, extraction_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT m.id AS material_id, m.project_id, m.source_sha256, e.id AS extraction_id, e.parser_id, "
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
        _refresh_exercise_citations_for_material(connection, material_id)
        _refresh_card_citations_for_material(connection, material_id)
        existing = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE revision_id = ? AND status = 'ready'", (revision["id"],)
        ).fetchone()[0]
        if existing:
            _sync_chunk_search_for_revision(connection, str(revision["id"]))
            _refresh_study_source_links_for_material(connection, material_id)
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
        _refresh_study_source_links_for_material(connection, material_id)
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
