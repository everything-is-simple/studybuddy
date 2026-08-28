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
def create_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                           title: object, description: object = "", position: int | None = None,
                           module_id: str | None = None, deck_id: str | None = None,
                           exercise_set_id: str | None = None) -> dict[str, object]:
    title_value = _study_text(title, code="study_plan_item_invalid_payload", maximum=STUDY_TEXT_MAX)
    description_value = _study_description(description)
    with connection:
        plan = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        _study_optional_reference(connection, table="knowledge_modules", value=module_id, project_id=project_id)
        _study_optional_reference(connection, table="study_decks", value=deck_id, project_id=project_id)
        _study_optional_reference(connection, table="exercise_sets", value=exercise_set_id, project_id=project_id)
        max_position = connection.execute("SELECT COALESCE(MAX(position), -1) FROM study_plan_items WHERE plan_id=?", (plan_id,)).fetchone()[0]
        item_position = max_position + 1 if position is None else position
        if not isinstance(item_position, int) or item_position < 0:
            raise ValueError("study_plan_item_invalid_payload")
        item_id = f"{STUDY_ITEM_PREFIX}{uuid.uuid4().hex}"
        now = utc_now()
        try:
            connection.execute(
                "INSERT INTO study_plan_items (id,plan_id,project_id,module_id,deck_id,exercise_set_id,title,description,position,status,user_edited,created_at,updated_at,completed_at,archived_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,'pending',1,?,?,NULL,NULL)",
                (item_id, plan_id, project_id, module_id, deck_id, exercise_set_id, title_value, description_value, item_position, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_plan_item_invalid_payload") from exc
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))

def update_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str,
                           title: object | None = None, description: object | None = None,
                           position: int | None = None, module_id: str | None = None,
                           deck_id: str | None = None, exercise_set_id: str | None = None) -> dict[str, object]:
    with connection:
        row = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if row is None:
            raise ValueError("study_plan_item_not_found")
        self_status = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        if row["status"] in {"completed", "skipped", "archived"}:
            raise ValueError("study_plan_item_edit_not_allowed")
        _study_optional_reference(connection, table="knowledge_modules", value=module_id, project_id=project_id)
        _study_optional_reference(connection, table="study_decks", value=deck_id, project_id=project_id)
        _study_optional_reference(connection, table="exercise_sets", value=exercise_set_id, project_id=project_id)
        next_position = row["position"] if position is None else position
        if not isinstance(next_position, int) or next_position < 0:
            raise ValueError("study_plan_item_invalid_payload")
        connection.execute(
            "UPDATE study_plan_items SET title=?,description=?,position=?,module_id=?,deck_id=?,exercise_set_id=?,user_edited=1,updated_at=? WHERE id=? AND plan_id=? AND project_id=?",
            (str(row["title"]) if title is None else _study_text(title, code="study_plan_item_invalid_payload", maximum=STUDY_TEXT_MAX),
             str(row["description"]) if description is None else _study_description(description), next_position,
             row["module_id"] if module_id is None else module_id, row["deck_id"] if deck_id is None else deck_id,
             row["exercise_set_id"] if exercise_set_id is None else exercise_set_id, utc_now(), item_id, plan_id, project_id),
        )
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))

def archive_study_plan_item(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str) -> dict[str, object]:
    with connection:
        row = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if row is None:
            raise ValueError("study_plan_item_not_found")
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        if row["status"] == "archived":
            return dict(row)
        if connection.execute("SELECT 1 FROM study_progress_events WHERE item_id=?", (item_id,)).fetchone() is not None:
            raise ValueError("study_plan_item_edit_not_allowed")
        now = utc_now()
        connection.execute("UPDATE study_plan_items SET status='archived',archived_at=?,updated_at=? WHERE id=?", (now, now, item_id))
    return dict(_study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id))

def _study_dependency_cycle(connection: sqlite3.Connection, *, plan_id: str, predecessor: str, successor: str) -> bool:
    graph: dict[str, list[str]] = {}
    for row in connection.execute("SELECT predecessor_item_id,successor_item_id FROM study_plan_dependencies WHERE plan_id=?", (plan_id,)).fetchall():
        graph.setdefault(str(row[0]), []).append(str(row[1]))
    graph.setdefault(predecessor, []).append(successor)
    stack = [successor]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == predecessor:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, []))
    return False

