from ._legacy_runtime import *
from ._legacy_part_00 import *
def save_material_with_extraction(connection: sqlite3.Connection, project_id: str,
                                  original_name: str, source_sha256: str,
                                  stored_path: Path, media_type: str,
                                  result: ParseResult) -> tuple[str, str]:
    material_id = f"material_{uuid.uuid4().hex}"
    extraction_id = f"extraction_{uuid.uuid4().hex}"
    created_at = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?)",
                           (project_id, "Default project", created_at))
        connection.execute(
            "INSERT INTO materials (id, project_id, original_name, source_sha256, stored_path, media_type, created_at, updated_at, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (material_id, project_id, original_name, source_sha256, str(stored_path), media_type, created_at, created_at),
        )
        connection.execute(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (extraction_id, material_id, result.parser_id, result.parser_version, result.status,
             result.text, json.dumps(result.warnings, ensure_ascii=False), created_at, result.error_code),
        )
        connection.executemany(
            "INSERT INTO text_spans VALUES (?, ?, ?, ?, ?, ?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, span.ordinal, span.kind, span.label, span.text)
             for span in result.spans],
        )
        _insert_search_row(connection, material_id, original_name, result.text)
    return material_id, extraction_id

def _snippet(text: str, tokens: list[str]) -> str:
    lowered = text.casefold()
    positions = [lowered.find(token.casefold()) for token in tokens if token.casefold() in lowered]
    if not positions:
        return ""
    start = max(0, min(positions) - 50)
    end = min(len(text), start + 160)
    return text[start:end]

def _search_rows(connection: sqlite3.Connection, status: str | None, query: str,
                 *, limit: int | None = None, offset: int = 0) -> list[sqlite3.Row]:
    tokens = _search_tokens(query)
    if not tokens:
        return []
    query_sql = (
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, e.created_at, m.updated_at, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, e.text AS search_text "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL AND e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))"
    )
    params: list[str] = []
    if status is not None:
        query_sql += " AND e.status = ?"
        params.append(status)
    if all(token.isascii() and token.replace("_", "").isalnum() for token in tokens):
        match = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
        query_sql += " AND m.id IN (SELECT material_id FROM material_search WHERE material_search MATCH ?)"
        params.append(match)
    else:
        for token in tokens:
            query_sql += " AND (instr(lower(m.original_name), lower(?)) > 0 OR instr(lower(e.text), lower(?)) > 0)"
            params.extend((token, token))
    query_sql += " ORDER BY e.created_at DESC, m.id DESC"
    if limit is not None:
        query_sql += " LIMIT ? OFFSET ?"
        params.extend((str(limit), str(offset)))
    rows = connection.execute(query_sql, params).fetchall()
    return [row for row in rows if all(
        token.casefold() in str(row[1]).casefold() or token.casefold() in str(row[10]).casefold()
        for token in tokens
    )]

def _search_count(connection: sqlite3.Connection, status: str | None, query: str) -> int:
    tokens = _search_tokens(query)
    if not tokens:
        return 0
    query_sql = (
        "SELECT COUNT(*) FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL AND e.id = COALESCE((SELECT r.extraction_id FROM material_revisions r "
        "WHERE r.material_id=m.id AND r.is_current=1 ORDER BY r.created_at DESC,r.id DESC LIMIT 1), "
        "(SELECT e2.id FROM extractions e2 WHERE e2.material_id=m.id ORDER BY e2.created_at DESC,e2.id DESC LIMIT 1))"
    )
    params: list[str] = []
    if status is not None:
        query_sql += " AND e.status = ?"
        params.append(status)
    if all(token.isascii() and token.replace("_", "").isalnum() for token in tokens):
        match = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
        query_sql += " AND m.id IN (SELECT material_id FROM material_search WHERE material_search MATCH ?)"
        params.append(match)
    else:
        for token in tokens:
            query_sql += " AND (instr(lower(m.original_name), lower(?)) > 0 OR instr(lower(e.text), lower(?)) > 0)"
            params.extend((token, token))
    return int(connection.execute(query_sql, params).fetchone()[0])

