from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    def _study_error(error: ValueError, *, default: str, not_found: set[str] | None = None,
                     conflict: set[str] | None = None) -> HTTPException:
        code = str(error)
        if not code or len(code) > 100 or any(ord(char) < 32 for char in code):
            code = default
        if code in (not_found or set()):
            status = 404
        elif code in (conflict or set()):
            status = 409
        else:
            status = 400
        return HTTPException(status_code=status, detail=code)

    def _phase9c_error(error: ValueError, *, default: str,
                       not_found: set[str] | None = None,
                       conflict: set[str] | None = None) -> HTTPException:
        return _study_error(error, default=default, not_found=not_found, conflict=conflict or {
            "practice_session_invalid_state", "practice_session_expired", "practice_session_item_not_found",
            "practice_submission_idempotency_mismatch", "review_not_allowed", "review_duplicate",
            "mistake_invalid_state", "mistake_archived", "cram_goal_invalid_state", "cram_goal_not_ready",
            "cram_session_scope_conflict", "cram_scope_conflict",
        })

    @app.get("/api/study/practice-recommendations")
    def study_practice_recommendations(limit: int = 10, weak_point: str | None = None) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return recommend_practice_exercises(connection, project_id=app.state.config.project_id,
                                                    limit=limit, weak_point=weak_point)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_recommendation_failed") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_recommendation_failed") from None

    @app.get("/api/study/practice-sessions")
    def study_practice_sessions(status: str | None = None) -> list[dict[str, object]]:
        try:
            with connect(app.state.config.database_path) as connection:
                return list_practice_sessions(connection, project_id=app.state.config.project_id, status=status)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_list_failed") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_list_failed") from None

    @app.post("/api/study/practice-sessions", status_code=201)
    def create_study_practice_session(request: PracticeSessionRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_practice_session(
                    connection, project_id=app.state.config.project_id, title=request.title,
                    exercise_ids=request.exercise_ids, duration_seconds=request.duration_seconds,
                    timezone_name=request.timezone, local_date=request.local_date,
                )
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_create_failed",
                                 not_found={"project_not_found", "exercise_not_ready"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_create_failed") from None

    @app.get("/api/study/practice-sessions/{session_id}")
    def get_study_practice_session(session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
            if result is None:
                raise HTTPException(status_code=404, detail="practice_session_not_found")
            return result
        except HTTPException:
            raise
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_read_failed") from None

    @app.post("/api/study/practice-sessions/{session_id}/start")
    def start_study_practice_session(session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return start_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_start_failed", not_found={"practice_session_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_start_failed") from None

    @app.post("/api/study/practice-sessions/{session_id}/items/{item_id}/submit")
    def submit_study_practice_item(session_id: str, item_id: str, request: PracticeSubmitRequest,
                                   idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return submit_practice_session_item(
                    connection, project_id=app.state.config.project_id, session_id=session_id,
                    item_id=item_id, answer=request.answer, submission_key=idempotency_key,
                )
        except ValueError as error:
            raise _phase9c_error(error, default="practice_submit_failed",
                                 not_found={"practice_session_not_found", "practice_session_item_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_submit_failed") from None

    @app.post("/api/study/practice-sessions/{session_id}/finish")
    def finish_study_practice_session(session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return finish_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_finish_failed", not_found={"practice_session_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_finish_failed") from None

    @app.post("/api/study/practice-sessions/{session_id}/archive")
    def archive_study_practice_session(session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_archive_failed", not_found={"practice_session_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_archive_failed") from None

    @app.get("/api/study/practice-sessions/{session_id}/result")
    def get_study_practice_result(session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_practice_result(connection, project_id=app.state.config.project_id, session_id=session_id)
            if result is None:
                raise HTTPException(status_code=404, detail="practice_session_not_found")
            return result
        except HTTPException:
            raise
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_result_read_failed") from None

    @app.get("/api/study/mistakes")
    def study_mistakes() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_mistake_cases(connection, project_id=app.state.config.project_id)

    @app.get("/api/study/mistakes/{mistake_id}")
    def get_study_mistake(mistake_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            result = get_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        if result is None:
            raise HTTPException(status_code=404, detail="mistake_not_found")
        return result

    @app.post("/api/study/attempts/{attempt_id}/review")
    def review_study_attempt(attempt_id: str, request: AttemptReviewRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return review_exercise_attempt(connection, project_id=app.state.config.project_id,
                                               attempt_id=attempt_id, decision=request.decision, feedback=request.feedback)
        except ValueError as error:
            raise _phase9c_error(error, default="attempt_review_failed", not_found={"attempt_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="attempt_review_failed") from None

    @app.post("/api/study/attempts/{attempt_id}/mark-mistake")
    def mark_study_attempt_mistake(attempt_id: str, request: MistakeMarkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return mark_mistake_from_attempt(connection, project_id=app.state.config.project_id,
                                                 attempt_id=attempt_id, feedback=request.feedback)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_mark_failed", not_found={"attempt_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_mark_failed") from None

    @app.get("/api/study/weak-points")
    def study_weak_points() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_weak_points(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/mistakes/{mistake_id}/feedback", status_code=201)
    def create_study_mistake_feedback(mistake_id: str, request: MistakeFeedbackRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return add_mistake_feedback(connection, project_id=app.state.config.project_id,
                                            mistake_case_id=mistake_id, event_kind=request.event_kind, content=request.content)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_feedback_failed", not_found={"mistake_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_feedback_failed") from None

    @app.post("/api/study/mistakes/{mistake_id}/redo")
    def redo_study_mistake(mistake_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return redo_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_redo_failed", not_found={"mistake_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_redo_failed") from None

    @app.post("/api/study/mistakes/{mistake_id}/archive")
    def archive_study_mistake(mistake_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_archive_failed", not_found={"mistake_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_archive_failed") from None

    @app.get("/api/study/cram-goals")
    def study_cram_goals(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_cram_goals(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/cram-goals", status_code=201)
    def create_study_cram_goal(request: CramGoalRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_cram_goal(connection, project_id=app.state.config.project_id, title=request.title,
                                        target_date=request.target_date, timezone_name=request.timezone,
                                        target_exercise_count=request.target_exercise_count, plan_id=request.plan_id,
                                        plan_item_id=request.plan_item_id)
        except ValueError as error:
            raise _phase9c_error(error, default="cram_goal_create_failed", not_found={"project_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="cram_goal_create_failed") from None

    @app.get("/api/study/cram-goals/{goal_id}")
    def get_study_cram_goal(goal_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            result = get_cram_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        if result is None:
            raise HTTPException(status_code=404, detail="cram_goal_not_found")
        return result

    def _transition_study_cram_goal(goal_id: str, target: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_cram_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id, target=target)
        except ValueError as error:
            raise _phase9c_error(error, default="cram_goal_transition_failed", not_found={"cram_goal_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="cram_goal_transition_failed") from None

    @app.post("/api/study/cram-goals/{goal_id}/active")
    def activate_study_cram_goal(goal_id: str) -> dict[str, object]:
        return _transition_study_cram_goal(goal_id, "active")

    @app.post("/api/study/cram-goals/{goal_id}/completed")
    def complete_study_cram_goal(goal_id: str) -> dict[str, object]:
        return _transition_study_cram_goal(goal_id, "completed")

    @app.post("/api/study/cram-goals/{goal_id}/archived")
    def archive_study_cram_goal(goal_id: str) -> dict[str, object]:
        return _transition_study_cram_goal(goal_id, "archived")

    @app.post("/api/study/cram-goals/{goal_id}/sessions", status_code=201)
    def create_study_cram_session(goal_id: str, request: CramSessionRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_cram_session(connection, project_id=app.state.config.project_id, goal_id=goal_id,
                                            title=request.title, exercise_ids=request.exercise_ids,
                                            duration_seconds=request.duration_seconds, timezone_name=request.timezone,
                                            local_date=request.local_date)
        except ValueError as error:
            raise _phase9c_error(error, default="cram_session_create_failed", not_found={"cram_goal_not_found", "exercise_not_ready"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="cram_session_create_failed") from None

    @app.get("/api/study/cram-goals/{goal_id}/sessions/{session_id}/result")
    def get_study_cram_result(goal_id: str, session_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_cram_result(connection, project_id=app.state.config.project_id, goal_id=goal_id, session_id=session_id)
            if result is None:
                raise HTTPException(status_code=404, detail="cram_goal_not_found")
            return result
        except HTTPException:
            raise
        except ValueError as error:
            raise _phase9c_error(error, default="cram_result_read_failed", not_found={"cram_goal_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="cram_result_read_failed") from None

    globals()['_study_error'] = _study_error
    globals()['_phase9c_error'] = _phase9c_error
    globals()['_transition_study_cram_goal'] = _transition_study_cram_goal
    context.update({'_study_error': _study_error, '_phase9c_error': _phase9c_error, '_transition_study_cram_goal': _transition_study_cram_goal})
    return context
