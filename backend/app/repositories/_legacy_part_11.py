from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
from ._legacy_part_05 import *
from ._legacy_part_06 import *
from ._legacy_part_07 import *
from ._legacy_part_08 import *
from ._legacy_part_09 import *
from ._legacy_part_10 import *
def list_study_source_candidates(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT m.id AS material_id,m.original_name,r.id AS revision_id,r.extraction_id,"
        "c.id AS chunk_id,c.chunk_index FROM materials m "
        "JOIN material_revisions r ON r.material_id=m.id AND r.is_current=1 "
        "JOIN chunks c ON c.revision_id=r.id AND c.status='ready' "
        "WHERE m.project_id=? AND m.deleted_at IS NULL ORDER BY m.original_name,m.id,c.chunk_index,c.id",
        (project_id,),
    ).fetchall()
    result = []
    for row in rows:
        spans = [str(value[0]) for value in connection.execute(
            "SELECT span_id FROM chunk_spans WHERE chunk_id=? ORDER BY span_id", (row["chunk_id"],)
        ).fetchall()]
        result.append({"material_id": row["material_id"], "material_name": row["original_name"],
                       "revision_id": row["revision_id"], "extraction_id": row["extraction_id"],
                       "chunk_id": row["chunk_id"], "chunk_index": row["chunk_index"],
                       "span_ids": spans})
    return result

def get_study_source_links(connection: sqlite3.Connection, *, project_id: str, plan_id: str | None = None,
                           module_id: str | None = None, item_id: str | None = None) -> list[dict[str, object]]:
    if module_id is not None:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM module_source_links WHERE project_id=? AND module_id=? ORDER BY created_at,id",
            (project_id, module_id),
        ).fetchall()]
    if item_id is not None:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM plan_item_source_links WHERE project_id=? AND plan_item_id=? ORDER BY created_at,id",
            (project_id, item_id),
        ).fetchall()]
    if plan_id is not None:
        query = (
            "SELECT l.* FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
            "WHERE i.plan_id=? AND l.project_id=? UNION "
            "SELECT l.* FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
            "WHERE i.plan_id=? AND l.project_id=? ORDER BY created_at,id"
        )
        params = (plan_id, project_id, plan_id, project_id)
    else:
        query = "SELECT * FROM plan_item_source_links WHERE project_id=? UNION SELECT * FROM module_source_links WHERE project_id=? ORDER BY created_at,id"
        params = (project_id, project_id)
    return [dict(row) for row in connection.execute(query, params).fetchall()]

def get_rhythm_settings(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object] | None:
    row = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    return dict(row) if row is not None else None

def save_rhythm_settings(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                         cadence: object, timezone_name: object, period_start: object,
                         target_minutes: object) -> dict[str, object]:
    if cadence not in RHYTHM_CADENCES:
        raise ValueError("study_rhythm_invalid_cadence")
    timezone_value = _rhythm_timezone(timezone_name)
    period_value = _rhythm_date(period_start)
    if (not isinstance(target_minutes, int) or isinstance(target_minutes, bool) or
            not 0 <= target_minutes <= RHYTHM_MAX_TARGET_MINUTES):
        raise ValueError("study_rhythm_target_out_of_range")
    now = utc_now()
    rhythm_id = f"rhythm_{uuid.uuid4().hex}"
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        existing = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if existing is None:
            connection.execute(
                "INSERT INTO rhythm_settings (id,project_id,plan_id,cadence,timezone,period_start,target_minutes,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (rhythm_id, project_id, plan_id, cadence, timezone_value, period_value, target_minutes, now, now),
            )
        else:
            _rhythm_validate_settings_allocation_limits(
                connection,
                settings={"project_id": project_id, "plan_id": plan_id, "cadence": cadence,
                          "timezone": timezone_value, "period_start": period_value},
            )
            connection.execute(
                "UPDATE rhythm_settings SET cadence=?,timezone=?,period_start=?,target_minutes=?,updated_at=? "
                "WHERE id=? AND project_id=? AND plan_id=?",
                (cadence, timezone_value, period_value, target_minutes, now, existing["id"], project_id, plan_id),
            )
    result = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    if result is None:
        raise ValueError("study_rhythm_persist_failed")
    return dict(result)

create_rhythm_settings = save_rhythm_settings

update_rhythm_settings = save_rhythm_settings

def _rhythm_allocation_row(connection: sqlite3.Connection, *, project_id: str,
                           plan_id: str, allocation_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM rhythm_allocations WHERE id=? AND project_id=? AND plan_id=?",
        (allocation_id, project_id, plan_id),
    ).fetchone()

