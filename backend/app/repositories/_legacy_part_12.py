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
from ._legacy_part_11 import *
def list_notes(connection: sqlite3.Connection, *, project_id: str,
               include_archived: bool = False) -> list[dict[str, object]]:
    where = "project_id=?" if include_archived else "project_id=? AND status!='archived'"
    return [_note_public(connection, project_id=project_id, note_id=str(row["id"])) for row in connection.execute(
        "SELECT id FROM notes WHERE " + where + " ORDER BY updated_at DESC,id DESC", (project_id,)
    ).fetchall()]

def get_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object] | None:
    return _note_public(connection, project_id=project_id, note_id=note_id) if _note_row(connection, project_id=project_id, note_id=note_id) else None

def update_note(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                title: object | None = None) -> dict[str, object]:
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        title_value = str(row["title"]) if title is None else _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
        connection.execute("UPDATE notes SET title=?,user_edited=1,updated_at=? WHERE id=? AND project_id=?", (title_value, utc_now(), note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)

def update_note_content(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                        title: object | None = None, blocks: object | None = None) -> dict[str, object]:
    """Atomically patch note title and ordered blocks when both are supplied."""
    if title is None and blocks is None:
        raise ValueError("study_note_invalid_payload")
    values = _note_validate_blocks(blocks) if blocks is not None else None
    title_value = None if title is None else _study_text(title, code="study_note_invalid_payload", maximum=NOTE_MAX_TITLE)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        now = utc_now()
        if values is not None:
            expected_provenance = "ai_generated" if row["provenance"] == "ai_generated" else "user_created"
            existing = connection.execute(
                "SELECT id FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)
            ).fetchall()
            common = min(len(existing), len(values))
            for position in range(common):
                kind, content, _ = values[position]
                connection.execute(
                    "UPDATE note_blocks SET position=?,block_kind=?,content=?,provenance=?,updated_at=? WHERE id=? AND note_id=?",
                    (position, kind, content, expected_provenance, now, existing[position]["id"], note_id),
                )
            for old in existing[common:]:
                connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (old["id"], note_id))
            for position, (kind, content, block_provenance) in enumerate(values[common:], start=common):
                connection.execute(
                    "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, expected_provenance, now, now),
                )
        connection.execute(
            "UPDATE notes SET title=COALESCE(?,title),user_edited=1,updated_at=? WHERE id=? AND project_id=?",
            (title_value, now, note_id, project_id),
        )
    return _note_public(connection, project_id=project_id, note_id=note_id)

def update_note_blocks(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                       blocks: object) -> dict[str, object]:
    values = _note_validate_blocks(blocks)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_block_edit_not_allowed")
        expected_provenance = "ai_generated" if row["provenance"] == "ai_generated" else "user_created"
        now = utc_now()
        existing = connection.execute(
            "SELECT id,position FROM note_blocks WHERE note_id=? AND project_id=? ORDER BY position,id", (note_id, project_id)
        ).fetchall()
        common = min(len(existing), len(values))
        for position in range(common):
            kind, content, _ = values[position]
            connection.execute(
                "UPDATE note_blocks SET position=?,block_kind=?,content=?,provenance=?,updated_at=? WHERE id=? AND note_id=?",
                (position, kind, content, expected_provenance, now, existing[position]["id"], note_id),
            )
        for old in existing[common:]:
            connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (old["id"], note_id))
        for position, (kind, content, block_provenance) in enumerate(values[common:], start=common):
            connection.execute(
                "INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"note_block_{uuid.uuid4().hex}", note_id, project_id, position, kind, content, block_provenance, now, now),
            )
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=? AND project_id=?", (now, note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)

