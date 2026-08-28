from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/study/notes")
    def study_notes(include_archived: bool = False) -> list[dict[str, object]]:
        try:
            with connect(app.state.config.database_path) as connection:
                return list_notes(connection, project_id=app.state.config.project_id, include_archived=include_archived)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_read_failed") from None

    @app.post("/api/study/notes", status_code=201)
    def create_study_note_route(request: NoteRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_user_note(connection, project_id=app.state.config.project_id,
                                        title=request.title, blocks=request.blocks)
        except ValueError as error:
            raise _study_error(error, default="study_note_invalid_payload", conflict={"study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_create_failed") from None

    @app.get("/api/study/notes/{note_id}")
    def get_study_note_route(note_id: str) -> dict[str, object]:
        note_id = _bounded_id(note_id, "study_note_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_note(connection, project_id=app.state.config.project_id, note_id=note_id)
            if result is None:
                raise HTTPException(status_code=404, detail="study_note_not_found")
            return result
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_read_failed") from None

    @app.patch("/api/study/notes/{note_id}")
    def patch_study_note_route(note_id: str, request: NotePatchRequest) -> dict[str, object]:
        note_id = _bounded_id(note_id, "study_note_not_found")
        if request.title is None and request.blocks is None:
            raise HTTPException(status_code=400, detail="study_note_invalid_payload")
        try:
            with connect(app.state.config.database_path) as connection:
                return update_note_content(connection, project_id=app.state.config.project_id, note_id=note_id,
                                           title=request.title, blocks=request.blocks)
        except ValueError as error:
            raise _study_error(error, default="study_note_invalid_payload",
                               not_found={"study_note_not_found"},
                               conflict={"study_note_edit_not_allowed", "study_note_block_edit_not_allowed", "study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_update_failed") from None

    @app.post("/api/study/notes/{note_id}/blocks", status_code=201)
    def create_study_note_block_route(note_id: str, request: NoteBlockRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_note_block(connection, project_id=app.state.config.project_id, note_id=note_id,
                                         block_kind=request.block_kind, content=request.content)
        except ValueError as error:
            raise _study_error(error, default="study_note_block_invalid", not_found={"study_note_not_found"},
                               conflict={"study_note_block_edit_not_allowed", "study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_block_create_failed") from None

    @app.put("/api/study/notes/{note_id}/blocks", status_code=200)
    def replace_study_note_blocks_route(note_id: str, request: NoteBlocksRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_note_blocks(connection, project_id=app.state.config.project_id, note_id=note_id,
                                          blocks=request.blocks)
        except ValueError as error:
            raise _study_error(error, default="study_note_block_invalid", not_found={"study_note_not_found"},
                               conflict={"study_note_block_edit_not_allowed", "study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_block_update_failed") from None

    @app.patch("/api/study/notes/{note_id}/blocks/{block_id}")
    def patch_study_note_block_route(note_id: str, block_id: str, request: NoteBlockRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_note_block(connection, project_id=app.state.config.project_id, note_id=note_id,
                                         block_id=block_id, block_kind=request.block_kind, content=request.content)
        except ValueError as error:
            raise _study_error(error, default="study_note_block_invalid",
                               not_found={"study_note_not_found", "study_note_block_not_found"},
                               conflict={"study_note_block_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_block_update_failed") from None

    @app.delete("/api/study/notes/{note_id}/blocks/{block_id}", status_code=204)
    def delete_study_note_block_route(note_id: str, block_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                delete_note_block(connection, project_id=app.state.config.project_id, note_id=note_id, block_id=block_id)
        except ValueError as error:
            raise _study_error(error, default="study_note_block_not_found",
                               not_found={"study_note_not_found", "study_note_block_not_found"},
                               conflict={"study_note_block_edit_not_allowed", "study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_block_delete_failed") from None
        return Response(status_code=204)

    @app.post("/api/study/notes/{note_id}/confirm")
    def confirm_study_note_route(note_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_note(connection, project_id=app.state.config.project_id, note_id=note_id)
        except ValueError as error:
            raise _study_error(error, default="study_note_invalid_state", not_found={"study_note_not_found"},
                               conflict={"study_note_invalid_state", "study_note_confirm_source_invalid", "study_note_empty"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_confirm_failed") from None

    @app.post("/api/study/notes/{note_id}/reject")
    def reject_study_note_route(note_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_note(connection, project_id=app.state.config.project_id, note_id=note_id, target="rejected")
        except ValueError as error:
            raise _study_error(error, default="study_note_invalid_state", not_found={"study_note_not_found"}, conflict={"study_note_invalid_state"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_reject_failed") from None

    @app.post("/api/study/notes/{note_id}/archive")
    def archive_study_note_route(note_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_note(connection, project_id=app.state.config.project_id, note_id=note_id)
        except ValueError as error:
            raise _study_error(error, default="study_note_invalid_state", not_found={"study_note_not_found"}, conflict={"study_note_invalid_state"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_archive_failed") from None

    @app.post("/api/study/notes/{note_id}/modules/{module_id}", status_code=201)
    def link_study_note_module_route(note_id: str, module_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                link_note_module(connection, project_id=app.state.config.project_id, note_id=note_id, module_id=module_id)
                note = get_note(connection, project_id=app.state.config.project_id, note_id=note_id)
                if note is None:
                    raise ValueError("study_note_not_found")
                return note
        except ValueError as error:
            raise _study_error(error, default="study_note_module_invalid", not_found={"study_note_not_found"},
                               conflict={"study_note_edit_not_allowed", "study_note_module_archived", "study_note_module_link_duplicate"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_module_link_failed") from None

    @app.delete("/api/study/notes/{note_id}/modules/{module_id}", status_code=204)
    def unlink_study_note_module_route(note_id: str, module_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                unlink_note_module(connection, project_id=app.state.config.project_id, note_id=note_id, module_id=module_id)
        except ValueError as error:
            raise _study_error(error, default="study_note_module_invalid", not_found={"study_note_not_found"},
                               conflict={"study_note_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_module_link_failed") from None
        return Response(status_code=204)

    @app.post("/api/study/notes/{note_id}/blocks/{block_id}/sources", status_code=201)
    def create_study_note_source_route(note_id: str, block_id: str, request: NoteSourceLinkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                payload = request.model_dump()
                context_chunk_ids = payload.pop("context_chunk_ids")
                return create_note_source_link(connection, project_id=app.state.config.project_id, note_id=note_id,
                                               block_id=block_id, payload=payload, context_chunk_ids=context_chunk_ids)
        except ValueError as error:
            raise _study_error(error, default="study_note_source_invalid", not_found={"study_note_not_found", "study_note_block_not_found"},
                               conflict={"study_note_source_invalid", "study_note_source_deleted", "study_note_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_source_create_failed") from None

    @app.delete("/api/study/notes/{note_id}/blocks/{block_id}/sources/{link_id}", status_code=204)
    def delete_study_note_source_route(note_id: str, block_id: str, link_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                delete_note_source_link(connection, project_id=app.state.config.project_id, note_id=note_id, link_id=link_id)
        except ValueError as error:
            raise _study_error(error, default="study_note_source_not_found", not_found={"study_note_not_found", "study_note_source_not_found"},
                               conflict={"study_note_source_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_source_delete_failed") from None
        return Response(status_code=204)

    @app.post("/api/study/notes/sources/refresh")
    def refresh_study_note_sources_route(request: NoteSourceRefreshRequest | None = None) -> dict[str, int]:
        try:
            with connect(app.state.config.database_path) as connection:
                return {"updated": refresh_note_source_links(connection, project_id=app.state.config.project_id,
                                                               note_id=request.note_id if request else None,
                                                               material_id=request.material_id if request else None)}
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_source_refresh_failed") from None

    @app.post("/api/study/notes/generate")
    def generate_study_note_route(request: NoteGenerationRequest,
                                  idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        config = app.state.config
        try:
            # Keep provider_not_configured inside the domain operation boundary:
            # generate_note must retain one safe failed operation for retry/audit.
            # Other provider configuration failures are still mapped safely below.
            if config.ai_provider_id is None:
                provider = None
            elif config.ai_provider_id == "fake":
                provider = provider_registry(config.ai_provider_id, config.ai_model_id).configured_provider()
            else:
                provider = provider_registry(config.ai_provider_id, config.ai_model_id,
                                             base_url=config.ai_base_url, api_key=config.ai_api_key,
                                             timeout_seconds=config.ai_timeout_seconds,
                                             max_retries=config.ai_max_retries).configured_provider()
            embedding_provider = None
            if request.retrieval_mode in {"vector", "hybrid"} and config.embedding_provider_id is not None:
                embedding_provider = EmbeddingProviderRegistry(
                    config.embedding_provider_id, config.embedding_model_id,
                    model_revision=config.embedding_model_revision, base_url=config.embedding_base_url,
                    api_key=config.embedding_api_key, timeout_seconds=config.embedding_timeout_seconds,
                    max_batch_size=config.embedding_max_batch_size, max_text_chars=config.embedding_max_text_chars,
                    max_dimensions=config.embedding_max_dimensions, max_response_bytes=config.embedding_max_response_bytes,
                    max_retries=config.embedding_max_retries,
                ).configured_provider()
            request_id, _ = correlation()
            with connect(config.database_path) as connection:
                return generate_note_draft(connection, project_id=config.project_id, topic=request.topic,
                                           material_id=request.material_id, provider=provider,
                                           source_revision=request.source_revision, retrieval_mode=request.retrieval_mode,
                                           allow_fallback=request.allow_retrieval_fallback,
                                           embedding_provider=embedding_provider, request_id=request_id,
                                           idempotency_key=idempotency_key)
        except ProviderError as error:
            status = _provider_http_status(error.code)
            raise HTTPException(status_code=status, detail={"provider_not_configured": "study_note_provider_not_configured"}.get(error.code, error.code)) from None
        except EmbeddingError as error:
            raise HTTPException(status_code=503, detail=error.code) from None
        except ValueError as error:
            code = str(error)
            mapped = {"provider_not_configured": "study_note_provider_not_configured", "provider_timeout": "study_note_provider_timeout"}.get(code, code)
            status = 503 if code in {"study_note_provider_not_configured", "study_note_provider_timeout", "study_note_provider_unavailable"} else 404 if code in {"study_note_source_deleted", "study_note_source_unavailable"} else 409 if code in {
                "study_note_generation_in_progress", "study_note_generation_idempotency_mismatch", "study_note_generation_stale_source",
                "study_note_generation_empty", "study_note_generation_not_ready"} else 400
            raise HTTPException(status_code=status, detail=mapped) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_note_generation_failed") from None

    @app.get("/api/study/notes/{note_id}/export")
    def export_study_note_route(note_id: str, format: str = "json") -> Response:
        if format not in {"json", "markdown"}:
            raise HTTPException(status_code=400, detail="study_note_export_failed")
        try:
            with connect(app.state.config.database_path) as connection:
                note = get_note(connection, project_id=app.state.config.project_id, note_id=note_id)
                if note is None:
                    raise ValueError("study_note_not_found")
            if format == "json":
                payload = {"format_version": "phase9b-note-v1", "exported_at": utc_now(), "note": note}
                content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                media_type, filename = "application/json", "studybuddy-note.json"
            else:
                lines = [f"# {note['title']}", "", f"- status: {note['status']}", f"- provenance: {note['provenance']}", ""]
                for block in note["blocks"]:
                    lines.extend([f"[{block['block_kind']}]", str(block["content"]), ""])
                    for source in block.get("sources", []):
                        lines.append(f"- citation: {source['citation_key']} ({source['status']})")
                content, media_type, filename = "\n".join(lines), "text/markdown", "studybuddy-note.md"
            if len(content.encode("utf-8")) > 256 * 1024:
                raise HTTPException(status_code=413, detail="study_note_export_failed")
            return Response(content=content, media_type=media_type,
                            headers={"Content-Disposition": f'attachment; filename="{filename}"'})
        except HTTPException:
            raise
        except ValueError as error:
            raise _study_error(error, default="study_note_export_failed", not_found={"study_note_not_found"}) from None
        except (sqlite3.Error, TypeError):
            raise HTTPException(status_code=500, detail="study_note_export_failed") from None
    return context
