from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    def _generated_items(raw: str, *, artifact_kind: str, count: int) -> tuple[list[dict[str, object]], list[list[str]]]:
        """Validate the bounded in-memory structured response; never persist it raw."""
        if len(raw) > 12000:
            raise ValueError("generation_schema_invalid")
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ValueError("generation_schema_invalid") from None
        if not isinstance(payload, dict) or set(payload) != {"items"} or not isinstance(payload["items"], list):
            raise ValueError("generation_schema_invalid")
        raw_items = payload["items"]
        if len(raw_items) != count:
            raise ValueError("generation_schema_invalid")
        items: list[dict[str, object]] = []
        citation_groups: list[list[str]] = []
        allowed = {"front", "back", "explanation", "tags"} if artifact_kind == "card" else {"exercise_type", "prompt", "options", "answer_key", "explanation"}
        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("generation_schema_invalid")
            citations = item.get("citations")
            if not isinstance(citations, list) or not citations or any(not isinstance(key, str) or not key for key in citations):
                raise ValueError("generation_schema_invalid")
            public = dict(item)
            public.pop("citations", None)
            if set(public) != allowed:
                raise ValueError("generation_schema_invalid")
            items.append(public)
            citation_groups.append(citations)
        return items, citation_groups

    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    def generate_draft(*, artifact_kind: str, container_id: str, request: GenerationRequest,
                       idempotency_key: str | None) -> dict[str, object]:
        if idempotency_key and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="generation_invalid_idempotency_key")
        request_id, _operation_correlation_id = correlation()
        operation: dict[str, object] | None = None
        try:
            with connect(app.state.config.database_path) as connection:
                operation = create_generation_operation(
                    connection, project_id=app.state.config.project_id, artifact_kind=artifact_kind,
                    container_id=container_id, topic=request.topic, material_ids=request.material_ids,
                    retrieval_mode=request.retrieval_mode, allow_fallback=request.allow_retrieval_fallback,
                    count=request.count, exercise_type=request.exercise_type, source_revision=request.source_revision,
                    request_id=request_id, idempotency_key=idempotency_key,
                )
                if operation.get("replay"):
                    return operation
                if request.retrieval_mode == "lexical":
                    retrieval = run_chunk_retrieval(connection, project_id=app.state.config.project_id,
                                                    query=request.topic, material_ids=request.material_ids, top_k=5)
                else:
                    config = app.state.config
                    embedding_provider = None
                    embedding_error_code = "embedding_provider_not_configured"
                    try:
                        embedding_provider = EmbeddingProviderRegistry(
                            config.embedding_provider_id, config.embedding_model_id,
                            model_revision=config.embedding_model_revision, base_url=config.embedding_base_url,
                            api_key=config.embedding_api_key, timeout_seconds=config.embedding_timeout_seconds,
                            max_batch_size=config.embedding_max_batch_size, max_text_chars=config.embedding_max_text_chars,
                            max_dimensions=config.embedding_max_dimensions,
                            max_response_bytes=config.embedding_max_response_bytes,
                            max_retries=config.embedding_max_retries,
                        ).configured_provider()
                    except (ProviderError, EmbeddingError) as error:
                        embedding_error_code = error.code
                        if request.retrieval_mode == "vector" or not request.allow_retrieval_fallback:
                            raise error
                    if request.retrieval_mode == "vector":
                        retrieval = run_vector_retrieval(connection, project_id=app.state.config.project_id,
                                                         query=request.topic, provider=embedding_provider,
                                                         material_ids=request.material_ids, top_k=5)
                    else:
                        retrieval = run_hybrid_retrieval(connection, project_id=app.state.config.project_id,
                                                         query=request.topic, provider=embedding_provider,
                                                         material_ids=request.material_ids, top_k=5,
                                                         allow_fallback=request.allow_retrieval_fallback,
                                                         embedding_error_code=embedding_error_code)
                connection.execute("UPDATE ai_operations SET retrieval_policy_version=?,retrieval_run_id=? WHERE id=? AND status='running'",
                                   (retrieval["policy_version"], retrieval["run_id"], operation["operation_id"]))
                # Do not retain a SQLite write transaction across Provider I/O.
                # The final operation/draft/citation write opens its own atomic transaction.
                connection.commit()
                if retrieval["status"] != "succeeded":
                    raise ValueError(str(retrieval["error_code"]))
                context = assemble_context(connection, project_id=app.state.config.project_id, hits=list(retrieval["hits"]))
                if not context["context_blocks"]:
                    raise ValueError("retrieval_empty")
                config = app.state.config
                provider = provider_registry(config.ai_provider_id, config.ai_model_id) if config.ai_provider_id == "fake" else provider_registry(
                    config.ai_provider_id, config.ai_model_id, base_url=config.ai_base_url, api_key=config.ai_api_key,
                    timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries)
                started = time.perf_counter()
                result = provider.configured_provider().generate_answer(ProviderRequest(
                    question=request.topic, context_blocks=list(context["context_blocks"]),
                    max_output_tokens=config.ai_max_output_tokens, max_prompt_chars=config.ai_max_prompt_chars,
                    max_answer_chars=config.ai_max_answer_chars, generation_kind=artifact_kind,
                    generation_count=request.count, exercise_type=request.exercise_type,
                ))
                items, citation_groups = _generated_items(result.answer_text, artifact_kind=artifact_kind, count=request.count)
                if artifact_kind == "exercise" and any(item.get("exercise_type") != request.exercise_type for item in items):
                    raise ValueError("generation_schema_invalid")
                latency_ms = result.latency_ms if result.latency_ms is not None else round((time.perf_counter() - started) * 1000)
                artifact = persist_generated_draft(
                    connection, project_id=app.state.config.project_id, operation_id=str(operation["operation_id"]),
                    artifact_kind=artifact_kind, container_id=container_id, source_revision=str(operation["source_revision"]),
                    items=items, citation_groups=citation_groups, context_blocks=list(context["context_blocks"]),
                    provider_id=result.provider_id, model_id=result.model_id, prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens, latency_ms=latency_ms,
                    provider_request_id=result.provider_request_id, total_tokens=result.total_tokens,
                    finish_reason=result.finish_reason,
                )
                return {"status": "succeeded", "operation_id": operation["operation_id"],
                        "retrieval_run_id": retrieval["run_id"], "artifacts": artifact, "replay": False}
        except (ProviderError, EmbeddingError) as error:
            code = error.code
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_generation_operation(connection, str(operation["operation_id"]), code)
            status = _provider_http_status(code) if isinstance(error, ProviderError) else 503
            raise HTTPException(status_code=status, detail=code) from None
        except ValueError as error:
            code = str(error)
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_generation_operation(connection, str(operation["operation_id"]), code)
            status = 404 if code in {"deck_not_found", "exercise_set_not_found", "material_not_found", "source_deleted"} else 409 if code in {"retrieval_not_ready", "retrieval_empty", "generation_in_progress", "generation_idempotency_key_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_generation_operation(connection, str(operation["operation_id"]), "generation_persist_failed")
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="generation_failed") from None

    globals()['generate_draft'] = generate_draft
    context.update({'generate_draft': generate_draft})
    return context
