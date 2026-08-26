from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .adapters.file_parsers.models import ParseResult
from .chunking import CHUNKING_STRATEGY, CHUNKING_VERSION, SourceSpan, chunk_text
from .embedding import (EMBEDDING_ENCODING, MAX_EMBEDDING_PAYLOAD_BYTES, EmbeddingError,
                         EmbeddingIdentity, EmbeddingProvider, cosine_similarity, decode_vector,
                         embedding_content_hash, embedding_staleness, encode_vector)
from .import_locks import acquire_hash_lock, release_hash_lock
from .migrations.runner import MigrationError, assert_schema_version, migrate
from .providers import (CaptureProviderError, CaptureTranscriptionProvider,
                        CaptureTranscriptionRequest, LLMProvider, ProviderError,
                        ProviderRequest)
from .storage import sha256_file, store_original

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
        "SELECT m.id, m.original_name, e.text FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))"
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
        "SELECT m.id, m.original_name, e.text FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.id = ? AND e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))",
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


TASK_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "stale"}
TASK_ACTIVE_STATUSES = {"running", "cancel_requested"}
TASK_STAGE_CODES = {
    "queued", "reading_source", "indexing", "provider_call", "persisting",
    "finalizing", "recovery_required",
}


def _task_row(connection: sqlite3.Connection, task_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM operation_tasks WHERE id=?", (task_id,)
    ).fetchone()


def create_operation_task(connection: sqlite3.Connection, *, task_id: str, project_id: str,
                           operation_id: str, task_kind: str, input_fingerprint: str,
                           idempotency_key_fingerprint: str | None = None,
                           max_retries: int = 0, parent_task_id: str | None = None) -> dict[str, object]:
    if not task_id or not project_id or not operation_id or not task_kind or not input_fingerprint:
        raise ValueError("task_invalid_request")
    if max_retries < 0:
        raise ValueError("task_invalid_request")
    existing = connection.execute(
        "SELECT * FROM operation_tasks WHERE operation_id=?", (operation_id,)
    ).fetchone()
    if existing is not None:
        if str(existing["project_id"]) != project_id:
            raise ValueError("task_project_scope_violation")
        if str(existing["input_fingerprint"]) != input_fingerprint or (
            existing["idempotency_key_fingerprint"] != idempotency_key_fingerprint
        ):
            raise ValueError("task_idempotency_key_mismatch")
        return dict(existing) | {"replay": True}
    now = utc_now()
    try:
        connection.execute(
            "INSERT INTO operation_tasks "
            "(id,project_id,operation_id,parent_task_id,task_kind,status,input_fingerprint,"
            "idempotency_key_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) "
            "VALUES (?,?,?,?,?,'queued',?,?,0,'queued',0,?,?,?)",
            (task_id, project_id, operation_id, parent_task_id, task_kind, input_fingerprint,
             idempotency_key_fingerprint, max_retries, now, now),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("task_create_conflict") from exc
    return dict(_task_row(connection, task_id)) | {"replay": False}


def get_operation_task(connection: sqlite3.Connection, *, task_id: str,
                       project_id: str | None = None) -> dict[str, object]:
    row = _task_row(connection, task_id)
    if row is None:
        raise ValueError("task_not_found")
    if project_id is not None and str(row["project_id"]) != project_id:
        raise ValueError("task_project_scope_violation")
    return dict(row)


def claim_operation_task(connection: sqlite3.Connection, *, task_id: str,
                         lease_seconds: int, attempt_id: str) -> dict[str, object]:
    if lease_seconds < 1 or not attempt_id:
        raise ValueError("task_invalid_request")
    row = _task_row(connection, task_id)
    if row is None:
        raise ValueError("task_not_found")
    if row["status"] != "queued":
        raise ValueError("task_already_running" if row["status"] in TASK_ACTIVE_STATUSES else "task_invalid_state_transition")
    now = utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
    connection.execute("BEGIN IMMEDIATE")
    try:
        current = _task_row(connection, task_id)
        if current is None:
            raise ValueError("task_not_found")
        if current["status"] != "queued":
            raise ValueError("task_already_running" if current["status"] in TASK_ACTIVE_STATUSES else "task_invalid_state_transition")
        connection.execute(
            "UPDATE operation_tasks SET status='running',started_at=COALESCE(started_at,?),updated_at=?,stage_code='reading_source' "
            "WHERE id=? AND status='queued'",
            (now, now, task_id),
        )
        connection.execute(
            "UPDATE ai_operations SET status='running',started_at=COALESCE(started_at,?),finished_at=NULL,error_code=NULL "
            "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='queued'",
            (now, task_id),
        )
        connection.execute(
            "INSERT INTO operation_task_attempts "
            "(id,task_id,project_id,attempt_number,status,progress_percent,stage_code,lease_started_at,lease_expires_at,heartbeat_at,created_at,started_at) "
            "SELECT ?,id,project_id,retry_count+1,'running',progress_percent,'reading_source',?,?,?,?,? FROM operation_tasks WHERE id=?",
            (attempt_id, now, expires, now, now, now, task_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"task_id": task_id, "attempt_id": attempt_id, "lease_expires_at": expires}


def update_operation_task_progress(connection: sqlite3.Connection, *, task_id: str,
                                   attempt_id: str, progress_percent: int | None,
                                   stage_code: str) -> bool:
    if progress_percent is not None and not 0 <= progress_percent <= 100:
        raise ValueError("task_invalid_progress")
    if stage_code not in TASK_STAGE_CODES:
        raise ValueError("task_invalid_stage")
    now = utc_now()
    cursor = connection.execute(
        "UPDATE operation_task_attempts SET progress_percent=COALESCE(?,progress_percent),stage_code=?,heartbeat_at=? "
        "WHERE id=? AND task_id=? AND status='running' AND "
        "(progress_percent IS NULL OR ? IS NULL OR progress_percent <= ?)",
        (progress_percent, stage_code, now, attempt_id, task_id, progress_percent, progress_percent),
    )
    if cursor.rowcount != 1:
        return False
    connection.execute(
        "UPDATE operation_tasks SET progress_percent=COALESCE(?,progress_percent),stage_code=?,updated_at=? "
        "WHERE id=? AND status IN ('running','cancel_requested')",
        (progress_percent, stage_code, now, task_id),
    )
    connection.commit()
    return True


def heartbeat_operation_task(connection: sqlite3.Connection, *, task_id: str,
                              attempt_id: str, lease_seconds: int) -> bool:
    now = utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
    cursor = connection.execute(
        "UPDATE operation_task_attempts SET lease_expires_at=?,heartbeat_at=? "
        "WHERE id=? AND task_id=? AND status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at > ?",
        (expires, now, attempt_id, task_id, now),
    )
    if cursor.rowcount:
        connection.commit()
        return True
    connection.rollback()
    return False


def request_operation_task_cancel(connection: sqlite3.Connection, *, task_id: str) -> str:
    row = _task_row(connection, task_id)
    if row is None:
        raise ValueError("task_not_found")
    now = utc_now()
    if row["status"] == "queued":
        connection.execute("UPDATE operation_tasks SET status='cancelled',finished_at=?,updated_at=? WHERE id=? AND status='queued'", (now, now, task_id))
        connection.execute(
            "UPDATE ai_operations SET status='cancelled',finished_at=?,error_code=NULL "
            "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='queued'",
            (now, task_id),
        )
        connection.commit()
        return "cancelled"
    if row["status"] == "running":
        connection.execute("UPDATE operation_tasks SET status='cancel_requested',cancel_requested_at=?,updated_at=? WHERE id=? AND status='running'", (now, now, task_id))
        connection.commit()
        return "cancel_requested"
    if row["status"] == "cancel_requested":
        return "cancel_requested"
    raise ValueError("task_cancel_not_allowed")


def retry_operation_task(connection: sqlite3.Connection, *, task_id: str,
                         retryable_error_codes: set[str]) -> dict[str, object]:
    row = _task_row(connection, task_id)
    if row is None:
        raise ValueError("task_not_found")
    if row["status"] not in {"failed", "stale"} or str(row["error_code"] or "") not in retryable_error_codes:
        raise ValueError("task_retry_not_allowed")
    if int(row["retry_count"]) >= int(row["max_retries"]):
        raise ValueError("task_retry_limit_reached")
    now = utc_now()
    connection.execute(
        "UPDATE operation_tasks SET status='queued',retry_count=retry_count+1,error_code=NULL,progress_percent=0,stage_code='queued',"
        "finished_at=NULL,cancel_requested_at=NULL,updated_at=? WHERE id=? AND status IN ('failed','stale')",
        (now, task_id),
    )
    connection.execute(
        "UPDATE ai_operations SET status='queued',finished_at=NULL,error_code=NULL "
        "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status IN ('failed','stale')",
        (task_id,),
    )
    connection.commit()
    return get_operation_task(connection, task_id=task_id)


def finish_operation_task(connection: sqlite3.Connection, *, task_id: str, attempt_id: str,
                          status: str, error_code: str | None = None) -> bool:
    if status not in {"succeeded", "failed", "cancelled", "stale"}:
        raise ValueError("task_invalid_state_transition")
    row = _task_row(connection, task_id)
    if row is None:
        raise ValueError("task_not_found")
    now = utc_now()
    task_status = "succeeded" if status == "succeeded" else status
    if row["status"] == "cancel_requested" and status == "succeeded":
        task_status = "succeeded"
    cursor = connection.execute(
        "UPDATE operation_task_attempts SET status=?,error_code=?,finished_at=? "
        "WHERE id=? AND task_id=? AND status='running' AND "
        "(?='stale' OR lease_expires_at IS NULL OR lease_expires_at > ?)",
        (status, error_code, now, attempt_id, task_id, status, now),
    )
    if cursor.rowcount != 1:
        connection.rollback()
        return False
    connection.execute(
        "UPDATE operation_tasks SET status=?,error_code=?,progress_percent=CASE WHEN ?='succeeded' THEN 100 ELSE progress_percent END,"
        "stage_code=CASE WHEN ?='succeeded' THEN 'finalizing' ELSE stage_code END,finished_at=?,updated_at=? "
        "WHERE id=? AND status IN ('running','cancel_requested')",
        (task_status, error_code, task_status, task_status, now, now, task_id),
    )
    connection.execute(
        "UPDATE ai_operations SET status=?,error_code=?,finished_at=? "
        "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='running'",
        (task_status, error_code, now, task_id),
    )
    connection.commit()
    return True


def recover_active_operation_tasks(connection: sqlite3.Connection) -> int:
    """On process startup, retain incomplete work as stale; never queue or execute it."""
    now = utc_now()
    rows = connection.execute(
        "SELECT id,task_id FROM operation_task_attempts WHERE status='running'"
    ).fetchall()
    for row in rows:
        connection.execute(
            "UPDATE operation_task_attempts SET status='stale',error_code='task_recovery_required',finished_at=? "
            "WHERE id=? AND status='running'",
            (now, row["id"]),
        )
    task_rows = connection.execute(
        "SELECT id FROM operation_tasks WHERE status IN ('running','cancel_requested')"
    ).fetchall()
    for row in task_rows:
        connection.execute(
            "UPDATE operation_tasks SET status='stale',error_code='task_recovery_required',finished_at=?,updated_at=? "
            "WHERE id=? AND status IN ('running','cancel_requested')",
            (now, now, row["id"]),
        )
        connection.execute(
            "UPDATE ai_operations SET status='stale',error_code='task_recovery_required',finished_at=? "
            "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='running'",
            (now, row["id"]),
        )
    if rows or task_rows:
        connection.commit()
    return len(task_rows)


def reclaim_stale_operation_tasks(connection: sqlite3.Connection) -> int:
    now = utc_now()
    rows = connection.execute(
        "SELECT id,task_id FROM operation_task_attempts WHERE status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?",
        (now,),
    ).fetchall()
    for row in rows:
        connection.execute("UPDATE operation_task_attempts SET status='stale',error_code='task_lease_expired',finished_at=? WHERE id=? AND status='running'", (now, row["id"]))
        connection.execute("UPDATE operation_tasks SET status='stale',error_code='task_lease_expired',finished_at=?,updated_at=? WHERE id=? AND status IN ('running','cancel_requested')", (now, now, row["task_id"]))
        connection.execute("UPDATE ai_operations SET status='stale',error_code='task_lease_expired',finished_at=? WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='running'", (now, row["task_id"]))
    if rows:
        connection.commit()
    return len(rows)


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
        "WHERE m.deleted_at IS NULL AND e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))"
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
        "WHERE m.deleted_at IS NULL AND e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))"
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
        # Restore does not promote retained 9C snapshot source status; only an
        # explicit re-index/refresh path may revalidate it.
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


def _refresh_phase9c_session_sources_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    rows = connection.execute(
        "SELECT id,source_revision,source_extraction_id,source_chunk_id FROM practice_session_items "
        "WHERE source_material_id=?", (material_id,)
    ).fetchall()
    for row in rows:
        status = "source_unavailable"
        material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
        if material is not None and material["deleted_at"] is not None:
            status = "source_deleted"
        elif material is not None and row["source_chunk_id"] is not None:
            chunk = connection.execute(
                "SELECT c.status,c.revision_id,c.extraction_id,r.is_current FROM chunks c "
                "JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                (row["source_chunk_id"], material_id),
            ).fetchone()
            if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                status = "valid" if (chunk["revision_id"] == row["source_revision"] and
                                      chunk["extraction_id"] == row["source_extraction_id"]) else "stale"
            elif chunk is not None:
                status = "stale"
        connection.execute("UPDATE practice_session_items SET citation_status=?,updated_at=? WHERE id=?",
                           (status, utc_now(), row["id"]))
        if row["source_revision"] is not None:
            connection.execute("UPDATE mistake_occurrences SET source_status=? WHERE source_revision=?",
                               (status, row["source_revision"]))


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
        connection.execute(
            "INSERT INTO exercise_attempts "
            "(id, exercise_id, answer_json, score, is_correct, grading_status, submitted_at, reviewed_at, feedback) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (attempt_id, exercise_id, json.dumps(answer, ensure_ascii=False), score,
             int(correct) if correct is not None else None, grading, utc_now(), None, ""),
        )
    return {"id": attempt_id, "exercise_id": exercise_id, "score": score, "is_correct": correct, "grading_status": grading}


# Phase 9C shared exercise-feedback domain repository. These functions own
# SQLite transactions and leave HTTP serialization to the later API task.
PHASE9C_SESSION_TITLE_MAX = 200
PHASE9C_SESSION_MAX_ITEMS = 50
PHASE9C_MIN_DURATION_SECONDS = 60
PHASE9C_MAX_DURATION_SECONDS = 7200
PHASE9C_FEEDBACK_MAX = 4000
PHASE9C_CORRECTION_MAX = 12000
PHASE9C_SESSION_STATUSES = {"draft", "active", "finished", "expired", "archived"}
PHASE9C_MISTAKE_STATUSES = {"open", "in_review", "fixed", "reopened", "archived"}
PHASE9C_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}


def _phase9c_text(value: object, *, code: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(code)
    value = value.strip()
    if not value and not allow_empty:
        raise ValueError(code)
    return value


def _phase9c_timezone(value: object, *, code: str) -> str:
    value = _phase9c_text(value, code=code, maximum=100)
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError(code) from None
    return value


def _phase9c_local_date(value: object, *, code: str) -> str:
    value = _phase9c_text(value, code=code, maximum=10)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(code) from None


def _phase9c_iso_now() -> tuple[str, datetime]:
    value = utc_now()
    return value, datetime.fromisoformat(value).astimezone(timezone.utc)


def _phase9c_parse_now(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _phase9c_source_snapshot(connection: sqlite3.Connection, exercise_id: str) -> dict[str, object]:
    citations = connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1", (exercise_id,)
    ).fetchone()
    if citations is None:
        return {"source_material_id": None, "source_revision": None, "source_extraction_id": None,
                "source_chunk_id": None, "source_span_id": None, "citation_key": None,
                "citation_status": "valid"}
    _refresh_exercise_citations(connection, exercise_id)
    citations = connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1", (exercise_id,)
    ).fetchone()
    status = citations["status"] if citations["status"] in PHASE9C_SOURCE_STATUSES else "source_unavailable"
    if status != "valid":
        raise ValueError("citation_invalid")
    return {"source_material_id": citations["material_id"], "source_revision": citations["revision_id"],
            "source_extraction_id": citations["extraction_id"], "source_chunk_id": citations["chunk_id"],
            "source_span_id": citations["span_id"], "citation_key": citations["citation_key"],
            "citation_status": status}


def _phase9c_project_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                              ready: bool = True) -> sqlite3.Row:
    sql = "SELECT * FROM exercises WHERE id=? AND project_id=?"
    params: tuple[object, ...] = (exercise_id, project_id)
    if ready:
        sql += " AND status='ready'"
    row = connection.execute(sql, params).fetchone()
    if row is None:
        raise ValueError("exercise_not_ready" if ready else "exercise_not_found")
    return row


def _phase9c_session_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    items = connection.execute(
        "SELECT id,session_id,exercise_id,position,exercise_type,prompt,options_json,explanation_snapshot,"
        "exercise_kind,source_material_id,source_revision,source_extraction_id,source_chunk_id,source_span_id,"
        "citation_key,citation_status,created_at,updated_at FROM practice_session_items "
        "WHERE session_id=? ORDER BY position,id", (row["id"],)
    ).fetchall()
    attempts = connection.execute(
        "SELECT session_item_id,score,is_correct,grading_status,submitted_at,reviewed_at FROM exercise_attempts "
        "WHERE session_id=? ORDER BY submitted_at,id", (row["id"],)
    ).fetchall()
    safe_items = []
    for item in items:
        payload = dict(item)
        payload["options"] = json.loads(payload.pop("options_json"))
        safe_items.append(payload)
    deterministic = [item for item in attempts if item["grading_status"] == "deterministic"]
    return {"id": row["id"], "project_id": row["project_id"], "session_kind": row["session_kind"],
            "cram_goal_id": row["cram_goal_id"], "status": row["status"], "title": row["title"],
            "duration_seconds": row["duration_seconds"], "timezone": row["timezone"],
            "local_date": row["local_date"], "started_at": row["started_at"],
            "deadline_at": row["deadline_at"], "finished_at": row["finished_at"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "items": safe_items,
            "summary": {"total_item_count": len(items), "submitted_count": len(attempts),
                        "unanswered_count": len(items) - len(attempts),
                        "correct_count": sum(item["is_correct"] == 1 for item in deterministic),
                        "incorrect_count": sum(item["is_correct"] == 0 for item in deterministic),
                        "pending_review_count": sum(item["grading_status"] == "pending_review" for item in attempts),
                        "scored_count": len(deterministic),
                        "score_total": sum(float(item["score"] or 0) for item in deterministic),
                        "source_warning_count": sum(item["citation_status"] != "valid" for item in items),
                        "last_attempt_at": attempts[-1]["submitted_at"] if attempts else None}}


def _phase9c_expire_if_needed(connection: sqlite3.Connection, row: sqlite3.Row, now: datetime, now_text: str) -> sqlite3.Row:
    if row["status"] == "active" and row["deadline_at"] is not None and now >= _phase9c_parse_now(str(row["deadline_at"])):
        connection.execute("UPDATE practice_sessions SET status='expired',finished_at=?,updated_at=? WHERE id=? AND status='active'",
                           (now_text, now_text, row["id"]))
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=?", (row["id"],)).fetchone()
    return row


def create_cram_goal(connection: sqlite3.Connection, *, project_id: str, title: object, target_date: object,
                     timezone_name: object = "UTC", target_exercise_count: object = 1,
                     plan_id: str | None = None, plan_item_id: str | None = None) -> dict[str, object]:
    title = _phase9c_text(title, code="cram_invalid_payload", maximum=200)
    target_date = _phase9c_local_date(target_date, code="cram_invalid_payload")
    timezone_name = _phase9c_timezone(timezone_name, code="cram_invalid_payload")
    if not isinstance(target_exercise_count, int) or isinstance(target_exercise_count, bool) or not 1 <= target_exercise_count <= 200:
        raise ValueError("cram_invalid_payload")
    goal_id, now = f"cram_goal_{uuid.uuid4().hex}", utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("project_not_found")
        if plan_id is not None:
            plan = connection.execute("SELECT project_id FROM study_plans WHERE id=?", (plan_id,)).fetchone()
            if plan is None or plan["project_id"] != project_id:
                raise ValueError("cram_scope_conflict")
        if plan_item_id is not None:
            item = connection.execute("SELECT project_id,plan_id FROM study_plan_items WHERE id=?", (plan_item_id,)).fetchone()
            if item is None or item["project_id"] != project_id or (plan_id is not None and item["plan_id"] != plan_id):
                raise ValueError("cram_scope_conflict")
        connection.execute("INSERT INTO cram_goals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (goal_id, project_id, title, target_date, timezone_name, target_exercise_count, "draft",
                            plan_id, plan_item_id, now, now, None, None))
    return get_cram_goal(connection, project_id=project_id, goal_id=goal_id) or {}


