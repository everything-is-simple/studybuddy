"""S2 metadata shares canonical module identity; evidence and practice are traceable."""
from __future__ import annotations

import json
import re
from uuid import uuid4

from .connection import utc_now
from .ai import assemble_context


def source_chunks(connection, *, project_id, material_id):
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (material_id,)).fetchone()
    if material is None or material["project_id"] != project_id:
        raise ValueError("material_not_found")
    if material["deleted_at"] is not None:
        raise ValueError("source_deleted")
    return [dict(row) for row in connection.execute(
        "SELECT c.id AS chunk_id,c.material_id,c.revision_id,c.extraction_id,c.chunk_index "
        "FROM chunks c JOIN material_revisions r ON r.id=c.revision_id "
        "WHERE c.material_id=? AND c.project_id=? AND c.status='ready' AND r.is_current=1 "
        "ORDER BY c.chunk_index,c.id", (material_id, project_id))]


def evidence_for_chunks(connection, *, project_id, material_id, chunk_ids):
    if not isinstance(chunk_ids, list) or not 1 <= len(chunk_ids) <= 10 or len(set(chunk_ids)) != len(chunk_ids):
        raise ValueError("knowledge_source_invalid")
    candidates = {row["chunk_id"]: row for row in source_chunks(connection, project_id=project_id, material_id=material_id)}
    if any(cid not in candidates for cid in chunk_ids):
        raise ValueError("knowledge_source_invalid")
    blocks = assemble_context(connection, project_id=project_id, hits=[{"chunk_id": cid} for cid in chunk_ids])["context_blocks"]
    if len(blocks) != len(chunk_ids):
        raise ValueError("knowledge_source_invalid")
    return {"material_id": material_id, "revision_id": candidates[chunk_ids[0]]["revision_id"],
            "chunk_ids": chunk_ids, "span_ids": sorted({s for b in blocks for s in b["span_ids"]}),
            "context": "\n".join(b["text"] for b in blocks)[:500]}


def source_status(connection, project_id, evidence):
    material = connection.execute("SELECT project_id,deleted_at FROM materials WHERE id=?", (evidence["material_id"],)).fetchone()
    if material is None or material["project_id"] != project_id:
        return "source_unavailable"
    if material["deleted_at"]:
        return "source_deleted"
    try:
        current = evidence_for_chunks(connection, project_id=project_id, material_id=evidence["material_id"], chunk_ids=evidence["chunk_ids"])
    except ValueError:
        return "stale"
    return "valid" if current["revision_id"] == evidence["revision_id"] else "stale"


def _values(payload):
    title, description, tags = payload.get("title"), payload.get("description", ""), payload.get("tags", [])
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("knowledge_module_invalid_payload")
    if not isinstance(description, str) or len(description) > 4000:
        raise ValueError("knowledge_module_invalid_payload")
    for name, default in (("importance", 1), ("difficulty", 3)):
        value = payload.get(name, default)
        if type(value) is not int or not 1 <= value <= 5:
            raise ValueError("knowledge_module_invalid_payload")
    minutes = payload.get("estimated_minutes")
    if minutes is not None and (type(minutes) is not int or not 1 <= minutes <= 1440):
        raise ValueError("knowledge_module_invalid_payload")
    if not isinstance(tags, list) or len(tags) > 10 or any(not isinstance(t, str) or not t.strip() or len(t) > 50 for t in tags):
        raise ValueError("knowledge_module_invalid_payload")
    return title.strip(), description, payload.get("importance", 1), payload.get("difficulty", 3), minutes, json.dumps(tags, ensure_ascii=False)


