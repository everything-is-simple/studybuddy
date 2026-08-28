from ._legacy_runtime import *
from ._legacy_part_00 import *
from ._legacy_part_01 import *
from ._legacy_part_02 import *
from ._legacy_part_03 import *
from ._legacy_part_04 import *
from ._legacy_part_05 import *
def upload_capture_asset(connection: sqlite3.Connection, *, project_id: str,
                         capture_session_id: str, source_path: Path,
                         original_name: object, media_type: object,
                         originals_root: Path, max_upload_bytes: int) -> dict[str, object]:
    """Bind one sensitive original to a draft session without exposing its path."""
    name = _phase9d_text(original_name, code="capture_upload_failed", maximum=255)
    media = _phase9d_text(media_type, code="capture_asset_type_not_supported", maximum=100)
    source = Path(source_path)
    if (Path(name).name != name or "/" in name or "\\" in name or
            media not in PHASE9D_CAPTURE_SUFFIXES or Path(name).suffix.lower() not in PHASE9D_CAPTURE_SUFFIXES[media]):
        raise ValueError("capture_asset_type_not_supported")
    if not isinstance(max_upload_bytes, int) or isinstance(max_upload_bytes, bool) or max_upload_bytes < 1:
        raise ValueError("capture_upload_failed")
    try:
        mode = source.lstat().st_mode
        size = source.stat().st_size
    except OSError:
        raise ValueError("capture_upload_failed") from None
    if not stat.S_ISREG(mode) or source.is_symlink():
        raise ValueError("capture_upload_failed")
    if size > max_upload_bytes:
        raise ValueError("capture_asset_too_large")
    if size < 1:
        raise ValueError("capture_upload_failed")
    try:
        with source.open("rb") as handle:
            header = handle.read(32)
    except OSError:
        raise ValueError("capture_upload_failed") from None
    if not _phase9d_asset_signature_valid(media, header):
        raise ValueError("capture_asset_type_not_supported")
    digest = sha256_file(source)
    lock = acquire_hash_lock(digest)
    stored = None
    try:
        stored = store_original(source, name, digest, originals_root)
        material_id = f"material_{uuid.uuid4().hex}"
        extraction_id = f"extraction_{uuid.uuid4().hex}"
        with connection:
            capture = connection.execute(
                "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
            ).fetchone()
            if capture is None:
                raise ValueError("capture_not_found")
            if capture["status"] != "draft" or capture["material_id"] is not None:
                raise ValueError("capture_invalid_state")
            if media not in PHASE9D_CAPTURE_ASSET_TYPES[str(capture["asset_kind"])] or media != capture["media_type"]:
                raise ValueError("capture_asset_type_not_supported")
            if name != capture["original_name"]:
                raise ValueError("capture_invalid_state")
            now = utc_now()
            connection.execute(
                "INSERT INTO materials (id,project_id,original_name,source_sha256,stored_path,media_type,created_at,updated_at,deleted_at) "
                "VALUES (?,?,?,?,?,?,?,?,NULL)",
                (material_id, project_id, name, digest, str(stored.path), media, now, now),
            )
            connection.execute(
                "INSERT INTO extractions (id,material_id,parser_id,parser_version,status,text,warnings_json,created_at,error_code) "
                "VALUES (?,?,?,?,?,'','[]',?,NULL)",
                (extraction_id, material_id, PHASE9D_CAPTURE_PARSER_ID, PHASE9D_CAPTURE_PARSER_VERSION, "empty", now),
            )
            _insert_search_row(connection, material_id, name, "")
            updated = connection.execute(
                "UPDATE capture_sessions SET status='uploaded',material_id=?,source_status='valid',updated_at=? "
                "WHERE id=? AND project_id=? AND status='draft' AND material_id IS NULL",
                (material_id, now, capture_session_id, project_id),
            )
            if updated.rowcount != 1:
                raise ValueError("capture_invalid_state")
    except ValueError:
        if stored is not None and stored.created:
            try:
                stored.path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    except (OSError, sqlite3.Error):
        if stored is not None and stored.created:
            try:
                stored.path.unlink(missing_ok=True)
            except OSError:
                pass
        raise ValueError("capture_upload_failed") from None
    finally:
        release_hash_lock(digest, lock)
    return get_capture_session(connection, project_id=project_id, capture_session_id=capture_session_id) or {}

