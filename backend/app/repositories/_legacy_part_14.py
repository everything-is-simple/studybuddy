from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
from ._legacy_part_05 import *
from ._legacy_part_06 import *
from ._legacy_part_07 import *
from ._legacy_part_08 import *
from ._legacy_part_09 import *
from ._legacy_part_10 import *
from ._legacy_part_11 import *
from ._legacy_part_12 import *
from ._legacy_part_13 import *
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

def create_task_backed_embedding_operation(connection: sqlite3.Connection, *, project_id: str,
                                          material_id: str, source_revision: str,
                                          provider_id: str, model_id: str | None,
                                          model_revision: str, idempotency_key: str | None = None,
                                          request_id: str | None = None, max_retries: int = 1) -> dict[str, object]:
    """Queue the approved embedding-only task; never persist source text in its task envelope."""
    if not project_id or not material_id or not source_revision or not provider_id or max_retries < 0:
        raise ValueError("embedding_task_invalid_request")
    material = connection.execute(
        "SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)
    ).fetchone()
    revision = connection.execute(
        "SELECT material_id,is_current FROM material_revisions WHERE id=?", (source_revision,)
    ).fetchone()
    if material is None:
        raise ValueError("material_not_found")
    if str(material["project_id"]) != project_id:
        raise ValueError("task_project_scope_violation")
    if material["deleted_at"] is not None:
        raise ValueError("source_deleted")
    if revision is None or str(revision["material_id"]) != material_id or int(revision["is_current"]) != 1:
        raise ValueError("source_stale")
    fingerprint = hashlib.sha256(
        f"embedding_index\x1f{material_id}\x1f{source_revision}\x1f{provider_id}\x1f{model_id or ''}\x1f{model_revision}".encode("utf-8")
    ).hexdigest()
    key_fingerprint = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None
    if idempotency_key is not None:
        existing = connection.execute(
            "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, idempotency_key)
        ).fetchone()
        if existing is not None:
            if (str(existing["operation_type"]) != "embedding_index" or
                    str(existing["input_fingerprint"]) != fingerprint):
                raise ValueError("embedding_index_idempotency_mismatch")
            task = connection.execute("SELECT * FROM operation_tasks WHERE operation_id=?", (existing["id"],)).fetchone()
            if task is None:
                raise ValueError("task_result_unavailable")
            return {"operation_id": str(existing["id"]), "task_id": str(task["id"]), "replay": True}
    operation_id, task_id, now = f"embedding_index_{uuid.uuid4().hex}", f"task_{uuid.uuid4().hex}", utc_now()
    try:
        with connection:
            connection.execute(
                "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
                "provider_id,model_id,request_id,idempotency_key,retry_count,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?)",
                (operation_id, "embedding_index", "queued", project_id, material_id, fingerprint,
                 source_revision, provider_id, model_id, request_id, idempotency_key, now),
            )
            create_operation_task(
                connection, task_id=task_id, project_id=project_id, operation_id=operation_id,
                task_kind="embedding_index", input_fingerprint=fingerprint,
                idempotency_key_fingerprint=key_fingerprint, max_retries=max_retries,
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("embedding_index_enqueue_failed") from exc
    return {"operation_id": operation_id, "task_id": task_id, "replay": False}