def list_materials(connection: sqlite3.Connection, status: str | None = None,
                   query: str | None = None) -> list[sqlite3.Row | dict[str, object]]:
    normalized = (query or "").strip()
    if normalized:
        results: list[dict[str, object]] = []
        for row in _search_rows(connection, status, normalized):
            payload = dict(row)
            text = str(payload.pop("search_text"))
            tokens = _search_tokens(normalized)
            fields = []
            if any(token.casefold() in str(payload["original_name"]).casefold() for token in tokens):
                fields.append("original_name")
            if any(token.casefold() in text.casefold() for token in tokens):
                fields.append("text")
            payload["match_fields"] = fields
            payload["snippet"] = _snippet(text, tokens)
            results.append(payload)
        return results
    query_sql = (
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id WHERE m.deleted_at IS NULL"
    )
    params: tuple[str, ...] = ()
    if status is not None:
        query_sql += " AND e.status = ?"
        params = (status,)
    query_sql += " ORDER BY e.created_at DESC, m.id DESC"
    return connection.execute(query_sql, params).fetchall()

def list_deleted_materials(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, m.deleted_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NOT NULL ORDER BY m.deleted_at DESC, m.id DESC"
    ).fetchall()

def list_materials_page(connection: sqlite3.Connection, status: str | None = None, query: str | None = None,
                        limit: int = 20, offset: int = 0) -> tuple[list[sqlite3.Row | dict[str, object]], int]:
    normalized = (query or "").strip()
    if normalized:
        # Keep the same filtering contract as list_materials while applying the
        # page window in SQLite rather than materializing every match.
        total = _search_count(connection, status, normalized)
        rows = _search_rows(connection, status, normalized, limit=limit, offset=offset)
        tokens = _search_tokens(normalized)
        results: list[dict[str, object]] = []
        for row in rows:
            payload = dict(row)
            text = str(payload.pop("search_text"))
            payload["match_fields"] = [field for field, value in (
                ("original_name", payload["original_name"]), ("text", text)
            ) if any(token.casefold() in str(value).casefold() for token in tokens)]
            payload["snippet"] = _snippet(text, tokens)
            results.append(payload)
        return results, total
    base = (
        " FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NULL"
    )
    params: list[str] = []
    if status is not None:
        base += " AND e.status = ?"
        params.append(status)
    total = int(connection.execute("SELECT COUNT(*)" + base, params).fetchone()[0])
    rows = connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count" + base +
        " ORDER BY e.created_at DESC, m.id DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return rows, total

def list_deleted_materials_page(connection: sqlite3.Connection, limit: int = 20,
                                offset: int = 0) -> tuple[list[sqlite3.Row], int]:
    base = (
        " FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.deleted_at IS NOT NULL"
    )
    total = int(connection.execute("SELECT COUNT(*)" + base).fetchone()[0])
    rows = connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.media_type, e.status, e.error_code, "
        "e.created_at, m.updated_at, m.deleted_at, length(e.text) AS text_length, "
        "(SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count" + base +
        " ORDER BY m.deleted_at DESC, m.id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return rows, total

def restore_material(connection: sqlite3.Connection, material_id: str) -> sqlite3.Row | None:
    updated_at = utc_now()
    with connection:
        cursor = connection.execute(
            "UPDATE materials SET deleted_at = NULL, updated_at = ? WHERE id = ? AND deleted_at IS NOT NULL",
            (updated_at, material_id),
        )
        if cursor.rowcount != 1:
            return None
        _refresh_exercise_citations_for_material(connection, material_id)
        _refresh_card_citations_for_material(connection, material_id)
        # Restore does not promote retained 9C snapshot source status; only an
        # explicit re-index/refresh path may revalidate it.
    return connection.execute(
        "SELECT m.id, m.original_name, m.source_sha256, m.stored_path, m.media_type, e.status, e.error_code, "
        "length(e.text) AS text_length, (SELECT COUNT(*) FROM text_spans s WHERE s.extraction_id = e.id) AS span_count, "
        "m.created_at, m.updated_at, m.deleted_at "
        "FROM materials m JOIN extractions e ON e.material_id = m.id "
        "WHERE m.id = ? AND m.deleted_at IS NULL",
        (material_id,),
    ).fetchone()

MAX_CARD_TEXT_LENGTH = 4000

MAX_CARD_TAGS = 20

MAX_CARD_CITATIONS = 20

MAX_DECK_TITLE_LENGTH = 200

MAX_EXERCISE_PROMPT_LENGTH = 4000

MAX_EXERCISE_OPTIONS = 10

