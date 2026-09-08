"""学习内容生成 API。

提供 AI 驱动的学习内容生成功能，包括学习卡片和练习题的生成。
基于材料检索的上下文生成，带完整操作审计和幂等控制。

生成流程（generate_draft，卡片/练习端点共享）：
1. create_generation_operation: 创建操作记录（幂等指纹，重放命中直接返回）
2. 检索上下文：词法模式用 run_chunk_retrieval；
   向量/混合模式构造 EmbeddingProviderRegistry（失败按策略降级或抛出）
3. 持久化 retrieval_run 关联并 commit（Provider I/O 不跨写事务）
4. assemble_context 装配上下文块
5. provider_registry 构造 LLM Provider 并生成
6. _generated_items 验证结构化响应（12 KB 上限，白名单字段）
7. persist_generated_draft 原子写草稿 + 引用

错误处理：Provider/Embedding 失败和 ValueError 都会把操作标记为
failed 后转换为稳定 HTTP 错误码；SQLite 错误收敛为 500。

导出：generate_draft 同时注入 globals() 和 context，
供卡片/练习路由端点调用。
"""

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """注册学习内容生成共享逻辑。

    本模块不直接挂载 HTTP 端点，而是提供 generate_draft 共享函数
    （由 study_practice 等模块的生成端点调用）和 _generated_items
    响应验证器。

    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）

    Returns:
        更新后的上下文字典（添加 generate_draft 供其他模块使用）
    """

    def _generated_items(raw: str, *, artifact_kind: str, count: int) -> tuple[list[dict[str, object]], list[list[str]]]:
        """验证并解析生成的结构化响应（只在内存中验证，绝不持久化原始响应）。

        Args:
            raw: LLM 返回的原始 JSON 字符串
            artifact_kind: 生成类型（"card" | "exercise"）
            count: 期望生成的项目数量

        Returns:
            (items, citation_groups) 元组：
            - items: 验证后的生成项列表（不含 citations 键）
            - citation_groups: 每个项的引用键列表

        Raises:
            ValueError: generation_schema_invalid - 响应超限、JSON 非法、
                        字段不符合白名单或数量不匹配
        """
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
        """生成学习内容草稿（卡片/练习端点共享的核心逻辑）。

        创建幂等操作 → 检索上下文 → 调用 LLM → 验证响应 →
        原子持久化草稿。Provider I/O 不跨 SQLite 写事务。

        Args:
            artifact_kind: 生成类型（"card" | "exercise"）
            container_id: 目标容器 ID（卡片组或练习集）
            request: GenerationRequest（topic/count/material_ids/
                     retrieval_mode/allow_retrieval_fallback/...）
            idempotency_key: 可选幂等键（>200 字符或含控制字符拒绝）

        Returns:
            {status: "succeeded", operation_id, retrieval_run_id,
             artifacts, replay: False}；重放命中时返回已有操作

        Raises:
            HTTPException(400): generation_invalid_idempotency_key、
                                generation_schema_invalid 等 ValueError 映射
            HTTPException(404): deck_not_found/exercise_set_not_found 等
            HTTPException(409): retrieval_not_ready/retrieval_empty/
                                generation_in_progress 等
            HTTPException(503): Provider/Embedding 错误
            HTTPException(500): generation_failed（SQLite 错误）
        """
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
                # Provider I/O 不跨 SQLite 写事务；最终的操作/草稿/引用写入使用独立原子事务。
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
