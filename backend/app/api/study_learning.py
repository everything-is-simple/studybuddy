from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/api/study/decks")
    def study_decks() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_decks(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/decks", status_code=201)
    def create_study_deck(request: DeckRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_deck(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="deck_create_failed") from None

    @app.get("/api/study/decks/{deck_id}")
    def study_deck(deck_id: str) -> dict[str, object]:
        if not deck_id or len(deck_id) > 100: raise HTTPException(status_code=404, detail="deck_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_deck(connection, project_id=app.state.config.project_id, deck_id=deck_id)
        if result is None: raise HTTPException(status_code=404, detail="deck_not_found")
        return result

    @app.get("/api/study/cards")
    def study_cards(deck_id: str | None = None) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_cards(connection, project_id=app.state.config.project_id, deck_id=deck_id)

    @app.get("/api/study/cards/{card_id}")
    def study_card(card_id: str) -> dict[str, object]:
        if not card_id or len(card_id) > 100:
            raise HTTPException(status_code=404, detail="card_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_card(connection, project_id=app.state.config.project_id, card_id=card_id)
        if result is None:
            raise HTTPException(status_code=404, detail="card_not_found")
        return result

    @app.post("/api/study/decks/{deck_id}/cards", status_code=201)
    def create_study_card(deck_id: str, request: CardRequest) -> dict[str, object]:
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
        if request.exercise_type is not None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="card", container_id=deck_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/cards/{card_id}")
    def update_study_card(card_id: str, request: CardRequest) -> dict[str, object]:
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
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="archived")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_archive_failed") from None

    @app.post("/api/study/cards/{card_id}/reviews", status_code=201)
    def review_study_card(card_id: str, request: CardReviewRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return review_card(connection, project_id=app.state.config.project_id, card_id=card_id, result=request.result)
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_review_failed") from None

    @app.get("/api/study/exercise-sets")
    def exercise_sets() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_exercise_sets(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/exercise-sets", status_code=201)
    def create_study_exercise_set(request: ExerciseSetRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_exercise_set(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_set_create_failed") from None

    @app.get("/api/study/exercise-sets/{set_id}")
    def study_exercise_set(set_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            result = get_exercise_set(connection, project_id=app.state.config.project_id, set_id=set_id)
        if result is None: raise HTTPException(status_code=404, detail="exercise_set_not_found")
        return result

    @app.get("/api/study/exercises")
    def study_exercises(set_id: str | None = None) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_exercises(connection, project_id=app.state.config.project_id, set_id=set_id)

    @app.get("/api/study/exercises/{exercise_id}")
    def study_exercise(exercise_id: str) -> dict[str, object]:
        if not exercise_id or len(exercise_id) > 100:
            raise HTTPException(status_code=404, detail="exercise_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_exercise(connection, project_id=app.state.config.project_id, exercise_id=exercise_id)
        if result is None:
            raise HTTPException(status_code=404, detail="exercise_not_found")
        return result

    @app.post("/api/study/exercise-sets/{set_id}/exercises", status_code=201)
    def create_study_exercise(set_id: str, request: ExerciseRequest) -> dict[str, object]:
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
        if request.exercise_type is None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="exercise", container_id=set_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/exercises/{exercise_id}")
    def update_study_exercise(exercise_id: str, request: ExerciseUpdateRequest) -> dict[str, object]:
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
        try:
            with connect(app.state.config.database_path) as connection:
                return submit_exercise_attempt(connection, project_id=app.state.config.project_id, exercise_id=exercise_id, answer=request.answer)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_attempt_failed") from None
    return context
