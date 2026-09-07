"""异步任务管理 API。

提供任务的查询、取消和重试操作。任务用于跟踪长时间运行的后台操作，
如材料索引、嵌入生成、报告生成等。

主要端点：
- GET /api/tasks - 查询任务列表（支持按状态/类型过滤）
- GET /api/tasks/{task_id} - 获取单个任务详情
- POST /api/tasks/{task_id}/cancel - 取消运行中的任务
- POST /api/tasks/{task_id}/retry - 重试失败的任务

关联模块：
- repositories.tasks - 任务数据访问层
- backend.app.task_runner - 任务执行引擎
"""

from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """注册任务管理相关路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（本模块未添加新的上下文项）
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    @app.get("/api/tasks")
    def task_list(status: str | None = None, task_kind: str | None = None,
                  operation_type: str | None = None, limit: int = 25,
                  offset: int = 0) -> dict[str, object]:
        """查询任务列表。
        
        支持按状态、任务类型、操作类型过滤，并提供分页。
        
        Args:
            status: 可选的任务状态过滤（"pending"|"running"|"completed"|"failed"）
            task_kind: 可选的任务类型过滤（如 "embedding"|"report_generation"）
            operation_type: 可选的操作类型过滤
            limit: 每页返回的最大任务数（默认 25，最大 100）
            offset: 分页偏移量（默认 0）
            
        Returns:
            包含任务列表和分页信息的字典：
            {
                "tasks": [
                    {
                        "id": str,
                        "status": str,
                        "task_kind": str,
                        "operation_type": str,
                        "created_at": str,
                        "updated_at": str,
                        "progress": int | None,
                        "error_code": str | None
                    },
                    ...
                ],
                "total": int,
                "limit": int,
                "offset": int
            }
            
        Raises:
            HTTPException(400): invalid_status/invalid_task_kind/invalid_limit - 参数无效
            HTTPException(500): task_list_failed - 数据库查询失败
        """
        try:
            with connect(app.state.config.database_path) as connection:
                return list_operation_tasks_public(connection, project_id=app.state.config.project_id,
                                                   status=status, task_kind=task_kind,
                                                   operation_type=operation_type, limit=limit, offset=offset)
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=400, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="task_list_failed") from None

    @app.get("/api/tasks/{task_id}")
    def task_status(task_id: str) -> dict[str, object]:
        """获取单个任务的详细状态。
        
        Args:
            task_id: 任务唯一标识符（长度 1-120 字符）
            
        Returns:
            任务详情字典：
            {
                "id": str,
                "status": "pending" | "running" | "completed" | "failed",
                "task_kind": str,
                "operation_type": str,
                "created_at": str (ISO 8601),
                "updated_at": str (ISO 8601),
                "started_at": str | None,
                "finished_at": str | None,
                "progress": int | None (0-100),
                "error_code": str | None,
                "error_message": str | None,
                "result": dict | None
            }
            
        Raises:
            HTTPException(404): task_not_found - 任务不存在或 task_id 格式无效
            HTTPException(409): task_access_denied - 任务属于其他项目
            HTTPException(500): task_read_failed - 数据库读取失败
        """
        if not task_id or len(task_id) > 120:
            raise HTTPException(status_code=404, detail="task_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                return get_operation_task_public(connection, task_id=task_id, project_id=app.state.config.project_id)
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "task_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="task_read_failed") from None

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str) -> dict[str, object]:
        """取消运行中或待处理的任务。
        
        只有 "pending" 或 "running" 状态的任务可以被取消。
        已完成或失败的任务不能取消。
        
        Args:
            task_id: 任务唯一标识符
            
        Returns:
            包含任务当前状态和取消结果的字典：
            {
                ...（任务详情字段）,
                "cancel_result": "cancelled" | "already_finished" | "not_cancellable"
            }
            
        Raises:
            HTTPException(404): task_not_found - 任务不存在
            HTTPException(409): task_already_finished - 任务已完成，无法取消
            HTTPException(409): task_not_cancellable - 任务类型不支持取消
            HTTPException(500): task_cancel_failed - 取消操作失败
            
        Side Effects:
            - 更新任务状态为 "failed"
            - 设置 error_code 为 "cancelled_by_user"
            - 记录 finished_at 时间戳
        """
        try:
            with connect(app.state.config.database_path) as connection:
                get_operation_task_public(connection, task_id=task_id, project_id=app.state.config.project_id)
                status = request_operation_task_cancel(connection, task_id=task_id)
                return {**get_operation_task_public(connection, task_id=task_id, project_id=app.state.config.project_id),
                        "cancel_result": status}
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "task_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="task_cancel_failed") from None

    @app.post("/api/tasks/{task_id}/retry")
    def retry_task(task_id: str) -> dict[str, object]:
        """重试失败的任务。
        
        只有 "failed" 状态的任务可以重试。
        重试会创建一个新的任务执行，保留原任务 ID。
        
        Args:
            task_id: 任务唯一标识符
            
        Returns:
            任务详情字典（状态重置为 "pending" 或 "running"）
            
        Raises:
            HTTPException(404): task_not_found - 任务不存在
            HTTPException(409): task_not_failed - 任务不是 "failed" 状态，无法重试
            HTTPException(409): task_retry_limit_exceeded - 超过最大重试次数
            HTTPException(500): task_retry_failed - 重试操作失败
            
        Side Effects:
            - 重置任务状态为 "pending"
            - 清除错误信息
            - 增加 retry_count
            - 通知 TaskRunner 重新执行任务
            
        Note:
            重试不会修改任务的 created_at，但会更新 updated_at。
            任务的 progress 和 result 会被清空。
        """
        try:
            with connect(app.state.config.database_path) as connection:
                get_operation_task_public(connection, task_id=task_id, project_id=app.state.config.project_id)
            runner = build_task_runner(app.state.config)
            runner.retry(task_id)
            with connect(app.state.config.database_path) as connection:
                return get_operation_task_public(connection, task_id=task_id, project_id=app.state.config.project_id)
        except TaskRunnerError as error:
            code = error.code
            raise HTTPException(status_code=404 if code == "task_not_found" else 409, detail=code) from None
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "task_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="task_retry_failed") from None
    return context