def list_rhythm_allocations(connection: sqlite3.Connection, *, project_id: str,
                            plan_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM rhythm_allocations WHERE project_id=? AND plan_id=? ORDER BY local_date,item_id,id",
        (project_id, plan_id),
    ).fetchall()]

def _rhythm_period_index(settings: sqlite3.Row | dict[str, object], local_date: str) -> int:
    delta = (date.fromisoformat(local_date) - date.fromisoformat(str(settings["period_start"]))).days
    return delta if settings["cadence"] == "daily" else delta // 7

def _rhythm_period_dates(settings: sqlite3.Row | dict[str, object], period_index: int) -> tuple[str, str]:
    start = date.fromisoformat(str(settings["period_start"]))
    first = start + timedelta(days=period_index if settings["cadence"] == "daily" else period_index * 7)
    last = first + timedelta(days=0 if settings["cadence"] == "daily" else 6)
    return first.isoformat(), last.isoformat()

def _rhythm_validate_allocation_limits(connection: sqlite3.Connection, *, settings: sqlite3.Row,
                                       item_id: str, local_date: str, planned_minutes: int,
                                       allocation_id: str | None = None) -> None:
    excluded = " AND id != ?" if allocation_id else ""
    item_params: list[object] = [item_id]
    if allocation_id:
        item_params.append(allocation_id)
    item_total = int(connection.execute(
        "SELECT COALESCE(SUM(planned_minutes),0) FROM rhythm_allocations WHERE item_id=?" + excluded,
        item_params,
    ).fetchone()[0])
    if item_total + planned_minutes > RHYTHM_MAX_ITEM_MINUTES:
        raise ValueError("study_rhythm_allocation_limit_exceeded")
    period_index = _rhythm_period_index(settings, local_date)
    period_start, period_end = _rhythm_period_dates(settings, period_index)
    period_params: list[object] = [settings["plan_id"], period_start, period_end]
    if allocation_id:
        period_params.append(allocation_id)
        exclusion = " AND id != ?"
    else:
        exclusion = ""
    period_total = int(connection.execute(
        "SELECT COALESCE(SUM(planned_minutes),0) FROM rhythm_allocations "
        "WHERE plan_id=? AND local_date BETWEEN ? AND ?" + exclusion, period_params,
    ).fetchone()[0])
    if period_total + planned_minutes > RHYTHM_MAX_PERIOD_MINUTES:
        raise ValueError("study_rhythm_allocation_limit_exceeded")

def _rhythm_validate_settings_allocation_limits(connection: sqlite3.Connection, *,
                                                 settings: dict[str, object]) -> None:
    """Reject a settings edit that would make preserved allocations overload a period.

    Settings edits intentionally do not rewrite allocations.  They still must not
    turn valid existing rows into a rhythm that violates the per-period ceiling.
    """
    totals: dict[int, int] = {}
    for row in connection.execute(
        "SELECT local_date,planned_minutes FROM rhythm_allocations WHERE project_id=? AND plan_id=?",
        (settings["project_id"], settings["plan_id"]),
    ).fetchall():
        index = _rhythm_period_index(settings, str(row["local_date"]))
        totals[index] = totals.get(index, 0) + int(row["planned_minutes"])
    if any(total > RHYTHM_MAX_PERIOD_MINUTES for total in totals.values()):
        raise ValueError("study_rhythm_allocation_limit_exceeded")

def create_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             item_id: str, local_date: object, planned_minutes: object) -> dict[str, object]:
    local_date_value = _rhythm_date(local_date)
    if (not isinstance(planned_minutes, int) or isinstance(planned_minutes, bool) or
            not 1 <= planned_minutes <= RHYTHM_MAX_ALLOCATION_MINUTES):
        raise ValueError("study_rhythm_invalid_payload")
    with connection:
        plan = _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if settings is None:
            raise ValueError("study_rhythm_not_configured")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if item is None:
            raise ValueError("study_rhythm_item_not_found")
        if item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        _rhythm_validate_allocation_limits(connection, settings=settings, item_id=item_id,
                                           local_date=local_date_value, planned_minutes=planned_minutes)
        allocation_id = f"rhythm_allocation_{uuid.uuid4().hex}"
        now = utc_now()
        try:
            connection.execute(
                "INSERT INTO rhythm_allocations (id,project_id,plan_id,item_id,local_date,planned_minutes,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (allocation_id, project_id, plan_id, item_id, local_date_value, planned_minutes, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_rhythm_allocation_duplicate") from exc
    return dict(_rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id))