def create_modules(connection, *, project_id, material_id, payloads, provenance="user_created", provider_id=None, model_id=None):
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= 10:
        raise ValueError("knowledge_module_invalid_payload")
    ids = []
    with connection:
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        prepared = [(_values(p), evidence_for_chunks(connection, project_id=project_id, material_id=material_id, chunk_ids=p.get("chunk_ids"))) for p in payloads]
        for values, evidence in prepared:
            module_id, now = "module_" + uuid4().hex, utc_now()
            ids.append(module_id)
            connection.execute("INSERT INTO knowledge_modules(id,project_id,title,description,status,created_at,updated_at) VALUES (?,?,?,?,'active',?,?)",
                               (module_id, project_id, values[0], values[1], now, now))
            connection.execute("INSERT INTO s2_knowledge_modules(id,material_id,source_evidence,importance,difficulty,estimated_minutes,tags,lifecycle,provenance,provider_id,model_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (module_id, material_id, json.dumps(evidence, ensure_ascii=False), *values[2:], "draft" if provenance == "ai_generated" else "confirmed", provenance, provider_id, model_id))
            for cid in evidence["chunk_ids"]:
                chunk = connection.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
                connection.execute("INSERT INTO module_source_links(id,project_id,module_id,material_id,revision_id,extraction_id,chunk_id,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'valid',?,?)",
                                   ("source_" + uuid4().hex, project_id, module_id, material_id, chunk["revision_id"], chunk["extraction_id"], cid, now, now))
    return [get_module(connection, project_id=project_id, module_id=i) for i in ids]


def practice_history(connection, *, project_id, module_id):
    return [dict(r) for r in connection.execute(
        "SELECT a.id,a.exercise_id,a.session_id,a.is_correct,a.grading_status,a.submitted_at "
        "FROM exercise_attempts a JOIN s2_module_exercises l ON l.exercise_id=a.exercise_id "
        "JOIN exercises e ON e.id=a.exercise_id AND e.project_id=? "
        "WHERE l.module_id=? ORDER BY a.submitted_at,a.id", (project_id, module_id))]


def get_module(connection, *, project_id, module_id, include_deleted=False):
    row = connection.execute("SELECT k.*,s.material_id,s.source_evidence,s.importance,s.difficulty,s.estimated_minutes,s.tags,s.lifecycle,s.provenance,s.user_edited,s.provider_id,s.model_id,s.deleted_at "
                             "FROM knowledge_modules k JOIN s2_knowledge_modules s ON s.id=k.id WHERE k.id=? AND k.project_id=?",
                             (module_id, project_id)).fetchone()
    if row is None or (row["deleted_at"] is not None and not include_deleted):
        return None
    result = dict(row)
    result["source_evidence"], result["tags"] = json.loads(result["source_evidence"]), json.loads(result["tags"])
    result["source_status"] = source_status(connection, project_id, result["source_evidence"])
    if result["source_status"] != "valid":
        result["source_evidence"].pop("context", None)
    level, state, last = 0.0, "not_started", None
    for attempt in practice_history(connection, project_id=project_id, module_id=module_id):
        last = attempt["submitted_at"]
        if attempt["is_correct"] is None:
            continue
        if attempt["is_correct"]:
            level += .1 * (1 - level)
            state = "mastered" if level >= .8 else "in_progress"
        else:
            level *= .8
            state = "needs_review"
    result.update(mastery_level=round(level, 6), learn_status=state, last_practiced_at=last)
    return result


def list_modules(connection, *, project_id, material_id=None, query=None, lifecycle=None, learn_status=None, importance=None, limit=50, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError("invalid_pagination")
    if lifecycle not in {None,"draft","confirmed","rejected"} or learn_status not in {None,"not_started","in_progress","mastered","needs_review"}:
        raise ValueError("knowledge_module_invalid_filter")
    if importance is not None and (type(importance) is not int or not 1 <= importance <= 5):
        raise ValueError("knowledge_module_invalid_filter")
    where, params = ["k.project_id=?", "s.deleted_at IS NULL", "k.status='active'"], [project_id]
    for value, column in ((material_id,"s.material_id"),(lifecycle,"s.lifecycle"),(importance,"s.importance")):
        if value is not None:
            where.append(column+"=?"); params.append(value)
    if query:
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError("knowledge_module_invalid_filter")
        tokens = re.findall(r"\w+", query)
        if not tokens:
            return {"modules": [], "total": 0, "has_more": False}
        where.append("k.id IN (SELECT module_id FROM s2_knowledge_modules_fts WHERE s2_knowledge_modules_fts MATCH ?)")
        params.append(" AND ".join('"'+t+'"*' for t in tokens))
    ids = connection.execute("SELECT k.id FROM knowledge_modules k JOIN s2_knowledge_modules s ON s.id=k.id WHERE "+" AND ".join(where)+" ORDER BY s.importance,k.created_at DESC,k.id", params).fetchall()
    rows = [get_module(connection, project_id=project_id, module_id=r[0]) for r in ids]
    if learn_status:
        rows = [r for r in rows if r["learn_status"] == learn_status]
    total = len(rows)
    return {"modules": rows[offset:offset+limit], "total": total, "has_more": offset+limit < total}


def update_module(connection, *, project_id, module_id, payload):
    old = get_module(connection, project_id=project_id, module_id=module_id)
    if old is None:
        raise ValueError("knowledge_module_not_found")
    if old["lifecycle"] == "rejected" or old["status"] != "active":
        raise ValueError("knowledge_module_invalid_state")
    values = _values({**old, **payload})
    with connection:
        connection.execute("UPDATE knowledge_modules SET title=?,description=?,updated_at=? WHERE id=?", (values[0],values[1],utc_now(),module_id))
        connection.execute("UPDATE s2_knowledge_modules SET importance=?,difficulty=?,estimated_minutes=?,tags=?,user_edited=1 WHERE id=?", (*values[2:],module_id))
    return get_module(connection, project_id=project_id, module_id=module_id)


def transition_module(connection, *, project_id, module_id, action):
    old = get_module(connection, project_id=project_id, module_id=module_id)
    if old is None:
        raise ValueError("knowledge_module_not_found")
    if action != "delete" and (old["lifecycle"] != "draft" or old["status"] != "active"):
        raise ValueError("knowledge_module_invalid_state")
    if action == "confirm" and old["source_status"] != "valid":
        raise ValueError("knowledge_source_invalid")
    with connection:
        if action == "delete":
            now = utc_now()
            connection.execute("UPDATE s2_knowledge_modules SET deleted_at=? WHERE id=?", (now,module_id))
            connection.execute("UPDATE knowledge_modules SET status='archived',archived_at=?,updated_at=? WHERE id=?", (now,now,module_id))
        else:
            connection.execute("UPDATE s2_knowledge_modules SET lifecycle=? WHERE id=?", ("confirmed" if action == "confirm" else "rejected",module_id))
    return get_module(connection, project_id=project_id, module_id=module_id, include_deleted=True)


def module_context(connection, *, project_id, module_ids):
    if not isinstance(module_ids, list) or not 1 <= len(module_ids) <= 10 or len(set(module_ids)) != len(module_ids):
        raise ValueError("knowledge_module_invalid_payload")
    modules, chunks = [], []
    for mid in module_ids:
        module = get_module(connection, project_id=project_id, module_id=mid)
        if module is None:
            raise ValueError("knowledge_module_not_found")
        if module["status"] != "active" or module["lifecycle"] != "confirmed" or module["source_status"] != "valid":
            raise ValueError("knowledge_module_not_ready")
        modules.append(module)
        chunks.extend(module["source_evidence"]["chunk_ids"])
    if len({m["source_evidence"]["revision_id"] for m in modules}) != 1:
        raise ValueError("knowledge_module_scope_conflict")
    blocks = assemble_context(connection, project_id=project_id, hits=[{"chunk_id": c} for c in dict.fromkeys(chunks)])["context_blocks"]
    if len(blocks) != len(set(chunks)):
        raise ValueError("knowledge_source_invalid")
    return modules, blocks
