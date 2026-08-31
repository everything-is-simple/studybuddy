from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
def _phase9c_materialize_mistake(connection: sqlite3.Connection, *, project_id: str, attempt_id: str, exercise_id: str,
                                  reason_code: str, origin: str, source_revision: str | None, source_status: str) -> str:
    fingerprint = hashlib.sha256(f"{exercise_id}\x1f{source_revision or ''}".encode()).hexdigest()
    case_id = _phase9c_mistake_case(connection, project_id=project_id, exercise_id=exercise_id, origin=origin, revision_fingerprint=fingerprint)
    existing = connection.execute("SELECT id FROM mistake_occurrences WHERE attempt_id=? AND reason_code=?", (attempt_id, reason_code)).fetchone()
    if existing is not None:
        return str(existing["id"])
    occurrence_id = f"mistake_occurrence_{uuid.uuid4().hex}"
    connection.execute("INSERT INTO mistake_occurrences VALUES (?,?,?,?,?,?,?,?,?)",
                       (occurrence_id, project_id, case_id, attempt_id, origin, reason_code, source_revision,
                        source_status if source_status in PHASE9C_SOURCE_STATUSES else "source_unavailable", utc_now()))
    return occurrence_id

def _phase9c_attempt_source(connection: sqlite3.Connection, attempt: sqlite3.Row) -> tuple[str | None, str]:
    if attempt["session_item_id"] is not None:
        item = connection.execute(
            "SELECT source_revision,citation_status FROM practice_session_items WHERE id=?",
            (attempt["session_item_id"],),
        ).fetchone()
        if item is not None:
            return item["source_revision"], item["citation_status"]
    citation = connection.execute(
        "SELECT revision_id,status FROM exercise_citations WHERE exercise_id=? ORDER BY position,id LIMIT 1",
        (attempt["exercise_id"],),
    ).fetchone()
    if citation is None:
        return None, "valid"
    return citation["revision_id"], citation["status"] if citation["status"] in PHASE9C_SOURCE_STATUSES else "source_unavailable"

def mark_mistake_from_attempt(connection: sqlite3.Connection, *, project_id: str, attempt_id: str,
                              feedback: object = "") -> dict[str, object]:
    """Explicit user marking; it is never inferred from an uncertain answer."""
    feedback = _phase9c_text(feedback, code="mistake_feedback_invalid", maximum=PHASE9C_CORRECTION_MAX, allow_empty=True)
    with connection:
        attempt = connection.execute(
            "SELECT a.* FROM exercise_attempts a JOIN exercises e ON e.id=a.exercise_id "
            "WHERE a.id=? AND e.project_id=?", (attempt_id, project_id)
        ).fetchone()
        if attempt is None:
            raise ValueError("attempt_not_found")
        source_revision, source_status = _phase9c_attempt_source(connection, attempt)
        _phase9c_materialize_mistake(
            connection, project_id=project_id, attempt_id=attempt_id, exercise_id=attempt["exercise_id"],
            reason_code="user_marked", origin="user_reported", source_revision=source_revision,
            source_status=source_status,
        )
        case = connection.execute(
            "SELECT id FROM mistake_cases WHERE project_id=? AND exercise_id=? "
            "ORDER BY updated_at DESC,id DESC LIMIT 1", (project_id, attempt["exercise_id"])
        ).fetchone()
        if feedback:
            add_mistake_feedback(connection, project_id=project_id, mistake_case_id=str(case["id"]),
                                 event_kind="user_note", content=feedback)
        return get_mistake_case(connection, project_id=project_id, mistake_case_id=str(case["id"])) or {}

