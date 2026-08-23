from __future__ import annotations

import io
import json
import mimetypes
import sqlite3
import os
import tempfile
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from .adapters.file_parsers import ParseOptions, parse_file
from .config import AppConfig, config_from_environment
from .db_audit import run_audit
from .import_locks import acquire_hash_lock, release_hash_lock
from .migrations.runner import MigrationError
from .observability import (correlation, emit_event, increment, metrics_snapshot, new_id, observe_http,
                            record_import, reset_correlation, route_class, set_correlation,
                            valid_request_id)
from .providers import EmbeddingProviderRegistry, ProviderError, ProviderRequest, provider_registry
from .embedding import EmbeddingError, FakeEmbeddingProvider
from .recovery import reconcile
from .startup_preflight import StartupPreflightError, preflight
from .repository import (VALID_STATUSES, MAX_CONTEXT_TOKENS, connect, assemble_context, create_or_get_revision,
                         create_qa_request, fail_qa_operation, get_material, get_material_index_status,
                         get_idempotent_qa_response, get_qa_citation_detail, get_qa_thread_history, get_spans, index_material_revision, list_qa_threads,
                         list_deleted_materials, list_materials,
                         list_materials_page, list_deleted_materials_page, material_state, persist_qa_answer,
                         purge_material, reclaim_stale_qa_operations, reclaim_stale_embedding_operations,
                         create_embedding_index_operation, finish_embedding_index_operation, rename_material, restore_material, run_chunk_retrieval,
                         run_hybrid_retrieval, run_vector_retrieval, save_material_with_extraction, soft_delete_material,
                         validate_citation_key, qa_request_fingerprint)
from .storage import sha256_file, store_original


def _provider_http_status(code: str) -> int:
    if code in {"provider_timeout"}:
        return 504
    if code in {"provider_rate_limited", "provider_quota_exceeded"}:
        return 429
    if code in {"provider_not_configured", "provider_invalid_config"}:
        return 503
    if code in {"provider_connection_failed", "provider_unavailable"}:
        return 503
    return 502


def _download_name(original_name: str, suffix: str = "") -> str:
    safe_name = Path(original_name).name.replace('"', "'")
    return f"{safe_name}{suffix}"


