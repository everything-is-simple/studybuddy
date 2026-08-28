from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
from ._legacy_part_05 import *
from ._legacy_part_06 import *
def complete_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                     operation_id: str, segments: object,
                                     language: object | None = None) -> dict[str, object]:
    values, full_text, quality_status = _phase9d_segment_values(segments)
    language_value = None if language is None else _phase9d_text(
        language, code="transcript_empty_or_invalid", maximum=32
    )
    with connection:
        operation = connection.execute(
            "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
            (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()
        if operation is None:
            raise ValueError("transcription_not_ready")
        if operation["status"] == "succeeded" and operation["output_artifact_id"] is not None:
            existing = connection.execute(
                "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                (operation["output_artifact_id"], project_id),
            ).fetchone()
            if existing is None:
                raise ValueError("transcription_failed")
            return {"draft": _phase9d_transcript_public(connection, existing),
                    "operation": _phase9d_operation_public(operation, replay=True), "replay": True}
        if operation["status"] != "running":
            raise ValueError("transcription_not_ready")
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?",
            (operation["capture_session_id"], project_id),
        ).fetchone()
        if capture is None or capture["status"] != "transcribing":
            raise ValueError("capture_invalid_state")
        if _phase9d_capture_source_status(connection, capture) != "valid":
            raise ValueError("capture_source_unavailable")
        draft_id, now = f"transcript_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO transcript_drafts (id,project_id,capture_session_id,operation_id,status,text,language,"
            "quality_status,edited_by_user,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (draft_id, project_id, capture["id"], operation_id, "draft", full_text,
             language_value, quality_status, now, now),
        )
        connection.executemany(
            "INSERT INTO transcript_segments (id,draft_id,project_id,ordinal,text,confidence,quality,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"transcript_segment_{uuid.uuid4().hex}", draft_id, project_id, ordinal,
              text, confidence, quality, now, now)
             for ordinal, (text, confidence, quality) in enumerate(values)],
        )
        connection.execute(
            "UPDATE ai_operations SET status='succeeded',output_artifact_id=?,finished_at=? "
            "WHERE id=? AND status='running'", (draft_id, now, operation_id)
        )
        connection.execute(
            "UPDATE capture_sessions SET status='review_required',updated_at=? "
            "WHERE id=? AND project_id=? AND status='transcribing'",
            (now, capture["id"], project_id),
        )
        draft = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
        finished = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return {"draft": _phase9d_transcript_public(connection, draft),
                "operation": _phase9d_operation_public(finished), "replay": False}

def edit_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                          capture_session_id: str, draft_id: str, text: object) -> dict[str, object]:
    """Apply an explicit user edit; provider output can never mutate this path."""
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("transcript_user_edit_protected")
        edited_text = _phase9d_text(text, code="transcript_empty_or_invalid", maximum=PHASE9D_TRANSCRIPT_MAX_TEXT)
        now = utc_now()
        edited_segments = [line.strip() for line in edited_text.splitlines() if line.strip()]
        if not edited_segments:
            edited_segments = [edited_text]
        existing_segments = connection.execute(
            "SELECT ordinal,confidence,quality FROM transcript_segments WHERE draft_id=? ORDER BY ordinal,id",
            (draft_id,),
        ).fetchall()
        connection.execute("DELETE FROM transcript_segments WHERE draft_id=?", (draft_id,))
        connection.executemany(
            "INSERT INTO transcript_segments (id,draft_id,project_id,ordinal,text,confidence,quality,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(f"transcript_segment_{uuid.uuid4().hex}", draft_id, project_id, ordinal,
              segment_text,
              float(existing_segments[ordinal]["confidence"]) if ordinal < len(existing_segments) else 1.0,
              str(existing_segments[ordinal]["quality"]) if ordinal < len(existing_segments) else "clear",
              now, now)
             for ordinal, segment_text in enumerate(edited_segments)],
        )
        connection.execute(
            "UPDATE transcript_drafts SET text=?,quality_status=?,edited_by_user=1,updated_at=? WHERE id=?",
            (edited_text, "uncertain" if any(
                str(existing_segments[index]["quality"]) == "uncertain"
                for index in range(min(len(existing_segments), len(edited_segments)))
            ) else "clear", now, draft_id),
        )
        updated = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
    return _phase9d_transcript_public(connection, updated)