def get_cram_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)).fetchone()
    return dict(row) if row is not None else None


def list_cram_goals(connection: sqlite3.Connection, *, project_id: str,
                    include_archived: bool = False) -> list[dict[str, object]]:
    query = "SELECT * FROM cram_goals WHERE project_id=?"
    params: list[object] = [project_id]
    if not include_archived:
        query += " AND status!='archived'"
    rows = connection.execute(query + " ORDER BY updated_at DESC,id DESC", params).fetchall()
    return [dict(row) for row in rows]


def transition_cram_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str, target: str) -> dict[str, object]:
    allowed = {"active": {"draft"}, "completed": {"active"}, "archived": {"draft", "active", "completed"}}
    with connection:
        row = connection.execute("SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)).fetchone()
        if row is None:
            raise ValueError("cram_goal_not_found")
        if target not in allowed or row["status"] not in allowed[target]:
            raise ValueError("cram_goal_invalid_state")
        if target == "completed" and connection.execute("SELECT 1 FROM practice_sessions WHERE cram_goal_id=? AND status IN ('finished','expired')", (goal_id,)).fetchone() is None:
            raise ValueError("cram_goal_not_ready")
        now = utc_now()
        connection.execute("UPDATE cram_goals SET status=?,updated_at=?,completed_at=?,archived_at=? WHERE id=?",
                           (target, now, now if target == "completed" else row["completed_at"],
                            now if target == "archived" else row["archived_at"], goal_id))
    return get_cram_goal(connection, project_id=project_id, goal_id=goal_id) or {}


def create_cram_session(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                        title: object, exercise_ids: list[str], duration_seconds: object = 600,
                        timezone_name: object = "UTC", local_date: object = "1970-01-01") -> dict[str, object]:
    """Create an explicit S5 session while reusing the S3 facts and grading."""
    goal = connection.execute(
        "SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)
    ).fetchone()
    if goal is None:
        raise ValueError("cram_goal_not_found")
    if goal["status"] != "active":
        raise ValueError("cram_goal_invalid_state")
    if not isinstance(exercise_ids, list) or not exercise_ids or len(exercise_ids) > PHASE9C_SESSION_MAX_ITEMS:
        raise ValueError("cram_selection_invalid")
    if len(exercise_ids) > int(goal["target_exercise_count"]):
        raise ValueError("cram_selection_invalid")
    return create_practice_session(
        connection, project_id=project_id, title=title, exercise_ids=exercise_ids,
        duration_seconds=duration_seconds, timezone_name=timezone_name,
        local_date=local_date, session_kind="cram", cram_goal_id=goal_id,
    )


def get_cram_result(connection: sqlite3.Connection, *, project_id: str,
                    goal_id: str, session_id: str) -> dict[str, object] | None:
    goal = get_cram_goal(connection, project_id=project_id, goal_id=goal_id)
    if goal is None:
        return None
    session = get_practice_session(connection, project_id=project_id, session_id=session_id)
    if session is None or session["session_kind"] != "cram" or session["cram_goal_id"] != goal_id:
        raise ValueError("cram_session_scope_conflict")
    result = get_practice_result(connection, project_id=project_id, session_id=session_id)
    item_ids = [str(item["id"]) for item in session["items"]]
    if item_ids:
        marks = connection.execute(
            "SELECT COUNT(*) FROM mistake_occurrences o JOIN exercise_attempts a ON a.id=o.attempt_id "
            "WHERE a.session_item_id IN ({})".format(",".join("?" for _ in item_ids)), item_ids
        ).fetchone()[0]
    else:
        marks = 0
    exercise_ids = {str(item["exercise_id"]) for item in session["items"]}
    weak_points = [point for point in list_weak_points(connection, project_id=project_id)
                   if str(point["exercise_id"]) in exercise_ids]
    return {"goal": {key: goal[key] for key in (
        "id", "project_id", "title", "target_date", "timezone", "target_exercise_count", "status",
    )}, "session": result["session"], "summary": {
        **result["summary"], "mistake_count": int(marks), "weak_points": weak_points,
    }}


def create_practice_session(connection: sqlite3.Connection, *, project_id: str, title: object,
                            exercise_ids: list[str], duration_seconds: object = 600,
                            timezone_name: object = "UTC", local_date: object = "1970-01-01",
                            session_kind: str = "practice", cram_goal_id: str | None = None) -> dict[str, object]:
    title = _phase9c_text(title, code="practice_invalid_payload", maximum=PHASE9C_SESSION_TITLE_MAX)
    timezone_name = _phase9c_timezone(timezone_name, code="practice_invalid_payload")
    local_date = _phase9c_local_date(local_date, code="practice_invalid_payload")
    if session_kind not in {"practice", "cram"} or not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool) or not PHASE9C_MIN_DURATION_SECONDS <= duration_seconds <= PHASE9C_MAX_DURATION_SECONDS:
        raise ValueError("practice_invalid_payload")
    if not isinstance(exercise_ids, list) or not 1 <= len(exercise_ids) <= PHASE9C_SESSION_MAX_ITEMS or len(set(exercise_ids)) != len(exercise_ids):
        raise ValueError("practice_invalid_selection")
    session_id, now = f"practice_session_{uuid.uuid4().hex}", utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("project_not_found")
        if session_kind == "practice" and cram_goal_id is not None:
            raise ValueError("practice_scope_conflict")
        if session_kind == "cram":
            goal = connection.execute("SELECT project_id,status FROM cram_goals WHERE id=?", (cram_goal_id,)).fetchone()
            if goal is None or goal["project_id"] != project_id or goal["status"] != "active":
                raise ValueError("cram_scope_conflict")
        connection.execute("INSERT INTO practice_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (session_id, project_id, session_kind, cram_goal_id, "draft", title, duration_seconds,
                            timezone_name, local_date, None, None, None, now, now))
        for position, exercise_id in enumerate(exercise_ids):
            exercise = _phase9c_project_exercise(connection, project_id=project_id, exercise_id=exercise_id)
            source = _phase9c_source_snapshot(connection, exercise_id)
            connection.execute(
                "INSERT INTO practice_session_items (id,session_id,project_id,exercise_id,position,exercise_type,prompt,options_json,"
                "explanation_snapshot,exercise_kind,source_material_id,source_revision,source_extraction_id,source_chunk_id,source_span_id,"
                "citation_key,citation_status,answer_key_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"practice_item_{uuid.uuid4().hex}", session_id, project_id, exercise_id, position, exercise["exercise_type"],
                 exercise["prompt"], exercise["options_json"], exercise["explanation"], exercise["exercise_kind"],
                 source["source_material_id"], source["source_revision"], source["source_extraction_id"], source["source_chunk_id"],
                 source["source_span_id"], source["citation_key"], source["citation_status"], exercise["answer_key_json"], now, now),
            )
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone()
        return _phase9c_session_public(connection, row)


def get_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object] | None:
    with connection:
        now_text, now = _phase9c_iso_now()
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            return None
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        return _phase9c_session_public(connection, row)


