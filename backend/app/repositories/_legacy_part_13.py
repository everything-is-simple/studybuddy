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