def _note_editable_block(connection: sqlite3.Connection, *, project_id: str, note_id: str, block_id: str) -> sqlite3.Row:
    note = _note_row(connection, project_id=project_id, note_id=note_id)
    if note is None:
        raise ValueError("study_note_not_found")
    if note["status"] != "draft":
        raise ValueError("study_note_block_edit_not_allowed")
    block = connection.execute("SELECT * FROM note_blocks WHERE id=? AND note_id=? AND project_id=?", (block_id, note_id, project_id)).fetchone()
    if block is None:
        raise ValueError("study_note_block_not_found")
    return block

def create_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                      block_kind: object, content: object) -> dict[str, object]:
    kind, body, _ = _note_block_values({"block_kind": block_kind, "content": content})
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_block_edit_not_allowed")
        total = int(connection.execute("SELECT COALESCE(SUM(length(content)),0) FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0])
        if total + len(body) > NOTE_MAX_CONTENT:
            raise ValueError("study_note_block_invalid")
        position = int(connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0])
        block_id = f"note_block_{uuid.uuid4().hex}"; now = utc_now()
        connection.execute("INSERT INTO note_blocks (id,note_id,project_id,position,block_kind,content,provenance,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (block_id,note_id,project_id,position,kind,body,str(note["provenance"]),now,now))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_blocks WHERE id=?", (block_id,)).fetchone())

def update_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                      block_id: str, block_kind: object | None = None, content: object | None = None) -> dict[str, object]:
    with connection:
        block = _note_editable_block(connection, project_id=project_id, note_id=note_id, block_id=block_id)
        kind, body, _ = _note_block_values({"block_kind": block["block_kind"] if block_kind is None else block_kind,
                                             "content": block["content"] if content is None else content})
        total = int(connection.execute("SELECT COALESCE(SUM(length(content)),0) FROM note_blocks WHERE note_id=? AND id!=?", (note_id,block_id)).fetchone()[0])
        if total + len(body) > NOTE_MAX_CONTENT:
            raise ValueError("study_note_block_invalid")
        now = utc_now()
        connection.execute("UPDATE note_blocks SET block_kind=?,content=?,updated_at=? WHERE id=?", (kind,body,now,block_id))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_blocks WHERE id=?", (block_id,)).fetchone())

def delete_note_block(connection: sqlite3.Connection, *, project_id: str, note_id: str, block_id: str) -> bool:
    with connection:
        block = _note_editable_block(connection, project_id=project_id, note_id=note_id, block_id=block_id)
        if int(connection.execute("SELECT COUNT(*) FROM note_blocks WHERE note_id=?", (note_id,)).fetchone()[0]) <= 1:
            raise ValueError("study_note_empty")
        deleted_position = int(block["position"])
        connection.execute("DELETE FROM note_blocks WHERE id=? AND note_id=?", (block_id,note_id))
        connection.execute("UPDATE note_blocks SET position=position-1 WHERE note_id=? AND position>?", (note_id,deleted_position))
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True