def list_practice_sessions(connection: sqlite3.Connection, *, project_id: str,
                           status: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    query = "SELECT * FROM practice_sessions WHERE project_id=?"
    if status is not None:
        if status not in PHASE9C_SESSION_STATUSES:
            raise ValueError("practice_invalid_payload")
        query += " AND status=?"
        params.append(status)
    rows = connection.execute(query + " ORDER BY created_at DESC,id DESC", params).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        if row["status"] == "active":
            with connection:
                now_text, now = _phase9c_iso_now()
                row = _phase9c_expire_if_needed(connection, row, now, now_text)
        result.append(_phase9c_session_public(connection, row))
    return result


def get_practice_result(connection: sqlite3.Connection, *, project_id: str,
                        session_id: str) -> dict[str, object] | None:
    session = get_practice_session(connection, project_id=project_id, session_id=session_id)
    if session is None:
        return None
    summary = dict(session["summary"])
    scored_count = int(summary["scored_count"])
    summary["score_ratio"] = (float(summary["score_total"]) / scored_count) if scored_count else None
    return {"session": {key: session[key] for key in (
        "id", "project_id", "session_kind", "status", "title", "duration_seconds",
        "timezone", "local_date", "started_at", "deadline_at", "finished_at",
    )}, "summary": summary}


def start_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        if row["status"] != "draft":
            raise ValueError("practice_session_invalid_state")
        for item in connection.execute("SELECT exercise_id FROM practice_session_items WHERE session_id=? ORDER BY position", (session_id,)).fetchall():
            _phase9c_project_exercise(connection, project_id=project_id, exercise_id=item["exercise_id"])
        now_text, now = _phase9c_iso_now()
        deadline = (now + timedelta(seconds=int(row["duration_seconds"]))).isoformat()
        connection.execute("UPDATE practice_sessions SET status='active',started_at=?,deadline_at=?,updated_at=? WHERE id=?",
                           (now_text, deadline, now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())


def archive_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        now_text, now = _phase9c_iso_now()
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        if row["status"] not in {"draft", "finished", "expired"}:
            raise ValueError("practice_session_invalid_state")
        connection.execute("UPDATE practice_sessions SET status='archived',updated_at=? WHERE id=?", (now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())


def _phase9c_session_item(connection: sqlite3.Connection, *, project_id: str, session_id: str, item_id: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    session = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
    if session is None:
        raise ValueError("practice_session_not_found")
    item = connection.execute("SELECT * FROM practice_session_items WHERE id=? AND session_id=? AND project_id=?", (item_id, session_id, project_id)).fetchone()
    if item is None:
        raise ValueError("practice_session_item_not_found")
    return session, item


def submit_practice_session_item(connection: sqlite3.Connection, *, project_id: str, session_id: str,
                                 item_id: str, answer: object, submission_key: str | None = None) -> dict[str, object]:
    with connection:
        session, item = _phase9c_session_item(connection, project_id=project_id, session_id=session_id, item_id=item_id)
        now_text, now = _phase9c_iso_now()
        session = _phase9c_expire_if_needed(connection, session, now, now_text)
        if session["status"] != "active":
            # Expiry is a persisted server-time state transition, not a failed
            # submission write. Commit it before returning the stable conflict.
            if session["status"] == "expired":
                connection.commit()
                raise ValueError("practice_session_expired")
            raise ValueError("practice_session_invalid_state")
        if submission_key is not None:
            submission_key = _phase9c_text(submission_key, code="practice_invalid_submission", maximum=200)
            duplicate = connection.execute("SELECT * FROM exercise_attempts WHERE session_id=? AND submission_key=?", (session_id, submission_key)).fetchone()
            if duplicate is not None:
                if duplicate["answer_json"] != json.dumps(answer, ensure_ascii=False):
                    raise ValueError("practice_submission_idempotency_mismatch")
                return {"id": duplicate["id"], "exercise_id": duplicate["exercise_id"], "session_id": session_id,
                        "session_item_id": duplicate["session_item_id"], "score": duplicate["score"],
                        "is_correct": None if duplicate["is_correct"] is None else bool(duplicate["is_correct"]),
                        "grading_status": duplicate["grading_status"], "submitted_at": duplicate["submitted_at"], "replay": True}
        existing = connection.execute("SELECT * FROM exercise_attempts WHERE session_item_id=?", (item_id,)).fetchone()
        if existing is not None:
            return {"id": existing["id"], "exercise_id": existing["exercise_id"], "session_id": session_id,
                    "session_item_id": item_id, "score": existing["score"], "is_correct": None if existing["is_correct"] is None else bool(existing["is_correct"]),
                    "grading_status": existing["grading_status"], "submitted_at": existing["submitted_at"], "replay": True}
        expected = json.loads(item["answer_key_json"])
        correct = score = None
        grading = "pending_review"
        if item["exercise_type"] == "multiple_choice":
            options = json.loads(item["options_json"])
            if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
                raise ValueError("invalid_exercise_answer")
            correct, score, grading = answer == expected, 1.0 if answer == expected else 0.0, "deterministic"
        elif item["exercise_type"] == "true_false":
            if not isinstance(answer, bool):
                raise ValueError("invalid_exercise_answer")
            correct, score, grading = answer == expected, 1.0 if answer == expected else 0.0, "deterministic"
        elif not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_EXERCISE_ANSWER_LENGTH:
            raise ValueError("invalid_exercise_answer")
        attempt_id = f"attempt_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO exercise_attempts (id,exercise_id,answer_json,score,is_correct,grading_status,submitted_at,reviewed_at,feedback,session_id,session_item_id,submission_key,submission_sequence) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, item["exercise_id"], json.dumps(answer, ensure_ascii=False), score, None if correct is None else int(correct),
             grading, now_text, None, "", session_id, item_id, submission_key, 0),
        )
        if correct is False:
            _phase9c_materialize_mistake(connection, project_id=project_id, attempt_id=attempt_id,
                                          exercise_id=str(item["exercise_id"]), reason_code="deterministic_incorrect", origin="deterministic",
                                          source_revision=item["source_revision"], source_status=item["citation_status"])
        return {"id": attempt_id, "exercise_id": item["exercise_id"], "session_id": session_id, "session_item_id": item_id,
                "score": score, "is_correct": correct, "grading_status": grading, "submitted_at": now_text, "replay": False}


def finish_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        now_text, now = _phase9c_iso_now()
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        if row["status"] == "expired":
            return _phase9c_session_public(connection, row)
        if row["status"] != "active":
            raise ValueError("practice_session_invalid_state")
        connection.execute("UPDATE practice_sessions SET status='finished',finished_at=?,updated_at=? WHERE id=?", (now_text, now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())


def _phase9c_mistake_case(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                           origin: str, revision_fingerprint: str) -> str:
    row = connection.execute("SELECT id,status FROM mistake_cases WHERE project_id=? AND exercise_id=? AND exercise_revision_fingerprint=?",
                             (project_id, exercise_id, revision_fingerprint)).fetchone()
    if row is not None:
        if row["status"] == "archived":
            raise ValueError("mistake_archived")
        if row["status"] == "fixed":
            connection.execute("UPDATE mistake_cases SET status='reopened',updated_at=?,fixed_at=NULL WHERE id=?", (utc_now(), row["id"]))
        return str(row["id"])
    case_id = f"mistake_{uuid.uuid4().hex}"
    now = utc_now()
    connection.execute("INSERT INTO mistake_cases VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (case_id, project_id, exercise_id, revision_fingerprint, "open", origin, now, now, None, None))
    return case_id


def _phase9c_materialize_mistake(connection: sqlite3.Connection, *, project_id: str, attempt_id: str, exercise_id: str,
                                  reason_code: str, origin: str, source_revision: str | None, source_status: str) -> str:
    fingerprint = hashlib.sha256(f"{exercise_id}\x1f{source_revision or ''}".encode()).hexdigest()
    case_id = _phase9c_mistake_case(connection, project_id=project_id, exercise_id=exercise_id, origin=origin, revision_fingerprint=fingerprint)
    existing = connection.execute("SELECT id FROM mistake_occurrences WHERE attempt_id=? AND reason_code=?", (attempt_id, reason_code)).fetchone()
    if existing is not None:
        return str(existing["id"])
    occurrence_id = f"mistake_occurrence_{uuid.uuid4().hex}"
    connection.execute("INSERT INTO mistake_occurrences VALUES (?,?,?,?,?,?,?,?,?)",
                       (occurrence_id, project_id, case_id, attempt_id, origin, reason_code, source_revision,
                        source_status if source_status in PHASE9C_SOURCE_STATUSES else "source_unavailable", utc_now()))
    return occurrence_id


def _phase9c_attempt_source(connection: sqlite3.Connection, attempt: sqlite3.Row) -> tuple[str | None, str]:
    if attempt["session_item_id"] is not None:
        item = connection.execute(
            "SELECT source_revision,citation_status FROM practice_session_items WHERE id=?",
            (attempt["session_item_id"],),
        ).fetchone()
        if item is not None:
            return item["source_revision"], item["citation_status"]
    citation = connection.execute(
        "SELECT revision_id,status FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1",
        (attempt["exercise_id"],),
    ).fetchone()
    if citation is None:
        return None, "valid"
    return citation["revision_id"], citation["status"] if citation["status"] in PHASE9C_SOURCE_STATUSES else "source_unavailable"


def mark_mistake_from_attempt(connection: sqlite3.Connection, *, project_id: str, attempt_id: str,
                              feedback: object = "") -> dict[str, object]:
    """Explicit user marking; it is never inferred from an uncertain answer."""
    feedback = _phase9c_text(feedback, code="mistake_feedback_invalid", maximum=PHASE9C_CORRECTION_MAX, allow_empty=True)
    with connection:
        attempt = connection.execute(
            "SELECT a.* FROM exercise_attempts a JOIN exercises e ON e.id=a.exercise_id "
            "WHERE a.id=? AND e.project_id=?", (attempt_id, project_id)
        ).fetchone()
        if attempt is None:
            raise ValueError("attempt_not_found")
        source_revision, source_status = _phase9c_attempt_source(connection, attempt)
        _phase9c_materialize_mistake(
            connection, project_id=project_id, attempt_id=attempt_id, exercise_id=attempt["exercise_id"],
            reason_code="user_marked", origin="user_reported", source_revision=source_revision,
            source_status=source_status,
        )
        case = connection.execute(
            "SELECT id FROM mistake_cases WHERE project_id=? AND exercise_id=? "
            "ORDER BY updated_at DESC,id DESC LIMIT 1", (project_id, attempt["exercise_id"])
        ).fetchone()
        if feedback:
            add_mistake_feedback(connection, project_id=project_id, mistake_case_id=str(case["id"]),
                                 event_kind="user_note", content=feedback)
        return get_mistake_case(connection, project_id=project_id, mistake_case_id=str(case["id"])) or {}


def review_exercise_attempt(connection: sqlite3.Connection, *, project_id: str, attempt_id: str,
                            decision: str, feedback: object = "") -> dict[str, object]:
    feedback = _phase9c_text(feedback, code="review_invalid_payload", maximum=PHASE9C_FEEDBACK_MAX, allow_empty=True)
    if decision not in {"correct", "incorrect", "uncertain"}:
        raise ValueError("review_invalid_decision")
    with connection:
        attempt = connection.execute(
            "SELECT a.* FROM exercise_attempts a JOIN exercises e ON e.id=a.exercise_id "
            "WHERE a.id=? AND e.project_id=?", (attempt_id, project_id)
        ).fetchone()
        if attempt is None:
            raise ValueError("attempt_not_found")
        if attempt["grading_status"] != "pending_review":
            raise ValueError("review_not_allowed")
        if connection.execute("SELECT 1 FROM exercise_attempt_reviews WHERE attempt_id=?", (attempt_id,)).fetchone() is not None:
            raise ValueError("review_duplicate")
        now = utc_now()
        review_id = f"review_{uuid.uuid4().hex}"
        connection.execute("INSERT INTO exercise_attempt_reviews VALUES (?,?,?,?,?,?,?,?,?)",
                           (review_id, project_id, attempt_id, attempt["exercise_id"], decision, feedback, "local_user", now, now))
        if decision == "incorrect":
            source_revision, source_status = _phase9c_attempt_source(connection, attempt)
            _phase9c_materialize_mistake(connection, project_id=project_id, attempt_id=attempt_id, exercise_id=attempt["exercise_id"],
                                          reason_code="review_incorrect", origin="human_review", source_revision=source_revision, source_status=source_status)
        return {"id": review_id, "attempt_id": attempt_id, "decision": decision, "feedback": feedback, "reviewer_kind": "local_user", "reviewed_at": now}


def add_mistake_feedback(connection: sqlite3.Connection, *, project_id: str, mistake_case_id: str,
                         event_kind: str, content: object) -> dict[str, object]:
    content = _phase9c_text(content, code="mistake_feedback_invalid", maximum=PHASE9C_CORRECTION_MAX,
                             allow_empty=event_kind != "user_correction")
    if event_kind not in {"user_correction", "user_note", "status_transition"}:
        raise ValueError("mistake_feedback_invalid")
    with connection:
        case = connection.execute("SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)).fetchone()
        if case is None:
            raise ValueError("mistake_not_found")
        if case["status"] == "archived":
            raise ValueError("mistake_invalid_state")
        now, event_id = utc_now(), f"feedback_{uuid.uuid4().hex}"
        connection.execute("INSERT INTO mistake_feedback_events VALUES (?,?,?,?,?,?,?)",
                           (event_id, project_id, mistake_case_id, event_kind, content, "user_created", now))
        if event_kind == "user_correction":
            connection.execute("UPDATE mistake_cases SET status='fixed',fixed_at=?,updated_at=? WHERE id=?", (now, now, mistake_case_id))
        elif event_kind == "status_transition":
            connection.execute("UPDATE mistake_cases SET status='in_review',updated_at=? WHERE id=? AND status='open'", (now, mistake_case_id))
        return {"id": event_id, "mistake_case_id": mistake_case_id, "event_kind": event_kind, "content": content, "provenance": "user_created", "created_at": now}


def archive_mistake_case(connection: sqlite3.Connection, *, project_id: str, mistake_case_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)).fetchone()
        if row is None:
            raise ValueError("mistake_not_found")
        if row["status"] == "archived":
            raise ValueError("mistake_invalid_state")
        now = utc_now()
        connection.execute("UPDATE mistake_cases SET status='archived',archived_at=?,updated_at=? WHERE id=?",
                           (now, now, mistake_case_id))
        result = connection.execute("SELECT * FROM mistake_cases WHERE id=?", (mistake_case_id,)).fetchone()
        return dict(result)


def get_mistake_case(connection: sqlite3.Connection, *, project_id: str,
                     mistake_case_id: str) -> dict[str, object] | None:
    case = connection.execute(
        "SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)
    ).fetchone()
    if case is None:
        return None
    occurrences = [dict(row) for row in connection.execute(
        "SELECT id,mistake_case_id,attempt_id,origin,reason_code,source_revision,source_status,created_at "
        "FROM mistake_occurrences WHERE mistake_case_id=? ORDER BY created_at,id", (mistake_case_id,)
    ).fetchall()]
    feedback = [dict(row) for row in connection.execute(
        "SELECT id,mistake_case_id,event_kind,content,provenance,created_at "
        "FROM mistake_feedback_events WHERE mistake_case_id=? ORDER BY created_at,id", (mistake_case_id,)
    ).fetchall()]
    return {**dict(case), "occurrences": occurrences, "feedback_events": feedback}


def list_mistake_cases(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT * FROM mistake_cases WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [get_mistake_case(connection, project_id=project_id, mistake_case_id=str(row["id"])) or {} for row in rows]


def redo_mistake_case(connection: sqlite3.Connection, *, project_id: str,
                      mistake_case_id: str, title: object | None = None) -> dict[str, object]:
    with connection:
        case = connection.execute(
            "SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)
        ).fetchone()
        if case is None:
            raise ValueError("mistake_not_found")
        if case["status"] == "archived":
            raise ValueError("mistake_archived")
        source = connection.execute(
            "SELECT a.session_id,s.session_kind,s.cram_goal_id,s.timezone,s.local_date,s.duration_seconds "
            "FROM mistake_occurrences o JOIN exercise_attempts a ON a.id=o.attempt_id "
            "LEFT JOIN practice_sessions s ON s.id=a.session_id "
            "WHERE o.mistake_case_id=? ORDER BY o.created_at DESC,o.id DESC LIMIT 1", (mistake_case_id,)
        ).fetchone()
        if source is None:
            raise ValueError("mistake_redo_not_ready")
        session_kind = source["session_kind"] or "practice"
        cram_goal_id = source["cram_goal_id"] if session_kind == "cram" else None
        session_title = title if title is not None else f"Redo: {case['exercise_id']}"
    return create_practice_session(
        connection, project_id=project_id, title=session_title,
        exercise_ids=[str(case["exercise_id"])], duration_seconds=int(source["duration_seconds"] or 600),
        timezone_name=str(source["timezone"] or "UTC"), local_date=str(source["local_date"] or date.today().isoformat()),
        session_kind=session_kind, cram_goal_id=cram_goal_id,
    )


def list_weak_points(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT c.exercise_id,c.exercise_revision_fingerprint,COUNT(o.id) AS occurrence_count,"
        "SUM(CASE WHEN c.status IN ('open','in_review','reopened') THEN 1 ELSE 0 END) AS open_count,"
        "SUM(CASE WHEN c.status='fixed' THEN 1 ELSE 0 END) AS fixed_count,"
        "SUM(CASE WHEN c.status='reopened' THEN 1 ELSE 0 END) AS reopened_count,"
        "SUM(CASE WHEN o.source_status!='valid' THEN 1 ELSE 0 END) AS source_warning_count,"
        "MAX(o.created_at) AS last_occurrence_at "
        "FROM mistake_cases c JOIN mistake_occurrences o ON o.mistake_case_id=c.id "
        "WHERE c.project_id=? AND c.status!='archived' GROUP BY c.exercise_id,c.exercise_revision_fingerprint "
        "ORDER BY last_occurrence_at DESC", (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


# Phase 9D shared extended-learning domain transactions. Provider execution,
# transcript confirmation, delivery execution, HTTP and UI remain in later gates.
PHASE9D_TRANSCRIPTION_OPERATION = "class_capture_transcription"
PHASE9D_TRANSCRIPT_CONFIDENCE_THRESHOLD = 0.70
PHASE9D_TRANSCRIPT_MAX_SEGMENTS = 1000
PHASE9D_TRANSCRIPT_MAX_TEXT = 200000
PHASE9D_REPORT_CONTENT_VERSION = "phase9d_report_v1"
PHASE9D_REPORT_KINDS = {"daily", "weekly", "monthly", "exam_alert"}
PHASE9D_REPORT_EXPORT_FORMATS = {"json", "markdown"}
PHASE9D_REPORT_PAYLOAD_FIELDS = {
    "period": {"report_kind", "period_start", "period_end", "timezone", "generated_at"},
    "plan": {"active_goal_count", "active_plan_count", "planned_item_count", "completed_item_count",
             "started_item_count", "skipped_item_count", "planned_minutes_total"},
    "rhythm": {"allocated_day_count", "allocated_minutes_total", "unallocated_eligible_item_count", "overload_day_count"},
    "practice": {"practice_session_count", "cram_session_count", "attempt_count", "deterministic_correct_count",
                 "deterministic_incorrect_count", "pending_review_count", "completed_session_count"},
    "feedback": {"open_mistake_count", "in_review_count", "fixed_count", "reopened_count", "archived_count", "weak_point_count"},
    "source_quality": {"valid_source_count", "stale_count", "source_deleted_count", "source_unavailable_count",
                       "uncertain_transcript_segment_count"},
    "quality_flags": {"has_pending_review", "has_source_warnings", "has_uncertain_capture"},
    "exam_alert": {"days_remaining_bucket", "is_imminent"},
}
PHASE9D_CAPTURE_ASSET_TYPES = {
    "audio": {"audio/wav", "audio/mpeg", "audio/mp4"},
    "image": {"image/png", "image/jpeg", "image/webp"},
}
PHASE9D_CAPTURE_SUFFIXES = {
    "image/png": {".png"}, "image/jpeg": {".jpg", ".jpeg"}, "image/webp": {".webp"},
    "audio/wav": {".wav"}, "audio/mpeg": {".mp3"}, "audio/mp4": {".m4a", ".mp4"},
}
PHASE9D_CAPTURE_PARSER_ID = "class_capture_original"
PHASE9D_CAPTURE_PARSER_VERSION = "1"
PHASE9D_TRANSCRIPT_PARSER_ID = "class_capture_transcript"
PHASE9D_TRANSCRIPT_PARSER_VERSION = "s2_v1"
PHASE9D_DELIVERY_CHANNELS = {"smtp", "feishu"}
PHASE9D_DELIVERY_MODES = {"off", "dry_run", "live"}
PHASE9D_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}
PHASE9D_TRANSCRIPTION_ERROR_CODES = {
    "transcription_failed", "transcription_provider_not_configured", "provider_timeout",
    "provider_unavailable", "capture_source_unavailable", "transcript_empty_or_invalid", "payload_too_large",
}


def _phase9d_text(value: object, *, code: str, maximum: int,
                   allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError(code)
    result = value.strip()
    if not result and not allow_empty:
        raise ValueError(code)
    return result


def _phase9d_idempotency_key(value: object | None) -> str | None:
    if value is None:
        return None
    return _phase9d_text(value, code="invalid_idempotency_key", maximum=200)


def _phase9d_asset_signature_valid(media_type: str, header: bytes) -> bool:
    checks = {
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "image/webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
        "audio/wav": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WAVE",
        "audio/mpeg": lambda value: value.startswith(b"ID3") or (len(value) >= 2 and value[0] == 0xff and value[1] & 0xe0 == 0xe0),
        "audio/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
    }
    return media_type in checks and checks[media_type](header)


def _phase9d_capture_source_status(connection: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    material_id = row["material_id"]
    if material_id is None:
        return None
    material = connection.execute(
        "SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)
    ).fetchone()
    if material is None or material["project_id"] != row["project_id"]:
        return "source_unavailable"
    if material["deleted_at"] is not None:
        return "source_deleted"
    persisted = row["source_status"]
    if persisted in {"source_deleted", "source_unavailable", "stale"}:
        return str(persisted)
    return "valid"


def _phase9d_transcript_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    segments = [dict(segment) for segment in connection.execute(
        "SELECT id,ordinal,text,confidence,quality,created_at,updated_at FROM transcript_segments "
        "WHERE draft_id=? AND project_id=? ORDER BY ordinal,id", (row["id"], row["project_id"])
    ).fetchall()]
    return {
        "id": row["id"], "capture_session_id": row["capture_session_id"],
        "operation_id": row["operation_id"], "status": row["status"], "text": row["text"],
        "language": row["language"], "quality_status": row["quality_status"],
        "edited_by_user": bool(row["edited_by_user"]), "created_at": row["created_at"],
        "updated_at": row["updated_at"], "segments": segments,
    }


def _phase9d_operation_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    return {
        "id": row["id"], "operation_type": row["operation_type"], "status": row["status"],
        "capture_session_id": row["capture_session_id"], "provider_id": row["provider_id"],
        "model_id": row["model_id"], "retry_count": int(row["retry_count"]),
        "error_code": row["error_code"], "output_artifact_id": row["output_artifact_id"],
        "created_at": row["created_at"], "started_at": row["started_at"],
        "finished_at": row["finished_at"], "replay": replay,
    }


def _phase9d_capture_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    drafts = [_phase9d_transcript_public(connection, draft) for draft in connection.execute(
        "SELECT * FROM transcript_drafts WHERE capture_session_id=? AND project_id=? "
        "ORDER BY created_at,id", (row["id"], row["project_id"])
    ).fetchall()]
    operations = [_phase9d_operation_public(operation) for operation in connection.execute(
        "SELECT * FROM ai_operations WHERE capture_session_id=? AND project_id=? "
        "AND operation_type=? ORDER BY created_at,id",
        (row["id"], row["project_id"], PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchall()]
    return {
        "id": row["id"], "project_id": row["project_id"], "status": row["status"],
        "asset_kind": row["asset_kind"], "material_id": row["material_id"],
        "original_name": row["original_name"], "media_type": row["media_type"],
        "source_status": _phase9d_capture_source_status(connection, row),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "confirmed_at": row["confirmed_at"], "rejected_at": row["rejected_at"],
        "archived_at": row["archived_at"], "transcript_drafts": drafts,
        "transcription_operations": operations,
    }


def create_capture_session(connection: sqlite3.Connection, *, project_id: str,
                           asset_kind: object, original_name: object, media_type: object,
                           material_id: str | None = None) -> dict[str, object]:
    if asset_kind not in PHASE9D_CAPTURE_ASSET_TYPES:
        raise ValueError("capture_asset_type_not_supported")
    name = _phase9d_text(original_name, code="capture_invalid_payload", maximum=255)
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("capture_invalid_payload")
    media = _phase9d_text(media_type, code="capture_asset_type_not_supported", maximum=100)
    if media not in PHASE9D_CAPTURE_ASSET_TYPES[str(asset_kind)]:
        raise ValueError("capture_asset_type_not_supported")
    capture_id, now = f"capture_session_{uuid.uuid4().hex}", utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("project_scope_violation")
        source_status = None
        status = "draft"
        if material_id is not None:
            material = connection.execute(
                "SELECT project_id,original_name,media_type,deleted_at FROM materials WHERE id=?", (material_id,)
            ).fetchone()
            if material is None:
                raise ValueError("capture_source_unavailable")
            if material["project_id"] != project_id:
                raise ValueError("project_scope_violation")
            if material["deleted_at"] is not None:
                raise ValueError("capture_source_unavailable")
            if material["media_type"] not in PHASE9D_CAPTURE_ASSET_TYPES[str(asset_kind)]:
                raise ValueError("capture_asset_type_not_supported")
            name, media = str(material["original_name"]), str(material["media_type"])
            source_status, status = "valid", "uploaded"
        try:
            connection.execute(
                "INSERT INTO capture_sessions (id,project_id,status,asset_kind,material_id,original_name,media_type,"
                "source_status,created_at,updated_at,confirmed_at,rejected_at,archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                (capture_id, project_id, status, asset_kind, material_id, name, media,
                 source_status, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("capture_invalid_state") from exc
    return get_capture_session(connection, project_id=project_id, capture_session_id=capture_id) or {}


def upload_capture_asset(connection: sqlite3.Connection, *, project_id: str,
                         capture_session_id: str, source_path: Path,
                         original_name: object, media_type: object,
                         originals_root: Path, max_upload_bytes: int) -> dict[str, object]:
    """Bind one sensitive original to a draft session without exposing its path."""
    name = _phase9d_text(original_name, code="capture_upload_failed", maximum=255)
    media = _phase9d_text(media_type, code="capture_asset_type_not_supported", maximum=100)
    source = Path(source_path)
    if (Path(name).name != name or "/" in name or "\\" in name or
            media not in PHASE9D_CAPTURE_SUFFIXES or Path(name).suffix.lower() not in PHASE9D_CAPTURE_SUFFIXES[media]):
        raise ValueError("capture_asset_type_not_supported")
    if not isinstance(max_upload_bytes, int) or isinstance(max_upload_bytes, bool) or max_upload_bytes < 1:
        raise ValueError("capture_upload_failed")
    try:
        mode = source.lstat().st_mode
        size = source.stat().st_size
    except OSError:
        raise ValueError("capture_upload_failed") from None
    if not stat.S_ISREG(mode) or source.is_symlink():
        raise ValueError("capture_upload_failed")
    if size > max_upload_bytes:
        raise ValueError("capture_asset_too_large")
    if size < 1:
        raise ValueError("capture_upload_failed")
    try:
        with source.open("rb") as handle:
            header = handle.read(32)
    except OSError:
        raise ValueError("capture_upload_failed") from None
    if not _phase9d_asset_signature_valid(media, header):
        raise ValueError("capture_asset_type_not_supported")
    digest = sha256_file(source)
    lock = acquire_hash_lock(digest)
    stored = None
    try:
        stored = store_original(source, name, digest, originals_root)
        material_id = f"material_{uuid.uuid4().hex}"
        extraction_id = f"extraction_{uuid.uuid4().hex}"
        with connection:
            capture = connection.execute(
                "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
            ).fetchone()
            if capture is None:
                raise ValueError("capture_not_found")
            if capture["status"] != "draft" or capture["material_id"] is not None:
                raise ValueError("capture_invalid_state")
            if media not in PHASE9D_CAPTURE_ASSET_TYPES[str(capture["asset_kind"])] or media != capture["media_type"]:
                raise ValueError("capture_asset_type_not_supported")
            if name != capture["original_name"]:
                raise ValueError("capture_invalid_state")
            now = utc_now()
            connection.execute(
                "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
                "VALUES (?,?,?,?,?,?,?,?,NULL)",
                (material_id, project_id, name, digest, str(stored.path), media, now, now),
            )
            connection.execute(
                "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
                "VALUES (?,?,?,?,?,'','[]',?,NULL)",
                (extraction_id, material_id, PHASE9D_CAPTURE_PARSER_ID, PHASE9D_CAPTURE_PARSER_VERSION, "empty", now),
            )
            _insert_search_row(connection, material_id, name, "")
            updated = connection.execute(
                "UPDATE capture_sessions SET status='uploaded',material_id=?,source_status='valid',updated_at=? "
                "WHERE id=? AND project_id=? AND status='draft' AND material_id IS NULL",
                (material_id, now, capture_session_id, project_id),
            )
            if updated.rowcount != 1:
                raise ValueError("capture_invalid_state")
    except ValueError:
        if stored is not None and stored.created:
            try:
                stored.path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    except (OSError, sqlite3.Error):
        if stored is not None and stored.created:
            try:
                stored.path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ValueError("capture_upload_failed") from None
    finally:
        release_hash_lock(digest, lock)
    return get_capture_session(connection, project_id=project_id, capture_session_id=capture_session_id) or {}


def get_capture_session(connection: sqlite3.Connection, *, project_id: str,
                        capture_session_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
    ).fetchone()
    return _phase9d_capture_public(connection, row) if row is not None else None


def list_capture_sessions(connection: sqlite3.Connection, *, project_id: str,
                          include_archived: bool = False) -> list[dict[str, object]]:
    clause = "" if include_archived else " AND status!='archived'"
    rows = connection.execute(
        "SELECT * FROM capture_sessions WHERE project_id=?" + clause + " ORDER BY updated_at DESC,id DESC",
        (project_id,),
    ).fetchall()
    return [_phase9d_capture_public(connection, row) for row in rows]


def _phase9d_transcription_fingerprint(*, capture_session_id: str, material_id: str,
                                       input_fingerprint: str) -> str:
    return hashlib.sha256(
        f"{PHASE9D_TRANSCRIPTION_OPERATION}\x1f{capture_session_id}\x1f{material_id}\x1f{input_fingerprint}".encode("utf-8")
    ).hexdigest()


def create_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                   capture_session_id: str, input_fingerprint: object,
                                   idempotency_key: object | None = None,
                                   provider_id: object = "fake", model_id: object = "fake-capture-v1") -> dict[str, object]:
    source_fingerprint = _phase9d_text(input_fingerprint, code="transcription_not_ready", maximum=64)
    if len(source_fingerprint) != 64 or any(char not in "0123456789abcdef" for char in source_fingerprint.lower()):
        raise ValueError("transcription_not_ready")
    key = _phase9d_idempotency_key(idempotency_key)
    provider = _phase9d_text(provider_id, code="transcription_provider_not_configured", maximum=100)
    model = _phase9d_text(model_id, code="transcription_provider_not_configured", maximum=200)
    if provider not in {"fake", "loopback"}:
        raise ValueError("transcription_provider_not_configured")
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        if capture["material_id"] is None:
            raise ValueError("capture_source_unavailable")
        fingerprint = _phase9d_transcription_fingerprint(
            capture_session_id=capture_session_id, material_id=str(capture["material_id"]),
            input_fingerprint=source_fingerprint.lower(),
        )
        if key is not None:
            existing = connection.execute(
                "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, key)
            ).fetchone()
            if existing is not None:
                if (existing["operation_type"] != PHASE9D_TRANSCRIPTION_OPERATION or
                        existing["capture_session_id"] != capture_session_id or
                        existing["input_fingerprint"] != fingerprint):
                    raise ValueError("transcription_idempotency_mismatch")
                if existing["status"] not in {"failed", "cancelled", "stale"}:
                    return _phase9d_operation_public(existing, replay=True)
                connection.execute(
                    "UPDATE ai_operations SET idempotency_key=NULL WHERE id=? AND status IN ('failed','cancelled','stale')",
                    (existing["id"],),
                )
        if capture["status"] not in {"uploaded", "failed", "rejected"}:
            raise ValueError("capture_invalid_state")
        source_status = _phase9d_capture_source_status(connection, capture)
        if source_status != "valid":
            raise ValueError("capture_source_unavailable")
        retry_count = int(connection.execute(
            "SELECT COUNT(*) FROM ai_operations WHERE project_id=? AND capture_session_id=? AND operation_type=?",
            (project_id, capture_session_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()[0])
        current_revision = connection.execute(
            "SELECT id FROM material_revisions WHERE material_id=? AND is_current=1 ORDER BY created_at DESC LIMIT 1",
            (capture["material_id"],),
        ).fetchone()
        operation_id, now = f"transcription_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
            "provider_id,model_id,retry_count,created_at,started_at,idempotency_key,capture_session_id) "
            "VALUES (?,?, 'running',?,?,?,?,?,?,?, ?,?,?,?)",
            (operation_id, PHASE9D_TRANSCRIPTION_OPERATION, project_id, capture["material_id"], fingerprint,
             current_revision["id"] if current_revision is not None else None, provider, model,
             retry_count, now, now, key, capture_session_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='transcribing',source_status='valid',updated_at=? "
            "WHERE id=? AND project_id=?", (now, capture_session_id, project_id)
        )
        operation = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return _phase9d_operation_public(operation)


def _phase9d_original_bytes(connection: sqlite3.Connection, *, project_id: str,
                             material_id: str, max_bytes: int) -> tuple[bytes, str, str]:
    material = connection.execute(
        "SELECT project_id,stored_path,source_sha256,media_type,deleted_at FROM materials WHERE id=?",
        (material_id,),
    ).fetchone()
    if material is None or material["project_id"] != project_id:
        raise ValueError("capture_source_unavailable")
    if material["deleted_at"] is not None:
        raise ValueError("capture_source_unavailable")
    path = Path(str(material["stored_path"]))
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("capture_source_unavailable")
    try:
        mode = path.lstat().st_mode
        size = path.stat().st_size
        if not stat.S_ISREG(mode) or size < 1 or size > max_bytes:
            raise ValueError("capture_source_unavailable")
        content = path.read_bytes()
    except (OSError, ValueError):
        raise ValueError("capture_source_unavailable") from None
    digest = hashlib.sha256(content).hexdigest()
    if digest != str(material["source_sha256"]):
        raise ValueError("capture_source_unavailable")
    return content, digest, str(material["media_type"])


def transcribe_capture_session(connection: sqlite3.Connection, *, project_id: str,
                               capture_session_id: str, provider: CaptureTranscriptionProvider,
                               idempotency_key: object | None = None,
                               max_upload_bytes: int = 50 * 1024 * 1024,
                               timeout_seconds: float = 30.0) -> dict[str, object]:
    """Run one fake/loopback transcription; raw bytes/results remain in memory only."""
    provider_id = getattr(provider, "provider_id", None)
    model_id = getattr(provider, "model_id", None)
    if provider_id not in {"fake", "loopback"} or not isinstance(model_id, str) or not model_id:
        raise ValueError("transcription_provider_not_configured")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        raise ValueError("transcription_failed")
    key = _phase9d_idempotency_key(idempotency_key)
    capture = connection.execute(
        "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
    ).fetchone()
    if capture is None:
        raise ValueError("capture_not_found")
    if key is not None:
        existing = connection.execute(
            "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, key)
        ).fetchone()
        if existing is not None:
            if (existing["operation_type"] != PHASE9D_TRANSCRIPTION_OPERATION or
                    existing["capture_session_id"] != capture_session_id or
                    existing["provider_id"] != provider_id or existing["model_id"] != model_id):
                raise ValueError("transcription_idempotency_mismatch")
            if existing["status"] not in {"failed", "cancelled", "stale"}:
                operation = _phase9d_operation_public(existing, replay=True)
                if existing["status"] == "succeeded" and existing["output_artifact_id"]:
                    draft = connection.execute(
                        "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                        (existing["output_artifact_id"], project_id),
                    ).fetchone()
                    if draft is not None:
                        return {"operation": operation, "draft": _phase9d_transcript_public(connection, draft), "replay": True}
                return {"operation": operation, "replay": True}
    if capture["material_id"] is None:
        raise ValueError("transcription_not_ready")
    content, digest, media_type = _phase9d_original_bytes(
        connection, project_id=project_id, material_id=str(capture["material_id"]), max_bytes=max_upload_bytes,
    )
    if capture["status"] not in {"uploaded", "failed", "rejected"}:
        raise ValueError("transcription_not_ready")
    operation = create_transcription_operation(
        connection, project_id=project_id, capture_session_id=capture_session_id,
        input_fingerprint=digest, idempotency_key=idempotency_key,
        provider_id=provider_id, model_id=model_id,
    )
    if operation.get("replay"):
        if operation["status"] == "succeeded" and operation.get("output_artifact_id"):
            draft = connection.execute(
                "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                (operation["output_artifact_id"], project_id),
            ).fetchone()
            if draft is not None:
                return {"operation": operation, "draft": _phase9d_transcript_public(connection, draft), "replay": True}
        return {"operation": operation, "replay": True}
    started = time.perf_counter()
    try:
        result = provider.transcribe(CaptureTranscriptionRequest(
            asset_kind=str(capture["asset_kind"]), media_type=media_type,
            content_sha256=digest, content=content,
        ))
        if time.perf_counter() - started > float(timeout_seconds):
            raise CaptureProviderError("provider_timeout")
        if not isinstance(result.segments, list):
            raise CaptureProviderError("transcription_failed")
        completed = complete_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]),
            segments=result.segments, language=result.language,
        )
        return {**completed, "replay": False}
    except CaptureProviderError as error:
        code = error.code if error.code in PHASE9D_TRANSCRIPTION_ERROR_CODES else "transcription_failed"
        failed = fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code=code,
        )
        raise ValueError(code) from None
    except ValueError as error:
        code = str(error) if str(error) in {"transcript_empty_or_invalid", "payload_too_large", "capture_source_unavailable"} else "transcription_failed"
        fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code=code,
        )
        raise ValueError(code) from None
    except Exception:
        fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code="transcription_failed",
        )
        raise ValueError("transcription_failed") from None


def get_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                operation_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
        (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchone()
    return _phase9d_operation_public(row) if row is not None else None


def list_transcription_operations(connection: sqlite3.Connection, *, project_id: str,
                                  capture_session_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT * FROM ai_operations WHERE project_id=? AND capture_session_id=? AND operation_type=? "
        "ORDER BY created_at,id", (project_id, capture_session_id, PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchall()
    return [_phase9d_operation_public(row) for row in rows]


def _phase9d_segment_values(segments: object) -> tuple[list[tuple[str, float, str]], str, str]:
    if not isinstance(segments, list) or not 1 <= len(segments) <= PHASE9D_TRANSCRIPT_MAX_SEGMENTS:
        raise ValueError("transcript_empty_or_invalid")
    values: list[tuple[str, float, str]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("transcript_empty_or_invalid")
        text = _phase9d_text(segment.get("text"), code="transcript_empty_or_invalid", maximum=20000)
        confidence = segment.get("confidence")
        if (not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or
                not 0.0 <= float(confidence) <= 1.0):
            raise ValueError("transcript_empty_or_invalid")
        quality = "clear" if float(confidence) >= PHASE9D_TRANSCRIPT_CONFIDENCE_THRESHOLD else "uncertain"
        values.append((text, float(confidence), quality))
    full_text = "\n".join(value[0] for value in values)
    if len(full_text) > PHASE9D_TRANSCRIPT_MAX_TEXT:
        raise ValueError("payload_too_large")
    quality_status = "uncertain" if any(value[2] == "uncertain" for value in values) else "clear"
    return values, full_text, quality_status


def complete_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                     operation_id: str, segments: object,
                                     language: object | None = None) -> dict[str, object]:
    values, full_text, quality_status = _phase9d_segment_values(segments)
    language_value = None if language is None else _phase9d_text(
        language, code="transcript_empty_or_invalid", maximum=32
    )
    with connection:
        operation = connection.execute(
            "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
            (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()
        if operation is None:
            raise ValueError("transcription_not_ready")
        if operation["status"] == "succeeded" and operation["output_artifact_id"] is not None:
            existing = connection.execute(
                "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                (operation["output_artifact_id"], project_id),
            ).fetchone()
            if existing is None:
                raise ValueError("transcription_failed")
            return {"draft": _phase9d_transcript_public(connection, existing),
                    "operation": _phase9d_operation_public(operation, replay=True), "replay": True}
        if operation["status"] != "running":
            raise ValueError("transcription_not_ready")
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?",
            (operation["capture_session_id"], project_id),
        ).fetchone()
        if capture is None or capture["status"] != "transcribing":
            raise ValueError("capture_invalid_state")
        if _phase9d_capture_source_status(connection, capture) != "valid":
            raise ValueError("capture_source_unavailable")
        draft_id, now = f"transcript_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO transcript_drafts (id,project_id,capture_session_id,operation_id,status,text,language,"
            "quality_status,edited_by_user,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (draft_id, project_id, capture["id"], operation_id, "draft", full_text,
             language_value, quality_status, now, now),
        )
        connection.executemany(
            "INSERT INTO transcript_segments (id,draft_id,project_id,ordinal,text,confidence,quality,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"transcript_segment_{uuid.uuid4().hex}", draft_id, project_id, ordinal,
              text, confidence, quality, now, now)
             for ordinal, (text, confidence, quality) in enumerate(values)],
        )
        connection.execute(
            "UPDATE ai_operations SET status='succeeded',output_artifact_id=?,finished_at=? "
            "WHERE id=? AND status='running'", (draft_id, now, operation_id)
        )
        connection.execute(
            "UPDATE capture_sessions SET status='review_required',updated_at=? "
            "WHERE id=? AND project_id=? AND status='transcribing'",
            (now, capture["id"], project_id),
        )
        draft = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
        finished = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return {"draft": _phase9d_transcript_public(connection, draft),
                "operation": _phase9d_operation_public(finished), "replay": False}


def edit_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                          capture_session_id: str, draft_id: str, text: object) -> dict[str, object]:
    """Apply an explicit user edit; provider output can never mutate this path."""
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("transcript_user_edit_protected")
        edited_text = _phase9d_text(text, code="transcript_empty_or_invalid", maximum=PHASE9D_TRANSCRIPT_MAX_TEXT)
        now = utc_now()
        edited_segments = [line.strip() for line in edited_text.splitlines() if line.strip()]
        if not edited_segments:
            edited_segments = [edited_text]
        existing_segments = connection.execute(
            "SELECT ordinal,confidence,quality FROM transcript_segments WHERE draft_id=? ORDER BY ordinal,id",
            (draft_id,),
        ).fetchall()
        connection.execute("DELETE FROM transcript_segments WHERE draft_id=?", (draft_id,))
        connection.executemany(
            "INSERT INTO transcript_segments (id,draft_id,project_id,ordinal,text,confidence,quality,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"transcript_segment_{uuid.uuid4().hex}", draft_id, project_id, ordinal,
              segment_text,
              float(existing_segments[ordinal]["confidence"]) if ordinal < len(existing_segments) else 1.0,
              str(existing_segments[ordinal]["quality"]) if ordinal < len(existing_segments) else "clear",
              now, now)
             for ordinal, segment_text in enumerate(edited_segments)],
        )
        connection.execute(
            "UPDATE transcript_drafts SET text=?,quality_status=?,edited_by_user=1,updated_at=? WHERE id=?",
            (edited_text, "uncertain" if any(
                str(existing_segments[index]["quality"]) == "uncertain"
                for index in range(min(len(existing_segments), len(edited_segments)))
            ) else "clear", now, draft_id),
        )
        updated = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
    return _phase9d_transcript_public(connection, updated)


def _phase9d_confirmed_revision_public(connection: sqlite3.Connection, *, project_id: str,
                                       material_id: str, revision_id: str) -> dict[str, object]:
    chunks = connection.execute(
        "SELECT id,revision_id,extraction_id,chunk_index,start_offset,end_offset,text,status "
        "FROM chunks WHERE project_id=? AND material_id=? AND revision_id=? ORDER BY chunk_index,id",
        (project_id, material_id, revision_id),
    ).fetchall()
    citations = []
    for chunk in chunks:
        key = _citation_key(material_id, str(chunk["id"]))
        validation = validate_citation_key(connection, key)
        citation_valid = bool(
            validation and validation.get("status") == "valid"
            and validation.get("material_id") == material_id
            and validation.get("chunk_id") == chunk["id"]
            and validation.get("revision_id") == revision_id
        )
        citations.append({
            "citation_key": key,
            "material_id": material_id,
            "revision_id": revision_id,
            "extraction_id": chunk["extraction_id"],
            "chunk_id": chunk["id"],
            "span_ids": [str(value[0]) for value in connection.execute(
                "SELECT span_id FROM chunk_spans WHERE chunk_id=? ORDER BY span_id", (chunk["id"],)
            ).fetchall()],
            "status": "valid" if citation_valid else "source_unavailable",
        })
    if not chunks or any(item["status"] != "valid" for item in citations):
        raise ValueError("transcript_citation_invalid")
    return {"id": revision_id, "material_id": material_id, "extraction_id": chunks[0]["extraction_id"] if chunks else None,
            "chunks": [dict(chunk) for chunk in chunks], "citations": citations}


def confirm_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                             capture_session_id: str, draft_id: str) -> dict[str, object]:
    """Confirm one reviewed draft into the capture material's next S2 revision."""
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] == "confirmed" and draft["status"] == "confirmed":
            revision = connection.execute(
                "SELECT id FROM material_revisions WHERE material_id=? AND parser_id=? AND is_current=1 "
                "ORDER BY created_at DESC,id DESC LIMIT 1", (capture["material_id"], PHASE9D_TRANSCRIPT_PARSER_ID)
            ).fetchone()
            if revision is None:
                raise ValueError("transcript_citation_invalid")
            return {"capture": _phase9d_capture_public(connection, capture), "draft": _phase9d_transcript_public(connection, draft),
                    "revision": _phase9d_confirmed_revision_public(connection, project_id=project_id,
                                                                    material_id=str(capture["material_id"]), revision_id=str(revision["id"])),
                    "replay": True}
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("capture_invalid_state")
        if capture["material_id"] is None or _phase9d_capture_source_status(connection, capture) != "valid":
            raise ValueError("capture_source_unavailable")
        text = _phase9d_text(draft["text"], code="transcript_empty_or_invalid", maximum=PHASE9D_TRANSCRIPT_MAX_TEXT)
        segments = connection.execute(
            "SELECT ordinal,text FROM transcript_segments WHERE draft_id=? ORDER BY ordinal,id", (draft_id,)
        ).fetchall()
        if not segments:
            raise ValueError("transcript_empty_or_invalid")
        now = utc_now()
        extraction_id = f"extraction_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)",
            (extraction_id, capture["material_id"], PHASE9D_TRANSCRIPT_PARSER_ID,
             PHASE9D_TRANSCRIPT_PARSER_VERSION, "success", text, "[]", now),
        )
        connection.executemany(
            "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, int(segment["ordinal"]) + 1, "document",
              f"transcript-segment-{int(segment['ordinal']) + 1}", str(segment["text"])) for segment in segments],
        )
        revision = _index_material_revision_in_transaction(
            connection, str(capture["material_id"]), extraction_id,
        )
        revision_id = str(revision["id"])
        connection.execute(
            "UPDATE transcript_drafts SET status='confirmed',updated_at=? WHERE id=? AND status='draft'",
            (now, draft_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='confirmed',confirmed_at=?,updated_at=? "
            "WHERE id=? AND project_id=? AND status='review_required'",
            (now, now, capture_session_id, project_id),
        )
        connection.execute(
            "UPDATE ai_operations SET source_revision=? WHERE id=? AND project_id=?",
            (revision_id, draft["operation_id"], project_id),
        )
        updated_capture = connection.execute("SELECT * FROM capture_sessions WHERE id=?", (capture_session_id,)).fetchone()
        updated_draft = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
        _replace_search_row(connection, str(capture["material_id"]))
        revision_public = _phase9d_confirmed_revision_public(
            connection, project_id=project_id, material_id=str(capture["material_id"]), revision_id=revision_id,
        )
        return {"capture": _phase9d_capture_public(connection, updated_capture),
                "draft": _phase9d_transcript_public(connection, updated_draft),
                "revision": revision_public, "replay": False}


def reject_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                            capture_session_id: str, draft_id: str) -> dict[str, object]:
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("capture_invalid_state")
        now = utc_now()
        connection.execute("UPDATE transcript_drafts SET status='rejected',updated_at=? WHERE id=?", (now, draft_id))
        connection.execute(
            "UPDATE capture_sessions SET status='rejected',rejected_at=?,updated_at=? WHERE id=? AND project_id=?",
            (now, now, capture_session_id, project_id),
        )
        return {"capture": _phase9d_capture_public(connection, connection.execute(
            "SELECT * FROM capture_sessions WHERE id=?", (capture_session_id,)
        ).fetchone()), "draft": _phase9d_transcript_public(connection, connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)
        ).fetchone())}