def review_exercise_attempt(connection: sqlite3.Connection, *, project_id: str, attempt_id: str,
                            decision: str, feedback: object = "") -> dict[str, object]:
    feedback = _phase9c_text(feedback, code="review_invalid_payload", maximum=PHASE9C_FEEDBACK_MAX, allow_empty=True)
    if decision not in {"correct", "incorrect", "uncertain"}:
        raise ValueError("review_invalid_decision")
    with connection:
        attempt = connection.execute(
            "SELECT a.* FROM exercise_attempts a JOIN exercises e ON e.id=a.exercise_id "
            "WHERE a.id=? AND e.project_id=?", (attempt_id, project_id)
        ).fetchone()
        if attempt is None:
            raise ValueError("attempt_not_found")
        if attempt["grading_status"] != "pending_review":
            raise ValueError("review_not_allowed")
        if connection.execute("SELECT 1 FROM exercise_attempt_reviews WHERE attempt_id=?", (attempt_id,)).fetchone() is not None:
            raise ValueError("review_duplicate")
        now = utc_now()
        review_id = f"review_{uuid.uuid4().hex}"
        connection.execute("INSERT INTO exercise_attempt_reviews VALUES (?,?,?,?,?,?,?,?,?)",
                           (review_id, project_id, attempt_id, attempt["exercise_id"], decision, feedback, "local_user", now, now))
        if decision == "incorrect":
            source_revision, source_status = _phase9c_attempt_source(connection, attempt)
            _phase9c_materialize_mistake(connection, project_id=project_id, attempt_id=attempt_id, exercise_id=attempt["exercise_id"],
                                          reason_code="review_incorrect", origin="human_review", source_revision=source_revision, source_status=source_status)
        return {"id": review_id, "attempt_id": attempt_id, "decision": decision, "feedback": feedback, "reviewer_kind": "local_user", "reviewed_at": now}

