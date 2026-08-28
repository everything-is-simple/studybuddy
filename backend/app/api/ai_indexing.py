from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.post("/api/materials/{material_id}/ai-index")
    def index_material(material_id: str, retry: bool = False) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                state = material_state(connection, material_id)
                if state == "missing":
                    raise HTTPException(status_code=404, detail="material_not_found")
                if state == "deleted":
                    raise HTTPException(status_code=404, detail="source_deleted")
                extraction = connection.execute(
                    "SELECT id FROM extractions WHERE material_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                    (material_id,),
                ).fetchone()
                if extraction is None:
                    raise HTTPException(status_code=404, detail="extraction_not_found")
                revision = index_material_revision(connection, material_id, str(extraction["id"]))
                reclaim_stale_embedding_operations(connection, project_id=app.state.config.project_id)
                previous = connection.execute(
                    "SELECT retry_count FROM ai_operations WHERE operation_type='embedding_index' AND material_id=? "
                    "ORDER BY created_at DESC, id DESC LIMIT 1", (material_id,)
                ).fetchone()
                operation_id = create_embedding_index_operation(
                    connection, project_id=app.state.config.project_id, material_id=material_id,
                    source_revision=str(revision["id"]), retry_count=(int(previous["retry_count"]) + 1 if retry and previous else 0),
                )
                # The lease must survive provider failure so operators can inspect and retry it.
                connection.commit()
                result = get_material_index_status(connection, material_id)
                config = app.state.config
                embedding_provider_id = config.embedding_provider_id or "fake"
                provider = EmbeddingProviderRegistry(
                    embedding_provider_id, config.embedding_model_id,
                    model_revision=config.embedding_model_revision,
                    base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                    max_batch_size=config.embedding_max_batch_size,
                    max_text_chars=config.embedding_max_text_chars,
                    max_dimensions=config.embedding_max_dimensions,
                    max_response_bytes=config.embedding_max_response_bytes,
                    max_retries=config.embedding_max_retries,
                ).configured_provider()
                from ..repository import index_embeddings_for_material
                result = {**result, "embedding": index_embeddings_for_material(
                    connection, material_id=material_id, provider=provider, retry_failed=retry,
                    operation_id=operation_id)}
                finish_embedding_index_operation(connection, operation_id, status="succeeded")
                result["index_operation_id"] = operation_id
        except HTTPException:
            raise
        except ValueError as exc:
            code = str(exc)
            status = 404 if code in {"source_deleted", "material_extraction_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except (sqlite3.Error, EmbeddingError, ProviderError) as error:
            if 'operation_id' in locals() and operation_id:
                try:
                    with connect(app.state.config.database_path) as connection:
                        finish_embedding_index_operation(connection, operation_id, status="failed", error_code=getattr(error, "code", "embedding_index_failed"))
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="ai_index_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return {**result, "revision_id": revision["id"]}

    @app.post("/api/materials/{material_id}/ai-index/tasks", status_code=202)
    def enqueue_embedding_index_task(
        material_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        """Explicitly queue the approved embedding stage; legacy /ai-index stays synchronous."""
        if idempotency_key is not None and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="embedding_index_invalid_idempotency_key")
        config = app.state.config
        request_id, _operation_correlation_id = correlation()
        try:
            provider_id, model_id, model_revision = embedding_provider_identity(config)
            with connect(config.database_path) as connection:
                state = material_state(connection, material_id)
                if state == "missing":
                    raise HTTPException(status_code=404, detail="material_not_found")
                if state == "deleted":
                    raise HTTPException(status_code=404, detail="source_deleted")
                extraction = connection.execute(
                    "SELECT id FROM extractions WHERE material_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (material_id,)
                ).fetchone()
                if extraction is None:
                    raise HTTPException(status_code=404, detail="extraction_not_found")
                # Revision/chunk creation remains the pre-existing synchronous source
                # transaction. Only provider-backed embedding is runner-approved here.
                revision = index_material_revision(connection, material_id, str(extraction["id"]))
                queued = create_task_backed_embedding_operation(
                    connection, project_id=config.project_id, material_id=material_id,
                    source_revision=str(revision["id"]), provider_id=provider_id, model_id=model_id,
                    model_revision=model_revision, idempotency_key=idempotency_key,
                    request_id=request_id,
                )
                task = get_operation_task_public(
                    connection, task_id=str(queued["task_id"]), project_id=config.project_id,
                )
        except HTTPException:
            raise
        except (EmbeddingError, ProviderError) as error:
            raise HTTPException(status_code=503, detail=error.code) from None
        except ValueError as error:
            code = str(error)
            status = 404 if code == "material_not_found" else 409 if code in {
                "source_deleted", "source_stale", "embedding_index_idempotency_mismatch",
                "task_project_scope_violation",
            } else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="embedding_index_enqueue_failed") from None
        return {**task, "replay": bool(queued["replay"])}

    @app.get("/api/materials/{material_id}/ai-index")
    def material_index_status(material_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_material_index_status(connection, material_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="ai_index_status_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return result
    return context