def fail_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                 operation_id: str, error_code: object = "transcription_failed") -> dict[str, object]:
    error = _phase9d_text(error_code, code="transcription_failed", maximum=100)
    if error not in PHASE9D_TRANSCRIPTION_ERROR_CODES:
        raise ValueError("transcription_failed")
    with connection:
        operation = connection.execute(
            "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
            (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()
        if operation is None:
            raise ValueError("transcription_not_ready")
        if operation["status"] == "failed":
            return _phase9d_operation_public(operation, replay=True)
        if operation["status"] != "running":
            raise ValueError("transcription_not_ready")
        now = utc_now()
        connection.execute(
            "UPDATE ai_operations SET status='failed',error_code=?,finished_at=? WHERE id=? AND status='running'",
            (error, now, operation_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='failed',updated_at=? "
            "WHERE id=? AND project_id=? AND status='transcribing'",
            (now, operation["capture_session_id"], project_id),
        )
        result = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return _phase9d_operation_public(result)


def _phase9d_report_period(report_kind: object, timezone_name: object,
                           period_start: object, period_end: object) -> tuple[str, str, str, ZoneInfo, datetime, datetime]:
    if report_kind not in PHASE9D_REPORT_KINDS:
        raise ValueError("report_invalid_kind")
    timezone_value = _phase9d_text(timezone_name, code="report_invalid_period", maximum=100)
    try:
        zone = ZoneInfo(timezone_value)
        start_date = date.fromisoformat(_phase9d_text(period_start, code="report_invalid_period", maximum=10))
        end_date = date.fromisoformat(_phase9d_text(period_end, code="report_invalid_period", maximum=10))
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("report_invalid_period") from None
    if start_date.isoformat() != period_start or end_date.isoformat() != period_end or start_date >= end_date:
        raise ValueError("report_invalid_period")
    start_utc = datetime.combine(start_date, datetime.min.time(), zone).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, datetime.min.time(), zone).astimezone(timezone.utc)
    return str(report_kind), timezone_value, start_date.isoformat(), zone, start_utc, end_utc


def _phase9d_in_period(value: object, start_utc: datetime, end_utc: datetime) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    normalized = parsed.astimezone(timezone.utc)
    return start_utc <= normalized < end_utc


def _phase9d_rows_in_period(rows: list[sqlite3.Row], field: str,
                            start_utc: datetime, end_utc: datetime) -> list[sqlite3.Row]:
    return [row for row in rows if _phase9d_in_period(row[field], start_utc, end_utc)]


def _phase9d_validate_safe_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != set(PHASE9D_REPORT_PAYLOAD_FIELDS):
        raise ValueError("report_redaction_violation")
    numeric_fields = {
        field for section, fields in PHASE9D_REPORT_PAYLOAD_FIELDS.items()
        if section not in {"period", "quality_flags", "exam_alert"}
        for field in fields
    }
    boolean_fields = set(PHASE9D_REPORT_PAYLOAD_FIELDS["quality_flags"]) | {"is_imminent"}
    for section, allowed in PHASE9D_REPORT_PAYLOAD_FIELDS.items():
        value = payload.get(section)
        if not isinstance(value, dict) or set(value) != allowed:
            raise ValueError("report_redaction_violation")
        for field, item in value.items():
            if field == "days_remaining_bucket":
                if item is not None and item not in {"0-3", "4-7", "8-14", "15+"}:
                    raise ValueError("report_redaction_violation")
            elif field == "generated_at":
                if not isinstance(item, str) or not item:
                    raise ValueError("report_redaction_violation")
                try:
                    generated = datetime.fromisoformat(item.replace("Z", "+00:00"))
                except ValueError:
                    raise ValueError("report_redaction_violation") from None
                if generated.tzinfo is None:
                    raise ValueError("report_redaction_violation")
            elif field in {"report_kind", "period_start", "period_end", "timezone"}:
                if not isinstance(item, str) or not item:
                    raise ValueError("report_redaction_violation")
            elif field in boolean_fields:
                if not isinstance(item, bool):
                    raise ValueError("report_redaction_violation")
            elif field in numeric_fields:
                if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                    raise ValueError("report_redaction_violation")
            else:
                raise ValueError("report_redaction_violation")
    period = payload["period"]
    if not isinstance(period.get("report_kind"), str) or period["report_kind"] not in PHASE9D_REPORT_KINDS:
        raise ValueError("report_redaction_violation")
    try:
        ZoneInfo(str(period["timezone"]))
        start_date = date.fromisoformat(str(period["period_start"]))
        end_date = date.fromisoformat(str(period["period_end"]))
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("report_redaction_violation") from None
    if (start_date.isoformat() != period["period_start"] or
            end_date.isoformat() != period["period_end"] or start_date >= end_date):
        raise ValueError("report_redaction_violation")
    return payload


def _phase9d_safe_markdown(payload: dict[str, object]) -> str:
    _phase9d_validate_safe_payload(payload)
    sections = ["# Study Report", "", f"Kind: {payload['period']['report_kind']}",
                f"Period: {payload['period']['period_start']} to {payload['period']['period_end']}",
                f"Timezone: {payload['period']['timezone']}"]
    for key in ("plan", "rhythm", "practice", "feedback", "source_quality", "quality_flags"):
        sections.extend(["", f"## {key.replace('_', ' ').title()}"])
        for field, value in payload[key].items():
            sections.append(f"- {field}: {str(value).lower() if isinstance(value, bool) else value}")
    if payload["period"]["report_kind"] == "exam_alert":
        sections.extend(["", "## Exam Alert"])
        for field, value in payload["exam_alert"].items():
            sections.append(f"- {field}: {str(value).lower() if isinstance(value, bool) else value}")
    return "\n".join(sections) + "\n"


def build_report_projection(connection: sqlite3.Connection, *, project_id: str,
                            report_kind: object, timezone_name: object,
                            period_start: object, period_end: object) -> dict[str, object]:
    kind, timezone_value, start_value, _zone, start_utc, end_utc = _phase9d_report_period(
        report_kind, timezone_name, period_start, period_end
    )
    end_value = date.fromisoformat(str(period_end)).isoformat()
    if not _study_project_exists(connection, project_id):
        raise ValueError("project_scope_violation")

    goals = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM learning_goals WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)
    plans = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM study_plans WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)
    items = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM study_plan_items WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)

    allocations = [row for row in connection.execute(
        "SELECT a.id,a.plan_id,a.item_id,a.local_date,a.planned_minutes,s.cadence,s.target_minutes "
        "FROM rhythm_allocations a LEFT JOIN rhythm_settings s ON s.plan_id=a.plan_id AND s.project_id=a.project_id "
        "WHERE a.project_id=?", (project_id,)
    ).fetchall() if start_value <= str(row["local_date"]) < end_value]
    allocation_item_ids = {str(row["item_id"]) for row in allocations}
    daily_totals: dict[tuple[str, str], int] = {}
    daily_targets: dict[tuple[str, str], int] = {}
    for row in allocations:
        key = (str(row["plan_id"]), str(row["local_date"]))
        daily_totals[key] = daily_totals.get(key, 0) + int(row["planned_minutes"])
        if row["cadence"] == "daily" and row["target_minutes"] is not None:
            daily_targets[key] = int(row["target_minutes"])

    sessions = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,session_kind,status,created_at FROM practice_sessions WHERE project_id=?", (project_id,)
    ).fetchall()), "created_at", start_utc, end_utc)
    attempts = _phase9d_rows_in_period(list(connection.execute(
        "SELECT a.id,a.grading_status,a.is_correct,a.submitted_at FROM exercise_attempts a "
        "JOIN exercises e ON e.id=a.exercise_id WHERE e.project_id=?", (project_id,)
    ).fetchall()), "submitted_at", start_utc, end_utc)
    cases = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,exercise_id,exercise_revision_fingerprint,status,updated_at FROM mistake_cases WHERE project_id=?",
        (project_id,),
    ).fetchall()), "updated_at", start_utc, end_utc)

    source_rows: list[sqlite3.Row] = []
    for table in ("module_source_links", "plan_item_source_links", "note_block_source_links"):
        source_rows.extend(_phase9d_rows_in_period(list(connection.execute(
            f"SELECT id,status,updated_at FROM {table} WHERE project_id=?", (project_id,)
        ).fetchall()), "updated_at", start_utc, end_utc))
    source_rows.extend(_phase9d_rows_in_period(list(connection.execute(
        "SELECT c.id,CASE WHEN m.id IS NULL THEN 'source_unavailable' "
        "WHEN m.deleted_at IS NOT NULL THEN 'source_deleted' "
        "ELSE COALESCE(c.source_status,'source_unavailable') END AS status,c.updated_at "
        "FROM capture_sessions c LEFT JOIN materials m ON m.id=c.material_id "
        "WHERE c.project_id=? AND c.material_id IS NOT NULL", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc))
    uncertain_segments = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,created_at FROM transcript_segments WHERE project_id=? AND quality='uncertain'", (project_id,)
    ).fetchall()), "created_at", start_utc, end_utc)

    active_cram_targets = []
    for row in connection.execute(
        "SELECT id,target_date FROM cram_goals WHERE project_id=? AND status='active'", (project_id,)
    ).fetchall():
        try:
            days = (date.fromisoformat(str(row["target_date"])) - date.fromisoformat(start_value)).days
        except ValueError:
            continue
        if days >= 0:
            active_cram_targets.append((days, str(row["id"])))
    active_cram_targets.sort()
    nearest_days = active_cram_targets[0][0] if active_cram_targets else None
    if nearest_days is None:
        days_bucket = None
    elif nearest_days <= 3:
        days_bucket = "0-3"
    elif nearest_days <= 7:
        days_bucket = "4-7"
    elif nearest_days <= 14:
        days_bucket = "8-14"
    else:
        days_bucket = "15+"

    item_counts = {status: sum(row["status"] == status for row in items)
                   for status in ("pending", "in_progress", "completed", "skipped")}
    case_counts = {status: sum(row["status"] == status for row in cases)
                   for status in ("open", "in_review", "fixed", "reopened", "archived")}
    source_counts = {status: sum(row["status"] == status for row in source_rows)
                     for status in PHASE9D_SOURCE_STATUSES}
    deterministic = [row for row in attempts if row["grading_status"] == "deterministic"]
    planned_minutes = sum(int(row["planned_minutes"]) for row in allocations)
    payload: dict[str, object] = {
        "period": {"report_kind": kind, "period_start": start_value, "period_end": end_value,
                   "timezone": timezone_value, "generated_at": utc_now()},
        "plan": {"active_goal_count": sum(row["status"] == "active" for row in goals),
                 "active_plan_count": sum(row["status"] == "active" for row in plans),
                 "planned_item_count": sum(row["status"] != "archived" for row in items),
                 "completed_item_count": item_counts["completed"],
                 "started_item_count": item_counts["in_progress"],
                 "skipped_item_count": item_counts["skipped"],
                 "planned_minutes_total": planned_minutes},
        "rhythm": {"allocated_day_count": len({str(row["local_date"]) for row in allocations}),
                   "allocated_minutes_total": planned_minutes,
                   "unallocated_eligible_item_count": sum(
                       row["status"] != "archived" and str(row["id"]) not in allocation_item_ids for row in items
                   ),
                   "overload_day_count": sum(total > daily_targets[key] for key, total in daily_totals.items()
                                             if key in daily_targets)},
        "practice": {"practice_session_count": sum(row["session_kind"] == "practice" for row in sessions),
                     "cram_session_count": sum(row["session_kind"] == "cram" for row in sessions),
                     "attempt_count": len(attempts),
                     "deterministic_correct_count": sum(row["is_correct"] == 1 for row in deterministic),
                     "deterministic_incorrect_count": sum(row["is_correct"] == 0 for row in deterministic),
                     "pending_review_count": sum(row["grading_status"] == "pending_review" for row in attempts),
                     "completed_session_count": sum(row["status"] in {"finished", "expired"} for row in sessions)},
        "feedback": {"open_mistake_count": case_counts["open"],
                     "in_review_count": case_counts["in_review"], "fixed_count": case_counts["fixed"],
                     "reopened_count": case_counts["reopened"], "archived_count": case_counts["archived"],
                     "weak_point_count": len({(str(row["exercise_id"]), str(row["exercise_revision_fingerprint"]))
                                              for row in cases if row["status"] != "archived"})},
        "source_quality": {"valid_source_count": source_counts["valid"],
                           "stale_count": source_counts["stale"],
                           "source_deleted_count": source_counts["source_deleted"],
                           "source_unavailable_count": source_counts["source_unavailable"],
                           "uncertain_transcript_segment_count": len(uncertain_segments)},
        "exam_alert": {"days_remaining_bucket": days_bucket,
                       "is_imminent": nearest_days is not None and nearest_days <= 7},
    }
    payload["quality_flags"] = {
        "has_pending_review": payload["practice"]["pending_review_count"] > 0,
        "has_source_warnings": sum(source_counts[status] for status in ("stale", "source_deleted", "source_unavailable")) > 0,
        "has_uncertain_capture": len(uncertain_segments) > 0,
    }
    basis = json.loads(json.dumps(payload))
    basis["period"].pop("generated_at", None)
    fact_identity = {
        "goals": [(row["id"], row["status"], row["updated_at"]) for row in goals],
        "plans": [(row["id"], row["status"], row["updated_at"]) for row in plans],
        "items": [(row["id"], row["status"], row["updated_at"]) for row in items],
        "allocations": [(row["id"], row["local_date"], row["planned_minutes"]) for row in allocations],
        "sessions": [(row["id"], row["status"], row["created_at"]) for row in sessions],
        "attempts": [(row["id"], row["grading_status"], row["is_correct"], row["submitted_at"]) for row in attempts],
        "cases": [(row["id"], row["status"], row["updated_at"]) for row in cases],
        "sources": [(row["id"], row["status"], row["updated_at"]) for row in source_rows],
        "uncertain_segments": [(row["id"], row["created_at"]) for row in uncertain_segments],
        "cram_targets": active_cram_targets,
    }
    for identities in fact_identity.values():
        identities.sort(key=lambda identity: tuple("" if value is None else str(value) for value in identity))
    fingerprint_source = json.dumps(
        {"version": PHASE9D_REPORT_CONTENT_VERSION, "payload": basis, "facts": fact_identity},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    _phase9d_validate_safe_payload(payload)
    return {"safe_payload": payload, "markdown_content": _phase9d_safe_markdown(payload),
            "aggregation_fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
            "content_version": PHASE9D_REPORT_CONTENT_VERSION}


def _phase9d_report_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    try:
        payload = _phase9d_validate_safe_payload(json.loads(str(row["safe_payload_json"])))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("report_redaction_violation") from None
    return {
        "id": row["id"], "project_id": row["project_id"], "report_kind": row["report_kind"],
        "timezone": row["timezone"], "period_start": row["period_start"],
        "period_end": row["period_end"], "status": row["status"],
        "content_version": row["content_version"], "safe_payload": payload,
        "markdown_content": row["markdown_content"], "error_code": row["error_code"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "ready_at": row["ready_at"], "archived_at": row["archived_at"], "replay": replay,
    }


def export_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                           report_id: str, format_name: object = "json") -> tuple[str, str]:
    if not isinstance(format_name, str) or format_name not in PHASE9D_REPORT_EXPORT_FORMATS:
        raise ValueError("report_redaction_violation")
    report = get_report_snapshot(connection, project_id=project_id, report_id=report_id)
    if report is None:
        raise ValueError("report_not_found")
    if report["status"] != "ready":
        raise ValueError("report_invalid_state")
    payload = _phase9d_validate_safe_payload(report["safe_payload"])
    if format_name == "json":
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), "application/json"
    markdown = str(report["markdown_content"])
    if not markdown or "stored_path" in markdown or "answer_key" in markdown or "answer_json" in markdown:
        raise ValueError("report_redaction_violation")
    return markdown, "text/markdown"