def _phase9d_confirmed_revision_public(connection: sqlite3.Connection, *, project_id: str,
                                       material_id: str, revision_id: str) -> dict[str, object]:
    chunks = connection.execute(
        "SELECT id,revision_id,extraction_id,chunk_index,start_offset,end_offset,text,status "
        "FROM chunks WHERE project_id=? AND material_id=? AND revision_id=? ORDER BY chunk_index,id",
        (project_id, material_id, revision_id),
    ).fetchall()
    citations = []
    for chunk in chunks:
        key = _citation_key(material_id, str(chunk["id"]))
        validation = validate_citation_key(connection, key)
        citation_valid = bool(
            validation and validation.get("status") == "valid"
            and validation.get("material_id") == material_id
            and validation.get("chunk_id") == chunk["id"]
            and validation.get("revision_id") == revision_id
        )
        citations.append({
            "citation_key": key,
            "material_id": material_id,
            "revision_id": revision_id,
            "extraction_id": chunk["extraction_id"],
            "chunk_id": chunk["id"],
            "span_ids": [str(value[0]) for value in connection.execute(
                "SELECT span_id FROM chunk_spans WHERE chunk_id=? ORDER BY span_id", (chunk["id"],)
            ).fetchall()],
            "status": "valid" if citation_valid else "source_unavailable",
        })
    if not chunks or any(item["status"] != "valid" for item in citations):
        raise ValueError("transcript_citation_invalid")
    return {"id": revision_id, "material_id": material_id, "extraction_id": chunks[0]["extraction_id"] if chunks else None,
            "chunks": [dict(chunk) for chunk in chunks], "citations": citations}

