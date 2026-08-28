from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
def create_cram_goal(connection: sqlite3.Connection, *, project_id: str, title: object, target_date: object,
                     timezone_name: object = "UTC", target_exercise_count: object = 1,
                     plan_id: str | None = None, plan_item_id: str | None = None) -> dict[str, object]:
    title = _phase9c_text(title, code="cram_invalid_payload", maximum=200)
    target_date = _phase9c_local_date(target_date, code="cram_invalid_payload")
    timezone_name = _phase9c_timezone(timezone_name, code="cram_invalid_payload")
    if not isinstance(target_exercise_count, int) or isinstance(target_exercise_count, bool) or not 1 <= target_exercise_count <= 200:
        raise ValueError("cram_invalid_payload")
    goal_id, now = f"cram_goal_{uuid.uuid4().hex}", utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("project_not_found")
        if plan_id is not None:
            plan = connection.execute("SELECT project_id FROM study_plans WHERE id=?", (plan_id,)).fetchone()
            if plan is None or plan["project_id"] != project_id:
                raise ValueError("cram_scope_conflict")
        if plan_item_id is not None:
            item = connection.execute("SELECT project_id,plan_id FROM study_plan_items WHERE id=?", (plan_item_id,)).fetchone()
            if item is None or item["project_id"] != project_id or (plan_id is not None and item["plan_id"] != plan_id):
                raise ValueError("cram_scope_conflict")
        connection.execute("INSERT INTO cram_goals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (goal_id, project_id, title, target_date, timezone_name, target_exercise_count, "draft",
                            plan_id, plan_item_id, now, now, None, None))
    return get_cram_goal(connection, project_id=project_id, goal_id=goal_id) or {}

def get_cram_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)).fetchone()
    return dict(row) if row is not None else None

def list_cram_goals(connection: sqlite3.Connection, *, project_id: str,
                    include_archived: bool = False) -> list[dict[str, object]]:
    query = "SELECT * FROM cram_goals WHERE project_id=?"
    params: list[object] = [project_id]
    if not include_archived:
        query += " AND status!='archived'"
    rows = connection.execute(query + " ORDER BY updated_at DESC,id DESC", params).fetchall()
    return [dict(row) for row in rows]

