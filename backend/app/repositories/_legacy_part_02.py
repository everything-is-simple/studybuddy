from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
def confirm_card(connection: sqlite3.Connection, *, project_id: str, card_id: str) -> dict[str, object]:
    row = connection.execute("SELECT deck_id,status FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None: raise ValueError("card_not_found")
    if row["status"] != "draft": raise ValueError("card_invalid_state")
    with connection:
        _refresh_card_citations(connection, card_id)
    if connection.execute("SELECT 1 FROM card_citations WHERE card_id=? AND status='valid'", (card_id,)).fetchone() is None:
        if connection.execute("SELECT card_type FROM study_cards WHERE id=?", (card_id,)).fetchone()[0] == "ai_generated": raise ValueError("citation_invalid")
    with connection: connection.execute("UPDATE study_cards SET status='ready',confirmed_at=?,updated_at=? WHERE id=?", (utc_now(), utc_now(), card_id))
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=row["deck_id"]) if item["id"] == card_id)

def transition_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, target: str) -> dict[str, object]:
    row = connection.execute("SELECT deck_id,status FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None:
        raise ValueError("card_not_found")
    allowed = {"rejected": {"draft"}, "archived": {"draft", "ready", "rejected", "stale"}}
    if target not in allowed or row["status"] not in allowed[target]:
        raise ValueError("card_invalid_state")
    now = utc_now()
    with connection:
        connection.execute("UPDATE study_cards SET status=?,updated_at=?,archived_at=? WHERE id=?", (target, now, now if target == "archived" else None, card_id))
    result = connection.execute("SELECT * FROM study_cards WHERE id=?", (card_id,)).fetchone()
    return _card_public(connection, result)

def review_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, result: str) -> dict[str, object]:
    if result not in {"again", "hard", "good", "easy"}: raise ValueError("invalid_card_review")
    if connection.execute("SELECT 1 FROM study_cards WHERE id=? AND project_id=? AND status='ready'", (card_id, project_id)).fetchone() is None: raise ValueError("card_not_ready")
    review_id = f"review_{uuid.uuid4().hex}"
    with connection: connection.execute("INSERT INTO card_reviews VALUES (?,?,?,?,?)", (review_id, card_id, result, utc_now(), "{}"))
    return {"id": review_id, "card_id": card_id, "result": result}

MAX_EXERCISE_EXPLANATION_LENGTH = 4000

MAX_EXERCISE_ANSWER_LENGTH = 1000

MAX_GENERATION_TOPIC_LENGTH = 500

MAX_GENERATION_COUNT = 10

GENERATION_PROMPT_VERSION = "phase8_draft_generation_v1"

def _exercise_payload(payload: dict[str, object], exercise_type: str) -> tuple[str, list[str], object, str]:
    if exercise_type not in {"multiple_choice", "true_false", "short_answer"}:
        raise ValueError("invalid_exercise_schema")
    prompt = _validate_text(payload.get("prompt"), code="invalid_exercise_schema", maximum=MAX_EXERCISE_PROMPT_LENGTH)
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str) or len(explanation) > MAX_EXERCISE_EXPLANATION_LENGTH:
        raise ValueError("invalid_exercise_schema")
    options = payload.get("options", [])
    if (not isinstance(options, list) or len(options) > MAX_EXERCISE_OPTIONS or
            any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in options)):
        raise ValueError("invalid_exercise_schema")
    options = [item.strip() for item in options]
    if len({item.casefold() for item in options}) != len(options):
        raise ValueError("invalid_exercise_schema")
    answer_key = payload.get("answer_key")
    if exercise_type == "multiple_choice":
        if len(options) < 2 or not isinstance(answer_key, int) or isinstance(answer_key, bool) or not 0 <= answer_key < len(options):
            raise ValueError("invalid_exercise_schema")
    elif exercise_type == "true_false":
        if (options and options != ["True", "False"]) or not isinstance(answer_key, bool):
            raise ValueError("invalid_exercise_schema")
        options = ["True", "False"]
    else:
        if options or not isinstance(answer_key, str) or not answer_key.strip() or len(answer_key) > MAX_EXERCISE_ANSWER_LENGTH:
            raise ValueError("invalid_exercise_schema")
        answer_key = answer_key.strip()
    return prompt, options, answer_key, explanation

