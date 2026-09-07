"""学习内容生成 API。

提供 AI 驱动的学习内容生成功能，包括学习卡片和练习题的生成。
支持基于材料检索的上下文生成和幂等性控制。

生成流程：
1. 检索相关材料内容（混合检索或向量检索）
2. 构建生成提示词
3. 调用 LLM 提供商生成内容
4. 验证和持久化生成结果
5. 创建学习卡片或练习题

主要端点：
- POST /api/study/cards/generate - 生成学习卡片（推荐使用异步版本）
- POST /api/study/exercises/generate - 生成练习题（推荐使用异步版本）

关联模块：
- repositories.ai - AI 操作记录
- providers.llm - LLM 提供商
- repositories.learning - 学习卡片管理
- repositories.practice - 练习题管理
"""

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """注册学习内容生成相关路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（添加 generate_draft 辅助函数供其他模块使用）
    """
    
    def _generated_items(raw: str, *, artifact_kind: str, count: int) -> tuple[list[dict[str, object]], list[list[str]]]:
        """验证并解析生成的结构化响应。
        
        Args:
            raw: LLM 返回的原始 JSON 字符串
            artifact_kind: 生成类型（"card" | "exercise"）
            count: 期望生成的项目数量
            
        Returns:
            (items, citation_groups) 元组：
            - items: 验证后的生成项列表
            - citation_groups: 每个项的引用键列表
            
        Raises:
            ValueError: generation_schema_invalid - 响应格式不符合预期
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
        allowed = {"front", "back", "citations"} if artifact_kind == "card" else {
            "question", "options", "correct_option", "explanation", "citations"
        }
        for raw_item in raw_items:
            if not isinstance(raw_item, dict) or set(raw_item) != allowed:
                raise ValueError("generation_schema_invalid")
            if artifact_kind == "card":
                front = raw_item["front"]
                back = raw_item["back"]
                if not isinstance(front, str) or not isinstance(back, str) or not front or not back:
                    raise ValueError("generation_schema_invalid")
                if len(front) > 500 or len(back) > 2000:
                    raise ValueError("generation_schema_invalid")
                items.append({"front": front, "back": back})
            else:
                question = raw_item["question"]
                options = raw_item["options"]
                correct_option = raw_item["correct_option"]
                explanation = raw_item["explanation"]
                if not isinstance(question, str) or not isinstance(options, list) or not isinstance(correct_option, int) or not isinstance(explanation, str):
                    raise ValueError("generation_schema_invalid")
                if not question or len(question) > 1000 or len(options) != 4:
                    raise ValueError("generation_schema_invalid")
                if not all(isinstance(opt, str) and opt and len(opt) <= 500 for opt in options):
                    raise ValueError("generation_schema_invalid")
                if not (0 <= correct_option < 4) or not explanation or len(explanation) > 2000:
                    raise ValueError("generation_schema_invalid")
                items.append({
                    "question": question,
                    "options": options,
                    "correct_option": correct_option,
                    "explanation": explanation,
                })
            citations = raw_item["citations"]
            if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
                raise ValueError("generation_schema_invalid")
            citation_groups.append(list(citations))
        return items, citation_groups

    def generate_draft(
        *,
        artifact_kind: str,
        deck_id: str | None,
        exercise_set_id: str | None,
        request,
    ) -> dict[str, object]:
        """生成学习内容草稿（核心生成逻辑）。
        
        此函数被卡片生成和练习题生成端点共享。
        
        Args:
            artifact_kind: 生成类型（"card" | "exercise"）
            deck_id: 目标卡片组 ID（当 artifact_kind="card" 时必需）
            exercise_set_id: 目标练习集 ID（当 artifact_kind="exercise" 时必需）
            request: 生成请求对象，包含：
                - topic: str - 生成主题
                - count: int - 生成数量（1-10）
                - material_ids: list[str] | None - 限定的材料 ID 列表
                - retrieval_mode: str - 检索模式（"hybrid" | "vector"）
                - allow_retrieval_fallback: bool - 允许检索降级
                - idempotency_key: str | None - 幂等键
                
        Returns:
            生成结果字典：
            {
                "operation_id": str,
                "status": "completed",
                "artifact_kind": "card" | "exercise",
                "topic": str,
                "count": int,
                "retrieval_mode": str,
                "items": [
                    {
                        "id": str,
                        "front": str,  # 仅卡片
                        "back": str,   # 仅卡片
                        "question": str,  # 仅练习
                        "options": list[str],  # 仅练习
                        "correct_option": int,  # 仅练习
                        "explanation": str,  # 仅练习
                        "citations": list[{
                            "key": str,
                            "material_id": str,
                            "span_index": int
                        }]
                    },
                    ...
                ],
                "retrieval": {
                    "retrieved_count": int,
                    "mode": str
                },
                "created_at": str
            }
            
        Raises:
            HTTPException(400):
                - invalid_topic - 主题为空或过长
                - invalid_count - 数量不在 1-10 范围
                - generation_idempotency_key_invalid - 幂等键格式无效
            HTTPException(404):
                - deck_not_found - 卡片组不存在
                - exercise_set_not_found - 练习集不存在
                - material_not_found - 指定的材料不存在
                - source_deleted - 材料已删除
            HTTPException(409):
                - retrieval_not_ready - 材料尚未索引
                - retrieval_empty - 检索结果为空
                - generation_in_progress - 生成操作正在进行
                - generation_idempotency_key_mismatch - 幂等键冲突
            HTTPException(503): provider_not_configured - LLM 提供商未配置
            HTTPException(500): generation_failed - 生成失败
            
        Note:
            - 此函数是同步的，可能需要 5-30 秒（取决于 LLM 响应速度）
            - 幂等键在 24 小时内有效
            - 生成的内容会自动关联引用出处
            - 检索降级：当 allow_retrieval_fallback=true 且向量检索失败时，
              自动降级到混合检索
        """
        config = app.state.config
        operation: dict[str, object] | None = None
        try:
            with connect(config.database_path) as connection:
                if artifact_kind == "card":
                    from ..repository import get_deck
                    target = get_deck(connection, deck_id, project_id=config.project_id)
                    if target is None:
                        raise ValueError("deck_not_found")
                else:
                    from ..repository import get_exercise_set
                    target = get_exercise_set(connection, exercise_set_id, project_id=config.project_id)
                    if target is None:
                        raise ValueError("exercise_set_not_found")
                embedding_provider = None
                embedding_error_code = None
                try:
                    embedding_provider_id = config.embedding_provider_id or "fake"
                    embedding_provider = EmbeddingProviderRegistry(
                        embedding_provider_id, config.embedding_model_id,
                        model_revision=config.embedding_model_revision,
                        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                        max_batch_size=config.embedding_max_batch_size,
                        max_text_chars=config.embedding_max_text_chars,
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
                if retrieval["retrieved_count"] == 0:
                    raise ValueError("retrieval_empty")
                llm_provider_id = config.llm_provider_id or "fake"
                llm_provider = LLMProviderRegistry(
                    llm_provider_id, config.llm_model_id,
                    base_url=config.llm_base_url, api_key=config.llm_api_key,
                    timeout_seconds=config.llm_timeout_seconds,
                    max_retries=config.llm_max_retries,
                    max_output_tokens=config.llm_max_output_tokens,
                ).configured_provider()
                operation = create_generation_operation(
                    connection, project_id=config.project_id, artifact_kind=artifact_kind,
                    deck_id=deck_id, exercise_set_id=exercise_set_id, topic=request.topic,
                    count=request.count, retrieval_mode=retrieval["mode"],
                    idempotency_key=request.idempotency_key,
                )
                connection.commit()
                prompt_request = ProviderRequest(
                    question=request.topic,
                    context_blocks=retrieval["blocks"],
                    generation_kind=artifact_kind,
                    generation_count=request.count,
                )
                llm_result = llm_provider.answer(prompt_request)
                items, citation_groups = _generated_items(llm_result.answer_text, artifact_kind=artifact_kind, count=request.count)
                if artifact_kind == "card":
                    from ..repository import create_cards
                    cards = create_cards(connection, deck_id=deck_id, items=items, citation_groups=citation_groups,
                                       retrieval_context=retrieval["blocks"])
                    result_items = cards
                else:
                    from ..repository import create_exercises
                    exercises = create_exercises(connection, exercise_set_id=exercise_set_id, items=items,
                                               citation_groups=citation_groups, retrieval_context=retrieval["blocks"])
                    result_items = exercises
                finish_generation_operation(connection, str(operation["operation_id"]), status="succeeded")
        except HTTPException:
            raise
        except (ProviderError, EmbeddingError) as error:
            code = error.code
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_generation_operation(connection, str(operation["operation_id"]), code)
                except sqlite3.Error:
                    pass
            status = 503 if code == "provider_not_configured" else 500
            raise HTTPException(status_code=status, detail=code) from None
        except ValueError as error:
            code = str(error)
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_generation_operation(connection, str(operation["operation_id"]), code)
                except sqlite3.Error:
                    pass
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
        return {
            "operation_id": operation["operation_id"],
            "status": "completed",
            "artifact_kind": artifact_kind,
            "topic": request.topic,
            "count": len(result_items),
            "retrieval_mode": retrieval["mode"],
            "items": result_items,
            "retrieval": {
                "retrieved_count": retrieval["retrieved_count"],
                "mode": retrieval["mode"],
            },
            "created_at": operation["created_at"],
        }

    globals()['generate_draft'] = generate_draft
    context.update({'generate_draft': generate_draft})
    return context