def create_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                           report_kind: object, timezone_name: object,
                           period_start: object, period_end: object) -> dict[str, object]:
    with connection:
        projection = build_report_projection(
            connection, project_id=project_id, report_kind=report_kind,
            timezone_name=timezone_name, period_start=period_start, period_end=period_end,
        )
        period = projection["safe_payload"]["period"]
        existing = connection.execute(
            "SELECT * FROM report_snapshots WHERE project_id=? AND report_kind=? AND period_start=? "
            "AND period_end=? AND content_version=? AND aggregation_fingerprint=?",
            (project_id, period["report_kind"], period["period_start"], period["period_end"],
             projection["content_version"], projection["aggregation_fingerprint"]),
        ).fetchone()
        if existing is not None:
            return _phase9d_report_public(existing, replay=True)
        report_id, now = f"report_{uuid.uuid4().hex}", utc_now()
        safe_json = json.dumps(
            projection["safe_payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        connection.execute(
            "INSERT INTO report_snapshots (id,project_id,report_kind,timezone,period_start,period_end,status,"
            "content_version,aggregation_fingerprint,safe_payload_json,markdown_content,error_code,created_at,"
            "updated_at,ready_at,archived_at) VALUES (?,?,?,?,?,?,'ready',?,?,?,?,NULL,?,?,?,NULL)",
            (report_id, project_id, period["report_kind"], period["timezone"], period["period_start"],
             period["period_end"], projection["content_version"], projection["aggregation_fingerprint"], safe_json,
             projection["markdown_content"], now, now, now),
        )
        row = connection.execute("SELECT * FROM report_snapshots WHERE id=?", (report_id,)).fetchone()
        return _phase9d_report_public(row)


def get_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                        report_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
    ).fetchone()
    return _phase9d_report_public(row) if row is not None else None