def _exercise_citations(connection: sqlite3.Connection, citations: object, exercise_id: str) -> list[tuple[object, ...]]:
    return _citation_rows(connection, citations, code="invalid_exercise_schema", artifact_id=exercise_id, table="exercise")

def _refresh_exercise_citations(connection: sqlite3.Connection, exercise_id: str) -> list[str]:
    """Persist the current source lifecycle without trusting saved citation state."""
    statuses: list[str] = []
    for citation in connection.execute("SELECT * FROM exercise_citations WHERE exercise_id=?", (exercise_id,)).fetchall():
        status = "source_unavailable"
        if citation["material_id"] is not None:
            material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (citation["material_id"],)).fetchone()
            if material is not None and material["deleted_at"] is not None:
                status = "source_deleted"
            elif material is not None and citation["chunk_id"] is not None:
                chunk = connection.execute(
                    "SELECT c.status, c.revision_id, c.extraction_id, r.is_current FROM chunks c "
                    "JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                    (citation["chunk_id"], citation["material_id"]),
                ).fetchone()
                if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                    status = "valid" if (chunk["revision_id"] == citation["revision_id"] and
                                            chunk["extraction_id"] == citation["extraction_id"]) else "stale"
                elif chunk is not None:
                    status = "stale"
        connection.execute("UPDATE exercise_citations SET status=? WHERE id=?", (status, citation["id"]))
        statuses.append(status)
    return statuses

def _refresh_exercise_citations_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    for row in connection.execute(
            "SELECT DISTINCT exercise_id FROM exercise_citations WHERE material_id=?", (material_id,)).fetchall():
        _refresh_exercise_citations(connection, str(row["exercise_id"]))

def _refresh_phase9c_session_sources_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    rows = connection.execute(
        "SELECT id,source_revision,source_extraction_id,source_chunk_id FROM practice_session_items "
        "WHERE source_material_id=?", (material_id,)
    ).fetchall()
    for row in rows:
        status = "source_unavailable"
        material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
        if material is not None and material["deleted_at"] is not None:
            status = "source_deleted"
        elif material is not None and row["source_chunk_id"] is not None:
            chunk = connection.execute(
                "SELECT c.status,c.revision_id,c.extraction_id,r.is_current FROM chunks c "
                "JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                (row["source_chunk_id"], material_id),
            ).fetchone()
            if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                status = "valid" if (chunk["revision_id"] == row["source_revision"] and
                                      chunk["extraction_id"] == row["source_extraction_id"]) else "stale"
            elif chunk is not None:
                status = "stale"
        connection.execute("UPDATE practice_session_items SET citation_status=?,updated_at=? WHERE id=?",
                           (status, utc_now(), row["id"]))
        if row["source_revision"] is not None:
            connection.execute("UPDATE mistake_occurrences SET source_status=? WHERE source_revision=?",
                               (status, row["source_revision"]))

def _validate_exercise_source_revision(connection: sqlite3.Connection, source_revision: str | None,
                                        citations: list[tuple[object, ...]], exercise_kind: str) -> None:
    if source_revision is not None:
        source = connection.execute(
            "SELECT r.id FROM material_revisions r JOIN materials m ON m.id=r.material_id "
            "WHERE r.id=? AND r.is_current=1 AND m.deleted_at IS NULL", (source_revision,)
        ).fetchone()
        if source is None:
            raise ValueError("citation_invalid")
    if citations and (source_revision is None or any(row[4] != source_revision for row in citations)):
        raise ValueError("citation_invalid")
    if exercise_kind == "ai_generated" and (not citations or source_revision is None):
        raise ValueError("citation_invalid")

