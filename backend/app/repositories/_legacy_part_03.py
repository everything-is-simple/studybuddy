from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
def persist_generated_draft(connection: sqlite3.Connection, *, project_id: str, operation_id: str,
                            artifact_kind: str, container_id: str, source_revision: str,
                            items: list[dict[str, object]], citation_groups: list[list[str]],
                            context_blocks: list[dict[str, object]], provider_id: str, model_id: str,
                            prompt_tokens: int | None, completion_tokens: int | None, latency_ms: int,
                            provider_request_id: str | None, total_tokens: int | None,
                            finish_reason: str | None) -> list[dict[str, object]]:
    if not items or len(items) != len(citation_groups) or any(not isinstance(item, dict) for item in items):
        raise ValueError("generation_schema_invalid")
    with connection:
        operation = connection.execute("SELECT status,source_revision FROM ai_operations WHERE id=? AND project_id=?", (operation_id, project_id)).fetchone()
    if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
        raise ValueError("generation_stale_source")
    allowed = {str(block.get("citation_key")): block for block in context_blocks}
    prepared: list[tuple[dict[str, object], list[dict[str, object]]]] = []
    for item, citation_keys in zip(items, citation_groups):
        if not isinstance(citation_keys, list) or not citation_keys:
            raise ValueError("generation_schema_invalid")
        citations_payload: list[dict[str, object]] = []
        for key in citation_keys:
            block = allowed.get(key)
            source = block.get("source_info") if isinstance(block, dict) else None
            if not isinstance(source, dict) or source.get("revision_id") != source_revision:
                raise ValueError("citation_verification_failed")
            validation = validate_citation_key(connection, key)
            if validation.get("status") != "valid" or validation.get("revision_id") != source_revision:
                raise ValueError("citation_verification_failed")
            citations_payload.append({"citation_key": key, "chunk_id": validation["chunk_id"], "quote": str(block["text"])[:500]})
        if len({entry["citation_key"] for entry in citations_payload}) != len(citations_payload):
            raise ValueError("citation_verification_failed")
        prepared.append((item, citations_payload))
    artifact_ids: list[str] = []
    with connection:
        operation = connection.execute("SELECT status,source_revision FROM ai_operations WHERE id=? AND project_id=?", (operation_id, project_id)).fetchone()
        if operation is None or operation["status"] != "running" or operation["source_revision"] != source_revision:
            raise ValueError("generation_stale_source")
        for item, citations_payload in prepared:
            if artifact_kind == "card":
                front, back, explanation, tags = _validate_card_payload(item)
                artifact_id = f"card_{uuid.uuid4().hex}"
                citation_rows = _citation_rows(connection, citations_payload, code="generation_schema_invalid", artifact_id=artifact_id, table="card")
                connection.execute("INSERT INTO study_cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (artifact_id, container_id, project_id, "ai_generated", "draft", front, back, explanation, json.dumps(tags, ensure_ascii=False), source_revision, 0, operation_id, utc_now(), utc_now(), None, None))
                connection.executemany("INSERT INTO card_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citation_rows)
            else:
                exercise_type = item.get("exercise_type")
                if not isinstance(exercise_type, str):
                    raise ValueError("generation_schema_invalid")
                prompt, options, answer_key, explanation = _exercise_payload(item, exercise_type)
                artifact_id = f"exercise_{uuid.uuid4().hex}"
                citation_rows = _exercise_citations(connection, citations_payload, artifact_id)
                _validate_exercise_source_revision(connection, source_revision, citation_rows, "ai_generated")
                connection.execute(
                    "INSERT INTO exercises (id,set_id,project_id,exercise_type,exercise_kind,status,prompt,options_json,answer_key_json,"
                    "explanation,source_revision,edited_by_user,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
                    "VALUES (?,?,?,?,?,'draft',?,?,?,?,?,0,?,?,?,NULL,NULL)",
                    (artifact_id, container_id, project_id, exercise_type, "ai_generated", prompt, json.dumps(options, ensure_ascii=False),
                     json.dumps(answer_key, ensure_ascii=False), explanation, source_revision, operation_id, utc_now(), utc_now()),
                )
                connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citation_rows)
            artifact_ids.append(artifact_id)
        connection.execute(
            "UPDATE ai_operations SET status='succeeded',output_artifact_id=?,provider_id=?,model_id=?,provider_request_id=?,"
            "prompt_tokens=?,completion_tokens=?,total_tokens=?,latency_ms=?,finish_reason=?,finished_at=? WHERE id=? AND status='running'",
            (artifact_ids[0], provider_id, model_id, provider_request_id, prompt_tokens, completion_tokens, total_tokens,
             latency_ms, finish_reason, utc_now(), operation_id),
        )
    rows = [connection.execute("SELECT * FROM study_cards WHERE id=?" if artifact_kind == "card" else "SELECT * FROM exercises WHERE id=?", (artifact_id,)).fetchone() for artifact_id in artifact_ids]
    return [_card_public(connection, row) if artifact_kind == "card" else _exercise_public(connection, row) for row in rows]

def list_exercises(connection: sqlite3.Connection, *, project_id: str, set_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    where = "project_id=?"
    if set_id is not None:
        where += " AND set_id=?"
        params.append(set_id)
    with connection:
        rows = connection.execute("SELECT * FROM exercises WHERE " + where + " ORDER BY updated_at DESC,id DESC", params).fetchall()
        for row in rows:
            _refresh_exercise_citations(connection, str(row["id"]))
    return [_exercise_public(connection, row) for row in rows]

def create_exercise(connection: sqlite3.Connection, *, project_id: str, set_id: str, exercise_type: str,
                    payload: dict[str, object], source_revision: str | None = None,
                    exercise_kind: str = "user_created") -> dict[str, object]:
    if exercise_kind not in {"user_created", "ai_generated"}:
        raise ValueError("invalid_exercise_schema")
    if connection.execute("SELECT 1 FROM exercise_sets WHERE id=? AND project_id=? AND status='active'", (set_id, project_id)).fetchone() is None:
        raise ValueError("exercise_set_not_found")
    prompt, options, answer_key, explanation = _exercise_payload(payload, exercise_type)
    exercise_id, now = f"exercise_{uuid.uuid4().hex}", utc_now()
    citations = _exercise_citations(connection, payload.get("citations", []), exercise_id)
    _validate_exercise_source_revision(connection, source_revision, citations, exercise_kind)
    with connection:
        connection.execute(
            "INSERT INTO exercises (id,set_id,project_id,exercise_type,exercise_kind,status,prompt,options_json,answer_key_json,"
            "explanation,source_revision,edited_by_user,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
            "VALUES (?,?,?,?,?,'draft',?,?,?,?,?,0,NULL,?,?,NULL,NULL)",
            (exercise_id, set_id, project_id, exercise_type, exercise_kind, prompt, json.dumps(options, ensure_ascii=False),
             json.dumps(answer_key, ensure_ascii=False), explanation, source_revision, now, now),
        )
        connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=set_id) if item["id"] == exercise_id)

