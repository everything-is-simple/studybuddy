from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/tasks/{task_id}")
    def task_status(task_id: str) -> dict[str, object]:
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