def list_report_snapshots(connection: sqlite3.Connection, *, project_id: str,
                          include_archived: bool = False) -> list[dict[str, object]]:
    clause = "" if include_archived else " AND status!='archived'"
    rows = connection.execute(
        "SELECT * FROM report_snapshots WHERE project_id=?" + clause + " ORDER BY created_at DESC,id DESC",
        (project_id,),
    ).fetchall()
    return [_phase9d_report_public(row) for row in rows]


def _phase9d_target_label(value: object) -> str:
    label = _phase9d_text(value, code="delivery_target_not_allowed", maximum=100)
    if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in label):
        raise ValueError("delivery_target_not_allowed")
    return label


def _phase9d_delivery_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    return {
        "id": row["id"], "report_id": row["report_id"], "channel": row["channel"],
        "mode": row["mode"], "target_label": row["target_label"], "status": row["status"],
        "error_code": row["error_code"], "retry_of": row["retry_of"],
        "created_at": row["created_at"], "finished_at": row["finished_at"], "replay": replay,
    }


def record_report_delivery_attempt(connection: sqlite3.Connection, *, project_id: str,
                                   report_id: str, channel: object, mode: object,
                                   target_label: object, idempotency_key: object | None = None,
                                   retry_of: str | None = None, status_override: str | None = None,
                                   error_code_override: str | None = None) -> dict[str, object]:
    if channel not in PHASE9D_DELIVERY_CHANNELS:
        raise ValueError("delivery_target_not_allowed")
    if mode not in PHASE9D_DELIVERY_MODES:
        raise ValueError("delivery_failed")
    if status_override not in {None, "blocked", "dry_run", "failed"}:
        raise ValueError("delivery_failed")
    if error_code_override is not None and error_code_override not in {
        "delivery_disabled", "delivery_target_not_allowed", "delivery_authorization_required",
        "delivery_live_not_approved", "delivery_failed",
    }:
        raise ValueError("delivery_failed")
    label = _phase9d_target_label(target_label)
    key = _phase9d_idempotency_key(idempotency_key)
    key_fingerprint = hashlib.sha256(f"{project_id}\x1f{key}".encode("utf-8")).hexdigest() if key else None
    with connection:
        report = connection.execute(
            "SELECT * FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
        ).fetchone()
        if report is None:
            raise ValueError("report_not_found")
        if report["status"] != "ready":
            raise ValueError("report_invalid_state")
        content_fingerprint = hashlib.sha256(
            f"{report['content_version']}\x1f{report['safe_payload_json']}".encode("utf-8")
        ).hexdigest()
        if key_fingerprint is not None:
            existing = connection.execute(
                "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? AND channel=? "
                "AND idempotency_key_fingerprint=? ORDER BY created_at,id LIMIT 1",
                (project_id, report_id, channel, key_fingerprint),
            ).fetchone()
            if existing is not None:
                if (existing["mode"] != mode or existing["target_label"] != label or
                        existing["content_fingerprint"] != content_fingerprint):
                    raise ValueError("delivery_idempotency_mismatch")
                return _phase9d_delivery_public(existing, replay=True)
        if retry_of is not None:
            previous = connection.execute(
                "SELECT id FROM report_delivery_attempts WHERE id=? AND project_id=? AND report_id=? AND status='failed'",
                (retry_of, project_id, report_id),
            ).fetchone()
            if previous is None:
                raise ValueError("delivery_failed")
        default_status, default_error_code = {
            "off": ("blocked", "delivery_disabled"),
            "dry_run": ("dry_run", None),
            "live": ("blocked", "delivery_live_not_approved"),
        }[str(mode)]
        status = status_override or default_status
        error_code = error_code_override if error_code_override is not None else default_error_code
        attempt_id, now = f"delivery_attempt_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO report_delivery_attempts (id,project_id,report_id,channel,mode,target_label,"
            "content_fingerprint,idempotency_key_fingerprint,status,error_code,retry_of,created_at,finished_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, project_id, report_id, channel, mode, label, content_fingerprint,
             key_fingerprint, status, error_code, retry_of, now, now),
        )
        row = connection.execute("SELECT * FROM report_delivery_attempts WHERE id=?", (attempt_id,)).fetchone()
        return _phase9d_delivery_public(row)


def find_report_delivery_replay(connection: sqlite3.Connection, *, project_id: str,
                                 report_id: str, channel: object, mode: object,
                                 target_label: object, idempotency_key: object | None,
                                 content_fingerprint: str) -> dict[str, object] | None:
    """Return an idempotent delivery result before any adapter is invoked."""
    key = _phase9d_idempotency_key(idempotency_key)
    if key is None:
        return None
    label = _phase9d_target_label(target_label)
    key_fingerprint = hashlib.sha256(f"{project_id}\x1f{key}".encode("utf-8")).hexdigest()
    existing = connection.execute(
        "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? AND channel=? "
        "AND idempotency_key_fingerprint=? ORDER BY created_at,id LIMIT 1",
        (project_id, report_id, channel, key_fingerprint),
    ).fetchone()
    if existing is None:
        return None
    if (existing["mode"] != mode or existing["target_label"] != label or
            existing["content_fingerprint"] != content_fingerprint):
        raise ValueError("delivery_idempotency_mismatch")
    return _phase9d_delivery_public(existing, replay=True)


def list_report_delivery_attempts(connection: sqlite3.Connection, *, project_id: str,
                                  report_id: str) -> list[dict[str, object]]:
    if connection.execute(
        "SELECT 1 FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
    ).fetchone() is None:
        raise ValueError("report_not_found")
    rows = connection.execute(
        "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? ORDER BY created_at,id",
        (project_id, report_id),
    ).fetchall()
    return [_phase9d_delivery_public(row) for row in rows]


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
RHYTHM_CADENCES = {"daily", "weekly"}
RHYTHM_MAX_TARGET_MINUTES = 10080
RHYTHM_MAX_ITEM_MINUTES = 10080
RHYTHM_MAX_PERIOD_MINUTES = 10080
RHYTHM_MAX_ALLOCATION_MINUTES = 1440
NOTE_STATUSES = {"draft", "confirmed", "rejected", "archived"}
NOTE_PROVENANCES = {"user_created", "ai_generated"}
NOTE_BLOCK_KINDS = {"text", "heading", "bullet"}
NOTE_MAX_TITLE = 400
NOTE_MAX_BLOCK_CONTENT = 12000
NOTE_MAX_CONTENT = 48000
NOTE_GENERATION_PROMPT_VERSION = "phase9b_note_generation_v1"


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


def _rhythm_date(value: object, *, code: str = "study_rhythm_invalid_date") -> str:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(code) from None
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(code)
    return value


def _rhythm_timezone(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("study_rhythm_invalid_timezone")
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        ZoneInfo(value)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError("study_rhythm_invalid_timezone") from None
    # IANA names are required. ZoneInfo accepts a few aliases/posix names;
    # reject the explicitly unsupported abbreviation/offset forms here.
    if value != "UTC" and "/" not in value:
        raise ValueError("study_rhythm_invalid_timezone")
    return value


def _rhythm_settings_row(connection: sqlite3.Connection, *, project_id: str,
                         plan_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM rhythm_settings WHERE project_id=? AND plan_id=?", (project_id, plan_id)
    ).fetchone()


def _rhythm_plan_for_write(connection: sqlite3.Connection, *, project_id: str,
                           plan_id: str) -> sqlite3.Row:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_rhythm_plan_not_found")
    if row["status"] in {"completed", "archived"}:
        raise ValueError("study_rhythm_edit_not_allowed")
    return row


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
    goal_id = f"{STUDY_GOAL_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)",
                           (project_id, "Default project", now))
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
    module_id = f"{STUDY_MODULE_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)",
                           (project_id, "Default project", now))
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
        "WHERE i.plan_id=? AND l.project_id=? "
        "UNION "
        "SELECT l.* FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
        "WHERE i.plan_id=? AND l.project_id=? ORDER BY created_at,id",
        (plan_id, project_id, plan_id, project_id),
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
        "SELECT COUNT(*) FROM ("
        "SELECT l.id,l.status FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
        "WHERE i.plan_id=? AND l.project_id=? "
        "UNION "
        "SELECT l.id,l.status FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
        "WHERE i.plan_id=? AND l.project_id=?"
        ") WHERE status != 'valid'",
        (plan_id, project_id, plan_id, project_id),
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
        if target == "active" and row["status"] == "draft":
            raise ValueError("study_plan_confirm_required")
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


def _study_source_status(connection: sqlite3.Connection, *, project_id: str | None = None,
                         material_id: str | None, revision_id: str | None,
                         extraction_id: str | None, chunk_id: str | None, span_id: str | None,
                         citation_key: str | None, strict: bool = True) -> str:
    if not material_id or not revision_id or not chunk_id:
        if strict:
            raise ValueError("study_source_invalid")
        return "stale"
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None:
        return "source_unavailable"
    if project_id is not None and material["project_id"] != project_id:
        return "stale"
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
        if strict:
            raise ValueError("study_source_invalid")
        return "stale"
    if citation_key is not None:
        validation = validate_citation_key(connection, citation_key)
        if validation is None or validation.get("chunk_id") != chunk_id:
            if strict:
                raise ValueError("study_source_invalid")
            return "stale"
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
    status = _study_source_status(connection, project_id=project_id, material_id=material_id,
                                  revision_id=revision_id, extraction_id=extraction_id,
                                  chunk_id=chunk_id, span_id=span_id, citation_key=citation_key)
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


def _refresh_note_source_links_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    rows = connection.execute(
        "SELECT id,project_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key "
        "FROM note_block_source_links WHERE material_id=?", (material_id,)
    ).fetchall()
    for row in rows:
        material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
        status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(
            connection, project_id=row["project_id"], material_id=row["material_id"], revision_id=row["revision_id"],
            extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"],
            citation_key=row["citation_key"], strict=False)
        connection.execute("UPDATE note_block_source_links SET status=?,updated_at=? WHERE id=?", (status, utc_now(), row["id"]))


def _refresh_study_source_links_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    _refresh_note_source_links_for_material(connection, material_id)
    for table, owner in (("module_source_links", "module_id"), ("plan_item_source_links", "plan_item_id")):
        rows = connection.execute(
            f"SELECT id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key FROM {table} WHERE material_id=?", (material_id,)
        ).fetchall()
        for row in rows:
            material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
            status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(connection, project_id=material["project_id"], material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
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
                material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (row["material_id"],)).fetchone()
                status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(connection, project_id=project_id, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
                changed += connection.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE id=? AND status!=?", (status, utc_now(), row["id"], status)).rowcount
    return changed


def get_study_source_links(connection: sqlite3.Connection, *, project_id: str, plan_id: str | None = None,
                           module_id: str | None = None, item_id: str | None = None) -> list[dict[str, object]]:
    if module_id is not None:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM module_source_links WHERE project_id=? AND module_id=? ORDER BY created_at,id",
            (project_id, module_id),
        ).fetchall()]
    if item_id is not None:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM plan_item_source_links WHERE project_id=? AND plan_item_id=? ORDER BY created_at,id",
            (project_id, item_id),
        ).fetchall()]
    if plan_id is not None:
        query = (
            "SELECT l.* FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
            "WHERE i.plan_id=? AND l.project_id=? UNION "
            "SELECT l.* FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
            "WHERE i.plan_id=? AND l.project_id=? ORDER BY created_at,id"
        )
        params = (plan_id, project_id, plan_id, project_id)
    else:
        query = "SELECT * FROM plan_item_source_links WHERE project_id=? UNION SELECT * FROM module_source_links WHERE project_id=? ORDER BY created_at,id"
        params = (project_id, project_id)
    return [dict(row) for row in connection.execute(query, params).fetchall()]


# Phase 9B domain transactions. These functions deliberately return safe dictionaries and
# raise stable ValueError codes; callers own HTTP mapping and project injection.
def get_rhythm_settings(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object] | None:
    row = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    return dict(row) if row is not None else None


def save_rhythm_settings(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                         cadence: object, timezone_name: object, period_start: object,
                         target_minutes: object) -> dict[str, object]:
    if cadence not in RHYTHM_CADENCES:
        raise ValueError("study_rhythm_invalid_cadence")
    timezone_value = _rhythm_timezone(timezone_name)
    period_value = _rhythm_date(period_start)
    if (not isinstance(target_minutes, int) or isinstance(target_minutes, bool) or
            not 0 <= target_minutes <= RHYTHM_MAX_TARGET_MINUTES):
        raise ValueError("study_rhythm_target_out_of_range")
    now = utc_now()
    rhythm_id = f"rhythm_{uuid.uuid4().hex}"
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        existing = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if existing is None:
            connection.execute(
                "INSERT INTO rhythm_settings (id,project_id,plan_id,cadence,timezone,period_start,target_minutes,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rhythm_id, project_id, plan_id, cadence, timezone_value, period_value, target_minutes, now, now),
            )
        else:
            _rhythm_validate_settings_allocation_limits(
                connection,
                settings={"project_id": project_id, "plan_id": plan_id, "cadence": cadence,
                          "timezone": timezone_value, "period_start": period_value},
            )
            connection.execute(
                "UPDATE rhythm_settings SET cadence=?,timezone=?,period_start=?,target_minutes=?,updated_at=? "
                "WHERE id=? AND project_id=? AND plan_id=?",
                (cadence, timezone_value, period_value, target_minutes, now, existing["id"], project_id, plan_id),
            )
    result = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    if result is None:
        raise ValueError("study_rhythm_persist_failed")
    return dict(result)


create_rhythm_settings = save_rhythm_settings
update_rhythm_settings = save_rhythm_settings


def _rhythm_allocation_row(connection: sqlite3.Connection, *, project_id: str,
                           plan_id: str, allocation_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM rhythm_allocations WHERE id=? AND project_id=? AND plan_id=?",
        (allocation_id, project_id, plan_id),
    ).fetchone()


def list_rhythm_allocations(connection: sqlite3.Connection, *, project_id: str,
                            plan_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM rhythm_allocations WHERE project_id=? AND plan_id=? ORDER BY local_date,item_id,id",
        (project_id, plan_id),
    ).fetchall()]


def _rhythm_period_index(settings: sqlite3.Row | dict[str, object], local_date: str) -> int:
    delta = (date.fromisoformat(local_date) - date.fromisoformat(str(settings["period_start"]))).days
    return delta if settings["cadence"] == "daily" else delta // 7


def _rhythm_period_dates(settings: sqlite3.Row | dict[str, object], period_index: int) -> tuple[str, str]:
    start = date.fromisoformat(str(settings["period_start"]))
    first = start + timedelta(days=period_index if settings["cadence"] == "daily" else period_index * 7)
    last = first + timedelta(days=0 if settings["cadence"] == "daily" else 6)
    return first.isoformat(), last.isoformat()


def _rhythm_validate_allocation_limits(connection: sqlite3.Connection, *, settings: sqlite3.Row,
                                       item_id: str, local_date: str, planned_minutes: int,
                                       allocation_id: str | None = None) -> None:
    excluded = " AND id != ?" if allocation_id else ""
    item_params: list[object] = [item_id]
    if allocation_id:
        item_params.append(allocation_id)
    item_total = int(connection.execute(
        "SELECT COALESCE(SUM(planned_minutes),0) FROM rhythm_allocations WHERE item_id=?" + excluded,
        item_params,
    ).fetchone()[0])
    if item_total + planned_minutes > RHYTHM_MAX_ITEM_MINUTES:
        raise ValueError("study_rhythm_allocation_limit_exceeded")
    period_index = _rhythm_period_index(settings, local_date)
    period_start, period_end = _rhythm_period_dates(settings, period_index)
    period_params: list[object] = [settings["plan_id"], period_start, period_end]
    if allocation_id:
        period_params.append(allocation_id)
        exclusion = " AND id != ?"
    else:
        exclusion = ""
    period_total = int(connection.execute(
        "SELECT COALESCE(SUM(planned_minutes),0) FROM rhythm_allocations "
        "WHERE plan_id=? AND local_date BETWEEN ? AND ?" + exclusion, period_params,
    ).fetchone()[0])
    if period_total + planned_minutes > RHYTHM_MAX_PERIOD_MINUTES:
        raise ValueError("study_rhythm_allocation_limit_exceeded")


def _rhythm_validate_settings_allocation_limits(connection: sqlite3.Connection, *,
                                                 settings: dict[str, object]) -> None:
    """Reject a settings edit that would make preserved allocations overload a period.

    Settings edits intentionally do not rewrite allocations.  They still must not
    turn valid existing rows into a rhythm that violates the per-period ceiling.
    """
    totals: dict[int, int] = {}
    for row in connection.execute(
        "SELECT local_date,planned_minutes FROM rhythm_allocations WHERE project_id=? AND plan_id=?",
        (settings["project_id"], settings["plan_id"]),
    ).fetchall():
        index = _rhythm_period_index(settings, str(row["local_date"]))
        totals[index] = totals.get(index, 0) + int(row["planned_minutes"])
    if any(total > RHYTHM_MAX_PERIOD_MINUTES for total in totals.values()):
        raise ValueError("study_rhythm_allocation_limit_exceeded")


def create_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             item_id: str, local_date: object, planned_minutes: object) -> dict[str, object]:
    local_date_value = _rhythm_date(local_date)
    if (not isinstance(planned_minutes, int) or isinstance(planned_minutes, bool) or
            not 1 <= planned_minutes <= RHYTHM_MAX_ALLOCATION_MINUTES):
        raise ValueError("study_rhythm_invalid_payload")
    with connection:
        plan = _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if settings is None:
            raise ValueError("study_rhythm_not_configured")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if item is None:
            raise ValueError("study_rhythm_item_not_found")
        if item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        _rhythm_validate_allocation_limits(connection, settings=settings, item_id=item_id,
                                           local_date=local_date_value, planned_minutes=planned_minutes)
        allocation_id = f"rhythm_allocation_{uuid.uuid4().hex}"
        now = utc_now()
        try:
            connection.execute(
                "INSERT INTO rhythm_allocations (id,project_id,plan_id,item_id,local_date,planned_minutes,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (allocation_id, project_id, plan_id, item_id, local_date_value, planned_minutes, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_rhythm_allocation_duplicate") from exc
    return dict(_rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id))