def get_capture_session(connection: sqlite3.Connection, *, project_id: str,
                        capture_session_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
    ).fetchone()
    return _phase9d_capture_public(connection, row) if row is not None else None

def list_capture_sessions(connection: sqlite3.Connection, *, project_id: str,
                          include_archived: bool = False) -> list[dict[str, object]]:
    clause = "" if include_archived else " AND status!='archived'"
    rows = connection.execute(
        "SELECT * FROM capture_sessions WHERE project_id=?" + clause + " ORDER BY updated_at DESC,id DESC",
        (project_id,),
    ).fetchall()
    return [_phase9d_capture_public(connection, row) for row in rows]

def _phase9d_transcription_fingerprint(*, capture_session_id: str, material_id: str,
                                       input_fingerprint: str) -> str:
    return hashlib.sha256(
        f"{PHASE9D_TRANSCRIPTION_OPERATION}\x1f{capture_session_id}\x1f{material_id}\x1f{input_fingerprint}".encode("utf-8")
    ).hexdigest()

def create_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                   capture_session_id: str, input_fingerprint: object,
                                   idempotency_key: object | None = None,
                                   provider_id: object = "fake", model_id: object = "fake-capture-v1") -> dict[str, object]:
    source_fingerprint = _phase9d_text(input_fingerprint, code="transcription_not_ready", maximum=64)
    if len(source_fingerprint) != 64 or any(char not in "0123456789abcdef" for char in source_fingerprint.lower()):
        raise ValueError("transcription_not_ready")
    key = _phase9d_idempotency_key(idempotency_key)
    provider = _phase9d_text(provider_id, code="transcription_provider_not_configured", maximum=100)
    model = _phase9d_text(model_id, code="transcription_provider_not_configured", maximum=200)
    if provider not in {"fake", "loopback"}:
        raise ValueError("transcription_provider_not_configured")
    with connection:
        capture = connection.execute(
            "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
        ).fetchone()
        if capture is None:
            raise ValueError("capture_not_found")
        if capture["material_id"] is None:
            raise ValueError("capture_source_unavailable")
        fingerprint = _phase9d_transcription_fingerprint(
            capture_session_id=capture_session_id, material_id=str(capture["material_id"]),
            input_fingerprint=source_fingerprint.lower(),
        )
        if key is not None:
            existing = connection.execute(
                "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, key)
            ).fetchone()
            if existing is not None:
                if (existing["operation_type"] != PHASE9D_TRANSCRIPTION_OPERATION or
                        existing["capture_session_id"] != capture_session_id or
                        existing["input_fingerprint"] != fingerprint):
                    raise ValueError("transcription_idempotency_mismatch")
                if existing["status"] not in {"failed", "cancelled", "stale"}:
                    return _phase9d_operation_public(existing, replay=True)
                connection.execute(
                    "UPDATE ai_operations SET idempotency_key=NULL WHERE id=? AND status IN ('failed','cancelled','stale')",
                    (existing["id"],),
                )
        if capture["status"] not in {"uploaded", "failed", "rejected"}:
            raise ValueError("capture_invalid_state")
        source_status = _phase9d_capture_source_status(connection, capture)
        if source_status != "valid":
            raise ValueError("capture_source_unavailable")
        retry_count = int(connection.execute(
            "SELECT COUNT(*) FROM ai_operations WHERE project_id=? AND capture_session_id=? AND operation_type=?",
            (project_id, capture_session_id, PHASE9D_TRANSCRIPTION_OPERATION),
        ).fetchone()[0])
        current_revision = connection.execute(
            "SELECT id FROM material_revisions WHERE material_id=? AND is_current=1 ORDER BY created_at DESC LIMIT 1",
            (capture["material_id"],),
        ).fetchone()
        operation_id, now = f"transcription_{uuid.uuid4().hex}", utc_now()
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,material_id,input_fingerprint,source_revision,"
            "provider_id,model_id,retry_count,created_at,started_at,idempotency_key,capture_session_id) "
            "VALUES (?,?, 'running',?,?,?,?,?,?,?, ?,?,?,?)",
            (operation_id, PHASE9D_TRANSCRIPTION_OPERATION, project_id, capture["material_id"], fingerprint,
             current_revision["id"] if current_revision is not None else None, provider, model,
             retry_count, now, now, key, capture_session_id),
        )
        connection.execute(
            "UPDATE capture_sessions SET status='transcribing',source_status='valid',updated_at=? "
            "WHERE id=? AND project_id=?", (now, capture_session_id, project_id)
        )
        operation = connection.execute("SELECT * FROM ai_operations WHERE id=?", (operation_id,)).fetchone()
        return _phase9d_operation_public(operation)

