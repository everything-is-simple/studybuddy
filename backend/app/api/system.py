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
        # Preserve the legacy response exactly until embedding is explicitly configured.
        if embedding_provider_id is None:
            return llm
        return {**llm, "llm": llm, "embedding": embedding}
    return context