def _validate_text(value: object, *, code: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(code)
    return value.strip()

def _validate_card_payload(payload: dict[str, object]) -> tuple[str, str, str, list[str]]:
    front = _validate_text(payload.get("front"), code="invalid_card_payload", maximum=MAX_CARD_TEXT_LENGTH)
    back = _validate_text(payload.get("back"), code="invalid_card_payload", maximum=MAX_CARD_TEXT_LENGTH)
    explanation = payload.get("explanation", "")
    if not isinstance(explanation, str) or len(explanation) > MAX_CARD_TEXT_LENGTH:
        raise ValueError("invalid_card_payload")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or len(tags) > MAX_CARD_TAGS or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 50 for tag in tags):
        raise ValueError("invalid_card_payload")
    return front, back, explanation, [tag.strip() for tag in tags]

def _citation_rows(connection: sqlite3.Connection, citations: object, *, code: str,
                   artifact_id: str, table: str) -> list[tuple[object, ...]]:
    if not isinstance(citations, list) or len(citations) > MAX_CARD_CITATIONS:
        raise ValueError(code)
    result: list[tuple[object, ...]] = []
    seen: set[str] = set()
    for position, item in enumerate(citations):
        if not isinstance(item, dict):
            raise ValueError("citation_invalid")
        key = item.get("citation_key")
        if not isinstance(key, str) or not key or len(key) > 100 or key in seen:
            raise ValueError("citation_invalid")
        seen.add(key)
        chunk_id = item.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("citation_invalid")
        chunk = connection.execute(
            "SELECT c.material_id, c.revision_id, c.extraction_id, c.text, c.status, r.is_current, m.deleted_at "
            "FROM chunks c JOIN material_revisions r ON r.id=c.revision_id JOIN materials m ON m.id=c.material_id "
            "WHERE c.id=?", (chunk_id,)
        ).fetchone()
        quote = item.get("quote", "")
        if chunk is None or not isinstance(quote, str) or not quote.strip() or len(quote) > 500:
            raise ValueError("citation_invalid")
        if chunk["status"] != "ready" or not chunk["is_current"] or chunk["deleted_at"] is not None or quote.strip() not in str(chunk["text"]):
            raise ValueError("citation_invalid")
        span_id = item.get("span_id")
        if span_id is not None and (not isinstance(span_id, str) or connection.execute(
                "SELECT 1 FROM chunk_spans WHERE chunk_id=? AND span_id=?", (chunk_id, span_id)).fetchone() is None):
            raise ValueError("citation_invalid")
        result.append((f"{table}_citation_{uuid.uuid4().hex}", artifact_id, key,
                       chunk["material_id"], chunk["revision_id"], chunk["extraction_id"], chunk_id,
                       span_id, quote.strip(), position, "valid"))
    return result

def create_deck(connection: sqlite3.Connection, *, project_id: str, title: str,
                description: str = "") -> dict[str, object]:
    title = _validate_text(title, code="invalid_deck_payload", maximum=MAX_DECK_TITLE_LENGTH)
    if not isinstance(description, str) or len(description) > 1000:
        raise ValueError("invalid_deck_payload")
    deck_id = f"deck_{uuid.uuid4().hex}"
    now = utc_now()
    with connection:
        connection.execute("INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (?, ?, ?)",
                           (project_id, "Default project", now))
        connection.execute("INSERT INTO study_decks VALUES (?,?,?,?,?,?,?,?)",
                           (deck_id, project_id, title, description, "active", now, now, None))
    return get_deck(connection, project_id=project_id, deck_id=deck_id) or {}

def get_deck(connection: sqlite3.Connection, *, project_id: str, deck_id: str) -> dict[str, object] | None:
    row = connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM study_decks WHERE id=? AND project_id=?", (deck_id, project_id)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["cards"] = list_cards(connection, project_id=project_id, deck_id=deck_id)
    return result