def update_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             allocation_id: str, local_date: object | None = None,
                             planned_minutes: object | None = None) -> dict[str, object]:
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        row = _rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id)
        if row is None:
            raise ValueError("study_rhythm_allocation_not_found")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=str(row["item_id"]))
        if item is None or item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        next_date = str(row["local_date"]) if local_date is None else _rhythm_date(local_date)
        next_minutes = int(row["planned_minutes"]) if planned_minutes is None else planned_minutes
        if (not isinstance(next_minutes, int) or isinstance(next_minutes, bool) or
                not 1 <= next_minutes <= RHYTHM_MAX_ALLOCATION_MINUTES):
            raise ValueError("study_rhythm_invalid_payload")
        settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
        if settings is None:
            raise ValueError("study_rhythm_not_configured")
        _rhythm_validate_allocation_limits(connection, settings=settings, item_id=str(row["item_id"]),
                                           local_date=next_date, planned_minutes=next_minutes,
                                           allocation_id=allocation_id)
        try:
            connection.execute(
                "UPDATE rhythm_allocations SET local_date=?,planned_minutes=?,updated_at=? WHERE id=? AND project_id=?",
                (next_date, next_minutes, utc_now(), allocation_id, project_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_rhythm_allocation_duplicate") from exc
    return dict(_rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id))

def delete_rhythm_allocation(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                             allocation_id: str) -> bool:
    with connection:
        _rhythm_plan_for_write(connection, project_id=project_id, plan_id=plan_id)
        row = _rhythm_allocation_row(connection, project_id=project_id, plan_id=plan_id, allocation_id=allocation_id)
        if row is None:
            raise ValueError("study_rhythm_allocation_not_found")
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=str(row["item_id"]))
        if item is None or item["status"] in {"completed", "archived"}:
            raise ValueError("study_rhythm_edit_not_allowed")
        connection.execute("DELETE FROM rhythm_allocations WHERE id=? AND project_id=?", (allocation_id, project_id))
    return True

def rhythm_summary(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                   local_date: object | None = None, periods: int = 1) -> dict[str, object]:
    # Validate an explicit business coordinate even if the plan has not yet
    # configured a rhythm, so read paths have the same strict date contract.
    requested_local_date = None if local_date is None else _rhythm_date(local_date)
    plan = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if plan is None:
        raise ValueError("study_rhythm_plan_not_found")
    settings = _rhythm_settings_row(connection, project_id=project_id, plan_id=plan_id)
    if settings is None:
        progress = study_progress_summary(connection, plan_id=plan_id, project_id=project_id)
        return {"settings": None, "buckets": [], "allocated_item_count": 0,
                "unassigned_item_count": progress["item_count"], "archived_item_count": progress["archived_count"],
                "item_projection": {key: progress[key] for key in ("pending_count", "in_progress_count", "completed_count", "skipped_count")},
                "source_warning_count": progress["source_warning_count"], "last_progress_event_at": progress["last_event_at"]}
    if not isinstance(periods, int) or isinstance(periods, bool) or not 1 <= periods <= 52:
        raise ValueError("study_rhythm_invalid_payload")
    if requested_local_date is None:
        from zoneinfo import ZoneInfo
        local_date_value = datetime.now(timezone.utc).astimezone(ZoneInfo(str(settings["timezone"]))).date().isoformat()
    else:
        local_date_value = requested_local_date
    current_index = _rhythm_period_index(settings, local_date_value)
    allocations = [dict(row) for row in connection.execute(
        "SELECT * FROM rhythm_allocations WHERE project_id=? AND plan_id=? ORDER BY local_date,item_id,id",
        (project_id, plan_id),
    ).fetchall()]
    item_rows = connection.execute(
        "SELECT i.id,i.status FROM study_plan_items i WHERE i.plan_id=? AND i.project_id=?", (plan_id, project_id)
    ).fetchall()
    item_statuses = {str(row["id"]): str(row["status"]) for row in item_rows}
    buckets: list[dict[str, object]] = []
    for index in range(current_index, current_index + periods):
        start, end = _rhythm_period_dates(settings, index)
        selected = [row for row in allocations if start <= str(row["local_date"]) <= end]
        active_selected = [row for row in selected if item_statuses.get(str(row["item_id"])) != "archived"]
        planned = sum(int(row["planned_minutes"]) for row in active_selected)
        buckets.append({"period_index": index, "local_date_start": start, "local_date_end": end,
                        "planned_minutes": planned, "target_minutes": int(settings["target_minutes"]),
                        "remaining_target_minutes": max(int(settings["target_minutes"]) - planned, 0),
                        "allocated_item_count": len({str(row["item_id"]) for row in active_selected})})
    allocated_ids = {str(row["item_id"]) for row in allocations if item_statuses.get(str(row["item_id"])) != "archived"}
    unassigned = sum(1 for row in item_rows if row["status"] != "archived" and str(row["id"]) not in allocated_ids)
    progress = study_progress_summary(connection, plan_id=plan_id, project_id=project_id)
    return {"settings": dict(settings), "buckets": buckets,
            "allocated_item_count": len(allocated_ids),
            "unassigned_item_count": unassigned,
            "archived_item_count": sum(1 for row in item_rows if row["status"] == "archived"),
            "item_projection": {key: progress[key] for key in ("pending_count", "in_progress_count", "completed_count", "skipped_count")},
            "source_warning_count": progress["source_warning_count"], "last_progress_event_at": progress["last_event_at"]}