def _checked_original_path(config: AppConfig, stored_path: str, expected_hash: str) -> Path:
    root = config.originals_root
    target = Path(stored_path)
    if not target.is_absolute():
        raise HTTPException(status_code=500, detail="original_path_invalid")
    try:
        root_stat = root.lstat()
        if not root.is_dir() or root.is_symlink():
            raise HTTPException(status_code=500, detail="original_path_invalid")
        target.relative_to(root)
        current = root
        for part in target.relative_to(root).parts:
            current = current / part
            if current.is_symlink():
                raise HTTPException(status_code=500, detail="original_path_invalid")
            current.lstat()
    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="original_path_invalid") from exc
    try:
        mode = target.lstat().st_mode
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    import stat
    if not stat.S_ISREG(mode):
        raise HTTPException(status_code=500, detail="original_not_found")
    try:
        actual_hash = sha256_file(target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    if actual_hash != expected_hash:
        raise HTTPException(status_code=500, detail="original_hash_mismatch")
    return target


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Do not expose a ready service until persistent storage is usable."""
    config: AppConfig = app.state.config
    app.state.ready = False
    try:
        preflight(config)
        increment("startup", "preflight", "success")
    except StartupPreflightError as error:
        increment("startup", "preflight", "failed")
        emit_event("startup_preflight_failed", level=40, error_code=str(error))
        raise
    try:
        with connect(config.database_path):
            pass
        increment("startup", "database", "success")
    except MigrationError as error:
        increment("startup", "database", "failed")
        emit_event("startup_database_failed", level=40, error_code=error.code)
        raise StartupPreflightError(error.code) from None
    except (OSError, sqlite3.Error, ValueError):
        increment("startup", "database", "failed")
        emit_event("startup_database_failed", level=40, error_code="database_startup_failed")
        raise StartupPreflightError("database_startup_failed") from None
    run_audit(config.database_path)
    increment("startup", "audit", "completed")
    reconcile(config)
    increment("startup", "recovery", "completed")
    app.state.ready = True
    emit_event("startup_ready", component="startup", outcome="ready")
    try:
        yield
    finally:
        app.state.ready = False


def _valid_filename(raw_name: str) -> str | None:
    original_name = Path(raw_name).name
    if (not raw_name or not original_name or original_name in {".", ".."}
            or raw_name != original_name or "/" in raw_name or "\\" in raw_name):
        return None
    return original_name


class RenameMaterialRequest(BaseModel):
    original_name: str


class ExportMaterialsRequest(BaseModel):
    material_ids: list[str]
    include_original: bool = True
    include_text: bool = True


class RetrievalRequest(BaseModel):
    query: str
    material_ids: list[str] | None = None
    top_k: int = 5
    mode: str = "lexical"
    allow_fallback: bool = True


class ContextRequest(BaseModel):
    hit_ids: list[str]
    max_tokens: int = 2000


class CitationValidateRequest(BaseModel):
    key: str


class QaAskRequest(BaseModel):
    question: str
    material_ids: list[str]
    thread_id: str | None = None
    top_k: int = 5
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True


def _rename_name(raw_name: str) -> str | None:
    name = raw_name.strip()
    if len(name) > 255:
        return None
    return _valid_filename(name)


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


def create_app(config: AppConfig | None = None) -> FastAPI:
    app = FastAPI(title="StudyBuddy", lifespan=lifespan)
    app.state.config = config or config_from_environment()
    app.state.ready = False

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID")
        request_id = supplied if valid_request_id(supplied) else new_id("req")
        operation_id = new_id("op")
        tokens = set_correlation(request_id, operation_id)
        started = time.perf_counter()
        route = route_class(request.url.path)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            status_class = f"{status_code // 100}xx"
            increment("http_requests", request.method, route, status_class)
            observe_http(route, duration_ms)
            emit_event("http_request", method=request.method, route=route,
                       status_class=status_class, duration_ms=round(duration_ms, 3))
            if 'response' in locals():
                response.headers["X-Request-ID"] = request_id
            reset_correlation(tokens)

    @app.get("/api/liveness")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/metrics")
    def metrics() -> dict[str, object]:
        return metrics_snapshot()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        if not app.state.ready:
            raise HTTPException(status_code=503, detail="service_not_ready")
        return {"status": "ok"}

    @app.get("/api/ai/capabilities")
    def ai_capabilities() -> dict[str, object]:
        config = app.state.config
        if config.ai_provider_id == "fake":
            llm = provider_registry(config.ai_provider_id, config.ai_model_id).capabilities()
        else:
            llm = provider_registry(
                config.ai_provider_id, config.ai_model_id,
                base_url=config.ai_base_url, api_key=config.ai_api_key,
                timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries,
            ).capabilities()
        embedding_provider_id = config.embedding_provider_id
        embedding_model_id = config.embedding_model_id
        embedding = EmbeddingProviderRegistry(
            embedding_provider_id, embedding_model_id,
            model_revision=config.embedding_model_revision,
            base_url=config.embedding_base_url, api_key=config.embedding_api_key,
            timeout_seconds=config.embedding_timeout_seconds,
            max_batch_size=config.embedding_max_batch_size,
            max_text_chars=config.embedding_max_text_chars,
            max_dimensions=config.embedding_max_dimensions,
            max_response_bytes=config.embedding_max_response_bytes,
            max_retries=config.embedding_max_retries,
        ).capabilities()
        # Preserve the legacy response exactly until embedding is explicitly configured.
        if embedding_provider_id is None:
            return llm
        return {**llm, "llm": llm, "embedding": embedding}

    def pagination_values(limit: str | None, offset: str | None) -> tuple[int, int, bool]:
        paged = limit is not None or offset is not None
        try:
            page_limit = 20 if limit is None else int(limit)
            page_offset = 0 if offset is None else int(offset)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid_pagination") from exc
        if page_limit < 1 or page_limit > 100 or page_offset < 0:
            raise HTTPException(status_code=400, detail="invalid_pagination")
        return page_limit, page_offset, paged

    @app.get("/api/materials")
    def materials(status: str | None = None, q: str | None = None, limit: str | None = None, offset: str | None = None) -> list[dict[str, object]] | dict[str, object]:
        if status is not None and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status")
        page_limit, page_offset, paged = pagination_values(limit, offset)
        with connect(app.state.config.database_path) as connection:
            if paged:
                items, total = list_materials_page(connection, status, q, page_limit, page_offset)
                return {"items": [dict(row) for row in items], "total": total, "limit": page_limit, "offset": page_offset, "has_more": page_offset + len(items) < total}
            return [dict(row) for row in list_materials(connection, status, q)]

    @app.get("/api/materials/deleted")
    def deleted_materials(limit: str | None = None, offset: str | None = None) -> list[dict[str, object]] | dict[str, object]:
        page_limit, page_offset, paged = pagination_values(limit, offset)
        with connect(app.state.config.database_path) as connection:
            if paged:
                items, total = list_deleted_materials_page(connection, page_limit, page_offset)
                return {"items": [dict(row) for row in items], "total": total, "limit": page_limit, "offset": page_offset, "has_more": page_offset + len(items) < total}
            return [dict(row) for row in list_deleted_materials(connection)]

    @app.post("/api/materials/export")
    def export_materials(request: ExportMaterialsRequest):
        if not request.material_ids or len(request.material_ids) > 200:
            raise HTTPException(status_code=400, detail="invalid_export_request")
        if len(set(request.material_ids)) != len(request.material_ids) or not (request.include_original or request.include_text):
            raise HTTPException(status_code=400, detail="invalid_export_request")
        placeholders = ",".join("?" for _ in request.material_ids)
        with connect(app.state.config.database_path) as connection:
            rows = connection.execute(
                f"SELECT m.id, m.original_name, m.stored_path, m.source_sha256, e.text "
                f"FROM materials m JOIN extractions e ON e.material_id = m.id "
                f"WHERE m.id IN ({placeholders}) AND m.deleted_at IS NULL",
                request.material_ids,
            ).fetchall()
        if len(rows) != len(request.material_ids):
            raise HTTPException(status_code=404, detail="material_not_found")
        by_id = {row["id"]: row for row in rows}
        ordered = [by_id[material_id] for material_id in request.material_ids]
        buffer = io.BytesIO()
        used: set[str] = set()
        logical_size = 0
        try:
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for row in ordered:
                    name = Path(row["original_name"]).name
                    stem, suffix = Path(name).stem, Path(name).suffix
                    def unique_entry(prefix: str, filename: str) -> str:
                        candidate = f"{prefix}/{filename}"
                        index = 2
                        while candidate in used:
                            candidate = f"{prefix}/{stem} ({index}){suffix}"
                            index += 1
                        used.add(candidate)
                        return candidate
                    if request.include_original:
                        target = _checked_original_path(app.state.config, row["stored_path"], row["source_sha256"])
                        data = target.read_bytes()
                        logical_size += len(data)
                        if logical_size > 256 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="export_too_large")
                        archive.writestr(unique_entry("originals", name), data)
                    if request.include_text:
                        text_name = f"{name}.extracted.txt"
                        data = str(row["text"]).encode("utf-8")
                        logical_size += len(data)
                        if logical_size > 256 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="export_too_large")
                        archive.writestr(unique_entry("text", text_name), data)
        except HTTPException:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=500, detail="material_export_failed") from exc
        buffer.seek(0)
        return Response(content=buffer.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="studybuddy-materials.zip"'})

    @app.post("/api/retrieval")
    def retrieve(request: RetrievalRequest) -> dict[str, object]:
        if request.material_ids is not None and (not request.material_ids or len(request.material_ids) > 200):
            raise HTTPException(status_code=400, detail="retrieval_invalid_materials")
        try:
            with connect(app.state.config.database_path) as connection:
                if request.mode not in {"lexical", "vector", "hybrid"}:
                    raise HTTPException(status_code=400, detail="retrieval_invalid_mode")
                if request.mode == "vector":
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id or "fake"
                    provider = provider_registry(embedding_provider_id, config.embedding_model_id).embedding_provider(
                        model_revision=config.embedding_model_revision,
                        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                        timeout_seconds=config.embedding_timeout_seconds,
                        max_batch_size=config.embedding_max_batch_size,
                        max_text_chars=config.embedding_max_text_chars,
                        max_dimensions=config.embedding_max_dimensions,
                        max_response_bytes=config.embedding_max_response_bytes,
                        max_retries=config.embedding_max_retries,
                    )
                    from .repository import run_vector_retrieval
                    return run_vector_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                                 provider=provider, material_ids=request.material_ids, top_k=request.top_k)
                if request.mode == "hybrid":
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id or "fake"
                    provider = provider_registry(embedding_provider_id, config.embedding_model_id).embedding_provider(
                        model_revision=config.embedding_model_revision,
                        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                        timeout_seconds=config.embedding_timeout_seconds,
                        max_batch_size=config.embedding_max_batch_size,
                        max_text_chars=config.embedding_max_text_chars,
                        max_dimensions=config.embedding_max_dimensions,
                        max_response_bytes=config.embedding_max_response_bytes,
                        max_retries=config.embedding_max_retries,
                    )
                    from .repository import run_hybrid_retrieval
                    return run_hybrid_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                                provider=provider, material_ids=request.material_ids, top_k=request.top_k,
                                                allow_fallback=request.allow_fallback)
                return run_chunk_retrieval(connection, project_id=app.state.config.project_id, query=request.query,
                                           material_ids=request.material_ids, top_k=request.top_k)
        except ValueError as exc:
            code = str(exc)
            status = 404 if code in {"material_not_found", "source_deleted"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except ProviderError as exc:
            raise HTTPException(status_code=_provider_http_status(exc.code), detail=exc.code) from None
        except EmbeddingError as exc:
            raise HTTPException(status_code=503, detail=exc.code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="retrieval_failed") from None

    @app.post("/api/context/assemble")
    def assemble_context_endpoint(request: ContextRequest) -> dict[str, object]:
        if request.hit_ids is None or len(request.hit_ids) > 200:
            if request.hit_ids is not None and len(request.hit_ids) > 200:
                raise HTTPException(status_code=400, detail="context_invalid_hits")
        if request.max_tokens <= 0 or request.max_tokens > MAX_CONTEXT_TOKENS:
            raise HTTPException(status_code=400, detail="context_invalid_max_tokens")
        try:
            with connect(app.state.config.database_path) as connection:
                return assemble_context(connection, project_id=app.state.config.project_id,
                                        hits=[{"chunk_id": h, "rank": i + 1} for i, h in enumerate(request.hit_ids)],
                                        max_tokens=request.max_tokens)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="context_assemble_failed") from None

    @app.post("/api/citation/validate")
    def validate_citation(request: CitationValidateRequest) -> dict[str, object]:
        if not request.key or len(request.key) > 80:
            raise HTTPException(status_code=400, detail="citation_invalid_key")
        try:
            with connect(app.state.config.database_path) as connection:
                return validate_citation_key(connection, request.key)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="citation_validate_failed") from None

    @app.get("/api/qa/threads")
    def qa_threads(limit: int = 50) -> dict[str, object]:
        if limit <= 0 or limit > 100:
            raise HTTPException(status_code=400, detail="qa_invalid_limit")
        try:
            with connect(app.state.config.database_path) as connection:
                items = list_qa_threads(connection, project_id=app.state.config.project_id, limit=limit)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="qa_history_failed") from None
        return {"items": items}

    @app.get("/api/qa/threads/{thread_id}")
    def qa_thread_history(thread_id: str) -> dict[str, object]:
        if not thread_id or len(thread_id) > 100:
            raise HTTPException(status_code=404, detail="qa_thread_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_qa_thread_history(connection, project_id=app.state.config.project_id, thread_id=thread_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="qa_history_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="qa_thread_not_found")
        return result

    @app.get("/api/qa/citations/{citation_key}")
    def qa_citation_detail(citation_key: str) -> dict[str, object]:
        if not citation_key or len(citation_key) > 80:
            raise HTTPException(status_code=404, detail="citation_not_found")
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_qa_citation_detail(connection, citation_key)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="citation_detail_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="citation_not_found")
        return result

    @app.post("/api/qa/ask")
    def ask_question(request: QaAskRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        if not request.material_ids or len(request.material_ids) > 200 or any(not item for item in request.material_ids):
            raise HTTPException(status_code=400, detail="qa_invalid_materials")
        if request.retrieval_mode not in {"lexical", "vector", "hybrid"}:
            raise HTTPException(status_code=400, detail="retrieval_invalid_mode")
        request_id, _operation_correlation_id = correlation()
        operation: dict[str, object] | None = None
        try:
            with connect(app.state.config.database_path) as connection:
                reclaim_stale_qa_operations(connection, project_id=app.state.config.project_id)
                if idempotency_key:
                    if len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key):
                        raise HTTPException(status_code=400, detail="qa_invalid_idempotency_key")
                    expected_fingerprint = qa_request_fingerprint(
                        question=request.question, material_ids=request.material_ids, thread_id=request.thread_id,
                        retrieval_mode=request.retrieval_mode,
                        allow_retrieval_fallback=request.allow_retrieval_fallback,
                    )
                    replay = get_idempotent_qa_response(
                        connection, project_id=app.state.config.project_id, idempotency_key=idempotency_key,
                        retrieval_mode=request.retrieval_mode, expected_fingerprint=expected_fingerprint,
                    )
                    if replay is not None:
                        return replay
                operation = create_qa_request(
                    connection, project_id=app.state.config.project_id, question=request.question,
                    material_ids=request.material_ids, thread_id=request.thread_id, request_id=request_id,
                    idempotency_key=idempotency_key, retrieval_mode=request.retrieval_mode,
                    allow_retrieval_fallback=request.allow_retrieval_fallback,
                )
                if operation.get("replay"):
                    replay = get_idempotent_qa_response(
                        connection, project_id=app.state.config.project_id, idempotency_key=idempotency_key,
                        retrieval_mode=request.retrieval_mode,
                        expected_fingerprint=qa_request_fingerprint(
                            question=request.question, material_ids=request.material_ids, thread_id=request.thread_id,
                            retrieval_mode=request.retrieval_mode,
                            allow_retrieval_fallback=request.allow_retrieval_fallback,
                        ),
                    )
                    if replay is not None:
                        return replay
                if request.retrieval_mode == "lexical":
                    retrieval = run_chunk_retrieval(
                        connection, project_id=app.state.config.project_id, query=request.question,
                        material_ids=request.material_ids, top_k=request.top_k,
                    )
                else:
                    config = app.state.config
                    embedding_provider_id = config.embedding_provider_id
                    embedding_provider = None
                    embedding_error_code = "embedding_provider_not_configured"
                    try:
                        embedding_provider = EmbeddingProviderRegistry(
                            embedding_provider_id, config.embedding_model_id,
                            model_revision=config.embedding_model_revision,
                            base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                            timeout_seconds=config.embedding_timeout_seconds,
                            max_batch_size=config.embedding_max_batch_size,
                            max_text_chars=config.embedding_max_text_chars,
                            max_dimensions=config.embedding_max_dimensions,
                            max_response_bytes=config.embedding_max_response_bytes,
                            max_retries=config.embedding_max_retries,
                        ).configured_provider()
                    except (ProviderError, EmbeddingError) as error:
                        embedding_error_code = error.code
                        if request.retrieval_mode == "vector" or not request.allow_retrieval_fallback:
                            fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                            raise HTTPException(status_code=503, detail=error.code) from None
                    if request.retrieval_mode == "vector":
                        retrieval = run_vector_retrieval(
                            connection, project_id=app.state.config.project_id, query=request.question,
                            provider=embedding_provider, material_ids=request.material_ids, top_k=request.top_k,
                        )
                    else:
                        retrieval = run_hybrid_retrieval(
                            connection, project_id=app.state.config.project_id, query=request.question,
                            provider=embedding_provider, material_ids=request.material_ids, top_k=request.top_k,
                            allow_fallback=request.allow_retrieval_fallback, embedding_error_code=embedding_error_code,
                        )
                connection.execute(
                    "UPDATE ai_operations SET retrieval_policy_version = ?, retrieval_run_id = ? WHERE id = ? AND status = 'running'",
                    (retrieval["policy_version"], retrieval["run_id"], operation["operation_id"]),
                )
                if retrieval["status"] != "succeeded":
                    fail_qa_operation(connection, str(operation["operation_id"]), str(retrieval["error_code"]))
                    raise HTTPException(status_code=409, detail=str(retrieval["error_code"]))
                context = assemble_context(
                    connection, project_id=app.state.config.project_id, hits=list(retrieval["hits"]),
                )
                if not context["context_blocks"]:
                    fail_qa_operation(connection, str(operation["operation_id"]), "retrieval_empty")
                    raise HTTPException(status_code=409, detail="retrieval_empty")
                try:
                    if app.state.config.ai_provider_id == "fake":
                        provider = provider_registry(
                            app.state.config.ai_provider_id, app.state.config.ai_model_id,
                        ).configured_provider()
                    else:
                        provider = provider_registry(
                            app.state.config.ai_provider_id, app.state.config.ai_model_id,
                            base_url=app.state.config.ai_base_url,
                            api_key=app.state.config.ai_api_key,
                            timeout_seconds=app.state.config.ai_timeout_seconds,
                            max_retries=app.state.config.ai_max_retries,
                        ).configured_provider()
                    started = time.perf_counter()
                    result = provider.generate_answer(ProviderRequest(
                        question=request.question, context_blocks=list(context["context_blocks"]),
                        max_output_tokens=app.state.config.ai_max_output_tokens,
                        max_prompt_chars=app.state.config.ai_max_prompt_chars,
                        max_answer_chars=app.state.config.ai_max_answer_chars,
                    ))
                    latency_ms = result.latency_ms if result.latency_ms is not None else round((time.perf_counter() - started) * 1000)
                except ProviderError as error:
                    fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                    raise HTTPException(status_code=_provider_http_status(error.code), detail=error.code) from None
                except EmbeddingError as error:
                    fail_qa_operation(connection, str(operation["operation_id"]), error.code)
                    raise HTTPException(status_code=503, detail=error.code) from None
                try:
                    persisted = persist_qa_answer(
                        connection, project_id=app.state.config.project_id,
                        operation_id=str(operation["operation_id"]), thread_id=str(operation["thread_id"]),
                        provider_id=result.provider_id, model_id=result.model_id,
                        answer_text=result.answer_text, citation_keys=result.citation_keys,
                        context_blocks=list(context["context_blocks"]), prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens, latency_ms=latency_ms,
                        provider_request_id=result.provider_request_id,
                        total_tokens=result.total_tokens, finish_reason=result.finish_reason,
                        retrieval_run_id=str(retrieval["run_id"]),
                    )
                except ValueError as error:
                    fail_qa_operation(connection, operation["operation_id"], str(error))
                    raise HTTPException(status_code=500, detail="qa_generation_failed") from None
        except HTTPException:
            raise
        except ValueError as error:
            code = str(error)
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_qa_operation(connection, str(operation["operation_id"]), code)
            status = 404 if code in {"material_not_found", "source_deleted", "qa_thread_not_found"} else 409 if code in {"qa_operation_in_progress", "qa_idempotency_key_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_qa_operation(connection, str(operation["operation_id"]), "qa_persist_failed")
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="qa_generation_failed") from None
        return {
            "status": "succeeded", "thread_id": operation["thread_id"],
            "user_message_id": operation["user_message_id"],
            "assistant_message_id": persisted["assistant_message_id"], "answer_id": persisted["answer_id"],
            "operation_id": operation["operation_id"], "answer_text": result.answer_text,
            "provider_id": result.provider_id, "model_id": result.model_id,
            "retrieval_run_id": retrieval["run_id"], "retrieval": {
                "mode": request.retrieval_mode, "policy_version": retrieval["policy_version"],
                "fallback": bool(retrieval.get("fallback", False)),
                "fallback_reason": retrieval.get("fallback_reason"), "run_id": retrieval["run_id"],
            }, "citations": persisted["citations"],
        }

    @app.post("/api/materials/{material_id}/ai-index")
    def index_material(material_id: str, retry: bool = False) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                state = material_state(connection, material_id)
                if state == "missing":
                    raise HTTPException(status_code=404, detail="material_not_found")
                if state == "deleted":
                    raise HTTPException(status_code=404, detail="source_deleted")
                extraction = connection.execute(
                    "SELECT id FROM extractions WHERE material_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                    (material_id,),
                ).fetchone()
                if extraction is None:
                    raise HTTPException(status_code=404, detail="extraction_not_found")
                revision = index_material_revision(connection, material_id, str(extraction["id"]))
                reclaim_stale_embedding_operations(connection, project_id=app.state.config.project_id)
                previous = connection.execute(
                    "SELECT retry_count FROM ai_operations WHERE operation_type='embedding_index' AND material_id=? "
                    "ORDER BY created_at DESC, id DESC LIMIT 1", (material_id,)
                ).fetchone()
                operation_id = create_embedding_index_operation(
                    connection, project_id=app.state.config.project_id, material_id=material_id,
                    source_revision=str(revision["id"]), retry_count=(int(previous["retry_count"]) + 1 if retry and previous else 0),
                )
                # The lease must survive provider failure so operators can inspect and retry it.
                connection.commit()
                result = get_material_index_status(connection, material_id)
                config = app.state.config
                embedding_provider_id = config.embedding_provider_id or "fake"
                provider = EmbeddingProviderRegistry(
                    embedding_provider_id, config.embedding_model_id,
                    model_revision=config.embedding_model_revision,
                    base_url=config.embedding_base_url, api_key=config.embedding_api_key,
                    max_batch_size=config.embedding_max_batch_size,
                    max_text_chars=config.embedding_max_text_chars,
                    max_dimensions=config.embedding_max_dimensions,
                    max_response_bytes=config.embedding_max_response_bytes,
                    max_retries=config.embedding_max_retries,
                ).configured_provider()
                from .repository import index_embeddings_for_material
                result = {**result, "embedding": index_embeddings_for_material(
                    connection, material_id=material_id, provider=provider, retry_failed=retry,
                    operation_id=operation_id)}
                finish_embedding_index_operation(connection, operation_id, status="succeeded")
                result["index_operation_id"] = operation_id
        except HTTPException:
            raise
        except ValueError as exc:
            code = str(exc)
            status = 404 if code in {"source_deleted", "material_extraction_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except (sqlite3.Error, EmbeddingError, ProviderError) as error:
            if 'operation_id' in locals() and operation_id:
                try:
                    with connect(app.state.config.database_path) as connection:
                        finish_embedding_index_operation(connection, operation_id, status="failed", error_code=getattr(error, "code", "embedding_index_failed"))
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="ai_index_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return {**result, "revision_id": revision["id"]}

    @app.get("/api/materials/{material_id}/ai-index")
    def material_index_status(material_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                result = get_material_index_status(connection, material_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="ai_index_status_failed") from None
        if result is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        return result

    @app.get("/api/materials/{material_id}/original")
    def download_original(material_id: str):
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            target = _checked_original_path(config, row["stored_path"], row["source_sha256"])
            return FileResponse(target, media_type=row["media_type"], filename=_download_name(row["original_name"]))

    @app.get("/api/materials/{material_id}/text")
    def export_text(material_id: str):
        config = app.state.config
        with connect(config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            headers = {"Content-Disposition": f'attachment; filename="{_download_name(row["original_name"], ".extracted.txt")}"'}
            return Response(content=row["text"], media_type="text/plain", headers=headers)

    @app.get("/api/materials/{material_id}")
    def material(material_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            row = get_material(connection, material_id)
            if row is None:
                raise HTTPException(status_code=404, detail="material_not_found")
            payload = dict(row)
            payload.pop("stored_path", None)
            payload["warnings"] = json.loads(payload.pop("warnings_json"))
            payload["spans"] = [dict(span) for span in get_spans(connection, row["extraction_id"])]
            return payload

    @app.post("/api/materials/{material_id}/restore")
    def restore_existing_material(material_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                state = material_state(connection, material_id)
                row = restore_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_restore_failed") from exc
        if row is None:
            if state == "missing":
                raise HTTPException(status_code=404, detail="material_not_found")
            raise HTTPException(status_code=404, detail="material_not_deleted")
        payload = dict(row)
        payload.pop("stored_path", None)
        return payload

    @app.post("/api/materials/{material_id}/purge")
    def purge_existing_material(material_id: str) -> dict[str, object]:
        config = app.state.config
        try:
            with connect(config.database_path) as connection:
                source_sha256, stored_path, _ = purge_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_purge_failed") from exc
        if source_sha256 is None or stored_path is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        lock = acquire_hash_lock(source_sha256)
        try:
            try:
                with connect(config.database_path) as connection:
                    remaining = connection.execute(
                        "SELECT COUNT(*) FROM materials WHERE source_sha256 = ?", (source_sha256,)
                    ).fetchone()[0]
            except sqlite3.Error:
                remaining = 1
            if remaining == 0:
                try:
                    target = _checked_original_path(config, stored_path, source_sha256)
                    target.unlink(missing_ok=True)
                except (HTTPException, OSError):
                    pass
        finally:
            release_hash_lock(source_sha256, lock)
        return {"status": "purged", "material_id": material_id}

    @app.patch("/api/materials/{material_id}")
    def rename_existing_material(material_id: str, request: RenameMaterialRequest) -> dict[str, object]:
        original_name = _rename_name(request.original_name)
        if original_name is None:
            raise HTTPException(status_code=400, detail="invalid_filename")
        try:
            with connect(app.state.config.database_path) as connection:
                row = rename_material(connection, material_id, original_name)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_update_failed") from exc
        if row is None:
            raise HTTPException(status_code=404, detail="material_not_found")
        payload = dict(row)
        payload.pop("stored_path", None)
        return payload

    @app.delete("/api/materials/{material_id}", status_code=204)
    def delete_existing_material(material_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                deleted = soft_delete_material(connection, material_id)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="material_delete_failed") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="material_not_found")
        return Response(status_code=204)

    @app.post("/api/materials", status_code=201)
    async def upload_material(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
        result = await _process_file(file, app.state.config, batch=False)
        record_import(str(result.get("status", "failed")))
        return result

    @app.post("/api/materials/batch", status_code=201)
    async def upload_materials(files: Annotated[list[UploadFile], File(...)]) -> dict[str, object]:
        items = [await _process_file(file, app.state.config, batch=True) for file in files]
        for item in items:
            record_import(str(item.get("status", "failed")))
        counts = {status: sum(item["status"] == status for item in items)
                  for status in ("success", "empty", "rejected", "failed")}
        return {"batch_id": f"batch_{uuid.uuid4().hex}", "total": len(items), **counts, "items": items}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    return app


INDEX_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>StudyBuddy 文件导入</title>
<style>*{box-sizing:border-box}body{font-family:system-ui,sans-serif;max-width:1060px;min-width:0;margin:0 auto;padding:32px;color:#17202a;background:#f6f7f9;overflow-wrap:anywhere}main{background:white;border:1px solid #d8dde3;padding:24px;border-radius:8px}h1{margin-top:0}button{background:#1769aa;color:white;border:0;border-radius:4px;padding:9px 14px;cursor:pointer;min-height:40px}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}button:disabled{cursor:not-allowed;opacity:.6}input{margin:12px 0}.status{padding:12px 0;color:#52606d;min-height:24px}.status.error,.error{color:#9a3412}.status.success{color:#166534}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.summary{display:flex;gap:16px;flex-wrap:wrap;color:#52606d}.batch-item{border-top:1px solid #e5e7eb;padding:7px 0}.layout{display:grid;grid-template-columns:320px 1fr;gap:24px;margin-top:24px}.filters{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0 12px}#search-form{display:flex;gap:6px;margin:8px 0}#search{min-width:0;flex:1;margin:0;padding:7px}#search-form button{padding:7px}.filters button{background:#e8edf2;color:#17202a;padding:6px 9px}.filters button.active{background:#1769aa;color:white}.item{display:block;width:100%;text-align:left;border:1px solid #d8dde3;background:#fff;color:#17202a;margin:6px 0}.item:hover{background:#eef5fb}#management{display:flex;gap:8px;margin:14px 0;flex-wrap:wrap}#management button{background:#52606d}.meta{color:#52606d;font-size:14px}.provider-status{border:1px solid #d8dde3;padding:10px;margin:14px 0;background:#fafbfc}.provider-status-error{border-color:#c2410c;background:#fff7ed}.provider-status strong{display:block;margin-bottom:4px}.qa-scope,.qa-history{border:1px solid #d8dde3;padding:10px;margin:10px 0;background:#fafbfc}.qa-scope-list,.qa-history-list{display:grid;gap:5px;max-height:180px;overflow:auto}.qa-scope label{display:flex;gap:7px;align-items:flex-start;overflow-wrap:anywhere}.qa-history button{display:block;width:100%;text-align:left;background:#fff;color:#17202a;border:1px solid #d8dde3;padding:7px}.qa-history button.active{border-color:#1769aa;background:#eef5fb}.qa-message{border-top:1px solid #e5e7eb;padding:10px 0}.qa-message-user{font-weight:600}.qa-message-assistant{white-space:pre-wrap;line-height:1.55}.qa-citation-detail{font-size:13px;color:#52606d;margin-top:5px;overflow-wrap:anywhere}.toast{position:fixed;right:20px;bottom:20px;background:#17202a;color:#fff;padding:10px 14px;border-radius:4px;max-width:min(360px,calc(100vw - 40px));z-index:5}.dialog-backdrop{position:fixed;inset:0;background:rgba(23,32,42,.45);display:grid;place-items:center;padding:20px;z-index:4}.dialog{background:#fff;max-width:560px;width:100%;max-height:80vh;overflow:auto;padding:20px;border:1px solid #d8dde3;border-radius:6px}.search-match{display:inline-block;color:#1769aa;font-size:13px;font-weight:600;margin-top:4px}.search-snippet{display:block;color:#52606d;font-size:14px;line-height:1.45;margin-top:4px;white-space:pre-wrap;overflow-wrap:anywhere}.search-highlight{background:#fff0a8;color:inherit;border-radius:2px;padding:0 1px}.content{white-space:pre-wrap;line-height:1.6;max-height:55vh;overflow:auto;border-top:1px solid #e5e7eb;padding-top:16px}.qa{border-top:1px solid #e5e7eb;margin-top:18px;padding-top:14px}.qa-workspace{display:grid;grid-template-columns:minmax(190px,260px) minmax(0,1fr);gap:14px;margin-top:10px}.qa-panel-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}.qa-panel-heading button{padding:6px 9px}.qa-thread-panel{min-width:0}.qa-thread-panel h4{margin:0 0 4px}.qa-timeline{display:grid;gap:8px;max-height:520px;overflow:auto;padding:4px 2px}.qa-empty{padding:18px 0}.qa-message{border-top:1px solid #e5e7eb;padding:10px 0}.qa-message-user{font-weight:600}.qa-message-assistant{white-space:pre-wrap;line-height:1.55;overflow-wrap:anywhere;min-width:0}.qa-message-failed{border-left:3px solid #c2410c;padding-left:8px}.qa-thread-status{min-height:20px}.qa textarea{box-sizing:border-box;width:100%;min-height:72px;padding:8px;margin:8px 0}.qa-answer{white-space:pre-wrap;line-height:1.55}.qa-citations{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.qa-citations button{background:#e8edf2;color:#17202a;padding:5px 8px}.citation-highlight{background:#fff0a8;color:inherit;border-radius:2px;padding:0 1px}@media(max-width:700px){body{padding:12px}main{padding:16px}.layout{grid-template-columns:1fr}.qa-workspace{grid-template-columns:1fr}.qa-timeline{max-height:420px;min-width:0}.qa-panel-heading{align-items:flex-start;flex-wrap:wrap}.qa-panel-heading button,.qa-scope button,#management button,#batch-export button{flex:1 1 140px}.qa textarea{min-height:96px}.content{max-height:none;overflow-x:hidden}.dialog-backdrop{padding:12px}.dialog{max-height:calc(100vh - 24px)}} </style></head>
<body><header class="app-header"><h1>StudyBuddy 文件导入与问答</h1><nav aria-label="主要视图"><a href="#materials" id="nav-materials">材料</a><a href="#qa" id="nav-qa">问答</a><span id="nav-context" class="meta" aria-live="polite">未选择材料</span></nav></header><main id="main-content"><section id="provider-status" class="provider-status" role="status" aria-live="polite" aria-atomic="true"><strong id="provider-status-title">AI Provider 状态</strong><div id="provider-status-detail" class="meta">正在读取运行配置</div></section><div id="page-status" class="status" role="status" aria-live="polite" aria-atomic="true"></div><form id="form"><label class="sr-only" for="file">选择要导入的文件</label><input id="file" type="file" multiple required><button id="file-import" type="submit">导入文件</button></form><div><label class="sr-only" for="folder">选择要导入的文件夹</label><input id="folder" type="file" webkitdirectory multiple><button id="folder-import" type="button">导入文件夹</button></div><div id="status" class="status" role="status" aria-live="polite" aria-atomic="true"></div><div id="summary" class="summary"></div><div id="batch-items"></div><section class="layout"><aside id="materials-panel" aria-labelledby="materials-heading"><h2 id="materials-heading">材料</h2><div id="views" class="filters" role="group" aria-label="材料视图"><button id="active-view" type="button" aria-current="page">正常材料</button><button id="deleted-view" type="button" aria-current="false">回收站</button></div><form id="search-form" role="search"><label class="sr-only" for="search">搜索材料</label><input id="search" type="search" placeholder="搜索材料" autocomplete="off"><button id="search-submit" type="submit">搜索</button><button id="search-clear" type="button" aria-label="清除输入">清除</button></form><div id="search-summary" class="meta"></div><div id="filters" class="filters"></div><div id="pagination" class="filters"><button id="page-prev" type="button">上一页</button><span id="page-info" class="meta"></span><button id="page-next" type="button">下一页</button></div><div id="batch-export" class="filters"><button id="select-all" type="button">全选当前列表</button><button id="export-selected-originals" type="button">导出选中原文件</button><button id="export-selected-text" type="button">导出选中文本</button><button id="export-selected-bundle" type="button">导出选中全部</button></div><div id="materials"></div></aside><article id="material-detail" aria-labelledby="title"><h2 id="title">选择材料</h2><div id="meta" class="meta" role="status" aria-live="polite"></div><div id="warnings" class="meta" role="alert" aria-live="assertive"></div><div id="spans" class="meta"></div><div id="management"><button id="rename" type="button">重命名</button><button id="delete" type="button">删除</button><button id="restore" type="button">恢复</button><button id="purge" type="button">永久删除</button><button id="download-original" type="button">下载原文件</button><button id="export-text" type="button">导出解析正文</button><button id="open-qa" type="button">进入问答</button></div><div id="content" class="content"></div><section id="qa" class="qa" aria-labelledby="qa-title"><div class="qa-panel-heading"><h3 id="qa-title">材料问答</h3><button id="qa-back-material" type="button">返回材料详情</button></div><div id="qa-status" class="meta" role="status" aria-live="polite" aria-atomic="true">选择已建立 AI 索引的正常材料后可提问</div><div class="qa-workspace"><aside class="qa-history" aria-labelledby="qa-history-title"><div class="qa-panel-heading"><strong id="qa-history-title">问答对话</strong><button id="qa-new-thread" type="button">新建对话</button></div><div id="qa-history-status" class="meta" role="status" aria-live="polite">加载中</div><div id="qa-history-list" class="qa-history-list"></div></aside><div class="qa-thread-panel"><h4 id="qa-thread-title">新对话</h4><div id="qa-thread-status" class="meta">尚未发送问题</div><div class="qa-scope"><strong>问答材料范围</strong><div id="qa-scope-summary" class="meta">默认使用当前材料</div><div id="qa-scope-list" class="qa-scope-list"></div><button id="qa-scope-current" type="button">使用当前材料</button><label for="qa-retrieval-mode">检索模式</label><select id="qa-retrieval-mode"><option value="lexical">词法</option><option value="vector">向量</option><option value="hybrid">混合</option></select><label><input id="qa-allow-fallback" type="checkbox" checked>混合模式允许词法回退</label><button id="qa-index" type="button" disabled>建立选中材料索引</button></div><div id="qa-timeline" class="qa-timeline"><div id="qa-empty" class="meta">新对话尚未有消息</div></div><label for="qa-question">问题</label><textarea id="qa-question" maxlength="1000" placeholder="输入与材料内容匹配的问题" disabled></textarea><div><button id="ai-index" type="button" disabled>建立当前材料索引</button><button id="qa-ask" type="button" disabled>提问</button><button id="qa-retry" type="button" hidden>重试</button></div><div id="qa-answer" class="qa-answer" hidden></div><div id="qa-citations" class="qa-citations" hidden></div></div></div></section></article></section></main><div id="qa-dialog-root"></div><div id="toast-root" aria-live="polite" aria-atomic="true"></div><div id="alert-root" role="alert" aria-live="assertive" aria-atomic="true"></div>
<script>const statusEl=document.querySelector('#status'),listEl=document.querySelector('#materials'),summaryEl=document.querySelector('#summary'),batchItemsEl=document.querySelector('#batch-items'),filterEl=document.querySelector('#filters');let currentFilter='';
function announce(message,kind='status'){statusEl.textContent=message;statusEl.className=`status ${kind==='error'?'error':kind==='success'?'success':''}`;const alertRoot=document.querySelector('#alert-root');alertRoot.textContent=kind==='error'?message:'';alertRoot.className=kind==='error'?'error':''}
function updateNavContext(){const view=viewMode==='deleted'?'回收站':'正常材料';const material=selectedMaterial?.original_name||'未选择材料';const thread=qaThreadId?` · 当前对话 ${document.querySelector('#qa-thread-title')?.textContent||'已选择'}`:'';const scope=qaScopeIds.length?` · 范围 ${qaScopeIds.length} 个材料`:'';document.querySelector('#nav-context').textContent=`${view} · ${material}${thread}${scope}`}
function setViewCurrent(){const active=viewMode==='active';document.querySelector('#active-view').setAttribute('aria-current',active?'page':'false');document.querySelector('#deleted-view').setAttribute('aria-current',active?'false':'page');updateNavContext()}
let viewMode='active';let currentQuery='';let providerCapabilities=null;let exportInFlight=false;let importInFlight=false;let currentOffset=0;let currentTotal=0;let currentHasMore=false;const PAGE_SIZE=20;
function textNode(tag, className, value){const node=document.createElement(tag);if(className)node.className=className;node.textContent=value;return node}
function renderMaterial(item, deleted){const button=document.createElement('button');button.className=`item${deleted?' deleted-item':''}`;button.dataset.id=item.id;button.setAttribute('aria-pressed',item.id===selectedMaterialId?'true':'false');if(!deleted){const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.className='material-select';checkbox.dataset.id=item.id;checkbox.setAttribute('aria-label',`选择材料 ${item.original_name}`);checkbox.addEventListener('click',event=>event.stopPropagation());button.append(checkbox,document.createTextNode(' '))}button.append(textNode('span','',item.original_name),document.createElement('br'));const meta=deleted?`已删除 · ${item.status} · ${item.deleted_at}`:`${item.status} · ${item.media_type} · ${item.text_length} 字 · ${item.span_count} spans${item.error_code?' · '+item.error_code:''}`;button.append(textNode('span','meta',meta),document.createElement('br'),textNode('span','meta',deleted?`${item.text_length} 字 · ${item.span_count} spans`:`${item.text_length} 字 · ${item.span_count} spans`));if(!deleted&&currentQuery){if(item.match_fields&&item.match_fields.length){const labels={original_name:'名称',text:'正文'};button.append(document.createElement('br'),textNode('span','search-match',`命中：${item.match_fields.map(field=>labels[field]||field).join('、')}`))}if(item.snippet){button.append(document.createElement('br'),textNode('span','search-snippet',item.snippet))}}button.onclick=()=>deleted?loadDeletedMaterial(item.id):loadMaterial(item.id);return button}
let listGeneration=0;
function activeMaterialsUrl(){return `/api/materials?${new URLSearchParams(Object.fromEntries([['status',currentFilter],['q',currentQuery],['limit',PAGE_SIZE],['offset',currentOffset]].filter(([,value])=>value!=='')))}`}
function updatePagination(){const page=currentTotal?Math.floor(currentOffset/PAGE_SIZE)+1:0;const pages=currentTotal?Math.ceil(currentTotal/PAGE_SIZE):0;document.querySelector('#page-info').textContent=pages?`第 ${page} 页 / 共 ${pages} 页 · 共 ${currentTotal} 项`:'共 0 项';document.querySelector('#page-prev').disabled=currentOffset===0;document.querySelector('#page-next').disabled=!currentHasMore}
function renderList(items,deleted){document.querySelector('#batch-export').style.display=deleted?'none':'flex';listEl.replaceChildren();if(!items.length){listEl.append(textNode('p','meta',deleted?'回收站为空':'暂无材料'))}else{items.forEach(item=>{if(!deleted)qaScopeMeta.set(item.id,item);listEl.append(renderMaterial(item,deleted))})}if(!deleted)renderQaScope()}
async function loadList(){const generation=++listGeneration;const deleted=viewMode==='deleted';const url=deleted?`/api/materials/deleted?limit=${PAGE_SIZE}&offset=${currentOffset}`:activeMaterialsUrl();try{const r=await fetch(url);if(!r.ok)throw new Error('list_load_failed');const payload=await r.json();const items=Array.isArray(payload)?payload:payload&&Array.isArray(payload.items)?payload.items:null;if(!items)throw new Error('list_payload_invalid');currentTotal=Array.isArray(payload)?items.length:Number.isFinite(payload.total)?payload.total:0;currentHasMore=Array.isArray(payload)?false:payload.has_more===true;if(generation!==listGeneration)return null;renderList(items,deleted);updatePagination();document.querySelector('#search-summary').textContent=!deleted&&currentQuery?`匹配 ${items.length}`:'';return items}catch(error){if(generation!==listGeneration)return null;announce('材料列表加载失败','error');return null}}
let selectedMaterialId=null;let selectedMaterial=null;let detailGeneration=0;let mutationInFlight=false;let uiGeneration=0;let qaInFlight=false;let qaThreadId=null;let qaScopeIds=[];let qaLastQuestion='';let qaLastError=null;let qaHistoryGeneration=0;const qaScopeMeta=new Map();let citationNavigationKey=null;
function selectedIds(){return [...document.querySelectorAll('.material-select:checked')].map(node=>node.dataset.id)}
function navigationState(){return {material:selectedMaterialId,thread:qaThreadId,scope:qaScopeIds.slice(),citation:citationNavigationKey}}
function writeNavigation(replace=false){const params=new URLSearchParams();const state=navigationState();if(state.material)params.set('material',state.material);if(state.thread)params.set('thread',state.thread);if(state.scope.length)params.set('scope',state.scope.join(','));if(state.citation)params.set('citation',state.citation);const url=params.toString()?`${location.pathname}?${params.toString()}`:location.pathname;history[replace?'replaceState':'pushState']({},'',url)}
function readNavigation(){const params=new URLSearchParams(location.search);return {material:params.get('material'),thread:params.get('thread'),scope:(params.get('scope')||'').split(',').filter(Boolean),citation:params.get('citation')}}
function enterQa(push=true){const selected=selectedIds();if(selected.length)qaScopeIds=selected;if(!qaScopeIds.length&&selectedMaterialId)qaScopeIds=[selectedMaterialId];if(!selectedMaterialId)return;document.querySelector('#qa').scrollIntoView({block:'start'});renderQaScope();document.querySelector('#qa-question').focus();document.querySelector('#nav-qa').setAttribute('aria-current','page');document.querySelector('#nav-materials').setAttribute('aria-current','false');if(push)writeNavigation(false);refreshQaIndex();updateNavContext()}
function returnToMaterial(){document.querySelector('#content').scrollIntoView({block:'start'});writeNavigation(false);document.querySelector('#nav-materials').setAttribute('aria-current','page');document.querySelector('#nav-qa').setAttribute('aria-current','false');document.querySelector('#open-qa').focus();updateNavContext()}
async function handleNavigation(){const state=readNavigation();if(state.scope.length)qaScopeIds=state.scope;qaThreadId=state.thread;citationNavigationKey=null;if(state.material){await loadMaterial(state.material,true);if(state.citation)await locateCitation(state.citation,true)}else{document.querySelector('#qa').scrollIntoView({block:'start'});if(state.thread)await loadQaHistory(state.thread);else renderQaScope()}}
function setExportBusy(busy){exportInFlight=busy;['export-selected-originals','export-selected-text','export-selected-bundle','select-all','download-original','export-text'].forEach(id=>document.querySelector('#'+id).disabled=busy||viewMode==='deleted'||((id==='download-original'||id==='export-text')&&!selectedMaterialId))}
function currentUi(){return {view:viewMode,id:selectedMaterialId,generation:uiGeneration,threadId:qaThreadId,scopeIds:qaScopeIds.slice()}}
function stillCurrent(context){return context.view===viewMode&&context.id===selectedMaterialId&&context.generation===uiGeneration&&(!('threadId' in context)||context.threadId===qaThreadId)&&(!context.scopeIds||context.scopeIds.join('\x1f')===qaScopeIds.join('\x1f'))}
async function readJsonObject(response){let value;try{value=await response.json()}catch(_){throw Error('invalid_json_response')}if(!value||typeof value!=='object'||Array.isArray(value))throw Error('invalid_json_response');return value}
async function saveDownload(response,filename,zip){const contentType=(response.headers.get('content-type')||'').toLowerCase();if(zip&&!contentType.includes('application/zip'))throw Error('invalid_zip_response');const blob=await response.blob();if(zip){const signature=new Uint8Array(await blob.slice(0,4).arrayBuffer());if(signature.length!==4||signature[0]!==0x50||signature[1]!==0x4b||signature[2]!==0x03||signature[3]!==0x04)throw Error('invalid_zip_body')}const url=URL.createObjectURL(blob);try{const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click()}finally{URL.revokeObjectURL(url)}}
async function exportSelected(includeOriginal,includeText){if(exportInFlight||viewMode==='deleted')return;const ids=selectedIds();if(!ids.length){announce('请选择至少一个材料','error');return}const context=currentUi();setExportBusy(true);try{const r=await fetch('/api/materials/export',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({material_ids:ids,include_original:includeOriginal,include_text:includeText})});if(!r.ok){if(stillCurrent(context))announce(r.status===413?'导出文件过大':'批量导出失败','error');return}await saveDownload(r,'studybuddy-materials.zip',true);if(stillCurrent(context))announce('批量导出完成','success')}catch(_){if(stillCurrent(context))statusEl.textContent='批量导出失败'}finally{setExportBusy(false)}}
function setMutationBusy(busy){mutationInFlight=busy;document.querySelector('#rename').disabled=busy||viewMode==='deleted'||!selectedMaterialId;document.querySelector('#delete').disabled=busy||viewMode==='deleted'||!selectedMaterialId;document.querySelector('#restore').disabled=busy||viewMode!=='deleted'||!selectedMaterialId;document.querySelector('#purge').disabled=busy||viewMode!=='deleted'||!selectedMaterialId;document.querySelector('#download-original').disabled=busy||viewMode!=='active'||!selectedMaterialId;document.querySelector('#export-text').disabled=busy||viewMode!=='active'||!selectedMaterialId;}
function toast(message,kind='status'){const root=document.querySelector('#toast-root');root.replaceChildren();const node=textNode('div','toast',message);node.setAttribute('role',kind==='error'?'alert':'status');node.setAttribute('aria-live',kind==='error'?'assertive':'polite');root.append(node);setTimeout(()=>{if(root.contains(node))root.replaceChildren()},2600)}
function providerStatusMessage(data){if(!data||typeof data!=='object')return ['AI Provider 状态不可用','无法读取运行配置'];const provider=data.provider_id,model=data.model_id;const name=provider&&model?`${provider} · ${model}`:'';if(data.status==='demo')return ['AI Provider：演示模式',`${name} · deterministic/demo provider，不代表真实 AI 服务`];if(data.status==='not_configured')return ['AI 服务尚未配置','材料管理仍可使用；配置真实 Provider 后才能进行真实问答'];if(data.status==='invalid_config')return ['AI Provider 配置不完整','请检查进程环境中的 Provider、model、base URL 和 API key 配置'];if(data.status==='configured'&&data.verification_status==='unverified')return ['AI Provider：已配置，尚未验证',`${name} · generic OpenAI-compatible 配置，未证明当前 endpoint/model 可用`];if(data.status==='temporarily_unavailable')return ['AI Provider：暂时不可用',`${name||'当前配置'} · 请稍后重试`];return ['AI Provider：状态未知',name||'请检查运行配置']}
function renderProviderStatus(data){providerCapabilities=data;const [title,detail]=providerStatusMessage(data);document.querySelector('#provider-status-title').textContent=title;document.querySelector('#provider-status-detail').textContent=detail;document.querySelector('#provider-status').classList.toggle('provider-status-error',data&&['invalid_config','temporarily_unavailable'].includes(data.status))}
async function loadProviderCapabilities(){try{const response=await fetch('/api/ai/capabilities');const data=await readJsonObject(response);renderProviderStatus(data)}catch(_){renderProviderStatus({status:'temporarily_unavailable',provider_id:null,model_id:null})}}
function setQaStatus(message,kind='meta'){const node=document.querySelector('#qa-status');node.className=`${kind==='error'?'meta error':'meta'}`;node.setAttribute('role',kind==='error'?'alert':'status');node.setAttribute('aria-live',kind==='error'?'assertive':'polite');node.textContent=message;updateNavContext()}
function clearQa(preserveContext=false){if(!preserveContext){qaThreadId=null;qaScopeIds=[];qaLastQuestion='';citationNavigationKey=null}qaInFlight=false;qaLastError=null;document.querySelector('#qa-question').value='';document.querySelector('#qa-question').disabled=true;document.querySelector('#qa-ask').disabled=true;document.querySelector('#ai-index').disabled=true;document.querySelector('#qa-index').disabled=true;document.querySelector('#qa-retry').hidden=true;document.querySelector('#qa-thread-title').textContent=qaThreadId?'正在恢复对话':'新对话';document.querySelector('#qa-thread-status').textContent='尚未发送问题';setQaStatus('选择已建立 AI 索引的正常材料后可提问');document.querySelector('#qa-answer').replaceChildren();document.querySelector('#qa-citations').replaceChildren();document.querySelector('#qa-timeline').replaceChildren(textNode('div','meta qa-empty','新对话尚未有消息'));document.querySelector('#qa-history-list').replaceChildren();document.querySelector('#qa-history-status').textContent='请选择材料';renderQaScope()}
function renderQaScope(){const list=document.querySelector('#qa-scope-list');list.replaceChildren();const boxes=[...document.querySelectorAll('.material-select')];const current=selectedMaterialId;const ids=qaScopeIds.length?qaScopeIds:(current?[current]:[]);qaScopeIds=ids.filter(id=>boxes.some(box=>box.dataset.id===id)||id===current||qaScopeMeta.has(id));boxes.forEach(box=>{const label=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.checked=qaScopeIds.includes(box.dataset.id);input.addEventListener('change',()=>{qaScopeIds=[...document.querySelectorAll('#qa-scope-list input:checked')].map(node=>node.value);writeNavigation(true);renderQaScope();refreshQaIndex()});input.value=box.dataset.id;const item=qaScopeMeta.get(box.dataset.id);label.append(input,document.createTextNode(item?.original_name||box.closest('.item')?.querySelector('span')?.textContent||box.dataset.id));list.append(label)});qaScopeIds.filter(id=>!boxes.some(box=>box.dataset.id===id)).forEach(id=>{const item=qaScopeMeta.get(id);const label=textNode('div','meta',`${item?.original_name||id} · 当前列表未显示`);list.append(label)});document.querySelector('#qa-scope-summary').textContent=qaScopeIds.length?`已选择 ${qaScopeIds.length} 个材料`:'未选择材料';updateNavContext()}
function setQaScopeToCurrent(){qaScopeIds=selectedMaterialId?[selectedMaterialId]:[];writeNavigation(true);renderQaScope();refreshQaIndex();toast('已切换到当前材料')}
async function restoreNavigation(){const state=readNavigation();if(state.scope.length)qaScopeIds=state.scope;qaThreadId=state.thread;citationNavigationKey=state.citation;if(state.material)await loadMaterial(state.material,true);else if(state.thread)await loadQaHistory(state.thread)}
function closeCitationDialog(){document.querySelector('#qa-dialog-root').replaceChildren()}
function showCitationDialog(data){const root=document.querySelector('#qa-dialog-root');const returnFocus=document.activeElement;root.replaceChildren();const backdrop=document.createElement('div');backdrop.className='dialog-backdrop';const dialog=document.createElement('div');dialog.className='dialog';dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-labelledby','citation-dialog-title');const title=textNode('h3','', '引用详情');title.id='citation-dialog-title';const body=textNode('div','',`状态：${data.status==='valid'?'可用':data.status==='source_deleted'?'来源已删除':'来源已不可用'}\n材料：${data.material_name||data.material_id||'未知'}\nRevision：${data.revision_id||'未知'}\nChunk：${data.chunk_id||'未知'}\n${data.excerpt?'摘录：'+data.excerpt:''}`);body.style.whiteSpace='pre-wrap';const close=document.createElement('button');close.type='button';close.textContent='关闭';const closeDialog=()=>{root.replaceChildren();document.removeEventListener('keydown',onKeydown);if(returnFocus&&typeof returnFocus.focus==='function')returnFocus.focus()};const onKeydown=event=>{if(event.key==='Escape')closeDialog()};close.onclick=closeDialog;dialog.append(title,body,close);backdrop.append(dialog);backdrop.onclick=event=>{if(event.target===backdrop)closeDialog()};root.append(backdrop);document.addEventListener('keydown',onKeydown);close.focus()}
function renderHistory(data){const timeline=document.querySelector('#qa-timeline');const answer=document.querySelector('#qa-answer');const citations=document.querySelector('#qa-citations');timeline.replaceChildren();answer.replaceChildren();citations.replaceChildren();const messages=data.messages||[];const latestAnswer=messages.slice().reverse().find(message=>message.role==='assistant');answer.textContent=latestAnswer?.content||'';if(!messages.length)timeline.append(textNode('div','meta qa-empty','新对话尚未有消息'));messages.forEach(message=>{const row=textNode('article',`qa-message qa-message-${message.role}`,'');row.append(textNode('div','qa-message-label',message.role==='user'?'你的问题':'AI 回答'));row.append(textNode('div',message.role==='user'?'qa-message-user':'qa-message-assistant',message.content||''));if(message.answer_status&&message.answer_status!=='ready')row.classList.add('qa-message-failed');if(message.citations){const citeRow=textNode('div','qa-citations','');message.citations.forEach(citation=>{const button=document.createElement('button');button.type='button';button.textContent=citation.status==='valid'?`引用 ${citation.position} · ${citation.material_name||'来源'}`:`引用 ${citation.position} · 来源不可用`;button.setAttribute('aria-label',button.textContent);button.onclick=()=>openCitation(citation);citeRow.append(button)});row.append(citeRow)}timeline.append(row)});const thread=data.thread||{};document.querySelector('#qa-thread-title').textContent=thread.title||'新对话';document.querySelector('#qa-thread-status').textContent=messages.length?`${messages.length} 条消息 · 最近更新 ${thread.updated_at||'未知时间'}`:'尚未发送问题';document.querySelector('#qa-empty')?.remove();setQaStatus(messages.length?'已加载问答历史':'新对话尚未有消息');updateNavContext();document.querySelector('#qa-question').focus()}
async function loadQaHistory(threadId){const generation=++qaHistoryGeneration;uiGeneration++;const context={generation,threadId};document.querySelector('#qa-thread-status').textContent='正在加载对话';document.querySelector('#qa-timeline').replaceChildren(textNode('div','meta qa-empty','正在加载对话'));try{const response=await fetch(`/api/qa/threads/${encodeURIComponent(threadId)}`);const data=await readJsonObject(response);if(generation!==qaHistoryGeneration||context.generation!==qaHistoryGeneration)return;qaThreadId=threadId;try{sessionStorage.setItem('studybuddy.qa.thread',threadId)}catch(_){}renderHistory(data);await refreshQaHistory()}catch(_){if(generation===qaHistoryGeneration){document.querySelector('#qa-thread-status').textContent='对话加载失败';setQaStatus('问答历史加载失败','error')}}}
async function refreshQaHistory(){const generation=++qaHistoryGeneration;const list=document.querySelector('#qa-history-list');const status=document.querySelector('#qa-history-status');status.textContent='加载中';try{const response=await fetch('/api/qa/threads');const data=await readJsonObject(response);if(generation!==qaHistoryGeneration)return;list.replaceChildren();if(!data.items?.length){status.textContent='暂无问答历史';return}status.textContent=`${data.items.length} 个对话`;data.items.forEach(item=>{const button=document.createElement('button');button.type='button';button.textContent=`${item.title||'未命名对话'} · ${item.message_count} 条消息 · ${item.status==='failed'?'失败':item.status==='empty'?'空对话':'进行中'}`;button.className=item.id===qaThreadId?'active':'';button.setAttribute('aria-current',item.id===qaThreadId?'true':'false');button.onclick=()=>loadQaHistory(item.id);list.append(button)})}catch(_){if(generation===qaHistoryGeneration)status.textContent='对话列表加载失败'}}
function newQaThread(){if(qaInFlight){uiGeneration++;qaInFlight=false}qaHistoryGeneration++;qaThreadId=null;qaLastQuestion='';qaLastError=null;document.querySelector('#qa-question').value='';document.querySelector('#qa-thread-title').textContent='新对话';document.querySelector('#qa-thread-status').textContent='尚未发送问题';document.querySelector('#qa-timeline').replaceChildren(textNode('div','meta qa-empty','新对话尚未有消息'));updateNavContext();document.querySelector('#qa-answer').replaceChildren();document.querySelector('#qa-citations').replaceChildren();document.querySelector('#qa-retry').hidden=true;setQaStatus('已新建对话，请确认材料范围后提问');renderQaScope();refreshQaIndex();document.querySelector('#qa-question').focus()}
async function openCitation(citation,fromNavigation=false){citationNavigationKey=citation.citation_key||null;writeNavigation(false);if(!fromNavigation)showCitationDialog(citation);if(citation.status!=='valid'){setQaStatus(citation.status==='source_deleted'?'引用来源已删除':'引用来源已不可用');return}const returnContext={thread:qaThreadId,scope:qaScopeIds.slice()};const changedMaterial=citation.material_id!==selectedMaterialId;if(changedMaterial){await loadMaterial(citation.material_id,true)}if(selectedMaterialId!==citation.material_id||!selectedMaterial)return;qaThreadId=returnContext.thread;qaScopeIds=returnContext.scope;writeNavigation(true);const start=citation.start_offset,end=citation.end_offset;if(typeof start==='number'&&typeof end==='number'){renderCitationLocation(selectedMaterial.text||'',start,end);if(changedMaterial||fromNavigation)closeCitationDialog();setQaStatus('已定位引用来源')}}
function clearMaterial(){detailGeneration++;uiGeneration++;selectedMaterialId=null;selectedMaterial=null;document.querySelector('#title').textContent='选择材料';document.querySelector('#meta').textContent='';document.querySelector('#warnings').textContent='';document.querySelector('#spans').textContent='';document.querySelector('#content').textContent='';document.querySelector('#rename').disabled=true;document.querySelector('#delete').disabled=true;document.querySelector('#restore').disabled=true;document.querySelector('#purge').disabled=true;document.querySelector('#download-original').disabled=true;document.querySelector('#export-text').disabled=true;clearQa()}
function queryTokens(){return currentQuery.trim().split(/\\s+/).filter(Boolean)}
function firstTextMatch(text,tokens){const lowered=text.toLocaleLowerCase();let found=null;for(const token of tokens){const start=lowered.indexOf(token.toLocaleLowerCase());if(start>=0&&(!found||start<found.start))found={start,end:start+token.length,token:text.slice(start,start+token.length)}}return found}
function renderDetailContent(text){const content=document.querySelector('#content');content.replaceChildren();const match=viewMode==='active'&&currentQuery?firstTextMatch(text,queryTokens()):null;if(!match){content.append(document.createTextNode(text));return null}content.append(document.createTextNode(text.slice(0,match.start)));const mark=document.createElement('mark');mark.className='search-highlight';mark.textContent=match.token;content.append(mark,document.createTextNode(text.slice(match.end)));requestAnimationFrame(()=>mark.scrollIntoView({block:'center',inline:'nearest'}));return match}
function searchContext(name,text){if(viewMode!=='active'||!currentQuery)return '';const tokens=queryTokens();const nameMatch=tokens.some(token=>name.toLocaleLowerCase().includes(token.toLocaleLowerCase()));const textMatch=tokens.some(token=>text.toLocaleLowerCase().includes(token.toLocaleLowerCase()));const fields=[];if(nameMatch)fields.push('名称');if(textMatch)fields.push('正文');return fields.length?`搜索命中：${fields.join('、')}`:''}
function qaMessage(code){return ({embedding_provider_not_configured:'Embedding 尚未配置，混合模式已回退到词法检索',embedding_provider_unavailable:'Embedding 服务暂时不可用，混合模式已回退到词法检索',embedding_provider_timeout:'Embedding 服务超时，混合模式已回退到词法检索',provider_invalid_config:'AI Provider 配置不完整，请检查运行配置',provider_not_configured:'AI 服务尚未配置',provider_timeout:'AI 服务响应超时，请稍后重试',provider_connection_failed:'AI 服务连接失败，请检查网络后重试',provider_rate_limited:'AI 服务请求过于频繁，请稍后重试',provider_quota_exceeded:'AI 服务额度不足，请检查 Provider 配置',provider_auth_failed:'AI 服务认证失败，请检查 Provider 配置',provider_forbidden:'AI 服务拒绝了请求，请检查 Provider 配置',provider_unavailable:'AI 服务暂时不可用，请稍后重试',provider_malformed_response:'AI 服务返回了无效响应',provider_schema_mismatch:'AI 服务返回格式不受支持',provider_refusal:'AI 服务拒绝生成回答',provider_output_too_large:'AI 服务回答超过允许大小',retrieval_not_ready:'请先为当前材料建立 AI 索引',retrieval_empty:'当前材料中未找到相关内容',source_deleted:'当前材料不可用',qa_generation_failed:'生成回答失败'})[code]||'问答请求失败'}
function setQaBusy(busy){qaInFlight=busy;const active=viewMode==='active'&&qaScopeIds.length>0;document.querySelector('#qa-question').disabled=busy||!active;document.querySelector('#qa-ask').disabled=busy||!active;document.querySelector('#ai-index').disabled=busy||!selectedMaterialId;document.querySelector('#qa-index').disabled=busy||!qaScopeIds.length}
async function refreshQaIndex(){if(viewMode!=='active'||!qaScopeIds.length){document.querySelector('#qa-question').disabled=true;document.querySelector('#qa-ask').disabled=true;return}const context=currentUi();try{const results=await Promise.all(qaScopeIds.map(id=>fetch(`/api/materials/${encodeURIComponent(id)}/ai-index`).then(async response=>response.ok?readJsonObject(response):{status:'unavailable'})));if(!stillCurrent(context))return;const ready=results.length>0&&results.every(data=>data.status==='ready');const empty=results.some(data=>data.status==='empty');document.querySelector('#qa-question').disabled=!ready;document.querySelector('#qa-ask').disabled=!ready;document.querySelector('#ai-index').disabled=false;document.querySelector('#qa-index').disabled=false;setQaStatus(ready?'可以基于选中材料提问':empty?'选中的材料没有可用于问答的正文':'请先建立 AI 索引（选中材料）')}catch(_){if(stillCurrent(context))setQaStatus('AI 索引状态获取失败','error')}}
function renderCitationLocation(text,start,end){const content=document.querySelector('#content');content.replaceChildren();content.append(document.createTextNode(text.slice(0,start)));const mark=document.createElement('mark');mark.className='citation-highlight';mark.textContent=text.slice(start,end);content.append(mark,document.createTextNode(text.slice(end)));requestAnimationFrame(()=>mark.scrollIntoView({block:'center',inline:'nearest'}))}
async function locateCitation(key,fromNavigation=false){const context=currentUi();try{const r=await fetch('/api/qa/citations/'+encodeURIComponent(key));if(!r.ok)throw Error('citation');const data=await readJsonObject(r);if(!stillCurrent(context))return;data.citation_key=key;await openCitation(data,fromNavigation)}catch(_){if(stillCurrent(context))setQaStatus('引用定位失败','error')}}
function renderQaAnswer(payload){const answer=document.querySelector('#qa-answer'),citations=document.querySelector('#qa-citations');if(payload.retrieval?.fallback){setQaStatus(`回答已生成（已回退：${payload.retrieval.fallback_reason||'词法检索'}）`)}answer.textContent=payload.answer_text;citations.replaceChildren();const timeline=document.querySelector('#qa-timeline');timeline.querySelector('.qa-empty')?.remove();const userRow=textNode('article','qa-message qa-message-user','');userRow.append(textNode('div','qa-message-label','你的问题'));userRow.append(textNode('div','qa-message-user',qaLastQuestion));timeline.append(userRow);const row=textNode('article','qa-message qa-message-assistant','');row.append(textNode('div','qa-message-label','AI 回答'));row.append(textNode('div','qa-message-assistant',payload.answer_text));const citeRow=textNode('div','qa-citations','');(payload.citations||[]).forEach(citation=>{const button=document.createElement('button');button.type='button';button.textContent=`引用 ${citation.position}`;button.onclick=()=>locateCitation(citation.citation_key);citeRow.append(button)});row.append(citeRow);timeline.append(row);timeline.scrollTop=timeline.scrollHeight;(payload.citations||[]).forEach((citation,index)=>{const button=document.createElement('button');button.type='button';button.textContent=`引用 ${citation.position}`;button.onclick=()=>locateCitation(citation.citation_key);citations.append(button)})}
async function askQa(){if(qaInFlight||viewMode!=='active'||!qaScopeIds.length)return;const question=document.querySelector('#qa-question').value.trim();if(!question){setQaStatus('请输入问题','error');return}const context={...currentUi(),threadId:qaThreadId,scopeIds:qaScopeIds.slice()};qaLastQuestion=question;qaLastError=null;setQaBusy(true);setQaStatus('正在检索并生成回答');const idempotencyKey=`qa-${crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random()}`;try{const r=await fetch('/api/qa/ask',{method:'POST',headers:{'content-type':'application/json','Idempotency-Key':idempotencyKey},body:JSON.stringify({question,material_ids:context.scopeIds,thread_id:context.threadId,top_k:5,retrieval_mode:document.querySelector('#qa-retrieval-mode').value,allow_retrieval_fallback:document.querySelector('#qa-allow-fallback').checked})});let payload=null;try{payload=await readJsonObject(r)}catch(_){}if(!r.ok){if(stillCurrent(context)){qaLastError=payload&&payload.detail;setQaStatus(qaMessage(qaLastError),'error');document.querySelector('#qa-retry').hidden=false;document.querySelector('#qa-thread-status').textContent='本次提问失败'}return}if(!payload||payload.status!=='succeeded'||typeof payload.answer_text!=='string')throw Error('invalid_qa_response');if(!stillCurrent(context))return;qaThreadId=typeof payload.thread_id==='string'?payload.thread_id:null;context.threadId=qaThreadId;try{sessionStorage.setItem('studybuddy.qa.thread',qaThreadId||'')}catch(_){}renderQaAnswer(payload);document.querySelector('#qa-thread-title').textContent=qaLastQuestion.slice(0,120);document.querySelector('#qa-thread-status').textContent='回答已生成';setQaStatus(payload.retrieval?.fallback?`回答已生成（已回退：${payload.retrieval.fallback_reason||'词法检索'}）`:'回答已生成');toast('问答完成');await refreshQaHistory()}catch(_){if(stillCurrent(context)){qaLastError='qa_generation_failed';setQaStatus('问答请求失败','error');document.querySelector('#qa-retry').hidden=false;document.querySelector('#qa-thread-status').textContent='本次提问失败'}}finally{if(stillCurrent(context))setQaBusy(false)}}
async function indexSelectedForAi(){if(qaInFlight||viewMode!=='active'||!selectedMaterialId)return;const ids=qaScopeIds.length?qaScopeIds:[selectedMaterialId];const context=currentUi();setQaBusy(true);setQaStatus('正在建立 AI 索引');try{for(const id of ids){const response=await fetch(`/api/materials/${encodeURIComponent(id)}/ai-index`,{method:'POST'});if(!response.ok)throw Error('index')}if(stillCurrent(context)){await refreshQaIndex();setQaStatus('AI 索引已建立');toast('AI 索引已建立')}}catch(_){if(stillCurrent(context)){setQaStatus('建立 AI 索引失败','error');document.querySelector('#qa-retry').hidden=false}}finally{if(stillCurrent(context))setQaBusy(false)}}
async function retryQa(){document.querySelector('#qa-retry').hidden=true;document.querySelector('#qa-question').value=qaLastQuestion;await askQa()}
async function loadMaterial(id,preserveQa=false){const generation=++detailGeneration;uiGeneration++;const savedThread=preserveQa?qaThreadId:null;const savedScope=preserveQa?qaScopeIds.slice():[];clearQa(preserveQa);const r=await fetch('/api/materials/'+encodeURIComponent(id));if(generation!==detailGeneration)return;if(!r.ok){announce('材料不可用','error');clearMaterial();return}const x=await r.json();if(generation!==detailGeneration)return;selectedMaterialId=id;selectedMaterial=x;qaScopeMeta.set(id,x);qaThreadId=savedThread;qaScopeIds=savedScope.length?savedScope:[id];renderQaScope();document.querySelector('#rename').disabled=mutationInFlight;document.querySelector('#delete').disabled=mutationInFlight;document.querySelector('#restore').disabled=true;document.querySelector('#download-original').disabled=mutationInFlight;document.querySelector('#export-text').disabled=mutationInFlight;document.querySelector('#open-qa').disabled=mutationInFlight;document.querySelector('#title').textContent=x.original_name;const context=searchContext(x.original_name,x.text||'');document.querySelector('#meta').textContent=`${x.status} · ${x.parser_id} ${x.parser_version} · SHA-256 ${x.source_sha256}${context?' · '+context:''}`;document.querySelector('#warnings').textContent=x.error_code?`error_code: ${x.error_code} · ${x.warnings.join(' ')}`:x.warnings.join(' ');document.querySelector('#spans').textContent=`spans: ${x.spans.length} · ${x.spans.map(s=>s.label).join(', ')}`;updateNavContext();const displayText=x.text||x.spans.filter(s=>s.text.trim()).map(s=>`[${s.label}]\\n${s.text}`).join('\\n\\n')||'没有可显示的正文';renderDetailContent(displayText);writeNavigation(true);await refreshQaIndex();if(savedThread)await loadQaHistory(savedThread)}
async function loadDeletedMaterial(id){const generation=++detailGeneration;uiGeneration++;const r=await fetch('/api/materials/deleted');const items=await r.json();if(generation!==detailGeneration)return;const x=items.find(item=>item.id===id);if(!x){announce('材料不可用','error');clearMaterial();return}selectedMaterialId=id;selectedMaterial=x;document.querySelector('#rename').disabled=true;document.querySelector('#delete').disabled=true;document.querySelector('#restore').disabled=mutationInFlight;document.querySelector('#purge').disabled=mutationInFlight;document.querySelector('#download-original').disabled=true;document.querySelector('#export-text').disabled=true;document.querySelector('#title').textContent=x.original_name;document.querySelector('#meta').textContent=`已删除 · ${x.status} · 删除于 ${x.deleted_at}`;document.querySelector('#warnings').textContent=x.error_code?`error_code: ${x.error_code}`:'';document.querySelector('#spans').textContent=`spans: ${x.span_count}`;document.querySelector('#content').replaceChildren();}
async function purgeSelected(){if(!selectedMaterialId||viewMode!=='deleted'||mutationInFlight)return;if(!window.confirm(`永久删除后不可恢复，且原文件可能被删除。确认永久删除“${selectedMaterial.original_name}”？`))return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id+'/purge',{method:'POST'});if(!r.ok){announce('永久删除失败','error');return}announce('材料已永久删除','success');clearMaterial();await loadList()}catch(_){statusEl.textContent='永久删除失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function restoreSelected(){if(!selectedMaterialId||mutationInFlight)return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id+'/restore',{method:'POST'});if(!r.ok){announce('恢复失败','error');return}const x=await readJsonObject(r);if(typeof x.id!=='string'){throw Error('invalid_restore_response')}announce('材料已恢复','success');clearMaterial();await setView('active');await loadMaterial(x.id)}catch(_){statusEl.textContent='恢复失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function downloadMaterial(kind){if(exportInFlight||!selectedMaterialId||viewMode!=='active')return;const context=currentUi();const filename=kind==='original'?selectedMaterial.original_name:`${selectedMaterial.original_name}.extracted.txt`;const failure=kind==='original'?'原文件下载失败':'正文导出失败';setExportBusy(true);try{const r=await fetch(`/api/materials/${context.id}/${kind}`);if(!r.ok){if(stillCurrent(context))announce(failure,'error');return}await saveDownload(r,filename,false);if(stillCurrent(context))announce(kind==='original'?'原文件下载完成':'正文导出完成','success')}catch(_){if(stillCurrent(context))announce(failure,'error')}finally{setExportBusy(false)}}
function downloadOriginal(){return downloadMaterial('original')}
function exportText(){return downloadMaterial('text')}
async function renameSelected(){if(!selectedMaterialId||viewMode==='deleted'||mutationInFlight)return;const name=window.prompt('输入新的材料名称',selectedMaterial.original_name);if(name===null)return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({original_name:name})});if(!r.ok){announce('重命名失败','error');return}const x=await readJsonObject(r);if(typeof x.id!=='string'){throw Error('invalid_rename_response')}announce('重命名成功','success');await loadList();await loadMaterial(id)}catch(_){statusEl.textContent='重命名失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function deleteSelected(){if(!selectedMaterialId||viewMode==='deleted'||mutationInFlight)return;if(!window.confirm(`确认删除材料“${selectedMaterial.original_name}”？`))return;const id=selectedMaterialId;mutationInFlight=true;listGeneration++;detailGeneration++;setMutationBusy(true);try{const r=await fetch('/api/materials/'+id,{method:'DELETE'});if(!r.ok){await r.json();announce('删除失败','error');return}announce('材料已删除','success');clearMaterial();await loadList()}catch(_){statusEl.textContent='删除失败'}finally{mutationInFlight=false;setMutationBusy(false)}}
async function submitSearch(){if(viewMode==='deleted')return;currentQuery=document.querySelector('#search').value.trim();currentOffset=0;await loadList()}
function setView(mode){uiGeneration++;viewMode=mode;currentOffset=0;document.querySelector('#active-view').classList.toggle('active',mode==='active');document.querySelector('#deleted-view').classList.toggle('active',mode==='deleted');setViewCurrent();filterEl.style.display=mode==='active'?'flex':'none';document.querySelector('#search-form').style.display=mode==='active'?'flex':'none';if(mode==='deleted'){currentQuery='';document.querySelector('#search').value='';document.querySelector('#search-summary').textContent=''}clearMaterial();return loadList()}
document.querySelector('#page-prev').onclick=async()=>{if(currentOffset===0)return;currentOffset=Math.max(0,currentOffset-PAGE_SIZE);await loadList()};document.querySelector('#page-next').onclick=async()=>{if(!currentHasMore)return;currentOffset+=PAGE_SIZE;await loadList()};document.querySelector('#select-all').onclick=()=>{const boxes=[...document.querySelectorAll('.material-select')];const checked=boxes.every(box=>box.checked);boxes.forEach(box=>box.checked=!checked);renderQaScope()};document.querySelector('#export-selected-originals').onclick=()=>exportSelected(true,false);document.querySelector('#export-selected-text').onclick=()=>exportSelected(false,true);document.querySelector('#export-selected-bundle').onclick=()=>exportSelected(true,true);document.querySelector('#rename').onclick=renameSelected;document.querySelector('#delete').onclick=deleteSelected;document.querySelector('#restore').onclick=restoreSelected;document.querySelector('#purge').onclick=purgeSelected;document.querySelector('#download-original').onclick=downloadOriginal;document.querySelector('#export-text').onclick=exportText;document.querySelector('#open-qa').onclick=()=>enterQa(true);document.querySelector('#qa-back-material').onclick=returnToMaterial;document.querySelector('#qa-ask').onclick=askQa;document.querySelector('#qa-retrieval-mode').onchange=()=>{document.querySelector('#qa-retry').hidden=true};document.querySelector('#qa-new-thread').onclick=newQaThread;document.querySelector('#ai-index').onclick=indexSelectedForAi;document.querySelector('#qa-index').onclick=indexSelectedForAi;document.querySelector('#qa-retry').onclick=retryQa;document.querySelector('#qa-scope-current').onclick=setQaScopeToCurrent;document.querySelector('#search-form').onsubmit=async event=>{event.preventDefault();await submitSearch()};document.querySelector('#search-clear').onclick=async()=>{document.querySelector('#search').value='';currentQuery='';currentOffset=0;await loadList()};document.querySelector('#active-view').onclick=()=>setView('active');document.querySelector('#deleted-view').onclick=()=>setView('deleted');window.addEventListener('popstate',()=>handleNavigation());clearMaterial();
function filters(){const labels=['全部','成功','空文件','拒绝','失败'];const statuses=['','success','empty','rejected','failed'];filterEl.replaceChildren();labels.forEach((label,i)=>{const button=document.createElement('button');button.textContent=label;button.dataset.status=statuses[i];button.classList.toggle('active',statuses[i]===currentFilter);button.onclick=async()=>{currentFilter=button.dataset.status;filters();await submitSearch()};filterEl.append(button)})}
function setImportBusy(busy){importInFlight=busy;['file-import','folder-import','file','folder'].forEach(id=>document.querySelector('#'+id).disabled=busy)}
function safeRelativeDisplayPath(file){const fallback=file.name;const value=file.webkitRelativePath||fallback;if(typeof value!=='string'||!value||value.includes('\\\\')||value.startsWith('/')||/^[A-Za-z]:/.test(value)||[...value].some(character=>{const code=character.charCodeAt(0);return code===0||code<32||code===127}))return fallback;const parts=value.split('/');return parts.some(part=>!part||part==='.'||part==='..')?fallback:value}
function renderBatchItems(items,displayPaths){batchItemsEl.replaceChildren();items.forEach((item,index)=>{const row=document.createElement('div');row.className='batch-item';const parts=[displayPaths[index]||item.original_name,item.status];if(item.error_code)parts.push(item.error_code);if(item.warnings&&item.warnings.length)parts.push(item.warnings.join(' '));row.textContent=parts.join(' · ');batchItemsEl.append(row)})}
async function importFiles(files,sourceLabel){if(importInFlight)return;if(!files.length){announce(sourceLabel==='folder'?'请选择一个文件夹':'请选择文件','error');return}const isFolder=sourceLabel==='folder';const isBatch=isFolder||files.length>1;const displayPaths=files.map(safeRelativeDisplayPath);setImportBusy(true);announce(isFolder?`正在导入文件夹：${files.length} 个文件`:`正在导入 ${files.length} 个文件`);try{const body=new FormData();if(isBatch)files.forEach(file=>body.append('files',file,file.name.split(/[\\/]/).pop()));else body.append('file',files[0],files[0].name.split(/[\\/]/).pop());const r=await fetch(isBatch?'/api/materials/batch':'/api/materials',{method:'POST',body});let x=null;try{x=await r.json()}catch(_){}if(!r.ok){announce(isFolder?'文件夹导入失败':'导入失败','error');return}currentOffset=0;if(!isBatch){announce(`导入完成：${x.status}，${x.text_length} 字符`,'success');summaryEl.textContent='';batchItemsEl.replaceChildren();await loadList();if(x.material_id)await loadMaterial(x.material_id);return}announce(`${isFolder?'文件夹':'批量'}导入完成：${x.total} 个文件`,'success');summaryEl.textContent=`总数 ${x.total} · 成功 ${x.success} · 空文件 ${x.empty} · 拒绝 ${x.rejected} · 失败 ${x.failed}`;renderBatchItems(x.items,isFolder?displayPaths:x.items.map(item=>item.original_name));await loadList();const first=x.items.find(item=>item.material_id);if(first)await loadMaterial(first.material_id)}catch(_){announce(isFolder?'文件夹导入失败':'导入失败','error')}finally{setImportBusy(false)}}
document.querySelector('#form').onsubmit=async event=>{event.preventDefault();await importFiles([...document.querySelector('#file').files],'file')};document.querySelector('#folder-import').onclick=async()=>{await importFiles([...document.querySelector('#folder').files],'folder')};filters();loadProviderCapabilities();loadList();refreshQaHistory();handleNavigation(); </script></body></html>"""

app = create_app()