def update_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                    payload: dict[str, object]) -> dict[str, object]:
    row = connection.execute("SELECT * FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    if row["status"] != "draft":
        raise ValueError("exercise_edit_not_allowed")
    if payload.get("answer_key") is None:
        payload = {**payload, "answer_key": json.loads(row["answer_key_json"])}
    prompt, options, answer_key, explanation = _exercise_payload(payload, str(row["exercise_type"]))
    citation_input = payload.get("citations", [])
    if not citation_input and row["exercise_kind"] == "ai_generated":
        citation_input = [dict(item) for item in connection.execute(
            "SELECT citation_key,chunk_id,quote FROM exercise_citations WHERE exercise_id=? ORDER BY position,id", (exercise_id,)
        ).fetchall()]
    citations = _exercise_citations(connection, citation_input, exercise_id)
    _validate_exercise_source_revision(connection, row["source_revision"], citations, str(row["exercise_kind"]))
    with connection:
        connection.execute("DELETE FROM exercise_citations WHERE exercise_id=?", (exercise_id,))
        connection.execute("UPDATE exercises SET prompt=?,options_json=?,answer_key_json=?,explanation=?,edited_by_user=1,updated_at=? WHERE id=?", (prompt, json.dumps(options, ensure_ascii=False), json.dumps(answer_key, ensure_ascii=False), explanation, utc_now(), exercise_id))
        connection.executemany("INSERT INTO exercise_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)

def confirm_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str) -> dict[str, object]:
    row = connection.execute("SELECT set_id,status,exercise_kind,source_revision FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    if row["status"] != "draft":
        raise ValueError("exercise_invalid_state")
    with connection:
        statuses = _refresh_exercise_citations(connection, exercise_id)
        if any(status != "valid" for status in statuses):
            raise ValueError("citation_invalid")
        if row["exercise_kind"] == "ai_generated" and (not statuses or row["source_revision"] is None):
            raise ValueError("citation_invalid")
        now = utc_now()
        connection.execute("UPDATE exercises SET status='ready',confirmed_at=?,updated_at=? WHERE id=?", (now, now, exercise_id))
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)

def transition_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                        target: str) -> dict[str, object]:
    row = connection.execute("SELECT set_id,status FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_found")
    allowed = {"rejected": {"draft"}, "archived": {"draft", "ready", "rejected", "stale"}}
    if target not in allowed or row["status"] not in allowed[target]:
        raise ValueError("exercise_invalid_state")
    now = utc_now()
    with connection:
        connection.execute("UPDATE exercises SET status=?,updated_at=?,archived_at=? WHERE id=?", (target, now, now if target == "archived" else None, exercise_id))
    return next(item for item in list_exercises(connection, project_id=project_id, set_id=str(row["set_id"])) if item["id"] == exercise_id)