def link_note_module(connection: sqlite3.Connection, *, project_id: str, note_id: str, module_id: str) -> dict[str, object]:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        module = _study_module_row(connection, project_id=project_id, module_id=module_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        if module is None:
            raise ValueError("study_note_module_invalid")
        if module["status"] != "active":
            raise ValueError("study_note_module_archived")
        link_id = f"note_module_{uuid.uuid4().hex}"
        try:
            connection.execute("INSERT INTO note_module_links (id,project_id,note_id,module_id) VALUES (?,?,?,?)", (link_id,project_id,note_id,module_id))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_note_module_link_duplicate") from exc
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return dict(connection.execute("SELECT * FROM note_module_links WHERE id=?", (link_id,)).fetchone())

def unlink_note_module(connection: sqlite3.Connection, *, project_id: str, note_id: str, module_id: str) -> bool:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_edit_not_allowed")
        cursor = connection.execute("DELETE FROM note_module_links WHERE project_id=? AND note_id=? AND module_id=?", (project_id,note_id,module_id))
        if cursor.rowcount != 1:
            raise ValueError("study_note_module_invalid")
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True

def _note_source_values(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                        block_id: str, payload: dict[str, object],
                        context_chunk_ids: object) -> tuple[str, ...]:
    required = ("material_id", "revision_id", "extraction_id", "chunk_id", "citation_key")
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not str(payload[key]).strip() for key in required):
        raise ValueError("study_note_source_invalid")
    material_id, revision_id = str(payload["material_id"]), str(payload["revision_id"])
    extraction_id, chunk_id, citation_key = str(payload["extraction_id"]), str(payload["chunk_id"]), str(payload["citation_key"])
    if (not isinstance(context_chunk_ids, list) or not context_chunk_ids or len(context_chunk_ids) > MAX_RETRIEVAL_TOP_K or
            any(not isinstance(chunk, str) or not chunk for chunk in context_chunk_ids)):
        raise ValueError("study_note_source_invalid")
    context = assemble_context(connection, project_id=project_id,
                               hits=[{"chunk_id": chunk, "rank": index + 1}
                                     for index, chunk in enumerate(context_chunk_ids)])
    context_source = next((block for block in context["context_blocks"]
                           if block.get("citation_key") == citation_key), None)
    source_info = context_source.get("source_info") if isinstance(context_source, dict) else None
    if (not isinstance(source_info, dict) or source_info.get("material_id") != material_id or
            source_info.get("revision_id") != revision_id or chunk_id not in context_chunk_ids):
        raise ValueError("study_note_source_invalid")
    span_id = payload.get("span_id")
    if span_id is not None and (not isinstance(span_id, str) or len(span_id) > 200):
        raise ValueError("study_note_source_invalid")
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None or material["project_id"] != project_id:
        raise ValueError("study_note_source_invalid")
    if material["deleted_at"] is not None:
        raise ValueError("study_note_source_deleted")
    chunk = connection.execute("SELECT revision_id,extraction_id,status FROM chunks WHERE id=? AND material_id=?", (chunk_id,material_id)).fetchone()
    validation = validate_citation_key(connection, citation_key)
    if (chunk is None or chunk["revision_id"] != revision_id or chunk["extraction_id"] != extraction_id or
            chunk["status"] != "ready" or validation is None or validation.get("status") != "valid" or
            validation.get("material_id") != material_id or validation.get("chunk_id") != chunk_id or
            validation.get("revision_id") != revision_id):
        raise ValueError("study_note_source_invalid")
    if span_id is not None and connection.execute("SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id,span_id)).fetchone() is None:
        raise ValueError("study_note_source_invalid")
    return material_id, revision_id, extraction_id, chunk_id, span_id, citation_key

def create_note_source_link(connection: sqlite3.Connection, *, project_id: str, note_id: str,
                            block_id: str, payload: dict[str, object],
                            context_chunk_ids: object) -> dict[str, object]:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_source_invalid")
        if connection.execute("SELECT 1 FROM note_blocks WHERE id=? AND note_id=? AND project_id=?", (block_id,note_id,project_id)).fetchone() is None:
            raise ValueError("study_note_block_not_found")
        values = _note_source_values(connection, project_id=project_id, note_id=note_id, block_id=block_id,
                                     payload=payload, context_chunk_ids=context_chunk_ids)
        link_id = f"note_source_{uuid.uuid4().hex}"; now = utc_now()
        try:
            connection.execute("INSERT INTO note_block_source_links (id,project_id,note_id,note_block_id,material_id,revision_id,extraction_id,chunk_id,span_id,citation_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (link_id,project_id,note_id,block_id,*values,"valid",now,now))
        except sqlite3.IntegrityError as exc:
            raise ValueError("study_note_source_invalid") from exc
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (now,note_id))
    return dict(connection.execute("SELECT * FROM note_block_source_links WHERE id=?", (link_id,)).fetchone())

def delete_note_source_link(connection: sqlite3.Connection, *, project_id: str, note_id: str, link_id: str) -> bool:
    with connection:
        note = _note_row(connection, project_id=project_id, note_id=note_id)
        if note is None:
            raise ValueError("study_note_not_found")
        if note["status"] != "draft":
            raise ValueError("study_note_source_invalid")
        cursor = connection.execute("DELETE FROM note_block_source_links WHERE id=? AND note_id=? AND project_id=?", (link_id,note_id,project_id))
        if cursor.rowcount != 1:
            raise ValueError("study_note_source_not_found")
        connection.execute("UPDATE notes SET user_edited=1,updated_at=? WHERE id=?", (utc_now(),note_id))
    return True

def confirm_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        if row["status"] != "draft":
            raise ValueError("study_note_invalid_state")
        blocks = connection.execute("SELECT id FROM note_blocks WHERE note_id=? AND project_id=?", (note_id,project_id)).fetchall()
        if not blocks:
            raise ValueError("study_note_empty")
        # Recompute link status inside the confirm transaction; persisted status is not trusted.
        _refresh_note_source_links(connection, project_id=project_id, note_id=note_id)
        if row["provenance"] == "ai_generated":
            missing = connection.execute("SELECT 1 FROM note_blocks b WHERE b.note_id=? AND NOT EXISTS (SELECT 1 FROM note_block_source_links l WHERE l.note_block_id=b.id AND l.status='valid')", (note_id,)).fetchone()
            if missing is not None:
                raise ValueError("study_note_confirm_source_invalid")
        now = utc_now()
        connection.execute("UPDATE notes SET status='confirmed',confirmed_at=?,updated_at=? WHERE id=? AND project_id=?", (now,now,note_id,project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)

def transition_note(connection: sqlite3.Connection, *, project_id: str, note_id: str, target: str) -> dict[str, object]:
    if target == "confirmed":
        return confirm_note(connection, project_id=project_id, note_id=note_id)
    with connection:
        row = _note_row(connection, project_id=project_id, note_id=note_id)
        if row is None:
            raise ValueError("study_note_not_found")
        allowed = {"rejected": {"draft"}, "archived": {"draft", "confirmed", "rejected"}}
        if target not in allowed or row["status"] not in allowed[target]:
            raise ValueError("study_note_invalid_state")
        now = utc_now()
        connection.execute("UPDATE notes SET status=?,archived_at=?,updated_at=? WHERE id=? AND project_id=?", (target, now if target == "archived" else None, now, note_id, project_id))
    return _note_public(connection, project_id=project_id, note_id=note_id)

def _refresh_note_source_links(connection: sqlite3.Connection, *, project_id: str,
                               note_id: str | None = None, material_id: str | None = None) -> int:
    where = ["project_id=?"]; params: list[object] = [project_id]
    if note_id is not None:
        where.append("note_id=?"); params.append(note_id)
    if material_id is not None:
        where.append("material_id=?"); params.append(material_id)
    rows = connection.execute("SELECT * FROM note_block_source_links WHERE " + " AND ".join(where), params).fetchall()
    changed = 0
    for row in rows:
        material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (row["material_id"],)).fetchone()
        if material is None:
            status = "source_unavailable"
        elif material["deleted_at"] is not None:
            status = "source_deleted"
        else:
            status = _study_source_status(connection, project_id=project_id, material_id=row["material_id"], revision_id=row["revision_id"], extraction_id=row["extraction_id"], chunk_id=row["chunk_id"], span_id=row["span_id"], citation_key=row["citation_key"], strict=False)
        changed += connection.execute("UPDATE note_block_source_links SET status=?,updated_at=? WHERE id=? AND status!=?", (status,utc_now(),row["id"],status)).rowcount
    return changed

def refresh_note_source_links(connection: sqlite3.Connection, *, project_id: str, note_id: str | None = None,
                              material_id: str | None = None) -> int:
    with connection:
        return _refresh_note_source_links(connection, project_id=project_id, note_id=note_id, material_id=material_id)

def archive_note(connection: sqlite3.Connection, *, project_id: str, note_id: str) -> dict[str, object]:
    return transition_note(connection, project_id=project_id, note_id=note_id, target="archived")