def _note_row(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM notes WHERE id=? AND project_id=?", (note_id, project_id)).fetchone()

def _note_blocks(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> list[dict[str, object]]:
    rows = connection.execute("SELECT * FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["sources"] = [dict(source) for source in connection.execute(
            "SELECT * FROM note_block_source_links WHERE note_block_id=? AND project_id=? ORDER BY created_at,id",
            (row["id"], project_id),
        ).fetchall()]
        result.append(item)
    return result

def _note_public(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    row = _note_row(connection, project_id=project_id, note_id=note_id)
    if row is None:
        raise ValueError("study_note_not_found")
    result = dict(row)
    result["blocks"] = _note_blocks(connection, project_id=project_id, note_id=note_id)
    result["modules"] = [dict(module) for module in connection.execute(
        "SELECT m.* FROM knowledge_modules m JOIN note_module_links l ON l.module_id=m.id "
        "WHERE l.note_id=? AND l.project_id=? ORDER BY m.id", (note_id, project_id)
    ).fetchall()]
    result["source_warning_count"] = sum(1 for block in result["blocks"] for source in block["sources"] if source["status"] != "valid")
    result["archived_module_warning_count"] = sum(1 for module in result["modules"] if module["status"] == "archived")
    return result

def _note_block_values(payload: object, *, code: str = "study_note_block_invalid") -> tuple[str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError(code)
    kind = payload.get("block_kind", "text")
    if kind not in NOTE_BLOCK_KINDS:
        raise ValueError(code)
    content = _study_text(payload.get("content"), code=code, maximum=NOTE_MAX_BLOCK_CONTENT)
    provenance = payload.get("provenance", "user_created")
    if provenance not in NOTE_PROVENANCES:
        raise ValueError(code)
    return str(kind), content, str(provenance)

def _note_validate_blocks(payloads: object) -> list[tuple[str, str, str]]:
    if not isinstance(payloads, list) or not payloads:
        raise ValueError("study_note_empty")
    values = [_note_block_values(payload) for payload in payloads]
    if sum(len(value[1]) for value in values) > NOTE_MAX_CONTENT:
        raise ValueError("study_note_block_invalid")
    return values

def create_note(connection: sqlite3.Connection, *, project_id: str, title: object,
                blocks: object, provenance: str = "user_created",
                generation_operation_id: str | None = None) -> dict[str, object]:
    title_value = _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
    if provenance not in NOTE_PROVENANCES or (provenance == "user_created") != (generation_operation_id is None):
        raise ValueError("study_note_invalid_payload")
    values = _note_validate_blocks(blocks)
    expected_block_provenance = "ai_generated" if provenance == "ai_generated" else "user_created"
    if any(block_provenance != expected_block_provenance for _, _, block_provenance in values):
        raise ValueError("study_note_block_invalid")
    note_id = f"note_{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        if not _study_project_exists(connection, project_id):
            raise ValueError("study_note_invalid_payload")
        if provenance == "ai_generated" and connection.execute(
                "SELECT 1 FROM ai_operations WHERE id=? AND project_id=? AND operation_type='generate_note'",
                (generation_operation_id, project_id)).fetchone() is None:
            raise ValueError("study_note_invalid_payload")
        connection.execute(
            "INSERT INTO notes (id,project_id,title,status,provenance,user_edited,generation_operation_id,created_at,updated_at,confirmed_at,archived_at) "
            "VALUES (?,?,?,?,?,0,?,?,?,NULL,NULL)",
            (note_id, project_id, title_value, "draft", provenance, generation_operation_id, now, now),
        )
        connection.executemany(
            "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, block_provenance, now, now)
             for position, (kind, content, block_provenance) in enumerate(values)],
        )
    return _note_public(connection, project_id=project_id, note_id=note_id)

def create_user_note(connection: sqlite3.Connection, *, project_id: str, title: object,
                     blocks: object) -> dict[str, object]:
    return create_note(connection, project_id=project_id, title=title, blocks=blocks)

