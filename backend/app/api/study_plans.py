from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/study/goals")
    def study_goals(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_learning_goals(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/goals", status_code=201)
    def create_study_goal(request: StudyGoalRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_learning_goal(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_goal_create_failed", not_found={"project_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_create_failed") from None

    @app.get("/api/study/goals/{goal_id}")
    def get_study_goal(goal_id: str) -> dict[str, object]:
        if not goal_id or len(goal_id) > 100:
            raise HTTPException(status_code=404, detail="learning_goal_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        if result is None:
            raise HTTPException(status_code=404, detail="learning_goal_not_found")
        return result

    @app.patch("/api/study/goals/{goal_id}")
    def patch_study_goal(goal_id: str, request: StudyGoalRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_goal_update_failed", not_found={"learning_goal_not_found"}, conflict={"learning_goal_archived"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_update_failed") from None

    @app.post("/api/study/goals/{goal_id}/archive")
    def archive_study_goal(goal_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        except ValueError as error:
            raise _study_error(error, default="study_goal_archive_failed", not_found={"learning_goal_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_archive_failed") from None

    @app.get("/api/study/modules")
    def study_modules(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_knowledge_modules(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/modules", status_code=201)
    def create_study_module(request: StudyModuleRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_knowledge_module(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_module_create_failed", not_found={"project_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_create_failed") from None

    @app.get("/api/study/modules/{module_id}")
    def get_study_module(module_id: str) -> dict[str, object]:
        if not module_id or len(module_id) > 100:
            raise HTTPException(status_code=404, detail="knowledge_module_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id)
        if result is None:
            raise HTTPException(status_code=404, detail="knowledge_module_not_found")
        return result

    @app.patch("/api/study/modules/{module_id}")
    def patch_study_module(module_id: str, request: StudyModuleRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_module_update_failed", not_found={"knowledge_module_not_found"}, conflict={"knowledge_module_archived"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_update_failed") from None

    @app.post("/api/study/modules/{module_id}/archive")
    def archive_study_module(module_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id)
        except ValueError as error:
            raise _study_error(error, default="study_module_archive_failed", not_found={"knowledge_module_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_archive_failed") from None

    @app.get("/api/study/plans")
    def study_plans(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_study_plans(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/plans", status_code=201)
    def create_study_plan_route(request: StudyPlanRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_study_plan(connection, project_id=app.state.config.project_id, goal_id=request.goal_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_plan_create_failed", not_found={"project_not_found"}, conflict={"learning_goal_archived", "study_plan_goal_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_create_failed") from None

    @app.get("/api/study/plans/{plan_id}")
    def get_study_plan_route(plan_id: str) -> dict[str, object]:
        if not plan_id or len(plan_id) > 100:
            raise HTTPException(status_code=404, detail="study_plan_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
        if result is None:
            raise HTTPException(status_code=404, detail="study_plan_not_found")
        return result

    @app.patch("/api/study/plans/{plan_id}")
    def patch_study_plan_route(plan_id: str, request: StudyPlanPatchRequest) -> dict[str, object]:
        if request.title is None and request.description is None:
            raise HTTPException(status_code=400, detail="study_plan_invalid_payload")
        try:
            with connect(app.state.config.database_path) as connection:
                return update_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_plan_update_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_update_failed") from None

    def _transition_plan_route(plan_id: str, target: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id, target=target)
        except ValueError as error:
            raise _study_error(error, default="study_plan_transition_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_invalid_state", "study_plan_confirm_required"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_transition_failed") from None

    @app.post("/api/study/plans/{plan_id}/confirm")
    def confirm_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "confirmed")

    @app.post("/api/study/plans/{plan_id}/activate")
    def activate_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "active")

    @app.post("/api/study/plans/{plan_id}/pause")
    def pause_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "paused")

    @app.post("/api/study/plans/{plan_id}/complete")
    def complete_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "completed")

    @app.post("/api/study/plans/{plan_id}/archive")
    def archive_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "archived")

    @app.post("/api/study/plans/{plan_id}/items", status_code=201)
    def create_study_plan_item_route(plan_id: str, request: StudyPlanItemRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_create_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_create_failed") from None

    @app.patch("/api/study/plans/{plan_id}/items/{item_id}")
    def patch_study_plan_item_route(plan_id: str, item_id: str, request: StudyPlanItemPatchRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_update_failed", not_found={"study_plan_not_found", "study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_plan_item_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_update_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/archive")
    def archive_study_plan_item_route(plan_id: str, item_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id)
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_archive_failed", not_found={"study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_plan_item_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_archive_failed") from None

    @app.post("/api/study/plans/{plan_id}/dependencies", status_code=201)
    def add_study_dependency_route(plan_id: str, request: StudyDependencyRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return add_study_plan_dependency(connection, project_id=app.state.config.project_id, plan_id=plan_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_dependency_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_dependency_invalid", "study_plan_dependency_cycle", "study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_dependency_failed") from None

    @app.delete("/api/study/plans/{plan_id}/dependencies/{dependency_id}", status_code=204)
    def remove_study_dependency_route(plan_id: str, dependency_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                remove_study_plan_dependency(connection, project_id=app.state.config.project_id, plan_id=plan_id, dependency_id=dependency_id)
        except ValueError as error:
            raise _study_error(error, default="study_plan_dependency_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_dependency_invalid", "study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_dependency_failed") from None
        return Response(status_code=204)

    @app.get("/api/study/plans/{plan_id}/progress")
    def study_progress_route(plan_id: str, item_id: str | None = None) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                plan = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                if plan is None:
                    raise ValueError("study_plan_not_found")
                return {"plan_id": plan_id, "events": list_study_progress_events(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id), "summary": study_progress_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id)}
        except ValueError as error:
            raise _study_error(error, default="study_progress_read_failed", not_found={"study_plan_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_progress_read_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/progress", status_code=201)
    def append_study_progress_route(plan_id: str, item_id: str, request: StudyProgressRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                plan = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                if plan is None:
                    raise ValueError("study_plan_not_found")
                if not any(str(item.get("id")) == item_id for item in plan["items"]):
                    raise ValueError("study_plan_item_not_found")
                event = append_study_progress_event(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, **request.model_dump())
                return {"event": event, "summary": study_progress_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id)}
        except ValueError as error:
            raise _study_error(error, default="study_progress_failed", not_found={"study_plan_not_found", "study_plan_item_not_found"}, conflict={"study_progress_invalid_event", "study_progress_event_duplicate"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_progress_failed") from None

    @app.post("/api/study/modules/{module_id}/sources", status_code=201)
    def create_module_source_route(module_id: str, request: StudySourceLinkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_module_source_link(connection, project_id=app.state.config.project_id, module_id=module_id, payload=request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_source_create_failed", not_found={"knowledge_module_not_found"}, conflict={"knowledge_module_archived", "study_source_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_create_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/sources", status_code=201)
    def create_item_source_route(plan_id: str, item_id: str, request: StudySourceLinkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_plan_item_source_link(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, payload=request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_source_create_failed", not_found={"study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_source_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_create_failed") from None

    @app.delete("/api/study/modules/{module_id}/sources/{link_id}", status_code=204)
    def delete_module_source_route(module_id: str, link_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                delete_module_source_link(connection, project_id=app.state.config.project_id, module_id=module_id, link_id=link_id)
        except ValueError as error:
            raise _study_error(error, default="study_source_delete_failed", not_found={"knowledge_module_not_found", "study_source_link_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_delete_failed") from None
        return Response(status_code=204)

    @app.delete("/api/study/plans/{plan_id}/items/{item_id}/sources/{link_id}", status_code=204)
    def delete_item_source_route(plan_id: str, item_id: str, link_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                delete_plan_item_source_link(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, link_id=link_id)
        except ValueError as error:
            raise _study_error(error, default="study_source_delete_failed", not_found={"study_plan_item_not_found", "study_source_link_not_found"}, conflict={"study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_delete_failed") from None
        return Response(status_code=204)

    @app.get("/api/study/source-candidates")
    def study_source_candidates() -> list[dict[str, object]]:
        try:
            with connect(app.state.config.database_path) as connection:
                return list_study_source_candidates(connection, project_id=app.state.config.project_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_candidates_failed") from None

    @app.get("/api/study/sources")
    def study_sources(module_id: str | None = None, plan_id: str | None = None, item_id: str | None = None) -> list[dict[str, object]]:
        if module_id and (plan_id or item_id):
            raise HTTPException(status_code=400, detail="study_source_invalid_scope")
        try:
            with connect(app.state.config.database_path) as connection:
                return get_study_source_links(connection, project_id=app.state.config.project_id, module_id=module_id, plan_id=plan_id, item_id=item_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_read_failed") from None

    @app.post("/api/study/sources/refresh")
    def refresh_study_sources() -> dict[str, int]:
        try:
            with connect(app.state.config.database_path) as connection:
                return {"updated": refresh_study_source_links(connection, project_id=app.state.config.project_id)}
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_refresh_failed") from None

    globals()['_transition_plan_route'] = _transition_plan_route
    context.update({'_transition_plan_route': _transition_plan_route})
    return context