def list_decks(connection: sqlite3.Connection, *, project_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute("SELECT id,project_id,title,description,status,created_at,updated_at,archived_at FROM study_decks WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project_id,)).fetchall()]

def list_cards(connection: sqlite3.Connection, *, project_id: str, deck_id: str | None = None) -> list[dict[str, object]]:
    params: list[object] = [project_id]
    where = "c.project_id=?"
    if deck_id is not None:
        where += " AND c.deck_id=?"; params.append(deck_id)
    with connection:
        rows = connection.execute("SELECT c.id,c.deck_id,c.card_type,c.status,c.front,c.back,c.explanation,c.tags_json,c.source_revision,c.edited_by_user,c.created_at,c.updated_at,c.confirmed_at,c.archived_at FROM study_cards c WHERE " + where + " ORDER BY c.updated_at DESC,c.id DESC", params).fetchall()
        for row in rows:
            _refresh_card_citations(connection, str(row["id"]))
    return [{**dict(row), "tags": json.loads(row["tags_json"]), "citations": list_card_citations(connection, str(row["id"]))} for row in rows]

def list_card_citations(connection: sqlite3.Connection, card_id: str) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute("SELECT citation_key,material_id,revision_id,extraction_id,chunk_id,span_id,quote,position,status FROM card_citations WHERE card_id=? ORDER BY position,id", (card_id,)).fetchall()]

def _refresh_card_citations(connection: sqlite3.Connection, card_id: str) -> list[str]:
    statuses: list[str] = []
    for citation in connection.execute("SELECT * FROM card_citations WHERE card_id=?", (card_id,)).fetchall():
        status = "source_unavailable"
        if citation["material_id"] is not None:
            material = connection.execute("SELECT deleted_at FROM materials WHERE id=?", (citation["material_id"],)).fetchone()
            if material is not None and material["deleted_at"] is not None:
                status = "source_deleted"
            elif material is not None and citation["chunk_id"] is not None:
                chunk = connection.execute(
                    "SELECT c.status,c.revision_id,c.extraction_id,r.is_current FROM chunks c JOIN material_revisions r ON r.id=c.revision_id WHERE c.id=? AND c.material_id=?",
                    (citation["chunk_id"], citation["material_id"]),
                ).fetchone()
                if chunk is not None and chunk["status"] == "ready" and chunk["is_current"]:
                    status = "valid" if chunk["revision_id"] == citation["revision_id"] and chunk["extraction_id"] == citation["extraction_id"] else "stale"
                elif chunk is not None:
                    status = "stale"
        connection.execute("UPDATE card_citations SET status=? WHERE id=?", (status, citation["id"]))
        statuses.append(status)
    return statuses

def _refresh_card_citations_for_material(connection: sqlite3.Connection, material_id: str) -> None:
    for row in connection.execute("SELECT DISTINCT card_id FROM card_citations WHERE material_id=?", (material_id,)).fetchall():
        _refresh_card_citations(connection, str(row["card_id"]))

def create_card(connection: sqlite3.Connection, *, project_id: str, deck_id: str, payload: dict[str, object], card_type: str = "user_created", source_revision: str | None = None) -> dict[str, object]:
    if card_type not in {"user_created", "ai_generated"}:
        raise ValueError("invalid_card_payload")
    if connection.execute("SELECT 1 FROM study_decks WHERE id=? AND project_id=? AND status='active'", (deck_id, project_id)).fetchone() is None:
        raise ValueError("deck_not_found")
    front, back, explanation, tags = _validate_card_payload(payload)
    card_id = f"card_{uuid.uuid4().hex}"
    now = utc_now()
    citations = _citation_rows(connection, payload.get("citations", []), code="invalid_card_payload", artifact_id=card_id, table="card")
    with connection:
        connection.execute("INSERT INTO study_cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (card_id, deck_id, project_id, card_type, "draft", front, back, explanation, json.dumps(tags, ensure_ascii=False), source_revision, 0, None, now, now, None, None))
        connection.executemany("INSERT INTO card_citations VALUES (?,?,?,?,?,?,?,?,?,?,?)", citations)
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=deck_id) if item["id"] == card_id)

def update_card(connection: sqlite3.Connection, *, project_id: str, card_id: str, payload: dict[str, object]) -> dict[str, object]:
    row = connection.execute("SELECT * FROM study_cards WHERE id=? AND project_id=?", (card_id, project_id)).fetchone()
    if row is None: raise ValueError("card_not_found")
    if row["status"] in {"ready", "archived"}: raise ValueError("card_edit_not_allowed")
    front, back, explanation, tags = _validate_card_payload(payload)
    with connection:
        connection.execute("UPDATE study_cards SET front=?,back=?,explanation=?,tags_json=?,edited_by_user=1,updated_at=? WHERE id=? AND status='draft'", (front, back, explanation, json.dumps(tags, ensure_ascii=False), utc_now(), card_id))
    return next(item for item in list_cards(connection, project_id=project_id, deck_id=row["deck_id"]) if item["id"] == card_id)

