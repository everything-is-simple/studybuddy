"""AI 索引管理 API。

提供材料的 AI 索引（嵌入向量生成）操作，包括同步索引、异步任务队列和状态查询。

索引流程：
1. 验证材料存在且未删除
2. 获取最新的文本提取记录
3. 创建材料修订版本和文本块
4. 调用嵌入提供商生成向量
5. 存储向量到数据库

主要端点：
- POST /api/materials/{material_id}/ai-index - 同步索引（遗留接口）
- POST /api/materials/{material_id}/ai-index/tasks - 异步索引（推荐）
- GET /api/materials/{material_id}/ai-index - 查询索引状态

关联模块：
- repositories.materials - 材料数据访问
- repositories.ai_operations - AI 操作记录
- providers.embedding - 嵌入向量提供商
- backend.app.task_runner - 异步任务执行器
"""

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """注册 AI 索引相关路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（本模块未添加新的上下文项）
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    @app.post("/api/materials/{material_id}/ai-index")
    def index_material(material_id: str, retry: bool = False) -> dict[str, object]:
        """同步索引材料（遗留接口）。
        
        此端点在请求-响应周期内完成整个索引过程，包括：
        1. 创建材料修订版本
        2. 切分文本块
        3. 调用嵌入提供商生成向量
        4. 存储向量到数据库
        
        对于大文件或慢速提供商，建议使用 POST /ai-index/tasks 异步接口。
        
        Args:
            material_id: 材料 ID
            retry: 是否重试失败的索引（默认 False）
                   - True: 重试之前失败的嵌入操作
                   - False: 跳过已成功的块，仅索引新块
        
        Returns:
            索引结果字典：
            {
                "material_id": str,
                "status": "indexed" | "partial" | "failed",
                "chunks_count": int,
                "embedded_count": int,
                "failed_count": int,
                "revision_id": str,
                "index_operation_id": str,
                "embedding": {
                    "new_count": int,
                    "skipped_count": int,
                    "failed_count": int
                }
            }
        
        Raises:
            HTTPException(404): 
                - material_not_found - 材料不存在
                - source_deleted - 材料已被删除
                - extraction_not_found - 缺少文本提取记录
                - material_extraction_mismatch - 提取记录不匹配
            HTTPException(400): 参数无效或材料状态不允许索引
            HTTPException(500): ai_index_failed - 索引过程失败
        
        Note:
            - 此接口是同步的，可能需要较长时间（取决于文件大小和提供商响应速度）
            - 索引操作会创建持久化的 operation 记录，即使提供商失败也可以事后检查和重试
            - retry=True 会增加重试计数，用于追踪材料的索引历史
        """
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
        """将嵌入索引操作加入异步任务队列（推荐接口）。
        
        此端点立即返回，实际的嵌入向量生成在后台异步执行。适用于：
        - 大文件（需要较长时间生成嵌入）
        - 批量索引多个材料
        - 需要避免阻塞用户界面的场景
        
        修订版本创建和文本块切分仍在同步阶段完成，只有嵌入向量生成是异步的。
        
        Args:
            material_id: 材料 ID
            idempotency_key: 可选的幂等键（HTTP Header: Idempotency-Key）
                            - 用于防止重复提交
                            - 最大长度 200 字符
                            - 不能包含控制字符（ASCII < 32）
        
        Returns:
            任务信息字典：
            {
                "id": str,              # 任务 ID
                "status": "pending",    # 任务状态
                "task_kind": "embedding_index",
                "operation_type": str,
                "created_at": str,
                "updated_at": str,
                "progress": int | None,
                "error_code": str | None,
                "replay": bool          # True 表示幂等键匹配了已存在的任务
            }
        
        Raises:
            HTTPException(400): embedding_index_invalid_idempotency_key - 幂等键格式无效
            HTTPException(404): 
                - material_not_found - 材料不存在
                - source_deleted - 材料已被删除
                - extraction_not_found - 缺少文本提取记录
            HTTPException(409):
                - source_stale - 源文件已过期
                - embedding_index_idempotency_mismatch - 幂等键冲突（相同键，不同参数）
                - task_project_scope_violation - 任务项目作用域违规
            HTTPException(503): 嵌入提供商不可用
            HTTPException(500): embedding_index_enqueue_failed - 入队失败
        
        Note:
            - 推荐使用此接口而非同步 /ai-index
            - 幂等键在 24 小时内有效，相同的键多次调用返回同一个任务
            - 客户端应使用 GET /api/tasks/{task_id} 轮询任务状态
            - 任务失败后可以通过 POST /api/tasks/{task_id}/retry 重试
        """
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
        """查询材料的 AI 索引状态。
        
        返回材料当前的索引状态，包括文本块数量、嵌入向量数量、失败数量等。
        
        Args:
            material_id: 材料 ID
        
        Returns:
            索引状态字典：
            {
                "material_id": str,
                "status": "not_indexed" | "indexed" | "partial" | "failed",
                "chunks_count": int,        # 文本块总数
                "embedded_count": int,      # 已嵌入向量的块数
                "failed_count": int,        # 嵌入失败的块数
                "last_indexed_at": str | None,
                "provider_id": str | None,
                "model_id": str | None
            }
        
        Raises:
            HTTPException(404): material_not_found - 材料不存在
            HTTPException(500): ai_index_status_failed - 状态查询失败
        
        Note:
            - 此接口是只读的，不会触发索引操作
            - status 字段含义：
              * not_indexed: 从未索引过
              * indexed: 所有块都已成功嵌入
              * partial: 部分块已嵌入，部分失败或待处理
              * failed: 索引操作失败
        """
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_material_index_status(connection, material_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="ai_index_status_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return result
    return context