def add_mistake_feedback(connection: sqlite3.Connection, *, project_id: str, mistake_case_id: str,
                         event_kind: str, content: object) -> dict[str, object]:
    content = _phase9c_text(content, code="mistake_feedback_invalid", maximum=PHASE9C_CORRECTION_MAX,
                             allow_empty=event_kind != "user_correction")
    if event_kind not in {"user_correction", "user_note", "status_transition"}:
        raise ValueError("mistake_feedback_invalid")
    with connection:
        case = connection.execute("SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)).fetchone()
        if case is None:
            raise ValueError("mistake_not_found")
        if case["status"] == "archived":
            raise ValueError("mistake_invalid_state")
        now, event_id = utc_now(), f"feedback_{uuid.uuid4().hex}"
        connection.execute("INSERT INTO mistake_feedback_events VALUES (?,?,?,?,?,?,?)",
                           (event_id, project_id, mistake_case_id, event_kind, content, "user_created", now))
        if event_kind == "user_correction":
            connection.execute("UPDATE mistake_cases SET status='fixed',fixed_at=?,updated_at=? WHERE id=?", (now, now, mistake_case_id))
        elif event_kind == "status_transition":
            connection.execute("UPDATE mistake_cases SET status='in_review',updated_at=? WHERE id=? AND status='open'", (now, mistake_case_id))
        return {"id": event_id, "mistake_case_id": mistake_case_id, "event_kind": event_kind, "content": content, "provenance": "user_created", "created_at": now}

def archive_mistake_case(connection: sqlite3.Connection, *, project_id: str, mistake_case_id: str) -> dict[str, object]:
    with connection:
        row = connection.execute("SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)).fetchone()
        if row is None:
            raise ValueError("mistake_not_found")
        if row["status"] == "archived":
            raise ValueError("mistake_invalid_state")
        now = utc_now()
        connection.execute("UPDATE mistake_cases SET status='archived',archived_at=?,updated_at=? WHERE id=?",
                           (now, now, mistake_case_id))
        result = connection.execute("SELECT * FROM mistake_cases WHERE id=?", (mistake_case_id,)).fetchone()
        return dict(result)

def get_mistake_case(connection: sqlite3.Connection, *, project_id: str,
                     mistake_case_id: str) -> dict[str, object] | None:
    case = connection.execute(
        "SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)
    ).fetchone()
    if case is None:
        return None
    occurrences = [dict(row) for row in connection.execute(
        "SELECT id,mistake_case_id,attempt_id,origin,reason_code,source_revision,source_status,created_at "
        "FROM mistake_occurrences WHERE mistake_case_id=? ORDER BY created_at,id", (mistake_case_id,)
    ).fetchall()]
    feedback = [dict(row) for row in connection.execute(
        "SELECT id,mistake_case_id,event_kind,content,provenance,created_at "
        "FROM mistake_feedback_events WHERE mistake_case_id=? ORDER BY created_at,id", (mistake_case_id,)
    ).fetchall()]
    return {**dict(case), "occurrences": occurrences, "feedback_events": feedback}

def list_mistake_cases(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT * FROM mistake_cases WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [get_mistake_case(connection, project_id=project_id, mistake_case_id=str(row["id"])) or {} for row in rows]

def redo_mistake_case(connection: sqlite3.Connection, *, project_id: str,
                      mistake_case_id: str, title: object | None = None) -> dict[str, object]:
    with connection:
        case = connection.execute(
            "SELECT * FROM mistake_cases WHERE id=? AND project_id=?", (mistake_case_id, project_id)
        ).fetchone()
        if case is None:
            raise ValueError("mistake_not_found")
        if case["status"] == "archived":
            raise ValueError("mistake_archived")
        source = connection.execute(
            "SELECT a.session_id,s.session_kind,s.cram_goal_id,s.timezone,s.local_date,s.duration_seconds "
            "FROM mistake_occurrences o JOIN exercise_attempts a ON a.id=o.attempt_id "
            "LEFT JOIN practice_sessions s ON s.id=a.session_id "
            "WHERE o.mistake_case_id=? ORDER BY o.created_at DESC,o.id DESC LIMIT 1", (mistake_case_id,)
        ).fetchone()
        if source is None:
            raise ValueError("mistake_redo_not_ready")
        session_kind = source["session_kind"] or "practice"
        cram_goal_id = source["cram_goal_id"] if session_kind == "cram" else None
        session_title = title if title is not None else f"Redo: {case['exercise_id']}"
    return create_practice_session(
        connection, project_id=project_id, title=session_title,
        exercise_ids=[str(case["exercise_id"])], duration_seconds=int(source["duration_seconds"] or 600),
        timezone_name=str(source["timezone"] or "UTC"), local_date=str(source["local_date"] or date.today().isoformat()),
        session_kind=session_kind, cram_goal_id=cram_goal_id,
    )

def list_weak_points(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT c.exercise_id,c.exercise_revision_fingerprint,COUNT(o.id) AS occurrence_count,"
        "SUM(CASE WHEN c.status IN ('open','in_review','reopened') THEN 1 ELSE 0 END) AS open_count,"
        "SUM(CASE WHEN c.status='fixed' THEN 1 ELSE 0 END) AS fixed_count,"
        "SUM(CASE WHEN c.status='reopened' THEN 1 ELSE 0 END) AS reopened_count,"
        "SUM(CASE WHEN o.source_status!='valid' THEN 1 ELSE 0 END) AS source_warning_count,"
        "MAX(o.created_at) AS last_occurrence_at "
        "FROM mistake_cases c JOIN mistake_occurrences o ON o.mistake_case_id=c.id "
        "WHERE c.project_id=? AND c.status!='archived' GROUP BY c.exercise_id,c.exercise_revision_fingerprint "
        "ORDER BY last_occurrence_at DESC", (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]

def recommend_practice_exercises(connection: sqlite3.Connection, *, project_id: str, limit: int = 10,
                                  weak_point: str | None = None) -> dict[str, object]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("practice_recommendation_invalid_query")
    if weak_point is not None:
        if not isinstance(weak_point, str) or not 1 <= len(weak_point.strip()) <= 200:
            raise ValueError("practice_recommendation_invalid_query")
        weak_point = weak_point.strip()
    rows = connection.execute(
        "SELECT e.* FROM exercises e WHERE e.project_id=? AND e.status='ready' "
        "ORDER BY e.id", (project_id,)).fetchall()
    items = []
    for row in rows:
        citations = connection.execute(
            "SELECT status FROM exercise_citations WHERE exercise_id=?", (row["id"],)
        ).fetchall()
        if row["exercise_kind"] == "ai_generated" and (not citations or any(c["status"] != "valid" for c in citations)):
            continue
        if any(c["status"] != "valid" for c in citations):
            continue
        attempts = connection.execute(
            "SELECT grading_status,is_correct,submitted_at FROM exercise_attempts WHERE exercise_id=? ORDER BY submitted_at DESC",
            (row["id"],)).fetchall()
        incorrect = sum(1 for a in attempts if a["is_correct"] == 0)
        pending = sum(1 for a in attempts if a["grading_status"] == "pending_review")
        weak_match = bool(weak_point and weak_point.lower() in str(row["prompt"]).lower())
        if weak_point and not weak_match:
            continue
        reasons = []
        if not attempts: reasons.append("never_attempted")
        if incorrect: reasons.append("recent_incorrect")
        if pending: reasons.append("pending_review")
        if weak_match: reasons.append("weak_point_match")
        reasons.append("source_valid")
        items.append({"exercise_id": row["id"], "exercise_type": row["exercise_type"], "prompt": row["prompt"],
                      "options": json.loads(row["options_json"]), "status": row["status"], "source_status": "valid",
                      "weak_point": weak_point if weak_match else None,
                      "attempt_summary": {"attempt_count": len(attempts), "incorrect_count": incorrect,
                                          "pending_review_count": pending,
                                          "last_attempt_at": attempts[0]["submitted_at"] if attempts else None},
                      "reason_codes": reasons})
    items.sort(key=lambda item: (0 if not item["attempt_summary"]["attempt_count"] else 1,
                                 0 if weak_point and item["weak_point"] else 1,
                                 -item["attempt_summary"]["incorrect_count"],
                                 -item["attempt_summary"]["pending_review_count"],
                                 item["attempt_summary"]["last_attempt_at"] is not None,
                                 item["attempt_summary"]["last_attempt_at"] or "",
                                 item["attempt_summary"]["attempt_count"], item["exercise_id"]))
    labels = {"never_attempted": "尚未练习", "recent_incorrect": "近期答错较多",
              "pending_review": "等待人工复核", "weak_point_match": "匹配当前薄弱点", "source_valid": "来源当前可用"}
    for item in items:
        item["reason_labels"] = [labels[code] for code in item["reason_codes"]]
    return {"status": "ready" if items[:limit] else "empty", "algorithm_version": "practice-recommendation-v1",
            "generated_at": utc_now(), "limit": limit, "items": items[:limit]}

PHASE9D_TRANSCRIPTION_OPERATION = "class_capture_transcription"

PHASE9D_TRANSCRIPT_CONFIDENCE_THRESHOLD = 0.70

PHASE9D_TRANSCRIPT_MAX_SEGMENTS = 1000

PHASE9D_TRANSCRIPT_MAX_TEXT = 200000

PHASE9D_REPORT_CONTENT_VERSION = "phase9d_report_v1"

PHASE9D_REPORT_KINDS = {"daily", "weekly", "monthly", "exam_alert"}

PHASE9D_REPORT_EXPORT_FORMATS = {"json", "markdown"}

# B3 report exports are bounded independently of upload/provider limits.
PHASE9D_REPORT_MAX_EXPORT_BYTES = 1024 * 1024

PHASE9D_REPORT_PAYLOAD_FIELDS = {
    "period": {"report_kind", "period_start", "period_end", "timezone", "generated_at"},
    "plan": {"active_goal_count", "active_plan_count", "planned_item_count", "completed_item_count",
             "started_item_count", "skipped_item_count", "planned_minutes_total"},
    "rhythm": {"allocated_day_count", "allocated_minutes_total", "unallocated_eligible_item_count", "overload_day_count"},
    "practice": {"practice_session_count", "cram_session_count", "attempt_count", "deterministic_correct_count",
                 "deterministic_incorrect_count", "pending_review_count", "completed_session_count"},
    "feedback": {"open_mistake_count", "in_review_count", "fixed_count", "reopened_count", "archived_count", "weak_point_count"},
    "source_quality": {"valid_source_count", "stale_count", "source_deleted_count", "source_unavailable_count",
                       "uncertain_transcript_segment_count"},
    "quality_flags": {"has_pending_review", "has_source_warnings", "has_uncertain_capture"},
    "exam_alert": {"days_remaining_bucket", "is_imminent"},
}

PHASE9D_CAPTURE_ASSET_TYPES = {
    "audio": {"audio/wav", "audio/mpeg", "audio/mp4"},
    "image": {"image/png", "image/jpeg", "image/webp"},
}

PHASE9D_CAPTURE_SUFFIXES = {
    "image/png": {".png"}, "image/jpeg": {".jpg", ".jpeg"}, "image/webp": {".webp"},
    "audio/wav": {".wav"}, "audio/mpeg": {".mp3"}, "audio/mp4": {".m4a", ".mp4"},
}

PHASE9D_CAPTURE_PARSER_ID = "class_capture_original"

PHASE9D_CAPTURE_PARSER_VERSION = "1"

PHASE9D_TRANSCRIPT_PARSER_ID = "class_capture_transcript"

PHASE9D_TRANSCRIPT_PARSER_VERSION = "s2_v1"

PHASE9D_DELIVERY_CHANNELS = {"smtp", "feishu"}

PHASE9D_DELIVERY_MODES = {"off", "dry_run", "live"}

PHASE9D_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}

PHASE9D_TRANSCRIPTION_ERROR_CODES = {
    "transcription_failed", "transcription_provider_not_configured", "provider_timeout",
    "provider_unavailable", "capture_source_unavailable", "transcript_empty_or_invalid", "payload_too_large",
}

def _phase9d_text(value: object, *, code: str, maximum: int,
                   allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError(code)
    result = value.strip()
    if not result and not allow_empty:
        raise ValueError(code)
    return result

def _phase9d_idempotency_key(value: object | None) -> str | None:
    if value is None:
        return None
    return _phase9d_text(value, code="invalid_idempotency_key", maximum=200)

def _phase9d_asset_signature_valid(media_type: str, header: bytes) -> bool:
    checks = {
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "image/webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
        "audio/wav": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WAVE",
        "audio/mpeg": lambda value: value.startswith(b"ID3") or (len(value) >= 2 and value[0] == 0xff and value[1] & 0xe0 == 0xe0),
        "audio/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
    }
    return media_type in checks and checks[media_type](header)

def _phase9d_capture_source_status(connection: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    material_id = row["material_id"]
    if material_id is None:
        return None
    material = connection.execute(
        "SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)
    ).fetchone()
    if material is None or material["project_id"] != row["project_id"]:
        return "source_unavailable"
    if material["deleted_at"] is not None:
        return "source_deleted"
    persisted = row["source_status"]
    if persisted in {"source_deleted", "source_unavailable", "stale"}:
        return str(persisted)
    return "valid"

def _phase9d_transcript_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    segments = [dict(segment) for segment in connection.execute(
        "SELECT id,ordinal,text,confidence,quality,created_at,updated_at FROM transcript_segments "
        "WHERE draft_id=? AND project_id=? ORDER BY ordinal,id", (row["id"], row["project_id"])
    ).fetchall()]
    return {
        "id": row["id"], "capture_session_id": row["capture_session_id"],
        "operation_id": row["operation_id"], "status": row["status"], "text": row["text"],
        "language": row["language"], "quality_status": row["quality_status"],
        "edited_by_user": bool(row["edited_by_user"]), "created_at": row["created_at"],
        "updated_at": row["updated_at"], "segments": segments,
    }

def _phase9d_operation_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    return {
        "id": row["id"], "operation_type": row["operation_type"], "status": row["status"],
        "capture_session_id": row["capture_session_id"], "provider_id": row["provider_id"],
        "model_id": row["model_id"], "retry_count": int(row["retry_count"]),
        "error_code": row["error_code"], "output_artifact_id": row["output_artifact_id"],
        "created_at": row["created_at"], "started_at": row["started_at"],
        "finished_at": row["finished_at"], "replay": replay,
    }

def _phase9d_capture_public(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    drafts = [_phase9d_transcript_public(connection, draft) for draft in connection.execute(
        "SELECT * FROM transcript_drafts WHERE capture_session_id=? AND project_id=? "
        "ORDER BY created_at,id", (row["id"], row["project_id"])
    ).fetchall()]
    operations = [_phase9d_operation_public(operation) for operation in connection.execute(
        "SELECT * FROM ai_operations WHERE capture_session_id=? AND project_id=? "
        "AND operation_type=? ORDER BY created_at,id",
        (row["id"], row["project_id"], PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchall()]
    return {
        "id": row["id"], "project_id": row["project_id"], "status": row["status"],
        "asset_kind": row["asset_kind"], "material_id": row["material_id"],
        "original_name": row["original_name"], "media_type": row["media_type"],
        "source_status": _phase9d_capture_source_status(connection, row),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "confirmed_at": row["confirmed_at"], "rejected_at": row["rejected_at"],
        "archived_at": row["archived_at"], "transcript_drafts": drafts,
        "transcription_operations": operations,
    }

def create_capture_session(connection: sqlite3.Connection, *, project_id: str,
                           asset_kind: object, original_name: object, media_type: object,
                           material_id: str | None = None) -> dict[str, object]:
    if asset_kind not in PHASE9D_CAPTURE_ASSET_TYPES:
        raise ValueError("capture_asset_type_not_supported")
    name = _phase9d_text(original_name, code="capture_invalid_payload", maximum=255)
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("capture_invalid_payload")
    media = _phase9d_text(media_type, code="capture_asset_type_not_supported", maximum=100)
    if media not in PHASE9D_CAPTURE_ASSET_TYPES[str(asset_kind)]:
        raise ValueError("capture_asset_type_not_supported")
    capture_id, now = f"capture_session_{uuid.uuid4().hex}", utc_now()
    with connection:
        connection.execute(
            "INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)",
            (project_id, "Default project", now),
        )
        source_status = None
        status = "draft"
        if material_id is not None:
            material = connection.execute(
                "SELECT project_id,original_name,media_type,deleted_at FROM materials WHERE id=?", (material_id,)
            ).fetchone()
            if material is None:
                raise ValueError("capture_source_unavailable")
            if material["project_id"] != project_id:
                raise ValueError("project_scope_violation")
            if material["deleted_at"] is not None:
                raise ValueError("capture_source_unavailable")
            if material["media_type"] not in PHASE9D_CAPTURE_ASSET_TYPES[str(asset_kind)]:
                raise ValueError("capture_asset_type_not_supported")
            name, media = str(material["original_name"]), str(material["media_type"])
            source_status, status = "valid", "uploaded"
        try:
            connection.execute(
                "INSERT INTO capture_sessions (id,project_id,status,asset_kind,material_id,original_name,media_type,"
                "source_status,created_at,updated_at,confirmed_at,rejected_at,archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                (capture_id, project_id, status, asset_kind, material_id, name, media,
                 source_status, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("capture_invalid_state") from exc
    return get_capture_session(connection, project_id=project_id, capture_session_id=capture_id) or {}