def list_exercise_attempts(connection: sqlite3.Connection, *, project_id: str, exercise_id: str) -> list[dict[str, object]]:
    if connection.execute("SELECT 1 FROM exercises WHERE id=? AND project_id=?", (exercise_id, project_id)).fetchone() is None:
        raise ValueError("exercise_not_found")
    rows = connection.execute(
        "SELECT id,exercise_id,score,is_correct,grading_status,submitted_at,reviewed_at,feedback "
        "FROM exercise_attempts WHERE exercise_id=? ORDER BY rowid", (exercise_id,)
    ).fetchall()
    return [{**dict(row), "is_correct": (None if row["is_correct"] is None else bool(row["is_correct"]))}
            for row in rows]

def submit_exercise_attempt(connection: sqlite3.Connection, *, project_id: str, exercise_id: str, answer: object) -> dict[str, object]:
    row = connection.execute("SELECT * FROM exercises WHERE id=? AND project_id=? AND status='ready'", (exercise_id, project_id)).fetchone()
    if row is None:
        raise ValueError("exercise_not_ready")
    if isinstance(answer, str) and len(answer) > MAX_EXERCISE_ANSWER_LENGTH:
        raise ValueError("invalid_exercise_answer")
    expected, correct, score, grading = json.loads(row["answer_key_json"]), None, None, "deterministic"
    if row["exercise_type"] == "multiple_choice":
        if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(json.loads(row["options_json"])):
            raise ValueError("invalid_exercise_answer")
        correct, score = answer == expected, 1.0 if answer == expected else 0.0
    elif row["exercise_type"] == "true_false":
        if not isinstance(answer, bool):
            raise ValueError("invalid_exercise_answer")
        correct, score = answer == expected, 1.0 if answer == expected else 0.0
    else:
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("invalid_exercise_answer")
        grading = "pending_review"
    attempt_id = f"attempt_{uuid.uuid4().hex}"
    with connection:
        connection.execute(
            "INSERT INTO exercise_attempts "
            "(id, exercise_id, answer_json, score, is_correct, grading_status, submitted_at, reviewed_at, feedback) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (attempt_id, exercise_id, json.dumps(answer, ensure_ascii=False), score,
             int(correct) if correct is not None else None, grading, utc_now(), None, ""),
        )
    return {"id": attempt_id, "exercise_id": exercise_id, "score": score, "is_correct": correct, "grading_status": grading}

PHASE9C_SESSION_TITLE_MAX = 200

PHASE9C_SESSION_MAX_ITEMS = 50

PHASE9C_MIN_DURATION_SECONDS = 60

PHASE9C_MAX_DURATION_SECONDS = 7200

PHASE9C_FEEDBACK_MAX = 4000

PHASE9C_CORRECTION_MAX = 12000

PHASE9C_SESSION_STATUSES = {"draft", "active", "finished", "expired", "archived"}

PHASE9C_MISTAKE_STATUSES = {"open", "in_review", "fixed", "reopened", "archived"}

PHASE9C_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}

