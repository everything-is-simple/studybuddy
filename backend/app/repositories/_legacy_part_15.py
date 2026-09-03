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
from ._legacy_part_14 import *
TASK_LIST_STATUSES = {"queued", "running", "cancel_requested", "succeeded", "failed", "cancelled", "stale"}

def list_operation_tasks_public(connection: sqlite3.Connection, *, project_id: str,
                                status: str | None = None, task_kind: str | None = None,
                                operation_type: str | None = None, limit: int = 25,
                                offset: int = 0) -> dict[str, object]:
    if not project_id or limit < 1 or limit > 100 or offset < 0:
        raise ValueError("task_invalid_request")
    if status is not None and status not in TASK_LIST_STATUSES:
        raise ValueError("task_invalid_filter")
    params: list[object] = [project_id]
    where = ["t.project_id=?"]
    if status is not None:
        where.append("t.status=?"); params.append(status)
    if task_kind is not None:
        if not task_kind or len(task_kind) > 100:
            raise ValueError("task_invalid_filter")
        where.append("t.task_kind=?"); params.append(task_kind)
    if operation_type is not None:
        if not operation_type or len(operation_type) > 100:
            raise ValueError("task_invalid_filter")
        where.append("o.operation_type=?"); params.append(operation_type)
    clause = " AND ".join(where)
    total = connection.execute(
        "SELECT COUNT(*) FROM operation_tasks t JOIN ai_operations o ON o.id=t.operation_id WHERE " + clause,
        params,
    ).fetchone()[0]
    rows = connection.execute(
        "SELECT t.id FROM operation_tasks t JOIN ai_operations o ON o.id=t.operation_id WHERE " + clause +
        " ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?", params + [limit, offset],
    ).fetchall()
    return {"items": [get_operation_task_public(connection, task_id=str(row["id"]), project_id=project_id) for row in rows],
            "total": int(total), "limit": limit, "offset": offset}

def get_operation_task_public(connection: sqlite3.Connection, *, task_id: str,
                              project_id: str) -> dict[str, object]:
    task = get_operation_task(connection, task_id=task_id, project_id=project_id)
    operation = connection.execute(
        "SELECT operation_type,status,provider_id,model_id,output_artifact_id FROM ai_operations WHERE id=? AND project_id=?",
        (task["operation_id"], project_id),
    ).fetchone()
    if operation is None:
        raise ValueError("task_result_unavailable")
    attempts = connection.execute(
        "SELECT COUNT(*) FROM operation_task_attempts WHERE task_id=? AND project_id=?", (task_id, project_id)
    ).fetchone()[0]
    return {
        "task_id": task["id"], "operation_id": task["operation_id"], "status": task["status"],
        "task_kind": task["task_kind"], "operation_type": operation["operation_type"],
        "progress_percent": task["progress_percent"], "stage_code": task["stage_code"],
        "retry_count": task["retry_count"], "attempt_count": attempts, "max_retries": task["max_retries"],
        "error_code": task["error_code"], "output_artifact_id": operation["output_artifact_id"],
        "provider_id": operation["provider_id"], "model_id": operation["model_id"],
        "created_at": task["created_at"], "started_at": task["started_at"],
        "updated_at": task["updated_at"], "finished_at": task["finished_at"],
        "cancel_requested": task["status"] == "cancel_requested",
    }

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
                                  retry_failed: bool = False, operation_id: str | None = None,
                                  expected_revision_id: str | None = None,
                                  checkpoint: Callable[[], bool | None] | None = None) -> dict[str, object]:
    """Explicit, synchronous SQLite-first indexing; never called during startup."""
    def check_checkpoint() -> None:
        if checkpoint is not None and checkpoint() is False:
            raise ValueError("task_cancel_requested")

    def require_current_source() -> None:
        if expected_revision_id is None:
            return
        source = connection.execute(
            "SELECT r.id FROM material_revisions r JOIN materials m ON m.id=r.material_id "
            "WHERE r.id=? AND r.material_id=? AND r.is_current=1 AND m.deleted_at IS NULL",
            (expected_revision_id, material_id),
        ).fetchone()
        if source is None:
            raise ValueError("source_stale")

    require_current_source()
    if getattr(provider, "dimensions", 0) == 0:
        probe_sql = "SELECT text FROM chunks WHERE material_id=? AND status='ready' "
        probe_args: tuple[str, ...] = (material_id,)
        if expected_revision_id is not None:
            probe_sql += "AND revision_id=? "
            probe_args = (material_id, expected_revision_id)
        probe = connection.execute(probe_sql + "ORDER BY chunk_index, id LIMIT 1", probe_args).fetchone()
        if probe is not None:
            check_checkpoint()
            provider.embed([str(probe["text"])])
            require_current_source()
            check_checkpoint()
    with connection:
        rows_sql = (
            "SELECT c.id, c.text, c.revision_id FROM chunks c JOIN materials m ON m.id=c.material_id "
            "JOIN material_revisions r ON r.id=c.revision_id WHERE c.material_id=? AND m.deleted_at IS NULL "
            "AND r.is_current=1 AND c.status='ready' "
        )
        rows_args: tuple[str, ...] = (material_id,)
        if expected_revision_id is not None:
            rows_sql += "AND c.revision_id=? "
            rows_args = (material_id, expected_revision_id)
        rows = connection.execute(rows_sql + "ORDER BY c.chunk_index, c.id", rows_args).fetchall()
        if not rows:
            return {"status": "empty", "material_id": material_id, "embedded_count": 0, "skipped_count": 0}
        # Do not retain a SQLite write transaction across provider calls. Each
        # completed provider batch commits its idempotent rows before the next call.
        connection.commit()
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
                check_checkpoint()
                vectors = provider.embed([str(row["text"]) for row, _ in todo])
                check_checkpoint()
                # Serialize source validation with the batch write. A delete or
                # revision refresh either wins before this check (no write), or
                # follows this committed, source-valid batch and marks it stale.
                connection.execute("BEGIN IMMEDIATE")
                require_current_source()
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
                connection.commit()
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
                connection.commit()
                raise
            except ValueError as error:
                if str(error) in {"source_stale", "task_cancel_requested", "task_lease_lost"}:
                    raise
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
                connection.commit()
                raise error
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
                connection.commit()
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