def add_study_plan_dependency(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                              predecessor_item_id: str, successor_item_id: str) -> dict[str, object]:
    with connection:
        plan = _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        left = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=predecessor_item_id)
        right = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=successor_item_id)
        if left is None or right is None or left["status"] == "archived" or right["status"] == "archived":
            raise ValueError("study_plan_dependency_invalid")
        if _study_dependency_cycle(connection, plan_id=plan_id, predecessor=predecessor_item_id, successor=successor_item_id):
            raise ValueError("study_plan_dependency_cycle")
        dependency_id = f"{STUDY_DEPENDENCY_PREFIX}{uuid.uuid4().hex}"
        try:
            connection.execute(
                "INSERT INTO study_plan_dependencies (id,plan_id,project_id,predecessor_item_id,successor_item_id,created_at) VALUES (?,?,?,?,?,?)",
                (dependency_id, plan_id, project_id, predecessor_item_id, successor_item_id, utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_plan_dependency_invalid") from exc
    return dict(connection.execute("SELECT * FROM study_plan_dependencies WHERE id=?", (dependency_id,)).fetchone())

def remove_study_plan_dependency(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                                 dependency_id: str) -> bool:
    with connection:
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        cursor = connection.execute("DELETE FROM study_plan_dependencies WHERE id=? AND plan_id=? AND project_id=?", (dependency_id, plan_id, project_id))
    if cursor.rowcount == 0:
        raise ValueError("study_plan_dependency_invalid")
    return True

def append_study_progress_event(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                                item_id: str, event_type: str, metadata: object | None = None,
                                event_id: str | None = None) -> dict[str, object]:
    if event_type not in STUDY_PROGRESS_EVENTS:
        raise ValueError("study_progress_invalid_event")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict) or len(json.dumps(metadata, ensure_ascii=False)) > STUDY_METADATA_MAX:
        raise ValueError("study_progress_invalid_event")
    with connection:
        plan = _study_plan_row(connection, project_id=project_id, plan_id=plan_id)
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if plan is None or item is None:
            raise ValueError("study_plan_item_not_found")
        if plan["status"] != "active" or item["status"] == "archived":
            raise ValueError("study_progress_invalid_event")
        if event_id is not None:
            existing = connection.execute("SELECT * FROM study_progress_events WHERE id=?", (event_id,)).fetchone()
            if existing is not None:
                if existing["plan_id"] == plan_id and existing["item_id"] == item_id and existing["event_type"] == event_type:
                    return dict(existing)
                raise ValueError("study_progress_event_duplicate")
        progress_id = event_id or f"{STUDY_PROGRESS_PREFIX}{uuid.uuid4().hex}"
        next_status = {"started": "in_progress", "completed": "completed", "skipped": "skipped", "reopened": "in_progress"}[event_type]
        completed_at = utc_now() if event_type == "completed" else None
        now = utc_now()
        connection.execute(
            "INSERT INTO study_progress_events (id,plan_id,item_id,project_id,event_type,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (progress_id, plan_id, item_id, project_id, event_type, json.dumps(metadata, ensure_ascii=False, separators=(",", ":")), now),
        )
        connection.execute("UPDATE study_plan_items SET status=?,completed_at=?,updated_at=? WHERE id=? AND plan_id=?", (next_status, completed_at, now, item_id, plan_id))
    return dict(connection.execute("SELECT * FROM study_progress_events WHERE id=?", (progress_id,)).fetchone())

def list_study_progress_events(connection: sqlite3.Connection, *, project_id: str, plan_id: str,
                               item_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id, plan_id]
    where = "project_id=? AND plan_id=?"
    if item_id is not None:
        where += " AND item_id=?"
        params.append(item_id)
    rows = connection.execute("SELECT * FROM study_progress_events WHERE " + where + " ORDER BY created_at,id", params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(str(item.pop("metadata_json")))
        result.append(item)
    return result

def _study_source_status(connection: sqlite3.Connection, *, project_id: str | None = None,
                         material_id: str | None, revision_id: str | None,
                         extraction_id: str | None, chunk_id: str | None, span_id: str | None,
                         citation_key: str | None, strict: bool = True) -> str:
    if not material_id or not revision_id or not chunk_id:
        if strict:
            raise ValueError("study_source_invalid")
        return "stale"
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None:
        return "source_unavailable"
    if project_id is not None and material["project_id"] != project_id:
        return "stale"
    if material["deleted_at"] is not None:
        return "source_deleted"
    chunk = connection.execute(
        "SELECT c.revision_id,c.extraction_id,c.status,r.is_current FROM chunks c JOIN material_revisions r ON r.id=c.revision_id "
        "WHERE c.id=? AND c.material_id=?", (chunk_id, material_id)
    ).fetchone()
    if chunk is None or chunk["revision_id"] != revision_id or (extraction_id is not None and chunk["extraction_id"] != extraction_id):
        return "stale"
    if chunk["status"] != "ready" or not chunk["is_current"]:
        return "stale"
    if span_id is not None and connection.execute("SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id, span_id)).fetchone() is None:
        if strict:
            raise ValueError("study_source_invalid")
        return "stale"
    if citation_key is not None:
        validation = validate_citation_key(connection, citation_key)
        if validation is None or validation.get("chunk_id") != chunk_id:
            if strict:
                raise ValueError("study_source_invalid")
            return "stale"
    return "valid"

def _study_source_payload(connection: sqlite3.Connection, *, project_id: str, payload: dict[str, object],
                          owner_type: str) -> tuple[object, ...]:
    required = ("material_id", "revision_id", "chunk_id")
    if any(not isinstance(payload.get(key), str) or not str(payload[key]) for key in required):
        raise ValueError("study_source_invalid")
    material_id = str(payload["material_id"]); revision_id = str(payload["revision_id"]); chunk_id = str(payload["chunk_id"])
    extraction_id = payload.get("extraction_id"); span_id = payload.get("span_id"); citation_key = payload.get("citation_key")
    for value in (extraction_id, span_id, citation_key):
        if value is not None and (not isinstance(value, str) or len(value) > 200):
            raise ValueError("study_source_invalid")
    status = _study_source_status(connection, project_id=project_id, material_id=material_id,
                                  revision_id=revision_id, extraction_id=extraction_id,
                                  chunk_id=chunk_id, span_id=span_id, citation_key=citation_key)
    if status != "valid":
        raise ValueError("study_source_invalid")
    prefix = "module_source" if owner_type == "module" else "plan_item_source"
    return (f"{prefix}_{uuid.uuid4().hex}", project_id, material_id, revision_id, extraction_id, chunk_id,
            span_id, citation_key, status, utc_now(), utc_now())

def create_module_source_link(connection: sqlite3.Connection, *, project_id: str, module_id: str,
                              payload: dict[str, object]) -> dict[str, object]:
    with connection:
        module = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if module is None:
            raise ValueError("knowledge_module_not_found")
        if module["status"] != "active":
            raise ValueError("knowledge_module_archived")
        row = _study_source_payload(connection, project_id=project_id, payload=payload, owner_type="module")
        link_id = row[0]
        try:
            connection.execute("INSERT INTO module_source_links (id,project_id,module_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (link_id, project_id, module_id, *row[2:]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_source_invalid") from exc
    return dict(connection.execute("SELECT * FROM module_source_links WHERE id=?", (link_id,)).fetchone())

def create_plan_item_source_link(connection: sqlite3.Connection, *, project_id: str, plan_id: str, item_id: str,
                                 payload: dict[str, object]) -> dict[str, object]:
    with connection:
        item = _study_item_row(connection, project_id=project_id, plan_id=plan_id, item_id=item_id)
        if item is None:
            raise ValueError("study_plan_item_not_found")
        _study_item_edit_plan(connection, project_id=project_id, plan_id=plan_id)
        row = _study_source_payload(connection, project_id=project_id, payload=payload, owner_type="item")
        link_id = row[0]
        try:
            connection.execute("INSERT INTO plan_item_source_links (id,project_id,plan_item_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (link_id, project_id, item_id, *row[2:]))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_source_invalid") from exc
    return dict(connection.execute("SELECT * FROM plan_item_source_links WHERE id=?", (link_id,)).fetchone())

def _refresh_note_source_links_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    rows = connection.execute(
        "SELECT id,project_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key "
        "FROM note_block_source_links WHERE material_id=?", (material_id,)
    ).fetchall()
    for row in rows:
        material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
        status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(
            connection, project_id=row["project_id"], material_id=row["material_id"], revision_id=row["revision_id"],
            extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"],
            citation_key=row["citation_key"], strict=False)
        connection.execute("UPDATE note_block_source_links SET status=?,updated_at=? WHERE id=?", (status, utc_now(), row["id"]))

def _refresh_study_source_links_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    _refresh_note_source_links_for_material(connection, material_id)
    for table, owner in (("module_source_links", "module_id"), ("plan_item_source_links", "plan_item_id")):
        rows = connection.execute(
            f"SELECT id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key FROM {table} WHERE material_id=?", (material_id,)
        ).fetchall()
        for row in rows:
            material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
            status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(connection, project_id=material["project_id"], material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
            connection.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE id=?", (status, utc_now(), row["id"]))

def refresh_study_source_links(connection: sqlite3.Connection, *, project_id: str, plan_id: str | None = None) -> int:
    with connection:
        changed = 0
        for table in ("module_source_links", "plan_item_source_links"):
            if table == "plan_item_source_links" and plan_id is not None:
                rows = connection.execute(
                    "SELECT l.id,l.material_id,l.revision_id,l.extraction_id,l.chunk_id,l.span_id,l.citation_key "
                    "FROM plan_item_source_links l JOIN study_plan_items i ON i.id=l.plan_item_id "
                    "WHERE l.project_id=? AND i.plan_id=?", (project_id, plan_id)
                ).fetchall()
            elif table == "module_source_links" and plan_id is not None:
                rows = connection.execute(
                    "SELECT l.id,l.material_id,l.revision_id,l.extraction_id,l.chunk_id,l.span_id,l.citation_key "
                    "FROM module_source_links l JOIN study_plan_items i ON i.module_id=l.module_id "
                    "WHERE l.project_id=? AND i.plan_id=?", (project_id, plan_id)
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key FROM {table} WHERE project_id=?",
                    (project_id,),
                ).fetchall()
            for row in rows:
                material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (row["material_id"],)).fetchone()
                status = "source_unavailable" if material is None else "source_deleted" if material["deleted_at"] is not None else _study_source_status(connection, project_id=project_id, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
                changed += connection.execute(f"UPDATE {table} SET status=?,updated_at=? WHERE id=? AND status!=?", (status, utc_now(), row["id"], status)).rowcount
    return changed

