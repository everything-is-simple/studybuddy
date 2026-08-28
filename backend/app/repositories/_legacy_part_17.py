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
from ._legacy_part_15 import *
from ._legacy_part_16 import *
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