def transition_cram_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str, target: str) -> dict[str, object]:
    allowed = {"active": {"draft"}, "completed": {"active"}, "archived": {"draft", "active", "completed"}}
    with connection:
        row = connection.execute("SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)).fetchone()
        if row is None:
            raise ValueError("cram_goal_not_found")
        if target not in allowed or row["status"] not in allowed[target]:
            raise ValueError("cram_goal_invalid_state")
        if target == "completed" and connection.execute("SELECT 1 FROM practice_sessions WHERE cram_goal_id=? AND status IN ('finished','expired')", (goal_id,)).fetchone() is None:
            raise ValueError("cram_goal_not_ready")
        now = utc_now()
        connection.execute("UPDATE cram_goals SET status=?,updated_at=?,completed_at=?,archived_at=? WHERE id=?",
                           (target, now, now if target == "completed" else row["completed_at"],
                            now if target == "archived" else row["archived_at"], goal_id))
    return get_cram_goal(connection, project_id=project_id, goal_id=goal_id) or {}

def create_cram_session(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                        title: object, exercise_ids: list[str], duration_seconds: object = 600,
                        timezone_name: object = "UTC", local_date: object = "1970-01-01") -> dict[str, object]:
    """Create an explicit S5 session while reusing the S3 facts and grading."""
    goal = connection.execute(
        "SELECT * FROM cram_goals WHERE id=? AND project_id=?", (goal_id, project_id)
    ).fetchone()
    if goal is None:
        raise ValueError("cram_goal_not_found")
    if goal["status"] != "active":
        raise ValueError("cram_goal_invalid_state")
    if not isinstance(exercise_ids, list) or not exercise_ids or len(exercise_ids) > PHASE9C_SESSION_MAX_ITEMS:
        raise ValueError("cram_selection_invalid")
    if len(exercise_ids) > int(goal["target_exercise_count"]):
        raise ValueError("cram_selection_invalid")
    return create_practice_session(
        connection, project_id=project_id, title=title, exercise_ids=exercise_ids,
        duration_seconds=duration_seconds, timezone_name=timezone_name,
        local_date=local_date, session_kind="cram", cram_goal_id=goal_id,
    )

def get_cram_result(connection: sqlite3.Connection, *, project_id: str,
                    goal_id: str, session_id: str) -> dict[str, object] | None:
    goal = get_cram_goal(connection, project_id=project_id, goal_id=goal_id)
    if goal is None:
        return None
    session = get_practice_session(connection, project_id=project_id, session_id=session_id)
    if session is None or session["session_kind"] != "cram" or session["cram_goal_id"] != goal_id:
        raise ValueError("cram_session_scope_conflict")
    result = get_practice_result(connection, project_id=project_id, session_id=session_id)
    item_ids = [str(item["id"]) for item in session["items"]]
    if item_ids:
        marks = connection.execute(
            "SELECT COUNT(*) FROM mistake_occurrences o JOIN exercise_attempts a ON a.id=o.attempt_id "
            "WHERE a.session_item_id IN ({})".format(",".join("?" for _ in item_ids)), item_ids
        ).fetchone()[0]
    else:
        marks = 0
    exercise_ids = {str(item["exercise_id"]) for item in session["items"]}
    weak_points = [point for point in list_weak_points(connection, project_id=project_id)
                   if str(point["exercise_id"]) in exercise_ids]
    return {"goal": {key: goal[key] for key in (
        "id", "project_id", "title", "target_date", "timezone", "target_exercise_count", "status",
    )}, "session": result["session"], "summary": {
        **result["summary"], "mistake_count": int(marks), "weak_points": weak_points,
    }}

def create_practice_session(connection: sqlite3.Connection, *, project_id: str, title: object,
                            exercise_ids: list[str], duration_seconds: object = 600,
                            timezone_name: object = "UTC", local_date: object = "1970-01-01",
                            session_kind: str = "practice", cram_goal_id: str | None = None) -> dict[str, object]:
    title = _phase9c_text(title, code="practice_invalid_payload", maximum=PHASE9C_SESSION_TITLE_MAX)
    timezone_name = _phase9c_timezone(timezone_name, code="practice_invalid_payload")
    local_date = _phase9c_local_date(local_date, code="practice_invalid_payload")
    if session_kind not in {"practice", "cram"} or not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool) or not PHASE9C_MIN_DURATION_SECONDS <= duration_seconds <= PHASE9C_MAX_DURATION_SECONDS:
        raise ValueError("practice_invalid_payload")
    if not isinstance(exercise_ids, list) or not 1 <= len(exercise_ids) <= PHASE9C_SESSION_MAX_ITEMS or len(set(exercise_ids)) != len(exercise_ids):
        raise ValueError("practice_invalid_selection")
    session_id, now = f"practice_session_{uuid.uuid4().hex}", utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("project_not_found")
        if session_kind == "practice" and cram_goal_id is not None:
            raise ValueError("practice_scope_conflict")
        if session_kind == "cram":
            goal = connection.execute("SELECT project_id,status FROM cram_goals WHERE id=?", (cram_goal_id,)).fetchone()
            if goal is None or goal["project_id"] != project_id or goal["status"] != "active":
                raise ValueError("cram_scope_conflict")
        connection.execute("INSERT INTO practice_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (session_id, project_id, session_kind, cram_goal_id, "draft", title, duration_seconds,
                            timezone_name, local_date, None, None, None, now, now))
        for position, exercise_id in enumerate(exercise_ids):
            exercise = _phase9c_project_exercise(connection, project_id=project_id, exercise_id=exercise_id)
            source = _phase9c_source_snapshot(connection, exercise_id)
            connection.execute(
                "INSERT INTO practice_session_items (id,session_id,project_id,exercise_id,position,exercise_type,prompt,options_json,"
                "explanation_snapshot,exercise_kind,source_material_id,source_revision,source_extraction_id,source_chunk_id,source_span_id,"
                "citation_key,citation_status,answer_key_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"practice_item_{uuid.uuid4().hex}", session_id, project_id, exercise_id, position, exercise["exercise_type"],
                 exercise["prompt"], exercise["options_json"], exercise["explanation"], exercise["exercise_kind"],
                 source["source_material_id"], source["source_revision"], source["source_extraction_id"], source["source_chunk_id"],
                 source["source_span_id"], source["citation_key"], source["citation_status"], exercise["answer_key_json"], now, now),
            )
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone()
        return _phase9c_session_public(connection, row)

