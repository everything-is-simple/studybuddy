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
STUDY_PLAN_STATUSES = {"draft", "confirmed", "active", "paused", "completed", "archived"}

STUDY_ITEM_STATUSES = {"pending", "in_progress", "completed", "skipped", "archived"}

STUDY_PROGRESS_EVENTS = {"started", "completed", "skipped", "reopened"}

STUDY_SOURCE_STATUSES = {"valid", "source_deleted", "source_unavailable", "stale"}

RHYTHM_CADENCES = {"daily", "weekly"}

RHYTHM_MAX_TARGET_MINUTES = 10080

RHYTHM_MAX_ITEM_MINUTES = 10080

RHYTHM_MAX_PERIOD_MINUTES = 10080

RHYTHM_MAX_ALLOCATION_MINUTES = 1440

NOTE_STATUSES = {"draft", "confirmed", "rejected", "archived"}

NOTE_PROVENANCES = {"user_created", "ai_generated"}

NOTE_BLOCK_KINDS = {"text", "heading", "bullet"}

NOTE_MAX_TITLE = 400

NOTE_MAX_BLOCK_CONTENT = 12000

NOTE_MAX_CONTENT = 48000

NOTE_GENERATION_PROMPT_VERSION = "phase9b_note_generation_v1"

def _study_text(value: object, *, code: str, maximum: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(code)
    result = value.strip()
    if not allow_empty and not result:
        raise ValueError(code)
    return result

def _study_description(value: object, *, code: str = "study_plan_invalid_payload") -> str:
    return _study_text(value, code=code, maximum=STUDY_DESCRIPTION_MAX, allow_empty=True)

def _study_project_exists(connection: sqlite3.Connection, project_id: str) -> bool:
    return connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is not None

def _rhythm_date(value: object, *, code: str = "study_rhythm_invalid_date") -> str:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(code) from None
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(code)
    return value

def _rhythm_timezone(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("study_rhythm_invalid_timezone")
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        ZoneInfo(value)
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError("study_rhythm_invalid_timezone") from None
    # IANA names are required. ZoneInfo accepts a few aliases/posix names;
    # reject the explicitly unsupported abbreviation/offset forms here.
    if value != "UTC" and "/" not in value:
        raise ValueError("study_rhythm_invalid_timezone")
    return value

def _rhythm_settings_row(connection: sqlite3.Connection, *, project_id: str,
                         plan_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM rhythm_settings WHERE project_id=? AND plan_id=?", (project_id, plan_id)
    ).fetchone()

def _rhythm_plan_for_write(connection: sqlite3.Connection, *, project_id: str,
                           plan_id: str) -> sqlite3.Row:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_rhythm_plan_not_found")
    if row["status"] in {"completed", "archived"}:
        raise ValueError("study_rhythm_edit_not_allowed")
    return row

def _study_goal_row(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM learning_goals WHERE id = ? AND project_id = ?", (goal_id, project_id)
    ).fetchone()

def _study_module_row(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM knowledge_modules WHERE id = ? AND project_id = ?", (module_id, project_id)
    ).fetchone()

def create_learning_goal(connection: sqlite3.Connection, *, project_id: str, title: object,
                         description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_goal_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description, code="study_goal_invalid_payload")
    goal_id = f"{STUDY_GOAL_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)",
                           (project_id, "Default project", now))
        connection.execute(
            "INSERT INTO learning_goals (id,project_id,title,description,status,created_at,updated_at,archived_at) "
            "VALUES (?,?,?,?,?,?,?,NULL)",
            (goal_id, project_id, title_value, description_value, "active", now, now),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))

def list_learning_goals(connection: sqlite3.Connection, *, project_id: str,
                        include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id = ?" if include_archived else "project_id = ? AND status = 'active'"
    return [dict(row) for row in connection.execute(
        "SELECT * FROM learning_goals WHERE " + where + " ORDER BY updated_at DESC, id DESC", (project_id,)
    ).fetchall()]

def get_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object] | None:
    row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
    return dict(row) if row is not None else None

def archive_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
        if row is None:
            raise ValueError("learning_goal_not_found")
        if row["status"] == "archived":
            return dict(row)
        connection.execute(
            "UPDATE learning_goals SET status='archived', archived_at=?, updated_at=? WHERE id=? AND project_id=?",
            (now, now, goal_id, project_id),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))

def update_learning_goal(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                         title: object | None = None, description: object | None = None) -> dict[str, object]:
    with connection:
        row = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
        if row is None:
            raise ValueError("learning_goal_not_found")
        if row["status"] == "archived":
            raise ValueError("learning_goal_archived")
        next_title = str(row["title"]) if title is None else _study_text(title, code="study_goal_invalid_payload", maximum=STUDY_TEXT_MAX)
        next_description = str(row["description"]) if description is None else _study_description(description, code="study_goal_invalid_payload")
        connection.execute(
            "UPDATE learning_goals SET title=?,description=?,updated_at=? WHERE id=? AND project_id=?",
            (next_title, next_description, utc_now(), goal_id, project_id),
        )
    return dict(_study_goal_row(connection, project_id=project_id, goal_id=goal_id))

