"""学习卡片组 API - 卡片组 CRUD 与卡片复习。

路由前缀 /api/study/decks，覆盖卡片组（deck）和卡片（card）：

卡片组：
- GET  /api/study/decks: 列出全部卡片组
- POST /api/study/decks: 创建卡片组
- GET  /api/study/decks/{id}: 卡片组详情

卡片：
- GET  /api/study/decks/{id}/cards: 卡片列表
- POST /api/study/decks/{id}/cards: 创建卡片
- PATCH /api/study/cards/{id}: 更新卡片
- POST /api/study/cards/{id}/confirm: 确认草稿卡片
- POST /api/study/cards/{id}/review: 复习打卡

业务规则由 repository 层实施（状态机/引用刷新/用户编辑保护），
本层只做请求验证和错误码转换。
"""
from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/study/decks")
    def study_decks() -> list[dict[str, object]]:
        """List all study decks for the project."""
        with connect(app.state.config.database_path) as connection:
            return list_decks(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/decks", status_code=201)
    def create_study_deck(request: DeckRequest) -> dict[str, object]:
        """Create a new study deck with title and optional description."""
        try:
            with connect(app.state.config.database_path) as connection:
                return create_deck(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="deck_create_failed") from None

    @app.get("/api/study/decks/{deck_id}")
    def study_deck(deck_id: str) -> dict[str, object]:
        """Get details for a specific study deck."""
        if not deck_id or len(deck_id) > 100: raise HTTPException(status_code=404, detail="deck_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_deck(connection, project_id=app.state.config.project_id, deck_id=deck_id)
        if result is None: raise HTTPException(status_code=404, detail="deck_not_found")
        return result

    @app.get("/api/study/cards")
    def study_cards(deck_id: str | None = None, status: str | None = None,
                    material_id: str | None = None, limit: int | None = None,
                    offset: int = 0) -> list[dict[str, object]] | dict[str, object]:
        """List cards with optional lifecycle/source filters and pagination."""
        if limit is not None and (limit < 1 or limit > 100):
            raise HTTPException(status_code=400, detail="invalid_pagination")
        if offset < 0:
            raise HTTPException(status_code=400, detail="invalid_pagination")
        try:
            with connect(app.state.config.database_path) as connection:
                rows = list_cards(connection, project_id=app.state.config.project_id, deck_id=deck_id,
                                  status=status, material_id=material_id, limit=limit, offset=offset)
            if limit is None:
                return rows
            total = int(rows[0].get("_total", 0)) if rows else 0
            for row in rows:
                row.pop("_total", None)
            return {"items": rows, "total": total, "limit": limit, "offset": offset,
                    "has_more": offset + len(rows) < total}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None

    @app.get("/api/study/card-citations/{citation_key}")
    def study_card_citation(citation_key: str) -> dict[str, object]:
        """Resolve a card citation to its material location."""
        if not citation_key or len(citation_key) > 100:
            raise HTTPException(status_code=404, detail="citation_not_found")
        with connect(app.state.config.database_path) as connection:
            citation = connection.execute(
                "SELECT cc.material_id,cc.revision_id,cc.extraction_id,cc.chunk_id,m.original_name AS material_name "
                "FROM card_citations cc JOIN study_cards c ON c.id=cc.card_id AND c.project_id=? "
                "LEFT JOIN materials m ON m.id=cc.material_id WHERE cc.citation_key=? "
                "ORDER BY cc.position,cc.id LIMIT 1",
                (app.state.config.project_id, citation_key),
            ).fetchone()
            if citation is None:
                raise HTTPException(status_code=404, detail="citation_not_found")
            base = {"citation_key": citation_key, "material_id": citation["material_id"],
                    "material_name": citation["material_name"], "revision_id": citation["revision_id"],
                    "chunk_id": citation["chunk_id"]}
            material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (citation["material_id"],)).fetchone()
            if material is None:
                return {**base, "status": "source_unavailable"}
            if material["deleted_at"] is not None:
                return {**base, "status": "source_deleted"}
            chunk = connection.execute(
                "SELECT c.start_offset,c.end_offset,c.revision_id,r.extraction_id FROM chunks c "
                "JOIN material_revisions r ON r.id=c.revision_id "
                "WHERE c.id=? AND c.material_id=? AND c.status='ready' AND r.is_current=1",
                (citation["chunk_id"], citation["material_id"]),
            ).fetchone()
            if chunk is None:
                return {**base, "status": "source_unavailable"}
            if (chunk["revision_id"] != citation["revision_id"] or
                    chunk["extraction_id"] != citation["extraction_id"]):
                return {**base, "status": "stale"}
            return {**base, "status": "valid", "start_offset": chunk["start_offset"],
                    "end_offset": chunk["end_offset"]}

    @app.get("/api/study/cards/{card_id}")
    def study_card(card_id: str) -> dict[str, object]:
        """Get details for a specific study card."""
        if not card_id or len(card_id) > 100:
            raise HTTPException(status_code=404, detail="card_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_card(connection, project_id=app.state.config.project_id, card_id=card_id)
        if result is None:
            raise HTTPException(status_code=404, detail="card_not_found")
        return result

    @app.post("/api/study/decks/{deck_id}/cards", status_code=201)
    def create_study_card(deck_id: str, request: CardRequest) -> dict[str, object]:
        """Create a new study card in the specified deck."""
        try:
            with connect(app.state.config.database_path) as connection:
                return create_card(connection, project_id=app.state.config.project_id, deck_id=deck_id, payload=request.model_dump(), card_type=request.card_type, source_revision=request.source_revision)
        except ValueError as error:
            code = str(error); status = 404 if code == "deck_not_found" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_create_failed") from None

    @app.post("/api/study/decks/{deck_id}/generate")
    def generate_study_cards(deck_id: str, request: GenerationRequest,
                             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        """Generate AI-drafted study cards from material revisions."""
        if request.exercise_type is not None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="card", container_id=deck_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/cards/{card_id}")
    def update_study_card(card_id: str, request: CardRequest) -> dict[str, object]:
        """Update an existing study card (draft state only)."""
        try:
            with connect(app.state.config.database_path) as connection:
                return update_card(connection, project_id=app.state.config.project_id, card_id=card_id, payload=request.model_dump())
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_found" else 409 if code == "card_edit_not_allowed" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_update_failed") from None

    @app.post("/api/study/cards/{card_id}/confirm")
    def confirm_study_card(card_id: str) -> dict[str, object]:
        """Confirm a draft card, transitioning it to confirmed state."""
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_card(connection, project_id=app.state.config.project_id, card_id=card_id)
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_found" else 409 if code in {"card_invalid_state", "citation_invalid"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_confirm_failed") from None

    @app.post("/api/study/cards/{card_id}/reject")
    def reject_study_card(card_id: str) -> dict[str, object]:
        """Reject a draft card, transitioning it to rejected state."""
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="rejected")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_reject_failed") from None

    @app.post("/api/study/cards/{card_id}/archive")
    def archive_study_card(card_id: str) -> dict[str, object]:
        """Archive a card, removing it from active review."""
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="archived")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_archive_failed") from None

    @app.post("/api/study/cards/{card_id}/restore")
    def restore_study_card(card_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="ready")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_restore_failed") from None

    @app.get("/api/study/cards/{card_id}/reviews")
    def study_card_reviews(card_id: str) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            if connection.execute("SELECT 1 FROM study_cards WHERE id=? AND project_id=?", (card_id, app.state.config.project_id)).fetchone() is None:
                raise HTTPException(status_code=404, detail="card_not_found")
            return [dict(row) for row in connection.execute(
                "SELECT id,card_id,result,reviewed_at,metadata_json FROM card_reviews WHERE card_id=? ORDER BY reviewed_at DESC,id DESC", (card_id,)
            ).fetchall()]

    @app.post("/api/study/cards/{card_id}/reviews", status_code=201)
    def review_study_card(card_id: str, request: CardReviewRequest,
                          idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        """Record a spaced-repetition review result for a card."""
        try:
            with connect(app.state.config.database_path) as connection:
                return review_card(connection, project_id=app.state.config.project_id, card_id=card_id,
                                   result=request.result, idempotency_key=idempotency_key)
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_review_failed") from None

    @app.get("/api/study/exercise-sets")
    def exercise_sets() -> list[dict[str, object]]:
        """List all exercise sets for the project."""
        with connect(app.state.config.database_path) as connection:
            return list_exercise_sets(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/exercise-sets", status_code=201)
    def create_study_exercise_set(request: ExerciseSetRequest) -> dict[str, object]:
        """Create a new exercise set with title and optional description."""
        try:
            with connect(app.state.config.database_path) as connection:
                return create_exercise_set(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_set_create_failed") from None

    @app.get("/api/study/exercise-sets/{set_id}")
    def study_exercise_set(set_id: str) -> dict[str, object]:
        """Get details for a specific exercise set."""
        with connect(app.state.config.database_path) as connection:
            result = get_exercise_set(connection, project_id=app.state.config.project_id, set_id=set_id)
        if result is None: raise HTTPException(status_code=404, detail="exercise_set_not_found")
        return result

    @app.get("/api/study/exercises")
    def study_exercises(set_id: str | None = None) -> list[dict[str, object]]:
        """List exercises, optionally filtered by set."""
        with connect(app.state.config.database_path) as connection:
            return list_exercises(connection, project_id=app.state.config.project_id, set_id=set_id)

    @app.get("/api/study/exercises/{exercise_id}")
    def study_exercise(exercise_id: str) -> dict[str, object]:
        """Get details for a specific exercise."""
        if not exercise_id or len(exercise_id) > 100:
            raise HTTPException(status_code=404, detail="exercise_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_exercise(connection, project_id=app.state.config.project_id, exercise_id=exercise_id)
        if result is None:
            raise HTTPException(status_code=404, detail="exercise_not_found")
        return result

    @app.post("/api/study/exercise-sets/{set_id}/exercises", status_code=201)
    def create_study_exercise(set_id: str, request: ExerciseRequest) -> dict[str, object]:
        """Create a new exercise in the specified set."""
        try:
            with connect(app.state.config.database_path) as connection:
                return create_exercise(connection, project_id=app.state.config.project_id, set_id=set_id, exercise_type=request.exercise_type, payload=request.model_dump(), source_revision=request.source_revision, exercise_kind=request.exercise_kind)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_set_not_found" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_create_failed") from None

    @app.post("/api/study/exercise-sets/{set_id}/generate")
    def generate_study_exercises(set_id: str, request: GenerationRequest,
                                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        """Generate AI-drafted exercises from material revisions."""
        if request.exercise_type is None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="exercise", container_id=set_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/exercises/{exercise_id}")
    def update_study_exercise(exercise_id: str, request: ExerciseUpdateRequest) -> dict[str, object]:
        """Update an existing exercise (draft state only)."""
        try:
            with connect(app.state.config.database_path) as connection:
                return update_exercise(connection, project_id=app.state.config.project_id,
                                       exercise_id=exercise_id, payload=request.model_dump())
        except ValueError as error:
            code = str(error)
            status = 404 if code == "exercise_not_found" else 409 if code == "exercise_edit_not_allowed" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_update_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/confirm")
    def confirm_study_exercise(exercise_id: str) -> dict[str, object]:
        """Confirm a draft exercise, transitioning it to confirmed state."""
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_exercise(connection, project_id=app.state.config.project_id, exercise_id=exercise_id)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_not_found" else 409
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_confirm_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/reject")
    def reject_study_exercise(exercise_id: str) -> dict[str, object]:
        """Reject a draft exercise, transitioning it to rejected state."""
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_exercise(connection, project_id=app.state.config.project_id,
                                           exercise_id=exercise_id, target="rejected")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "exercise_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_reject_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/archive")
    def archive_study_exercise(exercise_id: str) -> dict[str, object]:
        """Archive a confirmed exercise, removing it from active practice."""
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_exercise(connection, project_id=app.state.config.project_id,
                                           exercise_id=exercise_id, target="archived")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "exercise_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_archive_failed") from None

    @app.get("/api/study/exercises/{exercise_id}/attempts")
    def study_exercise_attempts(exercise_id: str) -> list[dict[str, object]]:
        """List all practice attempts for a specific exercise."""
        try:
            with connect(app.state.config.database_path) as connection:
                return list_exercise_attempts(connection, project_id=app.state.config.project_id,
                                              exercise_id=exercise_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="exercise_not_found") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_attempt_list_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/attempts", status_code=201)
    def attempt_study_exercise(exercise_id: str, request: ExerciseAttemptRequest) -> dict[str, object]:
        """Submit a practice attempt for an exercise."""
        try:
            with connect(app.state.config.database_path) as connection:
                return submit_exercise_attempt(connection, project_id=app.state.config.project_id, exercise_id=exercise_id, answer=request.answer)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_attempt_failed") from None
    return context
