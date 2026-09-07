"""Study practice, mistake tracking, and cram goal routes.

Provides REST endpoints for practice sessions (exercise drills with timed tracking),
mistake cases (wrong answers with review feedback), weak points (aggregated error patterns),
and cram goals (intensive study targets with deadline-driven sessions).

All routes enforce project_id isolation and validate state transitions.
"""
from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    """Register study practice routes with shared context.
    
    Args:
        app: FastAPI application instance
        context: Shared context dict (connection helpers, error mappers)
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    recommend_practice_exercises = context.get("recommend_practice_exercises")
    
    def _study_error(error: ValueError, *, default: str, not_found: set[str] | None = None,
                     conflict: set[str] | None = None) -> HTTPException:
        """Map ValueError to HTTPException with appropriate status code.
        
        Args:
            error: ValueError with error code as str(error)
            default: Fallback code if error message is invalid
            not_found: Set of codes that map to 404
            conflict: Set of codes that map to 409
            
        Returns:
            HTTPException with status 400/404/409 and sanitized detail
        """
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
        """Map ValueError to HTTPException with phase9c-specific conflict codes.
        
        Adds practice_session_*, mistake_*, cram_* conflict codes to the standard set.
        """
        return _study_error(error, default=default, not_found=not_found, conflict=conflict or {
            "practice_session_invalid_state", "practice_session_expired", "practice_session_item_not_found",
            "practice_submission_idempotency_mismatch", "review_not_allowed", "review_duplicate",
            "mistake_invalid_state", "mistake_archived", "cram_goal_invalid_state", "cram_goal_not_ready",
            "cram_session_scope_conflict", "cram_scope_conflict",
        })

    @app.get("/api/study/practice-recommendations")
    def study_practice_recommendations(limit: int = 10, weak_point: str | None = None) -> dict[str, object]:
        """Get recommended exercises for practice (weak-point-aware).
        
        Returns up to `limit` exercises prioritized by weak points, mistake frequency,
        and time since last practice.
        """
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
        """List practice sessions, optionally filtered by status."""
        try:
            with connect(app.state.config.database_path) as connection:
                return list_practice_sessions(connection, project_id=app.state.config.project_id, status=status)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_list_failed") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_list_failed") from None

    @app.post("/api/study/practice-sessions", status_code=201)
    def create_study_practice_session(request: PracticeSessionRequest) -> dict[str, object]:
        """Create a new practice session with exercise list and duration.
        
        Validates exercises are confirmed and links session to optional plan/date.
        """
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
        """Get details for a specific practice session."""
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
        """Start a practice session (transition pending → in_progress)."""
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
        """Submit an answer for a practice session item.
        
        Idempotency-Key header prevents duplicate submissions for the same attempt.
        """
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
        """Finish a practice session (transition in_progress → finished)."""
        try:
            with connect(app.state.config.database_path) as connection:
                return finish_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_finish_failed", not_found={"practice_session_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_finish_failed") from None

    @app.post("/api/study/practice-sessions/{session_id}/archive")
    def archive_study_practice_session(session_id: str) -> dict[str, object]:
        """Archive a finished practice session."""
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_practice_session(connection, project_id=app.state.config.project_id, session_id=session_id)
        except ValueError as error:
            raise _phase9c_error(error, default="practice_session_archive_failed", not_found={"practice_session_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="practice_session_archive_failed") from None

    @app.get("/api/study/practice-sessions/{session_id}/result")
    def get_study_practice_result(session_id: str) -> dict[str, object]:
        """Get aggregated result for a finished practice session."""
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
        """List all mistake cases (wrong answers requiring review)."""
        with connect(app.state.config.database_path) as connection:
            return list_mistake_cases(connection, project_id=app.state.config.project_id)

    @app.get("/api/study/mistakes/{mistake_id}")
    def get_study_mistake(mistake_id: str) -> dict[str, object]:
        """Get details for a specific mistake case."""
        with connect(app.state.config.database_path) as connection:
            result = get_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        if result is None:
            raise HTTPException(status_code=404, detail="mistake_not_found")
        return result

    @app.post("/api/study/attempts/{attempt_id}/review")
    def review_study_attempt(attempt_id: str, request: AttemptReviewRequest) -> dict[str, object]:
        """Review an exercise attempt (mark correct/incorrect with feedback)."""
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
        """Mark an incorrect attempt as a mistake case for tracking."""
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
        """List aggregated weak points (common mistake patterns)."""
        with connect(app.state.config.database_path) as connection:
            return list_weak_points(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/mistakes/{mistake_id}/feedback", status_code=201)
    def create_study_mistake_feedback(mistake_id: str, request: MistakeFeedbackRequest) -> dict[str, object]:
        """Add review feedback to a mistake case."""
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
        """Retry a mistake case (generates new practice opportunity)."""
        try:
            with connect(app.state.config.database_path) as connection:
                return redo_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_redo_failed", not_found={"mistake_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_redo_failed") from None

    @app.post("/api/study/mistakes/{mistake_id}/archive")
    def archive_study_mistake(mistake_id: str) -> dict[str, object]:
        """Archive a resolved mistake case."""
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_mistake_case(connection, project_id=app.state.config.project_id, mistake_case_id=mistake_id)
        except ValueError as error:
            raise _phase9c_error(error, default="mistake_archive_failed", not_found={"mistake_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="mistake_archive_failed") from None

    @app.get("/api/study/cram-goals")
    def study_cram_goals(include_archived: bool = False) -> list[dict[str, object]]:
        """List cram goals (intensive study targets with deadlines)."""
        with connect(app.state.config.database_path) as connection:
            return list_cram_goals(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/cram-goals", status_code=201)
    def create_study_cram_goal(request: CramGoalRequest) -> dict[str, object]:
        """Create a new cram goal with target date and exercise count."""
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
        """Get details for a specific cram goal."""
        with connect(app.state.config.database_path) as connection:
            result = get_cram_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        if result is None:
            raise HTTPException(status_code=404, detail="cram_goal_not_found")
        return result

    def _transition_study_cram_goal(goal_id: str, target: str) -> dict[str, object]:
        """Transition cram goal to target state (active/completed/archived)."""
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_cram_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id, target=target)
        except ValueError as error:
            raise _phase9c_error(error, default="cram_goal_transition_failed", not_found={"cram_goal_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="cram_goal_transition_failed") from None

    @app.post("/api/study/cram-goals/{goal_id}/active")
    def activate_study_cram_goal(goal_id: str) -> dict[str, object]:
        """Activate a pending cram goal."""
        return _transition_study_cram_goal(goal_id, "active")

    @app.post("/api/study/cram-goals/{goal_id}/completed")
    def complete_study_cram_goal(goal_id: str) -> dict[str, object]:
        """Mark an active cram goal as completed."""
        return _transition_study_cram_goal(goal_id, "completed")

    @app.post("/api/study/cram-goals/{goal_id}/archived")
    def archive_study_cram_goal(goal_id: str) -> dict[str, object]:
        """Archive a completed or abandoned cram goal."""
        return _transition_study_cram_goal(goal_id, "archived")

    @app.post("/api/study/cram-goals/{goal_id}/sessions", status_code=201)
    def create_study_cram_session(goal_id: str, request: CramSessionRequest) -> dict[str, object]:
        """Create a new cram session for a goal (timed practice run)."""
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
        """Get aggregated result for a finished cram session."""
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

    # Export local helpers for shared route context
    globals()['_study_error'] = _study_error
    globals()['_phase9c_error'] = _phase9c_error
    globals()['_transition_study_cram_goal'] = _transition_study_cram_goal
    context.update({'_study_error': _study_error, '_phase9c_error': _phase9c_error, '_transition_study_cram_goal': _transition_study_cram_goal})
    return context
