from ._legacy_runtime import *
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
                          status: str, error_code: str | None = None,
                          output_artifact_id: str | None = None) -> bool:
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
        "UPDATE ai_operations SET status=?,error_code=?,output_artifact_id=COALESCE(?,output_artifact_id),finished_at=? "
        "WHERE id=(SELECT operation_id FROM operation_tasks WHERE id=?) AND status='running'",
        (task_status, error_code, output_artifact_id, now, task_id),
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