def update_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             allocation_id: str, local_date: object | None = None,
                             planned_minutes: object | None = None) -> dict[str, object]:
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        row = _rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id)
        if row is None:
            raise ValueError("study_rhythm_allocation_not_found")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=str(row["item_id"]))
        if item is None or item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        next_date = str(row["local_date"]) if local_date is None else _rhythm_date(local_date)
        next_minutes = int(row["planned_minutes"]) if planned_minutes is None else planned_minutes
        if (not isinstance(next_minutes, int) or isinstance(next_minutes, bool) or
                not 1 <= next_minutes <= RHYTHM_MAX_ALLOCATION_MINUTES):
            raise ValueError("study_rhythm_invalid_payload")
        settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if settings is None:
            raise ValueError("study_rhythm_not_configured")
        _rhythm_validate_allocation_limits(connection, settings=settings, item_id=str(row["item_id"]),
                                           local_date=next_date, planned_minutes=next_minutes,
                                           allocation_id=allocation_id)
        try:
            connection.execute(
                "UPDATE rhythm_allocations SET local_date=?,planned_minutes=?,updated_at=? WHERE id=? AND project_id=?",
                (next_date, next_minutes, utc_now(), allocation_id, project_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_rhythm_allocation_duplicate") from exc
    return dict(_rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id))


def delete_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             allocation_id: str) -> bool:
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        row = _rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id)
        if row is None:
            raise ValueError("study_rhythm_allocation_not_found")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=str(row["item_id"]))
        if item is None or item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        connection.execute("DELETE FROM rhythm_allocations WHERE id=? AND project_id=?", (allocation_id, project_id))
    return True


def rhythm_summary(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                   local_date: object | None = None, periods: int = 1) -> dict[str, object]:
    # Validate an explicit business coordinate even if the plan has not yet
    # configured a rhythm, so read paths have the same strict date contract.
    requested_local_date = None if local_date is None else _rhythm_date(local_date)
    plan = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if plan is None:
        raise ValueError("study_rhythm_plan_not_found")
    settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    if settings is None:
        progress = study_progress_summary(connection, plan_id=plan_id, project_id=project_id)
        return {"settings": None, "buckets": [], "allocated_item_count": 0,
                "unassigned_item_count": progress["item_count"], "archived_item_count": progress["archived_count"],
                "item_projection": {key: progress[key] for key in ("pending_count", "in_progress_count", "completed_count", "skipped_count")},
                "source_warning_count": progress["source_warning_count"], "last_progress_event_at": progress["last_event_at"]}
    if not isinstance(periods, int) or isinstance(periods, bool) or not 1 <= periods <= 52:
        raise ValueError("study_rhythm_invalid_payload")
    if requested_local_date is None:
        from zoneinfo import ZoneInfo
        local_date_value = datetime.now(timezone.utc).astimezone(ZoneInfo(str(settings["timezone"]))).date().isoformat()
    else:
        local_date_value = requested_local_date
    current_index = _rhythm_period_index(settings, local_date_value)
    allocations = [dict(row) for row in connection.execute(
        "SELECT * FROM rhythm_allocations WHERE project_id=? AND plan_id=? ORDER BY local_date,item_id,id",
        (project_id, plan_id),
    ).fetchall()]
    item_rows = connection.execute(
        "SELECT i.id,i.status FROM study_plan_items i WHERE i.plan_id=? AND i.project_id=?", (plan_id, project_id)
    ).fetchall()
    item_statuses = {str(row["id"]): str(row["status"]) for row in item_rows}
    buckets: list[dict[str, object]] = []
    for index in range(current_index, current_index + periods):
        start, end = _rhythm_period_dates(settings, index)
        selected = [row for row in allocations if start <= str(row["local_date"]) <= end]
        active_selected = [row for row in selected if item_statuses.get(str(row["item_id"])) != "archived"]
        planned = sum(int(row["planned_minutes"]) for row in active_selected)
        buckets.append({"period_index": index, "local_date_start": start, "local_date_end": end,
                        "planned_minutes": planned, "target_minutes": int(settings["target_minutes"]),
                        "remaining_target_minutes": max(int(settings["target_minutes"]) - planned, 0),
                        "allocated_item_count": len({str(row["item_id"]) for row in active_selected})})
    allocated_ids = {str(row["item_id"]) for row in allocations if item_statuses.get(str(row["item_id"])) != "archived"}
    unassigned = sum(1 for row in item_rows if row["status"] != "archived" and str(row["id"]) not in allocated_ids)
    progress = study_progress_summary(connection, plan_id=plan_id, project_id=project_id)
    return {"settings": dict(settings), "buckets": buckets,
            "allocated_item_count": len(allocated_ids),
            "unassigned_item_count": unassigned,
            "archived_item_count": sum(1 for row in item_rows if row["status"] == "archived"),
            "item_projection": {key: progress[key] for key in ("pending_count", "in_progress_count", "completed_count", "skipped_count")},
            "source_warning_count": progress["source_warning_count"], "last_progress_event_at": progress["last_event_at"]}


def _note_row(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM notes WHERE id=? AND project_id=?", (note_id, project_id)).fetchone()


def _note_blocks(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT * FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["sources"] = [dict(source) for source in connection.execute(
            "SELECT * FROM note_block_source_links WHERE note_block_id=? AND project_id=? ORDER BY created_at,id",
            (row["id"], project_id),
        ).fetchall()]
        result.append(item)
    return result


def _note_public(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    row = _note_row(connection, project_id=project_id, note_id=note_id)
    if row is None:
        raise ValueError("study_note_not_found")
    result = dict(row)
    result["blocks"] = _note_blocks(connection, project_id=project_id, note_id=note_id)
    result["modules"] = [dict(module) for module in connection.execute(
        "SELECT m.* FROM knowledge_modules m JOIN note_module_links l ON l.module_id=m.id "
        "WHERE l.note_id=? AND l.project_id=? ORDER BY m.id", (note_id, project_id)
    ).fetchall()]
    result["source_warning_count"] = sum(1 for block in result["blocks"] for source in block["sources"] if source["status"] != "valid")
    result["archived_module_warning_count"] = sum(1 for module in result["modules"] if module["status"] == "archived")
    return result


def _note_block_values(payload: object, *, code: str = "study_note_block_invalid") -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError(code)
    kind = payload.get("block_kind", "text")
    if kind not in NOTE_BLOCK_KINDS:
        raise ValueError(code)
    content = _study_text(payload.get("content"), code=code, maximum=NOTE_MAX_BLOCK_CONTENT)
    provenance = payload.get("provenance", "user_created")
    if provenance not in NOTE_PROVENANCES:
        raise ValueError(code)
    return str(kind), content, str(provenance)


def _note_validate_blocks(payloads: object) -> list[tuple[str, str, str]]:
    if not isinstance(payloads, list) or not payloads:
        raise ValueError("study_note_empty")
    values = [_note_block_values(payload) for payload in payloads]
    if sum(len(value[1]) for value in values) > NOTE_MAX_CONTENT:
        raise ValueError("study_note_block_invalid")
    return values


def create_note(connection: sqlite3.Connection, *, project_id: str, title: object,
                blocks: object, provenance: str = "user_created",
                generation_operation_id: str | None = None) -> dict[str, object]:
    title_value = _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
    if provenance not in NOTE_PROVENANCES or (provenance == "user_created") != (generation_operation_id is None):
        raise ValueError("study_note_invalid_payload")
    values = _note_validate_blocks(blocks)
    expected_block_provenance = "ai_generated" if provenance == "ai_generated" else "user_created"
    if any(block_provenance != expected_block_provenance for _, _, block_provenance in values):
        raise ValueError("study_note_block_invalid")
    note_id = f"note_{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("study_note_invalid_payload")
        if provenance == "ai_generated" and connection.execute(
                "SELECT 1 FROM ai_operations WHERE id=? AND project_id=? AND operation_type='generate_note'",
                (generation_operation_id, project_id)).fetchone() is None:
            raise ValueError("study_note_invalid_payload")
        connection.execute(
            "INSERT INTO notes (id,project_id,title,status,provenance,user_edited,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
            "VALUES (?,?,?,?,?,0,?,?,?,NULL,NULL)",
            (note_id, project_id, title_value, "draft", provenance, generation_operation_id, now, now),
        )
        connection.executemany(
            "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, block_provenance, now, now)
             for position, (kind, content, block_provenance) in enumerate(values)],
        )
    return _note_public(connection, project_id=project_id, note_id=note_id)


def create_user_note(connection: sqlite3.Connection, *, project_id: str, title: object,
                     blocks: object) -> dict[str, object]:
    return create_note(connection, project_id=project_id, title=title, blocks=blocks)


def list_notes(connection: sqlite3.Connection, *, project_id: str,
               include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id=?" if include_archived else "project_id=? AND status!='archived'"
    return [_note_public(connection, project_id=project_id, note_id=str(row["id"])) for row in connection.execute(
        "SELECT id FROM notes WHERE " + where + " ORDER BY updated_at DESC,id DESC", (project_id,)
    ).fetchall()]


def get_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object] | None:
    return _note_public(connection, project_id=project_id, note_id=note_id) if _note_row(connection, project_id=project_id, note_id=note_id) else None


def update_note(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                title: object | None = None) -> dict[str, object]:
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        title_value = str(row["title"]) if title is None else _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
        connection.execute("UPDATE notes SET title=?,user_edited=1,updated_at=? WHERE id=? AND project_id=?", (title_value, utc_now(), note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)


def update_note_content(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                        title: object | None = None, blocks: object | None = None) -> dict[str, object]:
    """Atomically patch note title and ordered blocks when both are supplied."""
    if title is None and blocks is None:
        raise ValueError("study_note_invalid_payload")
    values = _note_validate_blocks(blocks) if blocks is not None else None
    title_value = None if title is None else _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        now = utc_now()
        if values is not None:
            expected_provenance = "ai_generated" if row["provenance"] == "ai_generated" else "user_created"
            existing = connection.execute(
                "SELECT id FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)
            ).fetchall()
            common = min(len(existing), len(values))
            for position in range(common):
                kind, content, _ = values[position]
                connection.execute(
                    "UPDATE note_blocks SET position=?,block_kind=?,content=?,provenance=?,updated_at=? WHERE id=? AND note_id=?",
                    (position, kind, content, expected_provenance, now, existing[position]["id"], note_id),
                )
            for old in existing[common:]:
                connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (old["id"], note_id))
            for position, (kind, content, block_provenance) in enumerate(values[common:], start=common):
                connection.execute(
                    "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, expected_provenance, now, now),
                )
        connection.execute(
            "UPDATE notes SET title=COALESCE(?,title),user_edited=1,updated_at=? WHERE id=? AND project_id=?",
            (title_value, now, note_id, project_id),
        )
    return _note_public(connection, project_id=project_id, note_id=note_id)


def update_note_blocks(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                       blocks: object) -> dict[str, object]:
    values = _note_validate_blocks(blocks)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_block_edit_not_allowed")
        expected_provenance = "ai_generated" if row["provenance"] == "ai_generated" else "user_created"
        now = utc_now()
        existing = connection.execute(
            "SELECT id,position FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)
        ).fetchall()
        common = min(len(existing), len(values))
        for position in range(common):
            kind, content, _ = values[position]
            connection.execute(
                "UPDATE note_blocks SET position=?,block_kind=?,content=?,provenance=?,updated_at=? WHERE id=? AND note_id=?",
                (position, kind, content, expected_provenance, now, existing[position]["id"], note_id),
            )
        for old in existing[common:]:
            connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (old["id"], note_id))
        for position, (kind, content, block_provenance) in enumerate(values[common:], start=common):
            connection.execute(
                "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, block_provenance, now, now),
            )
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=? AND project_id=?", (now, note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)


def _note_editable_block(connection: sqlite3.Connection, *, project_id: str, note_id: str, block_id: str) -> sqlite3.Row:
    note = _note_row(connection, project_id=project_id, note_id=note_id)
    if note is None:
        raise ValueError("study_note_not_found")
    if note["status"] != "draft":
        raise ValueError("study_note_block_edit_not_allowed")
    block = connection.execute("SELECT * FROM note_blocks WHERE id=? AND note_id=? AND project_id=?", (block_id, note_id, project_id)).fetchone()
    if block is None:
        raise ValueError("study_note_block_not_found")
    return block


def create_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                      block_kind: object, content: object) -> dict[str, object]:
    kind, body, _ = _note_block_values({"block_kind": block_kind, "content": content})
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_block_edit_not_allowed")
        total = int(connection.execute("SELECT COALESCE(SUM(length(content)),0) FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0])
        if total + len(body) > NOTE_MAX_CONTENT:
            raise ValueError("study_note_block_invalid")
        position = int(connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0])
        block_id = f"note_block_{uuid.uuid4().hex}"; now = utc_now()
        connection.execute("INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (block_id,note_id,project_id,position,kind,body,str(note["provenance"]),now,now))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_blocks WHERE id=?", (block_id,)).fetchone())


def update_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                      block_id: str, block_kind: object | None = None, content: object | None = None) -> dict[str, object]:
    with connection:
        block = _note_editable_block(connection, project_id=project_id, note_id=note_id, block_id=block_id)
        kind, body, _ = _note_block_values({"block_kind": block["block_kind"] if block_kind is None else block_kind,
                                             "content": block["content"] if content is None else content})
        total = int(connection.execute("SELECT COALESCE(SUM(length(content)),0) FROM note_blocks WHERE note_id=? AND id!=?", (note_id,block_id)).fetchone()[0])
        if total + len(body) > NOTE_MAX_CONTENT:
            raise ValueError("study_note_block_invalid")
        now = utc_now()
        connection.execute("UPDATE note_blocks SET block_kind=?,content=?,updated_at=? WHERE id=?", (kind,body,now,block_id))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_blocks WHERE id=?", (block_id,)).fetchone())


