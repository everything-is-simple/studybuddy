from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
from ._legacy_part_05 import *
from ._legacy_part_06 import *
from ._legacy_part_07 import *
def build_report_projection(connection: sqlite3.Connection, *, project_id: str,
                            report_kind: object, timezone_name: object,
                            period_start: object, period_end: object) -> dict[str, object]:
    kind, timezone_value, start_value, _zone, start_utc, end_utc = _phase9d_report_period(
        report_kind, timezone_name, period_start, period_end
    )
    end_value = date.fromisoformat(str(period_end)).isoformat()
    if not _study_project_exists(connection, project_id):
        raise ValueError("project_scope_violation")

    goals = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM learning_goals WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)
    plans = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM study_plans WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)
    items = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,status,updated_at FROM study_plan_items WHERE project_id=?", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc)

    allocations = [row for row in connection.execute(
        "SELECT a.id,a.plan_id,a.item_id,a.local_date,a.planned_minutes,s.cadence,s.target_minutes "
        "FROM rhythm_allocations a LEFT JOIN rhythm_settings s ON s.plan_id=a.plan_id AND s.project_id=a.project_id "
        "WHERE a.project_id=?", (project_id,)
    ).fetchall() if start_value <= str(row["local_date"]) < end_value]
    allocation_item_ids = {str(row["item_id"]) for row in allocations}
    daily_totals: dict[tuple[str, str], int] = {}
    daily_targets: dict[tuple[str, str], int] = {}
    for row in allocations:
        key = (str(row["plan_id"]), str(row["local_date"]))
        daily_totals[key] = daily_totals.get(key, 0) + int(row["planned_minutes"])
        if row["cadence"] == "daily" and row["target_minutes"] is not None:
            daily_targets[key] = int(row["target_minutes"])

    sessions = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,session_kind,status,created_at FROM practice_sessions WHERE project_id=?", (project_id,)
    ).fetchall()), "created_at", start_utc, end_utc)
    attempts = _phase9d_rows_in_period(list(connection.execute(
        "SELECT a.id,a.grading_status,a.is_correct,a.submitted_at FROM exercise_attempts a "
        "JOIN exercises e ON e.id=a.exercise_id WHERE e.project_id=?", (project_id,)
    ).fetchall()), "submitted_at", start_utc, end_utc)
    cases = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,exercise_id,exercise_revision_fingerprint,status,updated_at FROM mistake_cases WHERE project_id=?",
        (project_id,),
    ).fetchall()), "updated_at", start_utc, end_utc)

    source_rows: list[sqlite3.Row] = []
    for table in ("module_source_links", "plan_item_source_links", "note_block_source_links"):
        source_rows.extend(_phase9d_rows_in_period(list(connection.execute(
            f"SELECT id,status,updated_at FROM {table} WHERE project_id=?", (project_id,)
        ).fetchall()), "updated_at", start_utc, end_utc))
    source_rows.extend(_phase9d_rows_in_period(list(connection.execute(
        "SELECT c.id,CASE WHEN m.id IS NULL THEN 'source_unavailable' "
        "WHEN m.deleted_at IS NOT NULL THEN 'source_deleted' "
        "ELSE COALESCE(c.source_status,'source_unavailable') END AS status,c.updated_at "
        "FROM capture_sessions c LEFT JOIN materials m ON m.id=c.material_id "
        "WHERE c.project_id=? AND c.material_id IS NOT NULL", (project_id,)
    ).fetchall()), "updated_at", start_utc, end_utc))
    uncertain_segments = _phase9d_rows_in_period(list(connection.execute(
        "SELECT id,created_at FROM transcript_segments WHERE project_id=? AND quality='uncertain'", (project_id,)
    ).fetchall()), "created_at", start_utc, end_utc)

    active_cram_targets = []
    for row in connection.execute(
        "SELECT id,target_date FROM cram_goals WHERE project_id=? AND status='active'", (project_id,)
    ).fetchall():
        try:
            days = (date.fromisoformat(str(row["target_date"])) - date.fromisoformat(start_value)).days
        except ValueError:
            continue
        if days >= 0:
            active_cram_targets.append((days, str(row["id"])))
    active_cram_targets.sort()
    nearest_days = active_cram_targets[0][0] if active_cram_targets else None
    if nearest_days is None:
        days_bucket = None
    elif nearest_days <= 3:
        days_bucket = "0-3"
    elif nearest_days <= 7:
        days_bucket = "4-7"
    elif nearest_days <= 14:
        days_bucket = "8-14"
    else:
        days_bucket = "15+"

    item_counts = {status: sum(row["status"] == status for row in items)
                   for status in ("pending", "in_progress", "completed", "skipped")}
    case_counts = {status: sum(row["status"] == status for row in cases)
                   for status in ("open", "in_review", "fixed", "reopened", "archived")}
    source_counts = {status: sum(row["status"] == status for row in source_rows)
                     for status in PHASE9D_SOURCE_STATUSES}
    deterministic = [row for row in attempts if row["grading_status"] == "deterministic"]
    planned_minutes = sum(int(row["planned_minutes"]) for row in allocations)
    payload: dict[str, object] = {
        "period": {"report_kind": kind, "period_start": start_value, "period_end": end_value,
                   "timezone": timezone_value, "generated_at": utc_now()},
        "plan": {"active_goal_count": sum(row["status"] == "active" for row in goals),
                 "active_plan_count": sum(row["status"] == "active" for row in plans),
                 "planned_item_count": sum(row["status"] != "archived" for row in items),
                 "completed_item_count": item_counts["completed"],
                 "started_item_count": item_counts["in_progress"],
                 "skipped_item_count": item_counts["skipped"],
                 "planned_minutes_total": planned_minutes},
        "rhythm": {"allocated_day_count": len({str(row["local_date"]) for row in allocations}),
                   "allocated_minutes_total": planned_minutes,
                   "unallocated_eligible_item_count": sum(
                       row["status"] != "archived" and str(row["id"]) not in allocation_item_ids for row in items
                   ),
                   "overload_day_count": sum(total > daily_targets[key] for key, total in daily_totals.items()
                                             if key in daily_targets)},
        "practice": {"practice_session_count": sum(row["session_kind"] == "practice" for row in sessions),
                     "cram_session_count": sum(row["session_kind"] == "cram" for row in sessions),
                     "attempt_count": len(attempts),
                     "deterministic_correct_count": sum(row["is_correct"] == 1 for row in deterministic),
                     "deterministic_incorrect_count": sum(row["is_correct"] == 0 for row in deterministic),
                     "pending_review_count": sum(row["grading_status"] == "pending_review" for row in attempts),
                     "completed_session_count": sum(row["status"] in {"finished", "expired"} for row in sessions)},
        "feedback": {"open_mistake_count": case_counts["open"],
                     "in_review_count": case_counts["in_review"], "fixed_count": case_counts["fixed"],
                     "reopened_count": case_counts["reopened"], "archived_count": case_counts["archived"],
                     "weak_point_count": len({(str(row["exercise_id"]), str(row["exercise_revision_fingerprint"]))
                                              for row in cases if row["status"] != "archived"})},
        "source_quality": {"valid_source_count": source_counts["valid"],
                           "stale_count": source_counts["stale"],
                           "source_deleted_count": source_counts["source_deleted"],
                           "source_unavailable_count": source_counts["source_unavailable"],
                           "uncertain_transcript_segment_count": len(uncertain_segments)},
        "exam_alert": {"days_remaining_bucket": days_bucket,
                       "is_imminent": nearest_days is not None and nearest_days <= 7},
    }
    payload["quality_flags"] = {
        "has_pending_review": payload["practice"]["pending_review_count"] > 0,
        "has_source_warnings": sum(source_counts[status] for status in ("stale", "source_deleted", "source_unavailable")) > 0,
        "has_uncertain_capture": len(uncertain_segments) > 0,
    }
    basis = json.loads(json.dumps(payload))
    basis["period"].pop("generated_at", None)
    fact_identity = {
        "goals": [(row["id"], row["status"], row["updated_at"]) for row in goals],
        "plans": [(row["id"], row["status"], row["updated_at"]) for row in plans],
        "items": [(row["id"], row["status"], row["updated_at"]) for row in items],
        "allocations": [(row["id"], row["local_date"], row["planned_minutes"]) for row in allocations],
        "sessions": [(row["id"], row["status"], row["created_at"]) for row in sessions],
        "attempts": [(row["id"], row["grading_status"], row["is_correct"], row["submitted_at"]) for row in attempts],
        "cases": [(row["id"], row["status"], row["updated_at"]) for row in cases],
        "sources": [(row["id"], row["status"], row["updated_at"]) for row in source_rows],
        "uncertain_segments": [(row["id"], row["created_at"]) for row in uncertain_segments],
        "cram_targets": active_cram_targets,
    }
    for identities in fact_identity.values():
        identities.sort(key=lambda identity: tuple("" if value is None else str(value) for value in identity))
    fingerprint_source = json.dumps(
        {"version": PHASE9D_REPORT_CONTENT_VERSION, "payload": basis, "facts": fact_identity},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    _phase9d_validate_safe_payload(payload)
    return {"safe_payload": payload, "markdown_content": _phase9d_safe_markdown(payload),
            "aggregation_fingerprint": hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
            "content_version": PHASE9D_REPORT_CONTENT_VERSION}

def _phase9d_report_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    try:
        payload = _phase9d_validate_safe_payload(json.loads(str(row["safe_payload_json"])))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("report_redaction_violation") from None
    return {
        "id": row["id"], "project_id": row["project_id"], "report_kind": row["report_kind"],
        "timezone": row["timezone"], "period_start": row["period_start"],
        "period_end": row["period_end"], "status": row["status"],
        "content_version": row["content_version"], "safe_payload": payload,
        "markdown_content": row["markdown_content"], "error_code": row["error_code"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "ready_at": row["ready_at"], "archived_at": row["archived_at"], "replay": replay,
    }

def export_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                           report_id: str, format_name: object = "json") -> tuple[str, str]:
    if not isinstance(format_name, str) or format_name not in PHASE9D_REPORT_EXPORT_FORMATS:
        raise ValueError("report_redaction_violation")
    report = get_report_snapshot(connection, project_id=project_id, report_id=report_id)
    if report is None:
        raise ValueError("report_not_found")
    if report["status"] != "ready":
        raise ValueError("report_invalid_state")
    payload = _phase9d_validate_safe_payload(report["safe_payload"])
    if format_name == "json":
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(content.encode("utf-8")) > PHASE9D_REPORT_MAX_EXPORT_BYTES:
            raise ValueError("payload_too_large")
        return content, "application/json"
    markdown = str(report["markdown_content"])
    if not markdown or "stored_path" in markdown or "answer_key" in markdown or "answer_json" in markdown:
        raise ValueError("report_redaction_violation")
    if len(markdown.encode("utf-8")) > PHASE9D_REPORT_MAX_EXPORT_BYTES:
        raise ValueError("payload_too_large")
    return markdown, "text/markdown"

def create_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                           report_kind: object, timezone_name: object,
                           period_start: object, period_end: object) -> dict[str, object]:
    with connection:
        projection = build_report_projection(
            connection, project_id=project_id, report_kind=report_kind,
            timezone_name=timezone_name, period_start=period_start, period_end=period_end,
        )
        period = projection["safe_payload"]["period"]
        existing = connection.execute(
            "SELECT * FROM report_snapshots WHERE project_id=? AND report_kind=? AND period_start=? "
            "AND period_end=? AND content_version=? AND aggregation_fingerprint=?",
            (project_id, period["report_kind"], period["period_start"], period["period_end"],
             projection["content_version"], projection["aggregation_fingerprint"]),
        ).fetchone()
        if existing is not None:
            return _phase9d_report_public(existing, replay=True)
        report_id, now = f"report_{uuid.uuid4().hex}", utc_now()
        safe_json = json.dumps(
            projection["safe_payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        connection.execute(
            "INSERT INTO report_snapshots (id,project_id,report_kind,timezone,period_start,period_end,status,"
            "content_version,aggregation_fingerprint,safe_payload_json,markdown_content,error_code,created_at,"
            "updated_at,ready_at,archived_at) VALUES (?,?,?,?,?,?,'ready',?,?,?,?,NULL,?,?,?,NULL)",
            (report_id, project_id, period["report_kind"], period["timezone"], period["period_start"],
             period["period_end"], projection["content_version"], projection["aggregation_fingerprint"], safe_json,
             projection["markdown_content"], now, now, now),
        )
        row = connection.execute("SELECT * FROM report_snapshots WHERE id=?", (report_id,)).fetchone()
        return _phase9d_report_public(row)

def get_report_snapshot(connection: sqlite3.Connection, *, project_id: str,
                        report_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
    ).fetchone()
    return _phase9d_report_public(row) if row is not None else None

def list_report_snapshots(connection: sqlite3.Connection, *, project_id: str,
                          include_archived: bool = False) -> list[dict[str, object]]:
    clause = "" if include_archived else " AND status!='archived'"
    rows = connection.execute(
        "SELECT * FROM report_snapshots WHERE project_id=?" + clause + " ORDER BY created_at DESC,id DESC",
        (project_id,),
    ).fetchall()
    return [_phase9d_report_public(row) for row in rows]

def _phase9d_target_label(value: object) -> str:
    label = _phase9d_text(value, code="delivery_target_not_allowed", maximum=100)
    if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in label):
        raise ValueError("delivery_target_not_allowed")
    return label

