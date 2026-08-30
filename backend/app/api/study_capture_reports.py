from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.post("/api/study/capture-sessions", status_code=201)
    def create_capture_session_endpoint(request: CaptureSessionRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_capture_session(
                    connection, project_id=app.state.config.project_id,
                    asset_kind=request.asset_kind, original_name=request.original_name,
                    media_type=request.media_type,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="capture_create_failed") from None

    @app.get("/api/study/capture-sessions")
    def capture_sessions(include_archived: bool = False, limit: int = 100,
                         offset: int = 0) -> dict[str, object]:
        if limit < 1 or limit > 100 or offset < 0:
            raise HTTPException(status_code=400, detail="invalid_pagination")
        try:
            with connect(app.state.config.database_path) as connection:
                items = list_capture_sessions(
                    connection, project_id=app.state.config.project_id,
                    include_archived=include_archived,
                )
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="capture_list_failed") from None
        page = items[offset:offset + limit]
        return {"items": page, "total": len(items), "limit": limit,
                "offset": offset, "has_more": offset + len(page) < len(items)}

    @app.get("/api/study/capture-sessions/{capture_id}")
    def capture_session(capture_id: str) -> dict[str, object]:
        if not capture_id or len(capture_id) > 120:
            raise HTTPException(status_code=404, detail="capture_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_capture_session(
                    connection, project_id=app.state.config.project_id,
                    capture_session_id=capture_id,
                )
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="capture_read_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="capture_not_found")
        return result

    @app.post("/api/study/capture-sessions/{capture_id}/upload")
    async def upload_capture_session_asset(
        capture_id: str,
        file: Annotated[UploadFile, File(...)],
    ) -> dict[str, object]:
        config = app.state.config
        temporary_path: Path | None = None
        try:
            with connect(config.database_path) as connection:
                capture = get_capture_session(
                    connection, project_id=config.project_id,
                    capture_session_id=capture_id,
                )
            if capture is None:
                raise HTTPException(status_code=404, detail="capture_not_found")
            config.data_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=config.data_root, prefix=".capture-incoming-", delete=False
            ) as handle:
                temporary_path = Path(handle.name)
                size = 0
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > config.max_upload_bytes:
                        raise HTTPException(status_code=413, detail="capture_asset_too_large")
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            with connect(config.database_path) as connection:
                return upload_capture_asset(
                    connection, project_id=config.project_id,
                    capture_session_id=capture_id, source_path=temporary_path,
                    original_name=capture["original_name"], media_type=capture["media_type"],
                    originals_root=config.originals_root,
                    max_upload_bytes=config.max_upload_bytes,
                )
        except HTTPException:
            raise
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except (OSError, sqlite3.Error):
            raise HTTPException(status_code=500, detail="capture_upload_failed") from None
        finally:
            await file.close()
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @app.post("/api/study/capture-sessions/{capture_id}/transcribe")
    def transcribe_capture_session_endpoint(
        capture_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        if idempotency_key is not None and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="invalid_idempotency_key")
        config = app.state.config
        try:
            provider_id = config.asr_provider_id or "fake"
            model_id = config.asr_model_id if config.asr_provider_id else "fake-capture-v1"
            provider = provider_registry(
                provider_id, model_id,
            ).capture_provider(
                runtime_path=str(config.asr_runtime_path) if config.asr_runtime_path else None,
                model_path=str(config.asr_model_path) if config.asr_model_path else None,
                timeout_seconds=config.asr_timeout_seconds,
                max_output_bytes=config.asr_max_output_bytes,
            )
            with connect(config.database_path) as connection:
                return transcribe_capture_session(
                    connection, project_id=config.project_id,
                    capture_session_id=capture_id, provider=provider,
                    idempotency_key=idempotency_key,
                    max_upload_bytes=config.max_upload_bytes,
                )
        except ProviderError as error:
            raise HTTPException(status_code=503, detail="transcription_provider_not_configured") from None
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="transcription_failed") from None

    @app.get("/api/study/capture-sessions/{capture_id}/transcript")
    def capture_transcript(capture_id: str) -> dict[str, object]:
        result = capture_session(capture_id)
        drafts = result.get("transcript_drafts")
        return {"capture_session_id": capture_id, "transcript_drafts": drafts}

    @app.post("/api/study/capture-sessions/{capture_id}/transcript/edit")
    def edit_capture_transcript(capture_id: str, request: TranscriptEditRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return edit_transcript_draft(
                    connection, project_id=app.state.config.project_id,
                    capture_session_id=capture_id, draft_id=request.draft_id, text=request.text,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="transcript_edit_failed") from None

    @app.post("/api/study/capture-sessions/{capture_id}/confirm")
    def confirm_capture_transcript(capture_id: str, request: TranscriptActionRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_transcript_draft(
                    connection, project_id=app.state.config.project_id,
                    capture_session_id=capture_id, draft_id=request.draft_id,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="transcript_confirm_failed") from None

    @app.post("/api/study/capture-sessions/{capture_id}/reject")
    def reject_capture_transcript(capture_id: str, request: TranscriptActionRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return reject_transcript_draft(
                    connection, project_id=app.state.config.project_id,
                    capture_session_id=capture_id, draft_id=request.draft_id,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="transcript_reject_failed") from None

    @app.post("/api/study/capture-sessions/{capture_id}/archive")
    def archive_capture(capture_id: str) -> dict[str, object]:
        # The 9D domain contract currently has no archive transaction. Do not
        # add a route-level SQL mutation; expose a stable boundary until the
        # lifecycle gate supplies that domain operation.
        if not capture_id or len(capture_id) > 120:
            raise HTTPException(status_code=404, detail="capture_not_found")
        raise HTTPException(status_code=409, detail="capture_invalid_state")

    @app.post("/api/study/reports", status_code=201)
    def create_study_report(
        request: ReportRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        if idempotency_key is not None and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="invalid_idempotency_key")
        try:
            with connect(app.state.config.database_path) as connection:
                return create_report_snapshot(
                    connection, project_id=app.state.config.project_id,
                    report_kind=request.report_kind, timezone_name=request.timezone,
                    period_start=request.period_start, period_end=request.period_end,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="report_generation_failed") from None

    @app.get("/api/study/reports")
    def study_reports(include_archived: bool = False, limit: int = 100,
                      offset: int = 0) -> dict[str, object]:
        if limit < 1 or limit > 100 or offset < 0:
            raise HTTPException(status_code=400, detail="invalid_pagination")
        try:
            with connect(app.state.config.database_path) as connection:
                items = list_report_snapshots(
                    connection, project_id=app.state.config.project_id,
                    include_archived=include_archived,
                )
        except (ValueError, sqlite3.Error) as error:
            if isinstance(error, ValueError):
                raise HTTPException(status_code=400, detail="report_redaction_violation") from None
            raise HTTPException(status_code=500, detail="report_list_failed") from None
        page = items[offset:offset + limit]
        return {"items": page, "total": len(items), "limit": limit,
                "offset": offset, "has_more": offset + len(page) < len(items)}

    @app.get("/api/study/reports/{report_id}")
    def study_report(report_id: str) -> dict[str, object]:
        if not report_id or len(report_id) > 120:
            raise HTTPException(status_code=404, detail="report_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_report_snapshot(
                    connection, project_id=app.state.config.project_id, report_id=report_id,
                )
        except ValueError as error:
            raise HTTPException(status_code=500, detail="report_redaction_violation") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="report_read_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="report_not_found")
        return result

    @app.get("/api/study/reports/{report_id}/preview")
    def preview_study_report(report_id: str) -> dict[str, object]:
        return study_report(report_id)

    @app.get("/api/study/reports/{report_id}/export")
    def export_study_report(report_id: str, format: str = "json") -> Response:
        if format not in {"json", "markdown"}:
            raise HTTPException(status_code=400, detail="report_redaction_violation")
        try:
            with connect(app.state.config.database_path) as connection:
                content, media_type = export_report_snapshot(
                    connection, project_id=app.state.config.project_id,
                    report_id=report_id, format_name=format,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="report_export_failed") from None
        suffix = "json" if format == "json" else "md"
        return Response(
            content=content, media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="studybuddy-report.{suffix}"'},
        )

    @app.post("/api/study/reports/{report_id}/delivery")
    def deliver_study_report(
        report_id: str,
        request: DeliveryRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, object]:
        if idempotency_key is not None and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="invalid_idempotency_key")
        try:
            with connect(app.state.config.database_path) as connection:
                return execute_report_delivery(
                    connection, config=app.state.config,
                    project_id=app.state.config.project_id, report_id=report_id,
                    channel=request.channel, target_label=request.target_label,
                    mode=request.mode, authorization_granted=request.authorization_granted,
                    idempotency_key=idempotency_key, retry_of=request.retry_of,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="delivery_failed") from None

    @app.get("/api/study/reports/{report_id}/delivery-attempts")
    def report_delivery_attempts(report_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                items = list_report_delivery_attempts(
                    connection, project_id=app.state.config.project_id, report_id=report_id,
                )
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=_phase9d_http_status(code), detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="delivery_audit_failed") from None
        return {"items": items}
    return context
