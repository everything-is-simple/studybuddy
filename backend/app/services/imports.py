from __future__ import annotations

import mimetypes
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..adapters.file_parsers import ParseOptions, parse_file
from ..import_locks import acquire_hash_lock, release_hash_lock
from ..repository import connect, save_material_with_extraction
from ..storage import sha256_file, store_original

def _valid_filename(raw_name: str) -> str | None:
    original_name = Path(raw_name).name
    if (not raw_name or not original_name or original_name in {".", ".."}
            or raw_name != original_name or "/" in raw_name or "\\" in raw_name):
        return None
    return original_name

def _item(original_name: str, status: str, *, material_id: str | None = None,
          extraction_id: str | None = None, source_sha256: str = "", text_length: int = 0,
          span_count: int = 0, error_code: str | None = None,
          warnings: list[str] | None = None) -> dict[str, object]:
    return {"original_name": original_name, "status": status, "material_id": material_id,
            "extraction_id": extraction_id, "source_sha256": source_sha256,
            "text_length": text_length, "span_count": span_count,
            "error_code": error_code, "warnings": warnings or []}

async def _process_file(file: UploadFile, config: AppConfig, *, batch: bool) -> dict[str, object]:
    raw_name = file.filename or ""
    original_name = _valid_filename(raw_name)
    if original_name is None:
        await file.close()
        if not batch:
            raise HTTPException(status_code=400, detail="invalid_filename")
        return _item(raw_name, "rejected", error_code="invalid_filename")
    temporary_path: Path | None = None
    stored_path: Path | None = None
    stored_created = False
    stage = "temp_write"
    try:
        config.data_root.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_name).suffix.lower()
        with tempfile.NamedTemporaryFile(dir=config.data_root, prefix=".incoming-", suffix=suffix, delete=False) as handle:
            temporary_path = Path(handle.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > config.max_upload_bytes:
                    if not batch:
                        raise HTTPException(status_code=413, detail="file_too_large")
                    return _item(original_name, "rejected", error_code="file_too_large")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        digest = sha256_file(temporary_path)
        lock = acquire_hash_lock(digest)
        try:
            stage = "original_store"
            stored = store_original(temporary_path, original_name, digest, config.originals_root)
            stored_path, stored_created = stored.path, stored.created
            stage = "parse"
            result = parse_file(temporary_path, declared_media_type=file.content_type,
                                options=ParseOptions(max_bytes=config.max_upload_bytes))
            try:
                with connect(config.database_path) as connection:
                    material_id, extraction_id = save_material_with_extraction(
                        connection, config.project_id, original_name, digest, stored.path,
                        file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream", result,
                    )
            except Exception as exc:
                if stored.created:
                    try:
                        stored.path.unlink(missing_ok=True)
                    except OSError:
                        pass
                if not batch:
                    raise HTTPException(status_code=500, detail="material_persist_failed") from exc
                return _item(original_name, "failed", source_sha256=digest, error_code="material_persist_failed")
            return _item(original_name, result.status, material_id=material_id, extraction_id=extraction_id,
                         source_sha256=result.source_sha256, text_length=len(result.text),
                         span_count=len(result.spans), error_code=result.error_code, warnings=result.warnings)
        finally:
            release_hash_lock(digest, lock)
    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        if stored_created and stored_path is not None:
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                pass
        if not batch:
            raise HTTPException(status_code=500, detail="material_upload_failed") from exc
        error_code = {"temp_write": "material_upload_failed", "original_store": "original_store_failed"}.get(stage, "file_processing_failed")
        return _item(original_name, "failed", error_code=error_code)
    finally:
        await file.close()
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