def confirm_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                             capture_session_id: str, draft_id: str) -> dict[str, object]:
    """Confirm one reviewed draft into the capture material's next S2 revision."""
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] == "confirmed" and draft["status"] == "confirmed":
            revision = connection.execute(
                "SELECT id FROM material_revisions WHERE material_id=? AND parser_id=? AND is_current=1 "
                "ORDER BY created_at DESC,id DESC LIMIT 1", (capture["material_id"], PHASE9D_TRANSCRIPT_PARSER_ID)
            ).fetchone()
            if revision is None:
                raise ValueError("transcript_citation_invalid")
            return {"capture": _phase9d_capture_public(connection, capture), "draft": _phase9d_transcript_public(connection, draft),
                    "revision": _phase9d_confirmed_revision_public(connection, project_id=project_id,
                                                                    material_id=str(capture["material_id"]), revision_id=str(revision["id"])),
                    "replay": True}
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("capture_invalid_state")
        if capture["material_id"] is None or _phase9d_capture_source_status(connection, capture) != "valid":
            raise ValueError("capture_source_unavailable")
        text = _phase9d_text(draft["text"], code="transcript_empty_or_invalid", maximum=PHASE9D_TRANSCRIPT_MAX_TEXT)
        segments = connection.execute(
            "SELECT ordinal,text FROM transcript_segments WHERE draft_id=? ORDER BY ordinal,id", (draft_id,)
        ).fetchall()
        if not segments:
            raise ValueError("transcript_empty_or_invalid")
        now = utc_now()
        extraction_id = f"extraction_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
            "VALUES (?,?,?,?,?,?,?,?,NULL)",
            (extraction_id, capture["material_id"], PHASE9D_TRANSCRIPT_PARSER_ID,
             PHASE9D_TRANSCRIPT_PARSER_VERSION, "success", text, "[]", now),
        )
        connection.executemany(
            "INSERT INTO text_spans (id,extraction_id,ordinal,span_kind,label,text) VALUES (?,?,?,?,?,?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, int(segment["ordinal"]) + 1, "document",
              f"transcript-segment-{int(segment['ordinal']) + 1}", str(segment["text"])) for segment in segments],
        )
        revision = _index_material_revision_in_transaction(
            connection, str(capture["material_id"]), extraction_id,
        )
        revision_id = str(revision["id"])
        connection.execute(
            "UPDATE transcript_drafts SET status='confirmed',updated_at=? WHERE id=? AND status='draft'",
            (now, draft_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='confirmed',confirmed_at=?,updated_at=? "
            "WHERE id=? AND project_id=? AND status='review_required'",
            (now, now, capture_session_id, project_id),
        )
        connection.execute(
            "UPDATE ai_operations SET source_revision=? WHERE id=? AND project_id=?",
            (revision_id, draft["operation_id"], project_id),
        )
        updated_capture = connection.execute("SELECT * FROM capture_sessions WHERE id=?", (capture_session_id,)).fetchone()
        updated_draft = connection.execute("SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)).fetchone()
        _replace_search_row(connection, str(capture["material_id"]))
        revision_public = _phase9d_confirmed_revision_public(
            connection, project_id=project_id, material_id=str(capture["material_id"]), revision_id=revision_id,
        )
        return {"capture": _phase9d_capture_public(connection, updated_capture),
                "draft": _phase9d_transcript_public(connection, updated_draft),
                "revision": revision_public, "replay": False}

def reject_transcript_draft(connection: sqlite3.Connection, *, project_id: str,
                            capture_session_id: str, draft_id: str) -> dict[str, object]:
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        draft = connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=? AND capture_session_id=? AND project_id=?",
            (draft_id, capture_session_id, project_id),
        ).fetchone()
        if draft is None:
            raise ValueError("transcript_not_found")
        if capture["status"] != "review_required" or draft["status"] != "draft":
            raise ValueError("capture_invalid_state")
        now = utc_now()
        connection.execute("UPDATE transcript_drafts SET status='rejected',updated_at=? WHERE id=?", (now, draft_id))
        connection.execute(
            "UPDATE capture_sessions SET status='rejected',rejected_at=?,updated_at=? WHERE id=? AND project_id=?",
            (now, now, capture_session_id, project_id),
        )
        return {"capture": _phase9d_capture_public(connection, connection.execute(
            "SELECT * FROM capture_sessions WHERE id=?", (capture_session_id,)
        ).fetchone()), "draft": _phase9d_transcript_public(connection, connection.execute(
            "SELECT * FROM transcript_drafts WHERE id=?", (draft_id,)
        ).fetchone())}

def fail_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                 operation_id: str, error_code: object = "transcription_failed") -> dict[str, object]:
    error = _phase9d_text(error_code, code="transcription_failed", maximum=100)
    if error not in PHASE9D_TRANSCRIPTION_ERROR_CODES:
        raise ValueError("transcription_failed")
    with connection:
        operation = connection.execute(
            "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
            (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()
        if operation is None:
            raise ValueError("transcription_not_ready")
        if operation["status"] == "failed":
            return _phase9d_operation_public(operation, replay=True)
        if operation["status"] != "running":
            raise ValueError("transcription_not_ready")
        now = utc_now()
        connection.execute(
            "UPDATE ai_operations SET status='failed',error_code=?,finished_at=? WHERE id=? AND status='running'",
            (error, now, operation_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='failed',updated_at=? "
            "WHERE id=? AND project_id=? AND status='transcribing'",
            (now, operation["capture_session_id"], project_id),
        )
        result = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return _phase9d_operation_public(result)

def _phase9d_report_period(report_kind: object, timezone_name: object,
                           period_start: object, period_end: object) -> tuple[str, str, str, ZoneInfo, datetime, datetime]:
    if report_kind not in PHASE9D_REPORT_KINDS:
        raise ValueError("report_invalid_kind")
    timezone_value = _phase9d_text(timezone_name, code="report_invalid_period", maximum=100)
    try:
        zone = ZoneInfo(timezone_value)
        start_date = date.fromisoformat(_phase9d_text(period_start, code="report_invalid_period", maximum=10))
        end_date = date.fromisoformat(_phase9d_text(period_end, code="report_invalid_period", maximum=10))
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("report_invalid_period") from None
    if start_date.isoformat() != period_start or end_date.isoformat() != period_end or start_date >= end_date:
        raise ValueError("report_invalid_period")
    start_utc = datetime.combine(start_date, datetime.min.time(), zone).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, datetime.min.time(), zone).astimezone(timezone.utc)
    return str(report_kind), timezone_value, start_date.isoformat(), zone, start_utc, end_utc

def _phase9d_in_period(value: object, start_utc: datetime, end_utc: datetime) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    normalized = parsed.astimezone(timezone.utc)
    return start_utc <= normalized < end_utc

def _phase9d_rows_in_period(rows: list[sqlite3.Row], field: str,
                            start_utc: datetime, end_utc: datetime) -> list[sqlite3.Row]:
    return [row for row in rows if _phase9d_in_period(row[field], start_utc, end_utc)]

def _phase9d_validate_safe_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != set(PHASE9D_REPORT_PAYLOAD_FIELDS):
        raise ValueError("report_redaction_violation")
    numeric_fields = {
        field for section, fields in PHASE9D_REPORT_PAYLOAD_FIELDS.items()
        if section not in {"period", "quality_flags", "exam_alert"}
        for field in fields
    }
    boolean_fields = set(PHASE9D_REPORT_PAYLOAD_FIELDS["quality_flags"]) | {"is_imminent"}
    for section, allowed in PHASE9D_REPORT_PAYLOAD_FIELDS.items():
        value = payload.get(section)
        if not isinstance(value, dict) or set(value) != allowed:
            raise ValueError("report_redaction_violation")
        for field, item in value.items():
            if field == "days_remaining_bucket":
                if item is not None and item not in {"0-3", "4-7", "8-14", "15+"}:
                    raise ValueError("report_redaction_violation")
            elif field == "generated_at":
                if not isinstance(item, str) or not item:
                    raise ValueError("report_redaction_violation")
                try:
                    generated = datetime.fromisoformat(item.replace("Z", "+00:00"))
                except ValueError:
                    raise ValueError("report_redaction_violation") from None
                if generated.tzinfo is None:
                    raise ValueError("report_redaction_violation")
            elif field in {"report_kind", "period_start", "period_end", "timezone"}:
                if not isinstance(item, str) or not item:
                    raise ValueError("report_redaction_violation")
            elif field in boolean_fields:
                if not isinstance(item, bool):
                    raise ValueError("report_redaction_violation")
            elif field in numeric_fields:
                if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                    raise ValueError("report_redaction_violation")
            else:
                raise ValueError("report_redaction_violation")
    period = payload["period"]
    if not isinstance(period.get("report_kind"), str) or period["report_kind"] not in PHASE9D_REPORT_KINDS:
        raise ValueError("report_redaction_violation")
    try:
        ZoneInfo(str(period["timezone"]))
        start_date = date.fromisoformat(str(period["period_start"]))
        end_date = date.fromisoformat(str(period["period_end"]))
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("report_redaction_violation") from None
    if (start_date.isoformat() != period["period_start"] or
            end_date.isoformat() != period["period_end"] or start_date >= end_date):
        raise ValueError("report_redaction_violation")
    return payload

def _phase9d_safe_markdown(payload: dict[str, object]) -> str:
    _phase9d_validate_safe_payload(payload)
    sections = ["# Study Report", "", f"Kind: {payload['period']['report_kind']}",
                f"Period: {payload['period']['period_start']} to {payload['period']['period_end']}",
                f"Timezone: {payload['period']['timezone']}"]
    for key in ("plan", "rhythm", "practice", "feedback", "source_quality", "quality_flags"):
        sections.extend(["", f"## {key.replace('_', ' ').title()}"])
        for field, value in payload[key].items():
            sections.append(f"- {field}: {str(value).lower() if isinstance(value, bool) else value}")
    if payload["period"]["report_kind"] == "exam_alert":
        sections.extend(["", "## Exam Alert"])
        for field, value in payload["exam_alert"].items():
            sections.append(f"- {field}: {str(value).lower() if isinstance(value, bool) else value}")
    return "\n".join(sections) + "\n"