def create_knowledge_module(connection: sqlite3.Connection, *, project_id: str, title: object,
                            description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_module_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description, code="study_module_invalid_payload")
    module_id = f"{STUDY_MODULE_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id,name,created_at) VALUES (?,?,?)",
                           (project_id, "Default project", now))
        connection.execute(
            "INSERT INTO knowledge_modules (id,project_id,title,description,status,created_at,updated_at,archived_at) "
            "VALUES (?,?,?,?,?,?,?,NULL)",
            (module_id, project_id, title_value, description_value, "active", now, now),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))

def list_knowledge_modules(connection: sqlite3.Connection, *, project_id: str,
                           include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id = ?" if include_archived else "project_id = ? AND status = 'active'"
    return [dict(row) for row in connection.execute(
        "SELECT * FROM knowledge_modules WHERE " + where + " ORDER BY updated_at DESC, id DESC", (project_id,)
    ).fetchall()]

def get_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> dict[str, object] | None:
    row = _study_module_row(connection, project_id=project_id, module_id=module_id)
    return dict(row) if row is not None else None

def update_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str,
                            title: object | None = None, description: object | None = None) -> dict[str, object]:
    with connection:
        row = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if row is None:
            raise ValueError("knowledge_module_not_found")
        if row["status"] == "archived":
            raise ValueError("knowledge_module_archived")
        next_title = str(row["title"]) if title is None else _study_text(title, code="study_module_invalid_payload", maximum=STUDY_TEXT_MAX)
        next_description = str(row["description"]) if description is None else _study_description(description, code="study_module_invalid_payload")
        connection.execute(
            "UPDATE knowledge_modules SET title=?,description=?,updated_at=? WHERE id=? AND project_id=?",
            (next_title, next_description, utc_now(), module_id, project_id),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))

def archive_knowledge_module(connection: sqlite3.Connection, *, project_id: str, module_id: str) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if row is None:
            raise ValueError("knowledge_module_not_found")
        if row["status"] == "archived":
            return dict(row)
        connection.execute(
            "UPDATE knowledge_modules SET status='archived', archived_at=?, updated_at=? WHERE id=? AND project_id=?",
            (now, now, module_id, project_id),
        )
    return dict(_study_module_row(connection, project_id=project_id, module_id=module_id))

def _study_plan_row(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM study_plans WHERE id = ? AND project_id = ?", (plan_id, project_id)
    ).fetchone()

def _study_plan_items(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM study_plan_items WHERE plan_id=? AND project_id=? ORDER BY position,id",
        (plan_id, project_id),
    ).fetchall()]

def _study_dependencies(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT * FROM study_plan_dependencies WHERE plan_id=? AND project_id=? ORDER BY created_at,id",
        (plan_id, project_id),
    ).fetchall()]

def _study_source_links(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(
        "SELECT l.* FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
        "WHERE i.plan_id=? AND l.project_id=? "
        "UNION "
        "SELECT l.* FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
        "WHERE i.plan_id=? AND l.project_id=? ORDER BY created_at,id",
        (plan_id, project_id, plan_id, project_id),
    ).fetchall()]

def study_progress_summary(connection: sqlite3.Connection, *, plan_id: str, project_id: str) -> dict[str, object]:
    rows = connection.execute(
        "SELECT status, COUNT(*) AS count FROM study_plan_items WHERE plan_id=? AND project_id=? "
        "GROUP BY status", (plan_id, project_id)
    ).fetchall()
    counts = {status: int(row["count"]) for status, row in ((str(row["status"]), row) for row in rows)}
    item_count = sum(count for status, count in counts.items() if status != "archived")
    completed = counts.get("completed", 0)
    last_event = connection.execute(
        "SELECT created_at FROM study_progress_events WHERE plan_id=? AND project_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        (plan_id, project_id),
    ).fetchone()
    warnings = connection.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT l.id,l.status FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
        "WHERE i.plan_id=? AND l.project_id=? "
        "UNION "
        "SELECT l.id,l.status FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
        "WHERE i.plan_id=? AND l.project_id=?"
        ") WHERE status != 'valid'",
        (plan_id, project_id, plan_id, project_id),
    ).fetchone()[0]
    return {
        "item_count": item_count,
        "completed_count": completed,
        "skipped_count": counts.get("skipped", 0),
        "in_progress_count": counts.get("in_progress", 0),
        "pending_count": counts.get("pending", 0),
        "archived_count": counts.get("archived", 0),
        "completion_ratio": (completed / item_count) if item_count else 0.0,
        "last_event_at": last_event[0] if last_event else None,
        "source_warning_count": int(warnings),
    }

