from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    def _bounded_id(value: str, code: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 255 or any(ord(char) < 32 for char in value):
            raise HTTPException(status_code=404, detail=code)
        return value

    @app.get("/api/study/plans/{plan_id}/rhythm")
    def get_study_rhythm_route(plan_id: str) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                if get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id) is None:
                    raise ValueError("study_rhythm_plan_not_found")
                settings = get_rhythm_settings(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                return {"status": "configured", "plan_id": plan_id, "settings": settings} if settings else {
                    "status": "not_configured", "plan_id": plan_id, "settings": None,
                }
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_not_found", not_found={"study_rhythm_plan_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_summary_failed") from None

    @app.put("/api/study/plans/{plan_id}/rhythm")
    def save_study_rhythm_route(plan_id: str, request: RhythmSettingsRequest) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                settings = save_rhythm_settings(connection, project_id=app.state.config.project_id, plan_id=plan_id,
                                                 cadence=request.cadence, timezone_name=request.timezone,
                                                 period_start=request.period_start, target_minutes=request.target_minutes)
                return {"status": "configured", "plan_id": plan_id, "settings": settings}
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_persist_failed",
                               not_found={"study_rhythm_plan_not_found"},
                               conflict={"study_rhythm_edit_not_allowed", "study_rhythm_allocation_limit_exceeded"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_persist_failed") from None

    @app.get("/api/study/plans/{plan_id}/rhythm/weekly-trend")
    def study_weekly_trend_route(plan_id: str, local_date: str | None = None) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, 'study_rhythm_plan_not_found')
        try:
            with connect(app.state.config.database_path) as connection:
                return study_weekly_trend(connection, project_id=app.state.config.project_id,
                                           plan_id=plan_id, local_date=local_date)
        except ValueError as error:
            raise _study_error(error, default='study_rhythm_summary_failed',
                               not_found={'study_rhythm_plan_not_found'}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail='study_rhythm_summary_failed') from None

    @app.get("/api/study/plans/{plan_id}/rhythm/summary")
    def study_rhythm_summary_route(plan_id: str, local_date: str | None = None, periods: int = 1) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                return rhythm_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id,
                                      local_date=local_date, periods=periods)
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_summary_failed",
                               not_found={"study_rhythm_plan_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_summary_failed") from None

    @app.get("/api/study/plans/{plan_id}/rhythm/allocations")
    def list_study_rhythm_allocations_route(plan_id: str) -> list[dict[str, object]]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                if get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id) is None:
                    raise ValueError("study_rhythm_plan_not_found")
                return list_rhythm_allocations(connection, project_id=app.state.config.project_id, plan_id=plan_id)
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_allocation_not_found",
                               not_found={"study_rhythm_plan_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_summary_failed") from None

    @app.post("/api/study/plans/{plan_id}/rhythm/allocations", status_code=201)
    def create_study_rhythm_allocation_route(plan_id: str, request: RhythmAllocationRequest) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                return create_rhythm_allocation(connection, project_id=app.state.config.project_id, plan_id=plan_id,
                                                item_id=request.item_id, local_date=request.local_date,
                                                planned_minutes=request.planned_minutes)
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_invalid_payload",
                               not_found={"study_rhythm_plan_not_found", "study_rhythm_item_not_found"},
                               conflict={"study_rhythm_allocation_duplicate", "study_rhythm_allocation_limit_exceeded",
                                         "study_rhythm_edit_not_allowed", "study_rhythm_not_configured"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_persist_failed") from None

    @app.patch("/api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}")
    def update_study_rhythm_allocation_route(plan_id: str, allocation_id: str,
                                             request: RhythmAllocationPatchRequest) -> dict[str, object]:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        allocation_id = _bounded_id(allocation_id, "study_rhythm_allocation_not_found")
        if request.local_date is None and request.planned_minutes is None:
            raise HTTPException(status_code=400, detail="study_rhythm_invalid_payload")
        try:
            with connect(app.state.config.database_path) as connection:
                return update_rhythm_allocation(connection, project_id=app.state.config.project_id, plan_id=plan_id,
                                                allocation_id=allocation_id, local_date=request.local_date,
                                                planned_minutes=request.planned_minutes)
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_persist_failed",
                               not_found={"study_rhythm_allocation_not_found", "study_rhythm_plan_not_found"},
                               conflict={"study_rhythm_allocation_duplicate", "study_rhythm_allocation_limit_exceeded",
                                         "study_rhythm_edit_not_allowed", "study_rhythm_not_configured"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_persist_failed") from None

    @app.delete("/api/study/plans/{plan_id}/rhythm/allocations/{allocation_id}", status_code=204)
    def delete_study_rhythm_allocation_route(plan_id: str, allocation_id: str) -> Response:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        allocation_id = _bounded_id(allocation_id, "study_rhythm_allocation_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                delete_rhythm_allocation(connection, project_id=app.state.config.project_id, plan_id=plan_id,
                                         allocation_id=allocation_id)
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_persist_failed",
                               not_found={"study_rhythm_allocation_not_found", "study_rhythm_plan_not_found"},
                               conflict={"study_rhythm_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_rhythm_persist_failed") from None
        return Response(status_code=204)

    @app.get("/api/study/plans/{plan_id}/rhythm/export")
    def export_study_rhythm_route(plan_id: str, format: str = "json") -> Response:
        plan_id = _bounded_id(plan_id, "study_rhythm_plan_not_found")
        if format != "json":
            raise HTTPException(status_code=400, detail="study_rhythm_invalid_payload")
        try:
            with connect(app.state.config.database_path) as connection:
                plan = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                if plan is None:
                    raise ValueError("study_rhythm_plan_not_found")
                payload = {"format_version": "phase9b-rhythm-v1", "exported_at": utc_now(),
                           "plan": {"id": plan["id"], "title": plan["title"], "status": plan["status"]},
                           "settings": get_rhythm_settings(connection, project_id=app.state.config.project_id, plan_id=plan_id),
                           "allocations": list_rhythm_allocations(connection, project_id=app.state.config.project_id, plan_id=plan_id),
                           "summary": rhythm_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id)}
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if len(data.encode("utf-8")) > 256 * 1024:
                raise HTTPException(status_code=413, detail="study_rhythm_export_failed")
            return Response(content=data, media_type="application/json",
                            headers={"Content-Disposition": 'attachment; filename="studybuddy-rhythm.json"'})
        except HTTPException:
            raise
        except ValueError as error:
            raise _study_error(error, default="study_rhythm_export_failed", not_found={"study_rhythm_plan_not_found"}) from None
        except (sqlite3.Error, TypeError):
            raise HTTPException(status_code=500, detail="study_rhythm_export_failed") from None

    globals()['_bounded_id'] = _bounded_id
    context.update({'_bounded_id': _bounded_id})
    return context
