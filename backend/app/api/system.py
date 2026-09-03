from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/liveness")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/metrics")
    def metrics() -> dict[str, object]:
        return metrics_snapshot()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        status, _reason = readiness_snapshot()
        if status != "ready":
            # Public health never exposes a database path, SQL, source content,
            # diagnostic exception, provider detail, or task identifiers.
            raise HTTPException(status_code=503, detail="service_degraded" if status == "degraded" else "service_not_ready")
        return {"status": "ok"}

    @app.get("/api/readiness")
    def readiness() -> dict[str, str]:
        status, reason = readiness_snapshot()
        if status == "ready":
            return {"status": "ready"}
        raise HTTPException(status_code=503, detail={"status": status, "reason": reason})

    @app.get("/api/ai/capabilities")
    def ai_capabilities() -> dict[str, object]:
        config = app.state.config
        if config.ai_provider_id == "fake":
            llm = provider_registry(config.ai_provider_id, config.ai_model_id).capabilities()
        else:
            llm = provider_registry(
                config.ai_provider_id, config.ai_model_id,
                base_url=config.ai_base_url, api_key=config.ai_api_key,
                timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries,
            ).capabilities()
        embedding_provider_id = config.embedding_provider_id
        embedding_model_id = config.embedding_model_id
        embedding = EmbeddingProviderRegistry(
            embedding_provider_id, embedding_model_id,
            model_revision=config.embedding_model_revision,
            base_url=config.embedding_base_url, api_key=config.embedding_api_key,
            timeout_seconds=config.embedding_timeout_seconds,
            max_batch_size=config.embedding_max_batch_size,
            max_text_chars=config.embedding_max_text_chars,
            max_dimensions=config.embedding_max_dimensions,
            max_response_bytes=config.embedding_max_response_bytes,
            max_retries=config.embedding_max_retries,
        ).capabilities()
        capture = provider_registry(
            config.asr_provider_id or "fake",
            config.asr_model_id if config.asr_provider_id else "fake-capture-v1",
        ).capture_capabilities(
            runtime_path=str(config.asr_runtime_path) if config.asr_runtime_path else None,
            model_path=str(config.asr_model_path) if config.asr_model_path else None,
            timeout_seconds=config.asr_timeout_seconds,
            max_output_bytes=config.asr_max_output_bytes,
        )
        ocr = {
            "status": "not_configured", "configured": False, "verification_status": "not_applicable",
            "runtime_kind": "none", "network_required": False, "provider_id": None,
            "model_id": None, "supports": {"ocr": False},
        }
        if config.ocr_enabled and config.ocr_provider_id == "paddleocr" and config.ocr_model_root:
            try:
                ocr_provider = provider_registry(
                    "paddleocr", config.ocr_model_id,
                ).capture_provider(
                    ocr_model_root=str(config.ocr_model_root),
                    timeout_seconds=config.ocr_timeout_seconds,
                    max_output_bytes=config.ocr_max_output_bytes,
                )
            except ProviderError:
                ocr_provider = None
            if ocr_provider is not None:
                ocr = {
                    "status": "configured", "configured": True, "verification_status": "unverified",
                    "runtime_kind": "local_model", "network_required": False,
                    "provider_id": "paddleocr", "model_id": config.ocr_model_id,
                    "supports": {"ocr": True},
                }
        # Preserve legacy top-level LLM fields while adding independent, safe
        # capability snapshots for optional subsystems.
        if embedding_provider_id is None:
            return {**llm, "capture": capture, "ocr": ocr}
        return {**llm, "llm": llm, "embedding": embedding, "capture": capture, "ocr": ocr}

    @app.post("/api/system/provider-connection-test")
    def provider_connection_test(request: ProviderConnectionTestRequest) -> dict[str, str]:
        """Test Provider (LLM/Embedding) connection with synthetic payload.

        Contract: P1-5-0 frozen, P1-5-2 implementation.
        - Explicitly triggered (never automatic)
        - Fixed synthetic payload
        - Does not change configuration state
        - Bounded response (1 KB max)
        - Stable error code mapping
        """
        try:
            if request.provider_type == "llm":
                provider_llm_connection_test(
                    base_url=request.base_url,
                    api_key=request.api_key,
                    model_id=request.model_id,
                    timeout_seconds=request.timeout_seconds or 30.0,
                )
            elif request.provider_type == "embedding":
                provider_embedding_connection_test(
                    base_url=request.base_url,
                    api_key=request.api_key,
                    model_id=request.model_id,
                    timeout_seconds=request.timeout_seconds or 30.0,
                )
            else:
                raise HTTPException(status_code=400, detail="invalid_provider_type")
            return {"status": "ok"}
        except HTTPException:
            raise
        except ConnectionTestError as error:
            raise HTTPException(status_code=400, detail=error.code) from None
        except Exception:
            raise HTTPException(status_code=500, detail="connection_test_failed") from None

    @app.post("/api/system/email-connection-test")
    def email_connection_test(request: EmailConnectionTestRequest) -> dict[str, str]:
        """Test Email (SMTP/Feishu) connection with synthetic payload.

        Contract: P1-5-0 frozen, P1-5-2 implementation.
        - Explicitly triggered (never automatic)
        - Fixed synthetic payload
        - Does not change configuration state
        - Bounded response (1 KB max)
        - Stable error code mapping
        """
        try:
            if request.channel == "smtp":
                if not request.smtp_host or not request.smtp_port or request.smtp_sender is None or request.smtp_recipient is None:
                    raise HTTPException(status_code=400, detail="delivery_configuration_invalid")
                smtp_connection_test(
                    host=request.smtp_host,
                    port=request.smtp_port,
                    secure=request.smtp_secure if request.smtp_secure is not None else True,
                    username=request.smtp_username,
                    password=request.smtp_password,
                    sender=request.smtp_sender,
                    recipient=request.smtp_recipient,
                    timeout_seconds=request.timeout_seconds or 10.0,
                )
            elif request.channel == "feishu":
                if not request.feishu_webhook:
                    raise HTTPException(status_code=400, detail="delivery_configuration_invalid")
                feishu_connection_test(
                    webhook_url=request.feishu_webhook,
                    timeout_seconds=request.timeout_seconds or 10.0,
                )
            else:
                raise HTTPException(status_code=400, detail="invalid_channel")
            return {"status": "ok"}
        except ConnectionTestError as error:
            raise HTTPException(status_code=400, detail=error.code) from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="connection_test_failed") from None

    return context