def get_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object] | None:
    with connection:
        now_text, now = _phase9c_iso_now()
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            return None
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        return _phase9c_session_public(connection, row)

def list_practice_sessions(connection: sqlite3.Connection, *, project_id: str,
                           status: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    query = "SELECT * FROM practice_sessions WHERE project_id=?"
    if status is not None:
        if status not in PHASE9C_SESSION_STATUSES:
            raise ValueError("practice_invalid_payload")
        query += " AND status=?"
        params.append(status)
    rows = connection.execute(query + " ORDER BY created_at DESC,id DESC", params).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        if row["status"] == "active":
            with connection:
                now_text, now = _phase9c_iso_now()
                row = _phase9c_expire_if_needed(connection, row, now, now_text)
        result.append(_phase9c_session_public(connection, row))
    return result

def get_practice_result(connection: sqlite3.Connection, *, project_id: str,
                        session_id: str) -> dict[str, object] | None:
    session = get_practice_session(connection, project_id=project_id, session_id=session_id)
    if session is None:
        return None
    summary = dict(session["summary"])
    scored_count = int(summary["scored_count"])
    summary["score_ratio"] = (float(summary["score_total"]) / scored_count) if scored_count else None
    return {"session": {key: session[key] for key in (
        "id", "project_id", "session_kind", "status", "title", "duration_seconds",
        "timezone", "local_date", "started_at", "deadline_at", "finished_at",
    )}, "summary": summary}

def start_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        if row["status"] != "draft":
            raise ValueError("practice_session_invalid_state")
        for item in connection.execute("SELECT exercise_id FROM practice_session_items WHERE session_id=? ORDER BY position", (session_id,)).fetchall():
            _phase9c_project_exercise(connection, project_id=project_id, exercise_id=item["exercise_id"])
        now_text, now = _phase9c_iso_now()
        deadline = (now + timedelta(seconds=int(row["duration_seconds"]))).isoformat()
        connection.execute("UPDATE practice_sessions SET status='active',started_at=?,deadline_at=?,updated_at=? WHERE id=?",
                           (now_text, deadline, now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())

def archive_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        now_text, now = _phase9c_iso_now()
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        if row["status"] not in {"draft", "finished", "expired"}:
            raise ValueError("practice_session_invalid_state")
        connection.execute("UPDATE practice_sessions SET status='archived',updated_at=? WHERE id=?", (now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())

def _phase9c_session_item(connection: sqlite3.Connection, *, project_id: str, session_id: str, item_id: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    session = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
    if session is None:
        raise ValueError("practice_session_not_found")
    item = connection.execute("SELECT * FROM practice_session_items WHERE id=? AND session_id=? AND project_id=?", (item_id, session_id, project_id)).fetchone()
    if item is None:
        raise ValueError("practice_session_item_not_found")
    return session, item

def submit_practice_session_item(connection: sqlite3.Connection, *, project_id: str, session_id: str,
                                 item_id: str, answer: object, submission_key: str | None = None) -> dict[str, object]:
    with connection:
        session, item = _phase9c_session_item(connection, project_id=project_id, session_id=session_id, item_id=item_id)
        now_text, now = _phase9c_iso_now()
        session = _phase9c_expire_if_needed(connection, session, now, now_text)
        if session["status"] != "active":
            # Expiry is a persisted server-time state transition, not a failed
            # submission write. Commit it before returning the stable conflict.
            if session["status"] == "expired":
                connection.commit()
                raise ValueError("practice_session_expired")
            raise ValueError("practice_session_invalid_state")
        if submission_key is not None:
            submission_key = _phase9c_text(submission_key, code="practice_invalid_submission", maximum=200)
            duplicate = connection.execute("SELECT * FROM exercise_attempts WHERE session_id=? AND submission_key=?", (session_id, submission_key)).fetchone()
            if duplicate is not None:
                if duplicate["answer_json"] != json.dumps(answer, ensure_ascii=False):
                    raise ValueError("practice_submission_idempotency_mismatch")
                return {"id": duplicate["id"], "exercise_id": duplicate["exercise_id"], "session_id": session_id,
                        "session_item_id": duplicate["session_item_id"], "score": duplicate["score"],
                        "is_correct": None if duplicate["is_correct"] is None else bool(duplicate["is_correct"]),
                        "grading_status": duplicate["grading_status"], "submitted_at": duplicate["submitted_at"], "replay": True}
        existing = connection.execute("SELECT * FROM exercise_attempts WHERE session_item_id=?", (item_id,)).fetchone()
        if existing is not None:
            return {"id": existing["id"], "exercise_id": existing["exercise_id"], "session_id": session_id,
                    "session_item_id": item_id, "score": existing["score"], "is_correct": None if existing["is_correct"] is None else bool(existing["is_correct"]),
                    "grading_status": existing["grading_status"], "submitted_at": existing["submitted_at"], "replay": True}
        expected = json.loads(item["answer_key_json"])
        correct = score = None
        grading = "pending_review"
        if item["exercise_type"] == "multiple_choice":
            options = json.loads(item["options_json"])
            if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer < len(options):
                raise ValueError("invalid_exercise_answer")
            correct, score, grading = answer == expected, 1.0 if answer == expected else 0.0, "deterministic"
        elif item["exercise_type"] == "true_false":
            if not isinstance(answer, bool):
                raise ValueError("invalid_exercise_answer")
            correct, score, grading = answer == expected, 1.0 if answer == expected else 0.0, "deterministic"
        elif not isinstance(answer, str) or not answer.strip() or len(answer) > MAX_EXERCISE_ANSWER_LENGTH:
            raise ValueError("invalid_exercise_answer")
        attempt_id = f"attempt_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO exercise_attempts (id,exercise_id,answer_json,score,is_correct,grading_status,submitted_at,reviewed_at,feedback,session_id,session_item_id,submission_key,submission_sequence) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, item["exercise_id"], json.dumps(answer, ensure_ascii=False), score, None if correct is None else int(correct),
             grading, now_text, None, "", session_id, item_id, submission_key, 0),
        )
        if correct is False:
            _phase9c_materialize_mistake(connection, project_id=project_id, attempt_id=attempt_id,
                                          exercise_id=str(item["exercise_id"]), reason_code="deterministic_incorrect", origin="deterministic",
                                          source_revision=item["source_revision"], source_status=item["citation_status"])
        return {"id": attempt_id, "exercise_id": item["exercise_id"], "session_id": session_id, "session_item_id": item_id,
                "score": score, "is_correct": correct, "grading_status": grading, "submitted_at": now_text, "replay": False}

def finish_practice_session(connection: sqlite3.Connection, *, project_id: str, session_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM practice_sessions WHERE id=? AND project_id=?", (session_id, project_id)).fetchone()
        if row is None:
            raise ValueError("practice_session_not_found")
        now_text, now = _phase9c_iso_now()
        row = _phase9c_expire_if_needed(connection, row, now, now_text)
        if row["status"] == "expired":
            return _phase9c_session_public(connection, row)
        if row["status"] != "active":
            raise ValueError("practice_session_invalid_state")
        connection.execute("UPDATE practice_sessions SET status='finished',finished_at=?,updated_at=? WHERE id=?", (now_text, now_text, session_id))
        return _phase9c_session_public(connection, connection.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone())

def _phase9c_mistake_case(connection: sqlite3.Connection, *, project_id: str, exercise_id: str,
                           origin: str, revision_fingerprint: str) -> str:
    row = connection.execute("SELECT id,status FROM mistake_cases WHERE project_id=? AND exercise_id=? AND exercise_revision_fingerprint=?",
                             (project_id, exercise_id, revision_fingerprint)).fetchone()
    if row is not None:
        if row["status"] == "archived":
            raise ValueError("mistake_archived")
        if row["status"] == "fixed":
            connection.execute("UPDATE mistake_cases SET status='reopened',updated_at=?,fixed_at=NULL WHERE id=?", (utc_now(), row["id"]))
        return str(row["id"])
    case_id = f"mistake_{uuid.uuid4().hex}"
    now = utc_now()
    connection.execute("INSERT INTO mistake_cases VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (case_id, project_id, exercise_id, revision_fingerprint, "open", origin, now, now, None, None))
    return case_id