def _phase9c_text(value: object, *, code: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(code)
    value = value.strip()
    if not value and not allow_empty:
        raise ValueError(code)
    return value

def _phase9c_timezone(value: object, *, code: str) -> str:
    value = _phase9c_text(value, code=code, maximum=100)
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError(code) from None
    return value

def _phase9c_local_date(value: object, *, code: str) -> str:
    value = _phase9c_text(value, code=code, maximum=10)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(code) from None

def _phase9c_iso_now() -> tuple[str, datetime]:
    value = utc_now()
    return value, datetime.fromisoformat(value).astimezone(timezone.utc)

def _phase9c_parse_now(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)

def _phase9c_source_snapshot(connection: sqlite3.Connection, exercise_id: str) -> dict[str, object]:
    citations = connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1", (exercise_id,)
    ).fetchone()
    if citations is None:
        return {"source_material_id": None, "source_revision": None, "source_extraction_id": None,
                "source_chunk_id": None, "source_span_id": None, "citation_key": None,
                "citation_status": "valid"}
    _refresh_exercise_citations(connection, exercise_id)
    citations = connection.execute(
        "SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,status "
        "FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1", (exercise_id,)
    ).fetchone()
    status = citations["status"] if citations["status"] in PHASE9C_SOURCE_STATUSES else "source_unavailable"
    if status != "valid":
        raise ValueError("citation_invalid")
    return {"source_material_id": citations["material_id"], "source_revision": citations["revision_id"],
            "source_extraction_id": citations["extraction_id"], "source_chunk_id": citations["chunk_id"],
            "source_span_id": citations["span_id"], "citation_key": citations["citation_key"],
            "citation_status": status}

def _phase9c_project_exercise(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                              ready: bool = True) -> sqlite3.Row:
    sql = "SELECT * FROM exercises WHERE id=? AND project_id=?"
    params: tuple[object, ...] = (exercise_id, project_id)
    if ready:
        sql += " AND status='ready'"
    row = connection.execute(sql, params).fetchone()
    if row is None:
        raise ValueError("exercise_not_ready" if ready else "exercise_not_found")
    return row

def _phase9c_session_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    items = connection.execute(
        "SELECT id,session_id,exercise_id,position,exercise_type,prompt,options_json,explanation_snapshot,"
        "exercise_kind,source_material_id,source_revision,source_extraction_id,source_chunk_id,source_span_id,"
        "citation_key,citation_status,created_at,updated_at FROM practice_session_items "
        "WHERE session_id=? ORDER BY position,id", (row["id"],)
    ).fetchall()
    attempts = connection.execute(
        "SELECT session_item_id,score,is_correct,grading_status,submitted_at,reviewed_at FROM exercise_attempts "
        "WHERE session_id=? ORDER BY submitted_at,id", (row["id"],)
    ).fetchall()
    safe_items = []
    for item in items:
        payload = dict(item)
        payload["options"] = json.loads(payload.pop("options_json"))
        safe_items.append(payload)
    deterministic = [item for item in attempts if item["grading_status"] == "deterministic"]
    return {"id": row["id"], "project_id": row["project_id"], "session_kind": row["session_kind"],
            "cram_goal_id": row["cram_goal_id"], "status": row["status"], "title": row["title"],
            "duration_seconds": row["duration_seconds"], "timezone": row["timezone"],
            "local_date": row["local_date"], "started_at": row["started_at"],
            "deadline_at": row["deadline_at"], "finished_at": row["finished_at"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "items": safe_items,
            "summary": {"total_item_count": len(items), "submitted_count": len(attempts),
                        "unanswered_count": len(items) - len(attempts),
                        "correct_count": sum(item["is_correct"] == 1 for item in deterministic),
                        "incorrect_count": sum(item["is_correct"] == 0 for item in deterministic),
                        "pending_review_count": sum(item["grading_status"] == "pending_review" for item in attempts),
                        "scored_count": len(deterministic),
                        "score_total": sum(float(item["score"] or 0) for item in deterministic),
                        "source_warning_count": sum(item["citation_status"] != "valid" for item in items),
                        "last_attempt_at": attempts[-1]["submitted_at"] if attempts else None}}

def _phase9c_expire_if_needed(connection: sqlite3.Connection, row: sqlite3.Row, now: datetime, now_text: str) -> sqlite3.Row:
    if row["status"] == "active" and row["deadline_at"] is not None and now >= _phase9c_parse_now(str(row["deadline_at"])):
        connection.execute("UPDATE practice_sessions SET status='expired',finished_at=?,updated_at=? WHERE id=? AND status='active'",
                           (now_text, now_text, row["id"]))
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=?", (row["id"],)).fetchone()
    return row