def _exercise_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    result = {"id": row["id"], "set_id": row["set_id"], "exercise_type": row["exercise_type"],
              "exercise_kind": row["exercise_kind"], "status": row["status"], "prompt": row["prompt"],
              "options": json.loads(row["options_json"]), "explanation": row["explanation"],
              "source_revision": row["source_revision"], "edited_by_user": bool(row["edited_by_user"]),
              "created_at": row["created_at"], "updated_at": row["updated_at"],
              "confirmed_at": row["confirmed_at"], "archived_at": row["archived_at"]}
    result["citations"] = [dict(item) for item in connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,quote,position,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id", (row["id"],)).fetchall()]
    return result

def list_exercise_sets(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM exercise_sets WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [{**dict(row), "exercise_count": connection.execute("SELECT COUNT(*) FROM exercises WHERE set_id=?", (row["id"],)).fetchone()[0]} for row in rows]

def get_exercise_set(connection: sqlite3.Connection, *, project_id: str, set_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM exercise_sets WHERE id=? AND project_id=?", (set_id, project_id)).fetchone()
    if row is None:
        return None
    return {**dict(row), "exercises": list_exercises(connection, project_id=project_id, set_id=set_id)}

def create_exercise_set(connection: sqlite3.Connection, *, project_id: str, title: str, description: str = "") -> dict[str, object]:
    title = _validate_text(title, code="invalid_exercise_set_payload", maximum=MAX_DECK_TITLE_LENGTH)
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("invalid_exercise_set_payload")
    now, set_id = utc_now(), f"exercise_set_{uuid.uuid4().hex}"
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)", (project_id, "Default project", now))
        connection.execute("INSERT INTO exercise_sets VALUES (?,?,?,?,?,?,?,?)", (set_id, project_id, title, description, "active", now, now, None))
    return get_exercise_set(connection, project_id=project_id, set_id=set_id) or {}

def _generation_fingerprint(*, artifact_kind: str, container_id: str, topic: str, material_ids: list[str],
                            retrieval_mode: str, allow_fallback: bool, count: int,
                            exercise_type: str | None, source_revision: str | None) -> str:
    payload = "\x1f".join((artifact_kind, container_id, topic.strip(), "\x1e".join(sorted(material_ids)),
                            retrieval_mode, str(int(allow_fallback)), str(count), exercise_type or "", source_revision or ""))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _generation_public(connection: sqlite3.Connection, operation: sqlite3.Row) -> dict[str, object] | None:
    if operation["status"] != "succeeded" or not operation["output_artifact_id"]:
        return None
    artifact_kind = str(operation["operation_type"]).removeprefix("generate_")
    if artifact_kind == "card":
        rows = connection.execute("SELECT * FROM study_cards WHERE generation_operation_id=? ORDER BY created_at,id", (operation["id"],)).fetchall()
        artifacts = [_card_public(connection, row) for row in rows]
    else:
        rows = connection.execute("SELECT * FROM exercises WHERE generation_operation_id=? ORDER BY created_at,id", (operation["id"],)).fetchall()
        artifacts = [_exercise_public(connection, row) for row in rows]
    if not artifacts:
        return None
    return {"status": "succeeded", "operation_id": operation["id"], "retrieval_run_id": operation["retrieval_run_id"],
            "artifacts": artifacts}

def _card_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    return {**dict(row), "tags": json.loads(row["tags_json"]),
            "citations": list_card_citations(connection, str(row["id"]))}

def create_generation_operation(connection: sqlite3.Connection, *, project_id: str, artifact_kind: str,
                                container_id: str, topic: str, material_ids: list[str], retrieval_mode: str,
                                allow_fallback: bool, count: int, exercise_type: str | None,
                                source_revision: str | None, request_id: str | None,
                                idempotency_key: str | None) -> dict[str, object]:
    if artifact_kind not in {"card", "exercise"} or not isinstance(topic, str) or not topic.strip() or len(topic.strip()) > MAX_GENERATION_TOPIC_LENGTH:
        raise ValueError("generation_invalid_request")
    if (not material_ids or len(material_ids) != len(set(material_ids)) or len(material_ids) > 200 or
            retrieval_mode not in {"lexical", "vector", "hybrid"} or not isinstance(allow_fallback, bool) or
            not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_GENERATION_COUNT):
        raise ValueError("generation_invalid_request")
    if artifact_kind == "card":
        if exercise_type is not None or connection.execute("SELECT 1 FROM study_decks WHERE id=? AND project_id=? AND status='active'", (container_id, project_id)).fetchone() is None:
            raise ValueError("deck_not_found" if exercise_type is None else "generation_invalid_request")
    elif exercise_type not in {"multiple_choice", "true_false", "short_answer"} or connection.execute("SELECT 1 FROM exercise_sets WHERE id=? AND project_id=? AND status='active'", (container_id, project_id)).fetchone() is None:
        raise ValueError("exercise_set_not_found" if exercise_type in {"multiple_choice", "true_false", "short_answer"} else "generation_invalid_request")
    rows = connection.execute(
        "SELECT m.id, r.id AS revision_id FROM materials m LEFT JOIN material_revisions r ON r.material_id=m.id AND r.is_current=1 "
        "WHERE m.project_id=? AND m.id IN ({})".format(",".join("?" for _ in material_ids)),
        [project_id, *material_ids],
    ).fetchall()
    if len(rows) != len(material_ids):
        raise ValueError("material_not_found")
    if len(material_ids) != 1:
        raise ValueError("generation_invalid_request")
    material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (material_ids[0],)).fetchone()
    if material is None:
        raise ValueError("material_not_found")
    if material["deleted_at"] is not None:
        raise ValueError("source_deleted")
    current_revision = str(rows[0]["revision_id"]) if len(rows) == 1 and rows[0]["revision_id"] is not None else None
    if source_revision is not None and source_revision != current_revision:
        raise ValueError("generation_stale_source")
    if any(row["revision_id"] is None for row in rows) or connection.execute(
            "SELECT COUNT(*) FROM chunks c JOIN material_revisions r ON r.id=c.revision_id JOIN materials m ON m.id=c.material_id "
            "WHERE m.project_id=? AND m.deleted_at IS NULL AND r.is_current=1 AND c.status='ready' "
            "AND c.material_id IN ({})".format(",".join("?" for _ in material_ids)), [project_id, *material_ids]).fetchone()[0] == 0:
        raise ValueError("retrieval_not_ready")
    fingerprint = _generation_fingerprint(artifact_kind=artifact_kind, container_id=container_id, topic=topic,
                                          material_ids=material_ids, retrieval_mode=retrieval_mode,
                                          allow_fallback=allow_fallback, count=count, exercise_type=exercise_type,
                                          source_revision=current_revision)
    with connection:
        if idempotency_key:
            existing = connection.execute("SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, idempotency_key)).fetchone()
            if existing is not None:
                if existing["input_fingerprint"] != fingerprint:
                    raise ValueError("generation_idempotency_key_mismatch")
                if existing["status"] == "running":
                    raise ValueError("generation_in_progress")
                replay = _generation_public(connection, existing)
                if replay is not None:
                    return {**replay, "replay": True}
                connection.execute("UPDATE ai_operations SET idempotency_key=NULL WHERE id=?", (existing["id"],))
        operation_id, now = f"operation_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
            "retrieval_policy_version,prompt_version,request_id,retry_count,created_at,started_at,idempotency_key) "
            "VALUES (?,?,'running',?,?,?, ?,?,?,?,0,?,?,?)",
            (operation_id, f"generate_{artifact_kind}", project_id, material_ids[0] if len(material_ids) == 1 else None,
             fingerprint, current_revision, {"lexical": RETRIEVAL_POLICY_VERSION, "vector": VECTOR_POLICY_VERSION, "hybrid": HYBRID_POLICY_VERSION}[retrieval_mode],
             GENERATION_PROMPT_VERSION, request_id, now, now, idempotency_key),
        )
    return {"operation_id": operation_id, "replay": False, "source_revision": current_revision}

def fail_generation_operation(connection: sqlite3.Connection, operation_id: str, error_code: str) -> None:
    with connection:
        connection.execute("UPDATE ai_operations SET status='failed',error_code=?,finished_at=? WHERE id=? AND status='running'", (error_code, utc_now(), operation_id))