def delete_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str, block_id: str) -> bool:
    with connection:
        block = _note_editable_block(connection, project_id=project_id, note_id=note_id, block_id=block_id)
        if int(connection.execute("SELECT COUNT(*) FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0]) <= 1:
            raise ValueError("study_note_empty")
        deleted_position = int(block["position"])
        connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (block_id,note_id))
        connection.execute("UPDATE note_blocks SET position=position-1 WHERE note_id=? AND position>?", (note_id,deleted_position))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True


def link_note_module(connection: sqlite3.Connection, *, project_id: str, note_id: str, module_id: str) -> dict[str, object]:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        module = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        if module is None:
            raise ValueError("study_note_module_invalid")
        if module["status"] != "active":
            raise ValueError("study_note_module_archived")
        link_id = f"note_module_{uuid.uuid4().hex}"
        try:
            connection.execute("INSERT INTO note_module_links (id,project_id,note_id,module_id) VALUES (?,?,?,?)", (link_id,project_id,note_id,module_id))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_note_module_link_duplicate") from exc
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return dict(connection.execute("SELECT * FROM note_module_links WHERE id=?", (link_id,)).fetchone())


def unlink_note_module(connection: sqlite3.Connection, *, project_id: str, note_id: str, module_id: str) -> bool:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        cursor = connection.execute("DELETE FROM note_module_links WHERE project_id=? AND note_id=? AND module_id=?", (project_id,note_id,module_id))
        if cursor.rowcount != 1:
            raise ValueError("study_note_module_invalid")
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True


def _note_source_values(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                        block_id: str, payload: dict[str, object],
                        context_chunk_ids: object) -> tuple[str, ...]:
    required = ("material_id", "revision_id", "extraction_id", "chunk_id", "citation_key")
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not str(payload[key]).strip() for key in required):
        raise ValueError("study_note_source_invalid")
    material_id, revision_id = str(payload["material_id"]), str(payload["revision_id"])
    extraction_id, chunk_id, citation_key = str(payload["extraction_id"]), str(payload["chunk_id"]), str(payload["citation_key"])
    if (not isinstance(context_chunk_ids, list) or not context_chunk_ids or len(context_chunk_ids) > MAX_RETRIEVAL_TOP_K or
            any(not isinstance(chunk, str) or not chunk for chunk in context_chunk_ids)):
        raise ValueError("study_note_source_invalid")
    context = assemble_context(connection, project_id=project_id,
                               hits=[{"chunk_id": chunk, "rank": index + 1}
                                     for index, chunk in enumerate(context_chunk_ids)])
    context_source = next((block for block in context["context_blocks"]
                           if block.get("citation_key") == citation_key), None)
    source_info = context_source.get("source_info") if isinstance(context_source, dict) else None
    if (not isinstance(source_info, dict) or source_info.get("material_id") != material_id or
            source_info.get("revision_id") != revision_id or chunk_id not in context_chunk_ids):
        raise ValueError("study_note_source_invalid")
    span_id = payload.get("span_id")
    if span_id is not None and (not isinstance(span_id, str) or len(span_id) > 200):
        raise ValueError("study_note_source_invalid")
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None or material["project_id"] != project_id:
        raise ValueError("study_note_source_invalid")
    if material["deleted_at"] is not None:
        raise ValueError("study_note_source_deleted")
    chunk = connection.execute("SELECT revision_id,extraction_id,status FROM chunks WHERE id=? AND material_id=?", (chunk_id,material_id)).fetchone()
    validation = validate_citation_key(connection, citation_key)
    if (chunk is None or chunk["revision_id"] != revision_id or chunk["extraction_id"] != extraction_id or
            chunk["status"] != "ready" or validation is None or validation.get("status") != "valid" or
            validation.get("material_id") != material_id or validation.get("chunk_id") != chunk_id or
            validation.get("revision_id") != revision_id):
        raise ValueError("study_note_source_invalid")
    if span_id is not None and connection.execute("SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id,span_id)).fetchone() is None:
        raise ValueError("study_note_source_invalid")
    return material_id, revision_id, extraction_id, chunk_id, span_id, citation_key


def create_note_source_link(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                            block_id: str, payload: dict[str, object],
                            context_chunk_ids: object) -> dict[str, object]:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_source_invalid")
        if connection.execute("SELECT 1 FROM note_blocks WHERE id=? AND note_id=? AND project_id=?", (block_id,note_id,project_id)).fetchone() is None:
            raise ValueError("study_note_block_not_found")
        values = _note_source_values(connection, project_id=project_id, note_id=note_id, block_id=block_id,
                                     payload=payload, context_chunk_ids=context_chunk_ids)
        link_id = f"note_source_{uuid.uuid4().hex}"; now = utc_now()
        try:
            connection.execute("INSERT INTO note_block_source_links (id,project_id,note_id,note_block_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (link_id,project_id,note_id,block_id,*values,"valid",now,now))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_note_source_invalid") from exc
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_block_source_links WHERE id=?", (link_id,)).fetchone())


def delete_note_source_link(connection: sqlite3.Connection, *, project_id: str, note_id: str, link_id: str) -> bool:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_source_invalid")
        cursor = connection.execute("DELETE FROM note_block_source_links WHERE id=? AND note_id=? AND project_id=?", (link_id,note_id,project_id))
        if cursor.rowcount != 1:
            raise ValueError("study_note_source_not_found")
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True


def confirm_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_invalid_state")
        blocks = connection.execute("SELECT id FROM note_blocks WHERE note_id=? AND project_id=?", (note_id,project_id)).fetchall()
        if not blocks:
            raise ValueError("study_note_empty")
        # Recompute link status inside the confirm transaction; persisted status is not trusted.
        _refresh_note_source_links(connection, project_id=project_id, note_id=note_id)
        if row["provenance"] == "ai_generated":
            missing = connection.execute("SELECT 1 FROM note_blocks b WHERE b.note_id=? AND NOT EXISTS (SELECT 1 FROM note_block_source_links l WHERE l.note_block_id=b.id AND l.status='valid')", (note_id,)).fetchone()
            if missing is not None:
                raise ValueError("study_note_confirm_source_invalid")
        now = utc_now()
        connection.execute("UPDATE notes SET status='confirmed',confirmed_at=?,updated_at=? WHERE id=? AND project_id=?", (now,now,note_id,project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)


def transition_note(connection: sqlite3.Connection, *, project_id: str, note_id: str, target: str) -> dict[str, object]:
    if target == "confirmed":
        return confirm_note(connection, project_id=project_id, note_id=note_id)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        allowed = {"rejected": {"draft"}, "archived": {"draft", "confirmed", "rejected"}}
        if target not in allowed or row["status"] not in allowed[target]:
            raise ValueError("study_note_invalid_state")
        now = utc_now()
        connection.execute("UPDATE notes SET status=?,archived_at=?,updated_at=? WHERE id=? AND project_id=?", (target, now if target == "archived" else None, now, note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)


def _refresh_note_source_links(connection: sqlite3.Connection, *, project_id: str,
                               note_id: str | None = None, material_id: str | None = None) -> int:
    where = ["project_id=?"]; params: list[object] = [project_id]
    if note_id is not None:
        where.append("note_id=?"); params.append(note_id)
    if material_id is not None:
        where.append("material_id=?"); params.append(material_id)
    rows = connection.execute("SELECT * FROM note_block_source_links WHERE " + " AND ".join(where), params).fetchall()
    changed = 0
    for row in rows:
        material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (row["material_id"],)).fetchone()
        if material is None:
            status = "source_unavailable"
        elif material["deleted_at"] is not None:
            status = "source_deleted"
        else:
            status = _study_source_status(connection, project_id=project_id, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
        changed += connection.execute("UPDATE note_block_source_links SET status=?,updated_at=? WHERE id=? AND status!=?", (status,utc_now(),row["id"],status)).rowcount
    return changed


def refresh_note_source_links(connection: sqlite3.Connection, *, project_id: str, note_id: str | None = None,
                              material_id: str | None = None) -> int:
    with connection:
        return _refresh_note_source_links(connection, project_id=project_id, note_id=note_id, material_id=material_id)


def archive_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    return transition_note(connection, project_id=project_id, note_id=note_id, target="archived")


def _note_generation_fingerprint(*, topic: str, material_id: str, source_revision: str | None,
                                 retrieval_mode: str, allow_fallback: bool) -> str:
    payload = "\x1f".join(("generate_note", topic.strip(), material_id, source_revision or "",
                            retrieval_mode, str(int(allow_fallback))))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _note_generation_public(connection: sqlite3.Connection, operation: sqlite3.Row) -> dict[str, object] | None:
    if operation["status"] != "succeeded" or not operation["output_artifact_id"]:
        return None
    note = get_note(connection, project_id=str(operation["project_id"]), note_id=str(operation["output_artifact_id"]))
    if note is None:
        return None
    return {"status": "succeeded", "operation_id": operation["id"],
            "retrieval_run_id": operation["retrieval_run_id"], "note": note}


def create_note_generation_operation(connection: sqlite3.Connection, *, project_id: str, topic: object,
                                     material_id: object, source_revision: object | None = None,
                                     retrieval_mode: object = "lexical", allow_fallback: object = True,
                                     request_id: str | None = None, idempotency_key: str | None = None) -> dict[str, object]:
    if (not isinstance(topic, str) or not topic.strip() or len(topic.strip()) > MAX_GENERATION_TOPIC_LENGTH or
            not isinstance(material_id, str) or not material_id or retrieval_mode not in {"lexical", "vector", "hybrid"} or
            not isinstance(allow_fallback, bool) or (idempotency_key is not None and
            (not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 200 or
             any(ord(char) < 32 for char in idempotency_key)))):
        raise ValueError("study_note_generation_invalid_request")
    source = connection.execute(
        "SELECT m.id,m.deleted_at,r.id AS revision_id FROM materials m "
        "LEFT JOIN material_revisions r ON r.material_id=m.id AND r.is_current=1 "
        "WHERE m.id=? AND m.project_id=?", (material_id, project_id),
    ).fetchone()
    if source is None:
        raise ValueError("study_note_generation_invalid_request")
    if source["deleted_at"] is not None:
        raise ValueError("study_note_source_deleted")
    current_revision = str(source["revision_id"]) if source["revision_id"] is not None else None
    if source_revision is not None and (not isinstance(source_revision, str) or source_revision != current_revision):
        raise ValueError("study_note_generation_stale_source")
    fingerprint = _note_generation_fingerprint(topic=topic, material_id=material_id, source_revision=current_revision,
                                                retrieval_mode=str(retrieval_mode), allow_fallback=allow_fallback)
    with connection:
        if idempotency_key:
            existing = connection.execute(
                "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, idempotency_key)
            ).fetchone()
            if existing is not None:
                if existing["operation_type"] != "generate_note" or existing["input_fingerprint"] != fingerprint:
                    raise ValueError("study_note_generation_idempotency_mismatch")
                if existing["status"] == "running":
                    raise ValueError("study_note_generation_in_progress")
                replay = _note_generation_public(connection, existing)
                if replay is not None:
                    return {**replay, "replay": True}
                connection.execute("UPDATE ai_operations SET idempotency_key=NULL WHERE id=?", (existing["id"],))
        operation_id, now = f"operation_{uuid.uuid4().hex}", utc_now()
        policy = {"lexical": RETRIEVAL_POLICY_VERSION, "vector": VECTOR_POLICY_VERSION,
                  "hybrid": HYBRID_POLICY_VERSION}[str(retrieval_mode)]
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
            "retrieval_policy_version,prompt_version,request_id,retry_count,created_at,started_at,idempotency_key) "
            "VALUES (?,'generate_note','running',?,?,?,?,?,?,?,0,?,?,?)",
            (operation_id, project_id, material_id, fingerprint, current_revision, policy,
             NOTE_GENERATION_PROMPT_VERSION, request_id, now, now, idempotency_key),
        )
    return {"operation_id": operation_id, "source_revision": current_revision, "replay": False}


def fail_note_generation_operation(connection: sqlite3.Connection, *, operation_id: str,
                                   error_code: str) -> None:
    with connection:
        connection.execute(
            "UPDATE ai_operations SET status='failed',error_code=?,finished_at=? "
            "WHERE id=? AND operation_type='generate_note' AND status='running'",
            (error_code, utc_now(), operation_id),
        )


def _generated_note_payload(raw: object) -> tuple[str, list[tuple[str, str, list[str]]]]:
    if not isinstance(raw, str) or len(raw) > NOTE_MAX_CONTENT + 12000:
        raise ValueError("study_note_generation_schema_invalid")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("study_note_generation_schema_invalid") from None
    if not isinstance(payload, dict) or set(payload) != {"title", "blocks"}:
        raise ValueError("study_note_generation_schema_invalid")
    title = _study_text(payload.get("title"), code="study_note_generation_schema_invalid", maximum=NOTE_MAX_TITLE)
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("study_note_generation_schema_invalid")
    result: list[tuple[str, str, list[str]]] = []
    total = 0
    for block in blocks:
        if not isinstance(block, dict) or set(block) != {"block_kind", "content", "citation_keys"}:
            raise ValueError("study_note_generation_schema_invalid")
        kind = block.get("block_kind")
        if kind not in NOTE_BLOCK_KINDS:
            raise ValueError("study_note_generation_schema_invalid")
        content = _study_text(block.get("content"), code="study_note_generation_schema_invalid", maximum=NOTE_MAX_BLOCK_CONTENT)
        citations = block.get("citation_keys")
        if (not isinstance(citations, list) or not citations or len(citations) > MAX_CARD_CITATIONS or
                any(not isinstance(key, str) or not key for key in citations) or len(set(citations)) != len(citations)):
            raise ValueError("study_note_generation_schema_invalid")
        total += len(content)
        result.append((str(kind), content, list(citations)))
    if total > NOTE_MAX_CONTENT:
        raise ValueError("study_note_generation_schema_invalid")
    return title, result


def persist_generated_note_draft(connection: sqlite3.Connection, *, project_id: str, operation_id: str,
                                 source_revision: str, raw_output: object, context_blocks: list[dict[str, object]],
                                 provider_id: str, model_id: str, prompt_tokens: int | None,
                                 completion_tokens: int | None, latency_ms: int, provider_request_id: str | None,
                                 total_tokens: int | None, finish_reason: str | None) -> dict[str, object]:
    operation = connection.execute(
        "SELECT status,source_revision FROM ai_operations WHERE id=? AND project_id=? AND operation_type='generate_note'",
        (operation_id, project_id),
    ).fetchone()
    if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
        raise ValueError("study_note_generation_stale_source")
    title, blocks = _generated_note_payload(raw_output)
    allowed = {str(block.get("citation_key")): block for block in context_blocks if isinstance(block, dict)}
    prepared: list[tuple[str, str, list[tuple[str, str, str, str, str | None, str]]]] = []
    for kind, content, citations in blocks:
        sources = []
        for citation_key in citations:
            context = allowed.get(citation_key)
            source_info = context.get("source_info") if isinstance(context, dict) else None
            validation = validate_citation_key(connection, citation_key)
            if (not isinstance(source_info, dict) or validation is None or validation.get("status") != "valid" or
                    source_info.get("revision_id") != source_revision or validation.get("revision_id") != source_revision):
                raise ValueError("study_note_generation_citation_invalid")
            chunk = connection.execute(
                "SELECT material_id,revision_id,extraction_id,status FROM chunks WHERE id=?", (validation["chunk_id"],)
            ).fetchone()
            if (chunk is None or chunk["status"] != "ready" or chunk["material_id"] != validation["material_id"] or
                    chunk["revision_id"] != source_revision):
                raise ValueError("study_note_generation_citation_invalid")
            span_ids = context.get("span_ids", [])
            span_id = str(span_ids[0]) if isinstance(span_ids, list) and span_ids else None
            if span_id is not None and connection.execute(
                    "SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (validation["chunk_id"], span_id)
            ).fetchone() is None:
                raise ValueError("study_note_generation_citation_invalid")
            sources.append((str(validation["material_id"]), source_revision, str(chunk["extraction_id"]),
                            str(validation["chunk_id"]), span_id, citation_key))
        prepared.append((kind, content, sources))
    note_id, now = f"note_{uuid.uuid4().hex}", utc_now()
    with connection:
        operation = connection.execute(
            "SELECT status,material_id,source_revision FROM ai_operations WHERE id=? AND project_id=? AND operation_type='generate_note'",
            (operation_id, project_id),
        ).fetchone()
        if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
            raise ValueError("study_note_generation_stale_source")
        current = connection.execute(
            "SELECT 1 FROM materials m JOIN material_revisions r ON r.material_id=m.id "
            "WHERE m.id=? AND m.project_id=? AND m.deleted_at IS NULL AND r.id=? AND r.is_current=1",
            (operation["material_id"], project_id, source_revision),
        ).fetchone()
        if current is None:
            raise ValueError("study_note_generation_stale_source")
        for _kind, _content, sources in prepared:
            for material_id, revision_id, extraction_id, chunk_id, span_id, citation_key in sources:
                validation = validate_citation_key(connection, citation_key)
                if (_study_source_status(connection, project_id=project_id, material_id=material_id,
                                         revision_id=revision_id, extraction_id=extraction_id, chunk_id=chunk_id,
                                         span_id=span_id, citation_key=citation_key, strict=False) != "valid" or
                        validation is None or validation.get("status") != "valid" or
                        validation.get("material_id") != material_id or validation.get("chunk_id") != chunk_id or
                        validation.get("revision_id") != source_revision):
                    raise ValueError("study_note_generation_citation_invalid")
        connection.execute(
            "INSERT INTO notes (id,project_id,title,status,provenance,user_edited,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
            "VALUES (?,?,?,'draft','ai_generated',0,?,?,?,NULL,NULL)",
            (note_id, project_id, title, operation_id, now, now),
        )
        for position, (kind, content, sources) in enumerate(prepared):
            block_id = f"note_block_{uuid.uuid4().hex}"
            connection.execute(
                "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,'ai_generated',?,?)",
                (block_id, note_id, project_id, position, kind, content, now, now),
            )
            connection.executemany(
                "INSERT INTO note_block_source_links (id,project_id,note_id,note_block_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,'valid',?,?)",
                [(f"note_source_{uuid.uuid4().hex}", project_id, note_id, block_id, material_id, revision_id,
                  extraction_id, chunk_id, span_id, citation_key, now, now)
                 for material_id, revision_id, extraction_id, chunk_id, span_id, citation_key in sources],
            )
        connection.execute(
            "UPDATE ai_operations SET status='succeeded',output_artifact_id=?,provider_id=?,model_id=?,provider_request_id=?,"
            "prompt_tokens=?,completion_tokens=?,total_tokens=?,latency_ms=?,finish_reason=?,finished_at=? "
            "WHERE id=? AND status='running'",
            (note_id, provider_id, model_id, provider_request_id, prompt_tokens, completion_tokens, total_tokens,
             latency_ms, finish_reason, utc_now(), operation_id),
        )
    return _note_public(connection, project_id=project_id, note_id=note_id)


def generate_note_draft(connection: sqlite3.Connection, *, project_id: str, topic: object, material_id: object,
                        provider: LLMProvider | None, source_revision: object | None = None,
                        retrieval_mode: object = "lexical", allow_fallback: object = True,
                        embedding_provider: EmbeddingProvider | None = None, request_id: str | None = None,
                        idempotency_key: str | None = None) -> dict[str, object]:
    operation = create_note_generation_operation(
        connection, project_id=project_id, topic=topic, material_id=material_id, source_revision=source_revision,
        retrieval_mode=retrieval_mode, allow_fallback=allow_fallback, request_id=request_id, idempotency_key=idempotency_key,
    )
    if operation["replay"]:
        return operation
    operation_id = str(operation["operation_id"])
    try:
        if retrieval_mode == "lexical":
            retrieval = run_chunk_retrieval(connection, project_id=project_id, query=str(topic), material_ids=[str(material_id)], top_k=5)
        elif retrieval_mode == "vector":
            if embedding_provider is None:
                raise ValueError("study_note_generation_not_ready")
            retrieval = run_vector_retrieval(connection, project_id=project_id, query=str(topic), provider=embedding_provider, material_ids=[str(material_id)], top_k=5)
        else:
            retrieval = run_hybrid_retrieval(connection, project_id=project_id, query=str(topic), provider=embedding_provider,
                                             material_ids=[str(material_id)], top_k=5, allow_fallback=bool(allow_fallback))
        with connection:
            connection.execute("UPDATE ai_operations SET retrieval_policy_version=?,retrieval_run_id=? WHERE id=? AND status='running'",
                               (retrieval["policy_version"], retrieval["run_id"], operation_id))
        if retrieval["status"] != "succeeded":
            code = "study_note_generation_not_ready" if retrieval["error_code"] == "retrieval_not_ready" else "study_note_generation_empty"
            raise ValueError(code)
        context = assemble_context(connection, project_id=project_id, hits=list(retrieval["hits"]))
        if not context["context_blocks"]:
            raise ValueError("study_note_generation_empty")
        if provider is None:
            raise ProviderError("provider_not_configured")
        if getattr(provider, "provider_id", None) != "fake":
            raise ProviderError("provider_unavailable")
        result = provider.generate_answer(ProviderRequest(
            question=str(topic), context_blocks=list(context["context_blocks"]), generation_kind="note", generation_count=1,
        ))
        note = persist_generated_note_draft(
            connection, project_id=project_id, operation_id=operation_id, source_revision=str(operation["source_revision"]),
            raw_output=result.answer_text, context_blocks=list(context["context_blocks"]), provider_id=result.provider_id,
            model_id=result.model_id, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            latency_ms=result.latency_ms or 0, provider_request_id=result.provider_request_id,
            total_tokens=result.total_tokens, finish_reason=result.finish_reason,
        )
        return {"status": "succeeded", "operation_id": operation_id, "retrieval_run_id": retrieval["run_id"],
                "note": note, "replay": False}
    except ProviderError as error:
        code = {"provider_not_configured": "study_note_provider_not_configured", "provider_timeout": "study_note_provider_timeout"}.get(
            error.code, "study_note_provider_unavailable" if error.code in {"provider_unavailable", "provider_connection_failed"} else "study_note_generation_failed")
        fail_note_generation_operation(connection, operation_id=operation_id, error_code=code)
        raise ValueError(code) from None
    except ValueError as error:
        code = str(error)
        fail_note_generation_operation(connection, operation_id=operation_id, error_code=code)
        raise
    except sqlite3.Error:
        try:
            fail_note_generation_operation(connection, operation_id=operation_id, error_code="study_note_generation_failed")
        except sqlite3.Error:
            pass
        raise ValueError("study_note_generation_failed") from None


# Explicit aliases keep the domain surface readable to later API/workflow tasks.
get_study_rhythm = get_rhythm_settings
set_study_rhythm = save_rhythm_settings
get_rhythm_summary = rhythm_summary
create_study_rhythm_allocation = create_rhythm_allocation
update_study_rhythm_allocation = update_rhythm_allocation
delete_study_rhythm_allocation = delete_rhythm_allocation


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
        _refresh_phase9c_session_sources_for_material(connection, material_id)
        connection.execute(
            "UPDATE capture_sessions SET source_status='source_unavailable',updated_at=? WHERE material_id=?",
            (utc_now(), material_id),
        )
        connection.execute(
            "UPDATE note_block_source_links SET status = 'source_unavailable', updated_at = ? WHERE material_id = ?",
            (utc_now(), material_id),
        )
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
        _refresh_phase9c_session_sources_for_material(connection, material_id)
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
            _refresh_phase9c_session_sources_for_material(connection, material_id)
            connection.execute(
                "UPDATE capture_sessions SET source_status='source_deleted',updated_at=? WHERE material_id=?",
                (deleted_at, material_id),
            )
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


def _index_material_revision_in_transaction(connection: sqlite3.Connection, material_id: str,
                                            extraction_id: str, *, chunk_size: int = 800,
                                            overlap: int = 80) -> sqlite3.Row:
    row = _revision_payload(connection, material_id, extraction_id)
    if row is None:
        raise ValueError("material_extraction_mismatch")
    if connection.execute("SELECT deleted_at FROM materials WHERE id = ?", (material_id,)).fetchone()[0] is not None:
        raise ValueError("source_deleted")
    revision = create_or_get_revision(connection, material_id, extraction_id)
    _refresh_exercise_citations_for_material(connection, material_id)
    _refresh_card_citations_for_material(connection, material_id)
    _refresh_phase9c_session_sources_for_material(connection, material_id)
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


def index_material_revision(connection: sqlite3.Connection, material_id: str,
                            extraction_id: str, *, chunk_size: int = 800,
                            overlap: int = 80) -> sqlite3.Row:
    with connection:
        return _index_material_revision_in_transaction(
            connection, material_id, extraction_id, chunk_size=chunk_size, overlap=overlap,
        )


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