def _phase9d_delivery_public(row: sqlite3.Row, *, replay: bool = False) -> dict[str, object]:
    return {
        "id": row["id"], "report_id": row["report_id"], "channel": row["channel"],
        "mode": row["mode"], "target_label": row["target_label"], "status": row["status"],
        "error_code": row["error_code"], "retry_of": row["retry_of"],
        "created_at": row["created_at"], "finished_at": row["finished_at"], "replay": replay,
    }

def record_report_delivery_attempt(connection: sqlite3.Connection, *, project_id: str,
                                   report_id: str, channel: object, mode: object,
                                   target_label: object, idempotency_key: object | None = None,
                                   retry_of: str | None = None, status_override: str | None = None,
                                   error_code_override: str | None = None) -> dict[str, object]:
    if channel not in PHASE9D_DELIVERY_CHANNELS:
        raise ValueError("delivery_target_not_allowed")
    if mode not in PHASE9D_DELIVERY_MODES:
        raise ValueError("delivery_failed")
    if status_override not in {None, "blocked", "dry_run", "failed"}:
        raise ValueError("delivery_failed")
    if error_code_override is not None and error_code_override not in {
        "delivery_disabled", "delivery_target_not_allowed", "delivery_authorization_required",
        "delivery_live_not_approved", "delivery_failed",
    }:
        raise ValueError("delivery_failed")
    label = _phase9d_target_label(target_label)
    key = _phase9d_idempotency_key(idempotency_key)
    key_fingerprint = hashlib.sha256(f"{project_id}\x1f{key}".encode("utf-8")).hexdigest() if key else None
    with connection:
        report = connection.execute(
            "SELECT * FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
        ).fetchone()
        if report is None:
            raise ValueError("report_not_found")
        if report["status"] != "ready":
            raise ValueError("report_invalid_state")
        content_fingerprint = hashlib.sha256(
            f"{report['content_version']}\x1f{report['safe_payload_json']}".encode("utf-8")
        ).hexdigest()
        if key_fingerprint is not None:
            existing = connection.execute(
                "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? AND channel=? "
                "AND idempotency_key_fingerprint=? ORDER BY created_at,id LIMIT 1",
                (project_id, report_id, channel, key_fingerprint),
            ).fetchone()
            if existing is not None:
                if (existing["mode"] != mode or existing["target_label"] != label or
                        existing["content_fingerprint"] != content_fingerprint):
                    raise ValueError("delivery_idempotency_mismatch")
                return _phase9d_delivery_public(existing, replay=True)
        if retry_of is not None:
            previous = connection.execute(
                "SELECT id FROM report_delivery_attempts WHERE id=? AND project_id=? AND report_id=? AND status='failed'",
                (retry_of, project_id, report_id),
            ).fetchone()
            if previous is None:
                raise ValueError("delivery_failed")
        default_status, default_error_code = {
            "off": ("blocked", "delivery_disabled"),
            "dry_run": ("dry_run", None),
            "live": ("blocked", "delivery_live_not_approved"),
        }[str(mode)]
        status = status_override or default_status
        error_code = error_code_override if error_code_override is not None else default_error_code
        attempt_id, now = f"delivery_attempt_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO report_delivery_attempts (id,project_id,report_id,channel,mode,target_label,"
            "content_fingerprint,idempotency_key_fingerprint,status,error_code,retry_of,created_at,finished_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (attempt_id, project_id, report_id, channel, mode, label, content_fingerprint,
             key_fingerprint, status, error_code, retry_of, now, now),
        )
        row = connection.execute("SELECT * FROM report_delivery_attempts WHERE id=?", (attempt_id,)).fetchone()
        return _phase9d_delivery_public(row)