def _study_plan_public(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object]:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_plan_not_found")
    return {
        **dict(row),
        "items": _study_plan_items(connection, plan_id=plan_id, project_id=project_id),
        "dependencies": _study_dependencies(connection, plan_id=plan_id, project_id=project_id),
        "source_links": _study_source_links(connection, plan_id=plan_id, project_id=project_id),
        "progress": study_progress_summary(connection, plan_id=plan_id, project_id=project_id),
    }

def create_study_plan(connection: sqlite3.Connection, *, project_id: str, goal_id: str,
                      title: object, description: object = "") -> dict[str, object]:
    title_value = _study_text(title, code="study_plan_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description)
    goal = _study_goal_row(connection, project_id=project_id, goal_id=goal_id)
    if goal is None:
        raise ValueError("study_plan_goal_invalid")
    if goal["status"] != "active":
        raise ValueError("learning_goal_archived")
    plan_id = f"{STUDY_PLAN_PREFIX}{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute(
            "INSERT INTO study_plans (id,project_id,goal_id,title,description,status,user_edited,created_at,updated_at,"
            "confirmed_at,activated_at,completed_at,archived_at) VALUES (?,?,?,?,?,'draft',0,?,?,NULL,NULL,NULL,NULL)",
            (plan_id, project_id, goal_id, title_value, description_value, now, now),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)

def list_study_plans(connection: sqlite3.Connection, *, project_id: str,
                      include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id=?" if include_archived else "project_id=? AND status!='archived'"
    rows = connection.execute("SELECT id FROM study_plans WHERE " + where + " ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()
    return [_study_plan_public(connection, project_id=project_id, plan_id=str(row[0])) for row in rows]

def get_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> dict[str, object] | None:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id) if row is not None else None

def _study_plan_for_edit(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row:
    row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    if row is None:
        raise ValueError("study_plan_not_found")
    if row["status"] not in {"draft", "confirmed"}:
        raise ValueError("study_plan_edit_not_allowed")
    return row

def update_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                      title: object | None = None, description: object | None = None) -> dict[str, object]:
    now = utc_now()
    with connection:
        row = _study_plan_for_edit(connection, project_id=project_id, plan_id=plan_id)
        title_value = str(row["title"]) if title is None else _study_text(title, code="study_plan_invalid_payload", maximum=STUDY_TEXT_MAX)
        description_value = str(row["description"]) if description is None else _study_description(description)
        next_status = "draft" if row["status"] == "confirmed" else row["status"]
        connection.execute(
            "UPDATE study_plans SET title=?,description=?,status=?,user_edited=1,updated_at=?,confirmed_at=? WHERE id=? AND project_id=?",
            (title_value, description_value, next_status, now, None if next_status == "draft" else row["confirmed_at"], plan_id, project_id),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)

def transition_study_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                          target: str) -> dict[str, object]:
    allowed = {
        "draft": {"confirmed", "archived"}, "confirmed": {"draft", "active", "archived"},
        "active": {"paused", "completed", "archived"}, "paused": {"active", "completed", "archived"},
        "completed": {"archived"}, "archived": set(),
    }
    now = utc_now()
    with connection:
        row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
        if row is None:
            raise ValueError("study_plan_not_found")
        if target == "active" and row["status"] == "draft":
            raise ValueError("study_plan_confirm_required")
        if target not in allowed.get(str(row["status"]), set()):
            raise ValueError("study_plan_invalid_state")
        if target == "active" and row["status"] != "confirmed":
            raise ValueError("study_plan_confirm_required")
        confirmed_at = now if target == "confirmed" else row["confirmed_at"]
        activated_at = now if target == "active" else row["activated_at"]
        completed_at = now if target == "completed" else row["completed_at"]
        archived_at = now if target == "archived" else row["archived_at"]
        connection.execute(
            "UPDATE study_plans SET status=?,confirmed_at=?,activated_at=?,completed_at=?,archived_at=?,updated_at=? WHERE id=? AND project_id=?",
            (target, confirmed_at, activated_at, completed_at, archived_at, now, plan_id, project_id),
        )
    return _study_plan_public(connection, project_id=project_id, plan_id=plan_id)

def _study_item_row(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM study_plan_items WHERE id=? AND project_id=? AND plan_id=?", (item_id, project_id, plan_id)
    ).fetchone()

def _study_item_edit_plan(connection: sqlite3.Connection, *, project_id: str, plan_id: str) -> sqlite3.Row:
    row = _study_plan_for_edit(connection, project_id=project_id, plan_id=plan_id)
    if row["status"] == "confirmed":
        now = utc_now()
        connection.execute("UPDATE study_plans SET status='draft',confirmed_at=NULL,updated_at=? WHERE id=?", (now, plan_id))
        row = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
    return row

def _study_optional_reference(connection: sqlite3.Connection, *, table: str, value: str | None,
                              project_id: str, archived_allowed: bool = False) -> None:
    if value is None:
        return
    row = connection.execute(f"SELECT project_id,status FROM {table} WHERE id=?", (value,)).fetchone()
    if row is None or row["project_id"] != project_id or (not archived_allowed and row["status"] != "active"):
        raise ValueError("study_plan_item_invalid_payload")