def _phase9d_original_bytes(connection: sqlite3.Connection, *, project_id: str,
                             material_id: str, max_bytes: int) -> tuple[bytes, str, str]:
    material = connection.execute(
        "SELECT project_id,stored_path,source_sha256,media_type,deleted_at FROM materials WHERE id=?",
        (material_id,),
    ).fetchone()
    if material is None or material["project_id"] != project_id:
        raise ValueError("capture_source_unavailable")
    if material["deleted_at"] is not None:
        raise ValueError("capture_source_unavailable")
    path = Path(str(material["stored_path"]))
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("capture_source_unavailable")
    try:
        mode = path.lstat().st_mode
        size = path.stat().st_size
        if not stat.S_ISREG(mode) or size < 1 or size > max_bytes:
            raise ValueError("capture_source_unavailable")
        content = path.read_bytes()
    except (OSError, ValueError):
        raise ValueError("capture_source_unavailable") from None
    digest = hashlib.sha256(content).hexdigest()
    if digest != str(material["source_sha256"]):
        raise ValueError("capture_source_unavailable")
    return content, digest, str(material["media_type"])

def transcribe_capture_session(connection: sqlite3.Connection, *, project_id: str,
                               capture_session_id: str, provider: CaptureTranscriptionProvider,
                               idempotency_key: object | None = None,
                               max_upload_bytes: int = 50 * 1024 * 1024,
                               timeout_seconds: float = 30.0) -> dict[str, object]:
    """Run one fake/loopback transcription; raw bytes/results remain in memory only."""
    provider_id = getattr(provider, "provider_id", None)
    model_id = getattr(provider, "model_id", None)
    if provider_id not in {"fake", "loopback"} or not isinstance(model_id, str) or not model_id:
        raise ValueError("transcription_provider_not_configured")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        raise ValueError("transcription_failed")
    key = _phase9d_idempotency_key(idempotency_key)
    capture = connection.execute(
        "SELECT * FROM capture_sessions WHERE id=? AND project_id=?", (capture_session_id, project_id)
    ).fetchone()
    if capture is None:
        raise ValueError("capture_not_found")
    if key is not None:
        existing = connection.execute(
            "SELECT * FROM ai_operations WHERE project_id=? AND idempotency_key=?", (project_id, key)
        ).fetchone()
        if existing is not None:
            if (existing["operation_type"] != PHASE9D_TRANSCRIPTION_OPERATION or
                    existing["capture_session_id"] != capture_session_id or
                    existing["provider_id"] != provider_id or existing["model_id"] != model_id):
                raise ValueError("transcription_idempotency_mismatch")
            if existing["status"] not in {"failed", "cancelled", "stale"}:
                operation = _phase9d_operation_public(existing, replay=True)
                if existing["status"] == "succeeded" and existing["output_artifact_id"]:
                    draft = connection.execute(
                        "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                        (existing["output_artifact_id"], project_id),
                    ).fetchone()
                    if draft is not None:
                        return {"operation": operation, "draft": _phase9d_transcript_public(connection, draft), "replay": True}
                return {"operation": operation, "replay": True}
    if capture["material_id"] is None:
        raise ValueError("transcription_not_ready")
    content, digest, media_type = _phase9d_original_bytes(
        connection, project_id=project_id, material_id=str(capture["material_id"]), max_bytes=max_upload_bytes,
    )
    if capture["status"] not in {"uploaded", "failed", "rejected"}:
        raise ValueError("transcription_not_ready")
    operation = create_transcription_operation(
        connection, project_id=project_id, capture_session_id=capture_session_id,
        input_fingerprint=digest, idempotency_key=idempotency_key,
        provider_id=provider_id, model_id=model_id,
    )
    if operation.get("replay"):
        if operation["status"] == "succeeded" and operation.get("output_artifact_id"):
            draft = connection.execute(
                "SELECT * FROM transcript_drafts WHERE id=? AND project_id=?",
                (operation["output_artifact_id"], project_id),
            ).fetchone()
            if draft is not None:
                return {"operation": operation, "draft": _phase9d_transcript_public(connection, draft), "replay": True}
        return {"operation": operation, "replay": True}
    started = time.perf_counter()
    try:
        result = provider.transcribe(CaptureTranscriptionRequest(
            asset_kind=str(capture["asset_kind"]), media_type=media_type,
            content_sha256=digest, content=content,
        ))
        if time.perf_counter() - started > float(timeout_seconds):
            raise CaptureProviderError("provider_timeout")
        if not isinstance(result.segments, list):
            raise CaptureProviderError("transcription_failed")
        completed = complete_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]),
            segments=result.segments, language=result.language,
        )
        return {**completed, "replay": False}
    except CaptureProviderError as error:
        code = error.code if error.code in PHASE9D_TRANSCRIPTION_ERROR_CODES else "transcription_failed"
        failed = fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code=code,
        )
        raise ValueError(code) from None
    except ValueError as error:
        code = str(error) if str(error) in {"transcript_empty_or_invalid", "payload_too_large", "capture_source_unavailable"} else "transcription_failed"
        fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code=code,
        )
        raise ValueError(code) from None
    except Exception:
        fail_transcription_operation(
            connection, project_id=project_id, operation_id=str(operation["id"]), error_code="transcription_failed",
        )
        raise ValueError("transcription_failed") from None

