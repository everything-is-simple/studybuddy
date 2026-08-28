from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.post("/api/retrieval")
    def retrieve(request: RetrievalRequest) -> dict[str, object]:
        if request.material_ids is not None and (not request.material_ids or len(request.material_ids) > 200):
            raise HTTPException(status_code=400, detail="retrieval_invalid_materials")
        try:
            with connect(app.state.config.database_path) as connection:
                if request.mode not in {"lexical", "vector", "hybrid"}:
                    raise HTTPException(status_code=400, detail="retrieval_invalid_mode")
                if request.mode == "vector":
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id or "fake"
                    provider = provider_registry(embedding_provider_id, config.embedding_model_id).embedding_provider(
                        model_revision=config.embedding_model_revision,
                        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                        timeout_seconds=config.embedding_timeout_seconds,
                        max_batch_size=config.embedding_max_batch_size,
                        max_text_chars=config.embedding_max_text_chars,
                        max_dimensions=config.embedding_max_dimensions,
                        max_response_bytes=config.embedding_max_response_bytes,
                        max_retries=config.embedding_max_retries,
                    )
                    from ..repository import run_vector_retrieval
                    return run_vector_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                                 provider=provider, material_ids=request.material_ids, top_k=request.top_k)
                if request.mode == "hybrid":
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id or "fake"
                    provider = provider_registry(embedding_provider_id, config.embedding_model_id).embedding_provider(
                        model_revision=config.embedding_model_revision,
                        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                        timeout_seconds=config.embedding_timeout_seconds,
                        max_batch_size=config.embedding_max_batch_size,
                        max_text_chars=config.embedding_max_text_chars,
                        max_dimensions=config.embedding_max_dimensions,
                        max_response_bytes=config.embedding_max_response_bytes,
                        max_retries=config.embedding_max_retries,
                    )
                    from ..repository import run_hybrid_retrieval
                    return run_hybrid_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                                provider=provider, material_ids=request.material_ids, top_k=request.top_k,
                                                allow_fallback=request.allow_fallback)
                return run_chunk_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                           material_ids=request.material_ids, top_k=request.top_k)
        except ValueError as exc:
            code = str(exc)
            status = 404 if code in {"material_not_found", "source_deleted"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except ProviderError as exc:
            raise HTTPException(status_code=_provider_http_status(exc.code), detail=exc.code) from None
        except EmbeddingError as exc:
            raise HTTPException(status_code=503, detail=exc.code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="retrieval_failed") from None

    @app.post("/api/context/assemble")
    def assemble_context_endpoint(request: ContextRequest) -> dict[str, object]:
        if request.hit_ids is None or len(request.hit_ids) > 200:
            if request.hit_ids is not None and len(request.hit_ids) > 200:
                raise HTTPException(status_code=400, detail="context_invalid_hits")
        if request.max_tokens <= 0 or request.max_tokens > MAX_CONTEXT_TOKENS:
            raise HTTPException(status_code=400, detail="context_invalid_max_tokens")
        try:
            with connect(app.state.config.database_path) as connection:
                return assemble_context(connection, project_id=app.state.config.project_id,
                                        hits=[{"chunk_id": h, "rank": i + 1} for i, h in enumerate(request.hit_ids)],
                                        max_tokens=request.max_tokens)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="context_assemble_failed") from None

    @app.post("/api/citation/validate")
    def validate_citation(request: CitationValidateRequest) -> dict[str, object]:
        if not request.key or len(request.key) > 80:
            raise HTTPException(status_code=400, detail="citation_invalid_key")
        try:
            with connect(app.state.config.database_path) as connection:
                return validate_citation_key(connection, request.key)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="citation_validate_failed") from None

    @app.get("/api/qa/threads")
    def qa_threads(limit: int = 50) -> dict[str, object]:
        if limit <= 0 or limit > 100:
            raise HTTPException(status_code=400, detail="qa_invalid_limit")
        try:
            with connect(app.state.config.database_path) as connection:
                items = list_qa_threads(connection, project_id=app.state.config.project_id, limit=limit)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="qa_history_failed") from None
        return {"items": items}

    @app.get("/api/qa/threads/{thread_id}")
    def qa_thread_history(thread_id: str) -> dict[str, object]:
        if not thread_id or len(thread_id) > 100:
            raise HTTPException(status_code=404, detail="qa_thread_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_qa_thread_history(connection, project_id=app.state.config.project_id, thread_id=thread_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="qa_history_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="qa_thread_not_found")
        return result

    @app.get("/api/qa/citations/{citation_key}")
    def qa_citation_detail(citation_key: str) -> dict[str, object]:
        if not citation_key or len(citation_key) > 80:
            raise HTTPException(status_code=404, detail="citation_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_qa_citation_detail(connection, citation_key)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="citation_detail_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="citation_not_found")
        return result

    @app.post("/api/qa/ask")
    def ask_question(request: QaAskRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        if not request.material_ids or len(request.material_ids) > 200 or any(not item for item in request.material_ids):
            raise HTTPException(status_code=400, detail="qa_invalid_materials")
        if request.retrieval_mode not in {"lexical", "vector", "hybrid"}:
            raise HTTPException(status_code=400, detail="retrieval_invalid_mode")
        request_id, _operation_correlation_id = correlation()
        operation: dict[str, object] | None = None
        try:
            with connect(app.state.config.database_path) as connection:
                reclaim_stale_qa_operations(connection, project_id=app.state.config.project_id)
                if idempotency_key:
                    if len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key):
                        raise HTTPException(status_code=400, detail="qa_invalid_idempotency_key")
                    expected_fingerprint = qa_request_fingerprint(
                        question=request.question, material_ids=request.material_ids, thread_id=request.thread_id,
                        retrieval_mode=request.retrieval_mode,
                        allow_retrieval_fallback=request.allow_retrieval_fallback,
                    )
                    replay = get_idempotent_qa_response(
                        connection, project_id=app.state.config.project_id, idempotency_key=idempotency_key,
                        retrieval_mode=request.retrieval_mode, expected_fingerprint=expected_fingerprint,
                    )
                    if replay is not None:
                        return replay
                operation = create_qa_request(
                    connection, project_id=app.state.config.project_id, question=request.question,
                    material_ids=request.material_ids, thread_id=request.thread_id, request_id=request_id,
                    idempotency_key=idempotency_key, retrieval_mode=request.retrieval_mode,
                    allow_retrieval_fallback=request.allow_retrieval_fallback,
                )
                if operation.get("replay"):
                    replay = get_idempotent_qa_response(
                        connection, project_id=app.state.config.project_id, idempotency_key=idempotency_key,
                        retrieval_mode=request.retrieval_mode,
                        expected_fingerprint=qa_request_fingerprint(
                            question=request.question, material_ids=request.material_ids, thread_id=request.thread_id,
                            retrieval_mode=request.retrieval_mode,
                            allow_retrieval_fallback=request.allow_retrieval_fallback,
                        ),
                    )
                    if replay is not None:
                        return replay
                if request.retrieval_mode == "lexical":
                    retrieval = run_chunk_retrieval(
                        connection, project_id=app.state.config.project_id, query=request.question,
                        material_ids=request.material_ids, top_k=request.top_k,
                    )
                else:
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id
                    embedding_provider = None
                    embedding_error_code = "embedding_provider_not_configured"
                    try:
                        embedding_provider = EmbeddingProviderRegistry(
                            embedding_provider_id, config.embedding_model_id,
                            model_revision=config.embedding_model_revision,
                            base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                            timeout_seconds=config.embedding_timeout_seconds,
                            max_batch_size=config.embedding_max_batch_size,
                            max_text_chars=config.embedding_max_text_chars,
                            max_dimensions=config.embedding_max_dimensions,
                            max_response_bytes=config.embedding_max_response_bytes,
                            max_retries=config.embedding_max_retries,
                        ).configured_provider()
                    except (ProviderError, EmbeddingError) as error:
                        embedding_error_code = error.code
                        if request.retrieval_mode == "vector" or not request.allow_retrieval_fallback:
                            fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                            raise HTTPException(status_code=503, detail=error.code) from None
                    if request.retrieval_mode == "vector":
                        retrieval = run_vector_retrieval(
                            connection, project_id=app.state.config.project_id, query=request.question,
                            provider=embedding_provider, material_ids=request.material_ids, top_k=request.top_k,
                        )
                    else:
                        retrieval = run_hybrid_retrieval(
                            connection, project_id=app.state.config.project_id, query=request.question,
                            provider=embedding_provider, material_ids=request.material_ids, top_k=request.top_k,
                            allow_fallback=request.allow_retrieval_fallback, embedding_error_code=embedding_error_code,
                        )
                connection.execute(
                    "UPDATE ai_operations SET retrieval_policy_version = ?, retrieval_run_id = ? WHERE id = ? AND status = 'running'",
                    (retrieval["policy_version"], retrieval["run_id"], operation["operation_id"]),
                )
                if retrieval["status"] != "succeeded":
                    fail_qa_operation(connection, str(operation["operation_id"]), str(retrieval["error_code"]))
                    raise HTTPException(status_code=409, detail=str(retrieval["error_code"]))
                context = assemble_context(
                    connection, project_id=app.state.config.project_id, hits=list(retrieval["hits"]),
                )
                if not context["context_blocks"]:
                    fail_qa_operation(connection, str(operation["operation_id"]), "retrieval_empty")
                    raise HTTPException(status_code=409, detail="retrieval_empty")
                try:
                    if app.state.config.ai_provider_id == "fake":
                        provider = provider_registry(
                            app.state.config.ai_provider_id, app.state.config.ai_model_id,
                        ).configured_provider()
                    else:
                        provider = provider_registry(
                            app.state.config.ai_provider_id, app.state.config.ai_model_id,
                            base_url=app.state.config.ai_base_url,
                            api_key=app.state.config.ai_api_key,
                            timeout_seconds=app.state.config.ai_timeout_seconds,
                            max_retries=app.state.config.ai_max_retries,
                        ).configured_provider()
                    started = time.perf_counter()
                    result = provider.generate_answer(ProviderRequest(
                        question=request.question, context_blocks=list(context["context_blocks"]),
                        max_output_tokens=app.state.config.ai_max_output_tokens,
                        max_prompt_chars=app.state.config.ai_max_prompt_chars,
                        max_answer_chars=app.state.config.ai_max_answer_chars,
                    ))
                    latency_ms = result.latency_ms if result.latency_ms is not None else round((time.perf_counter() - started) * 1000)
                except ProviderError as error:
                    fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                    raise HTTPException(status_code=_provider_http_status(error.code), detail=error.code) from None
                except EmbeddingError as error:
                    fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                    raise HTTPException(status_code=503, detail=error.code) from None
                try:
                    persisted = persist_qa_answer(
                        connection, project_id=app.state.config.project_id,
                        operation_id=str(operation["operation_id"]), thread_id=str(operation["thread_id"]),
                        provider_id=result.provider_id, model_id=result.model_id,
                        answer_text=result.answer_text, citation_keys=result.citation_keys,
                        context_blocks=list(context["context_blocks"]), prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens, latency_ms=latency_ms,
                        provider_request_id=result.provider_request_id,
                        total_tokens=result.total_tokens, finish_reason=result.finish_reason,
                        retrieval_run_id=str(retrieval["run_id"]),
                    )
                except ValueError as error:
                    fail_qa_operation(connection, operation["operation_id"], str(error))
                    raise HTTPException(status_code=500, detail="qa_generation_failed") from None
        except HTTPException:
            raise
        except ValueError as error:
            code = str(error)
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_qa_operation(connection, str(operation["operation_id"]), code)
            status = 404 if code in {"material_not_found", "source_deleted", "qa_thread_not_found"} else 409 if code in {"qa_operation_in_progress", "qa_idempotency_key_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_qa_operation(connection, str(operation["operation_id"]), "qa_persist_failed")
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="qa_generation_failed") from None
        return {
            "status": "succeeded", "thread_id": operation["thread_id"],
            "user_message_id": operation["user_message_id"],
            "assistant_message_id": persisted["assistant_message_id"], "answer_id": persisted["answer_id"],
            "operation_id": operation["operation_id"], "answer_text": result.answer_text,
            "provider_id": result.provider_id, "model_id": result.model_id,
            "retrieval_run_id": retrieval["run_id"], "retrieval": {
                "mode": request.retrieval_mode, "policy_version": retrieval["policy_version"],
                "fallback": bool(retrieval.get("fallback", False)),
                "fallback_reason": retrieval.get("fallback_reason"), "run_id": retrieval["run_id"],
            }, "citations": persisted["citations"],
        }
    return context