def find_report_delivery_replay(connection: sqlite3.Connection, *, project_id: str,
                                 report_id: str, channel: object, mode: object,
                                 target_label: object, idempotency_key: object | None,
                                 content_fingerprint: str) -> dict[str, object] | None:
    """Return an idempotent delivery result before any adapter is invoked."""
    key = _phase9d_idempotency_key(idempotency_key)
    if key is None:
        return None
    label = _phase9d_target_label(target_label)
    key_fingerprint = hashlib.sha256(f"{project_id}\x1f{key}".encode("utf-8")).hexdigest()
    existing = connection.execute(
        "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? AND channel=? "
        "AND idempotency_key_fingerprint=? ORDER BY created_at,id LIMIT 1",
        (project_id, report_id, channel, key_fingerprint),
    ).fetchone()
    if existing is None:
        return None
    if (existing["mode"] != mode or existing["target_label"] != label or
            existing["content_fingerprint"] != content_fingerprint):
        raise ValueError("delivery_idempotency_mismatch")
    return _phase9d_delivery_public(existing, replay=True)

def list_report_delivery_attempts(connection: sqlite3.Connection, *, project_id: str,
                                  report_id: str) -> list[dict[str, object]]:
    if connection.execute(
        "SELECT 1 FROM report_snapshots WHERE id=? AND project_id=?", (report_id, project_id)
    ).fetchone() is None:
        raise ValueError("report_not_found")
    rows = connection.execute(
        "SELECT * FROM report_delivery_attempts WHERE project_id=? AND report_id=? ORDER BY created_at,id",
        (project_id, report_id),
    ).fetchall()
    return [_phase9d_delivery_public(row) for row in rows]

STUDY_TEXT_MAX = 4000

STUDY_DESCRIPTION_MAX = 10000

STUDY_METADATA_MAX = 10000

STUDY_GOAL_PREFIX = "goal_"

STUDY_MODULE_PREFIX = "module_"

STUDY_PLAN_PREFIX = "plan_"

STUDY_ITEM_PREFIX = "plan_item_"

STUDY_DEPENDENCY_PREFIX = "plan_dependency_"

STUDY_PROGRESS_PREFIX = "progress_"

STUDY_SOURCE_PREFIX = "study_source_"