def get_transcription_operation(connection: sqlite3.Connection, *, project_id: str,
                                operation_id: str) -> dict[str, object] | None:
    row = connection.execute(
        "SELECT * FROM ai_operations WHERE id=? AND project_id=? AND operation_type=?",
        (operation_id, project_id, PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchone()
    return _phase9d_operation_public(row) if row is not None else None

def list_transcription_operations(connection: sqlite3.Connection, *, project_id: str,
                                  capture_session_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT * FROM ai_operations WHERE project_id=? AND capture_session_id=? AND operation_type=? "
        "ORDER BY created_at,id", (project_id, capture_session_id, PHASE9D_TRANSCRIPTION_OPERATION),
    ).fetchall()
    return [_phase9d_operation_public(row) for row in rows]

def _phase9d_segment_values(segments: object) -> tuple[list[tuple[str, float, str]], str, str]:
    if not isinstance(segments, list) or not 1 <= len(segments) <= PHASE9D_TRANSCRIPT_MAX_SEGMENTS:
        raise ValueError("transcript_empty_or_invalid")
    values: list[tuple[str, float, str]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("transcript_empty_or_invalid")
        text = _phase9d_text(segment.get("text"), code="transcript_empty_or_invalid", maximum=20000)
        confidence = segment.get("confidence")
        if (not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or
                not 0.0 <= float(confidence) <= 1.0):
            raise ValueError("transcript_empty_or_invalid")
        quality = "clear" if float(confidence) >= PHASE9D_TRANSCRIPT_CONFIDENCE_THRESHOLD else "uncertain"
        values.append((text, float(confidence), quality))
    full_text = "\n".join(value[0] for value in values)
    if len(full_text) > PHASE9D_TRANSCRIPT_MAX_TEXT:
        raise ValueError("payload_too_large")
    quality_status = "uncertain" if any(value[2] == "uncertain" for value in values) else "clear"
    return values, full_text, quality_status

