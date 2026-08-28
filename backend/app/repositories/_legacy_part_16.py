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

