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
                         validate_citation_key, qa_request_fingerprint, create_deck, get_deck,
                         list_decks, list_cards, create_card, update_card, confirm_card, transition_card, review_card,
                         create_exercise_set, list_exercise_sets, get_exercise_set, list_exercises,
                         create_exercise, update_exercise, confirm_exercise, transition_exercise,
                         list_exercise_attempts, submit_exercise_attempt, create_generation_operation,
                         fail_generation_operation, persist_generated_draft,
                         create_learning_goal, list_learning_goals, get_learning_goal, update_learning_goal,
                         archive_learning_goal, create_knowledge_module, list_knowledge_modules,
                         get_knowledge_module, update_knowledge_module, archive_knowledge_module,
                         create_study_plan, list_study_plans, get_study_plan, update_study_plan,
                         transition_study_plan, create_study_plan_item, update_study_plan_item,
                         archive_study_plan_item, add_study_plan_dependency, remove_study_plan_dependency,
                         append_study_progress_event, list_study_progress_events, study_progress_summary,
                         create_module_source_link, create_plan_item_source_link, get_study_source_links,
                         refresh_study_source_links)
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


class DeckRequest(BaseModel):
    title: str
    description: str = ""


class CardRequest(BaseModel):
    front: str
    back: str
    explanation: str = ""
    tags: list[str] = []
    citations: list[dict[str, object]] = []
    card_type: str = "user_created"
    source_revision: str | None = None


class CardReviewRequest(BaseModel):
    result: str


class ExerciseSetRequest(BaseModel):
    title: str
    description: str = ""


class ExerciseRequest(BaseModel):
    exercise_type: str
    prompt: str
    options: list[str] = []
    answer_key: object
    explanation: str = ""
    citations: list[dict[str, object]] = []
    exercise_kind: str = "user_created"
    source_revision: str | None = None


class ExerciseAttemptRequest(BaseModel):
    answer: object


class ExerciseUpdateRequest(BaseModel):
    prompt: str
    options: list[str] = []
    # The ordinary study UI never receives an answer key.  Omission preserves
    # the internal key for draft-only wording/explanation edits.
    answer_key: object | None = None
    explanation: str = ""
    citations: list[dict[str, object]] = []


class GenerationRequest(BaseModel):
    topic: str
    material_ids: list[str]
    retrieval_mode: str = "lexical"
    allow_retrieval_fallback: bool = True
    count: int = 1
    exercise_type: str | None = None
    source_revision: str | None = None


class StudyGoalRequest(BaseModel):
    title: str
    description: str = ""


class StudyModuleRequest(BaseModel):
    title: str
    description: str = ""


class StudyPlanRequest(BaseModel):
    goal_id: str
    title: str
    description: str = ""


class StudyPlanPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class StudyPlanItemRequest(BaseModel):
    title: str
    description: str = ""
    position: int | None = None
    module_id: str | None = None
    deck_id: str | None = None
    exercise_set_id: str | None = None


class StudyPlanItemPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    position: int | None = None
    module_id: str | None = None
    deck_id: str | None = None
    exercise_set_id: str | None = None


class StudyDependencyRequest(BaseModel):
    predecessor_item_id: str
    successor_item_id: str


class StudyProgressRequest(BaseModel):
    event_type: str
    metadata: dict[str, object] = {}
    event_id: str | None = None


class StudySourceLinkRequest(BaseModel):
    material_id: str
    revision_id: str
    extraction_id: str | None = None
    chunk_id: str
    span_id: str | None = None
    citation_key: str | None = None


def _generated_items(raw: str, *, artifact_kind: str, count: int) -> tuple[list[dict[str, object]], list[list[str]]]:
    """Validate the bounded in-memory structured response; never persist it raw."""
    if len(raw) > 12000:
        raise ValueError("generation_schema_invalid")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("generation_schema_invalid") from None
    if not isinstance(payload, dict) or set(payload) != {"items"} or not isinstance(payload["items"], list):
        raise ValueError("generation_schema_invalid")
    raw_items = payload["items"]
    if len(raw_items) != count:
        raise ValueError("generation_schema_invalid")
    items: list[dict[str, object]] = []
    citation_groups: list[list[str]] = []
    allowed = {"front", "back", "explanation", "tags"} if artifact_kind == "card" else {"exercise_type", "prompt", "options", "answer_key", "explanation"}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("generation_schema_invalid")
        citations = item.get("citations")
        if not isinstance(citations, list) or not citations or any(not isinstance(key, str) or not key for key in citations):
            raise ValueError("generation_schema_invalid")
        public = dict(item)
        public.pop("citations", None)
        if set(public) != allowed:
            raise ValueError("generation_schema_invalid")
        items.append(public)
        citation_groups.append(citations)
    return items, citation_groups


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

    def generate_draft(*, artifact_kind: str, container_id: str, request: GenerationRequest,
                       idempotency_key: str | None) -> dict[str, object]:
        if idempotency_key and (len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key)):
            raise HTTPException(status_code=400, detail="generation_invalid_idempotency_key")
        request_id, _operation_correlation_id = correlation()
        operation: dict[str, object] | None = None
        try:
            with connect(app.state.config.database_path) as connection:
                operation = create_generation_operation(
                    connection, project_id=app.state.config.project_id, artifact_kind=artifact_kind,
                    container_id=container_id, topic=request.topic, material_ids=request.material_ids,
                    retrieval_mode=request.retrieval_mode, allow_fallback=request.allow_retrieval_fallback,
                    count=request.count, exercise_type=request.exercise_type, source_revision=request.source_revision,
                    request_id=request_id, idempotency_key=idempotency_key,
                )
                if operation.get("replay"):
                    return operation
                if request.retrieval_mode == "lexical":
                    retrieval = run_chunk_retrieval(connection, project_id=app.state.config.project_id,
                                                    query=request.topic, material_ids=request.material_ids, top_k=5)
                else:
                    config = app.state.config
                    embedding_provider = None
                    embedding_error_code = "embedding_provider_not_configured"
                    try:
                        embedding_provider = EmbeddingProviderRegistry(
                            config.embedding_provider_id, config.embedding_model_id,
                            model_revision=config.embedding_model_revision, base_url=config.embedding_base_url,
                            api_key=config.embedding_api_key, timeout_seconds=config.embedding_timeout_seconds,
                            max_batch_size=config.embedding_max_batch_size, max_text_chars=config.embedding_max_text_chars,
                            max_dimensions=config.embedding_max_dimensions,
                            max_response_bytes=config.embedding_max_response_bytes,
                            max_retries=config.embedding_max_retries,
                        ).configured_provider()
                    except (ProviderError, EmbeddingError) as error:
                        embedding_error_code = error.code
                        if request.retrieval_mode == "vector" or not request.allow_retrieval_fallback:
                            raise error
                    if request.retrieval_mode == "vector":
                        retrieval = run_vector_retrieval(connection, project_id=app.state.config.project_id,
                                                         query=request.topic, provider=embedding_provider,
                                                         material_ids=request.material_ids, top_k=5)
                    else:
                        retrieval = run_hybrid_retrieval(connection, project_id=app.state.config.project_id,
                                                         query=request.topic, provider=embedding_provider,
                                                         material_ids=request.material_ids, top_k=5,
                                                         allow_fallback=request.allow_retrieval_fallback,
                                                         embedding_error_code=embedding_error_code)
                connection.execute("UPDATE ai_operations SET retrieval_policy_version=?,retrieval_run_id=? WHERE id=? AND status='running'",
                                   (retrieval["policy_version"], retrieval["run_id"], operation["operation_id"]))
                # Do not retain a SQLite write transaction across Provider I/O.
                # The final operation/draft/citation write opens its own atomic transaction.
                connection.commit()
                if retrieval["status"] != "succeeded":
                    raise ValueError(str(retrieval["error_code"]))
                context = assemble_context(connection, project_id=app.state.config.project_id, hits=list(retrieval["hits"]))
                if not context["context_blocks"]:
                    raise ValueError("retrieval_empty")
                config = app.state.config
                provider = provider_registry(config.ai_provider_id, config.ai_model_id) if config.ai_provider_id == "fake" else provider_registry(
                    config.ai_provider_id, config.ai_model_id, base_url=config.ai_base_url, api_key=config.ai_api_key,
                    timeout_seconds=config.ai_timeout_seconds, max_retries=config.ai_max_retries)
                started = time.perf_counter()
                result = provider.configured_provider().generate_answer(ProviderRequest(
                    question=request.topic, context_blocks=list(context["context_blocks"]),
                    max_output_tokens=config.ai_max_output_tokens, max_prompt_chars=config.ai_max_prompt_chars,
                    max_answer_chars=config.ai_max_answer_chars, generation_kind=artifact_kind,
                    generation_count=request.count, exercise_type=request.exercise_type,
                ))
                items, citation_groups = _generated_items(result.answer_text, artifact_kind=artifact_kind, count=request.count)
                if artifact_kind == "exercise" and any(item.get("exercise_type") != request.exercise_type for item in items):
                    raise ValueError("generation_schema_invalid")
                latency_ms = result.latency_ms if result.latency_ms is not None else round((time.perf_counter() - started) * 1000)
                artifact = persist_generated_draft(
                    connection, project_id=app.state.config.project_id, operation_id=str(operation["operation_id"]),
                    artifact_kind=artifact_kind, container_id=container_id, source_revision=str(operation["source_revision"]),
                    items=items, citation_groups=citation_groups, context_blocks=list(context["context_blocks"]),
                    provider_id=result.provider_id, model_id=result.model_id, prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens, latency_ms=latency_ms,
                    provider_request_id=result.provider_request_id, total_tokens=result.total_tokens,
                    finish_reason=result.finish_reason,
                )
                return {"status": "succeeded", "operation_id": operation["operation_id"],
                        "retrieval_run_id": retrieval["run_id"], "artifacts": artifact, "replay": False}
        except (ProviderError, EmbeddingError) as error:
            code = error.code
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_generation_operation(connection, str(operation["operation_id"]), code)
            status = _provider_http_status(code) if isinstance(error, ProviderError) else 503
            raise HTTPException(status_code=status, detail=code) from None
        except ValueError as error:
            code = str(error)
            if operation is not None:
                with connect(app.state.config.database_path) as connection:
                    fail_generation_operation(connection, str(operation["operation_id"]), code)
            status = 404 if code in {"deck_not_found", "exercise_set_not_found", "material_not_found", "source_deleted"} else 409 if code in {"retrieval_not_ready", "retrieval_empty", "generation_in_progress", "generation_idempotency_key_mismatch"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            if operation is not None:
                try:
                    with connect(app.state.config.database_path) as connection:
                        fail_generation_operation(connection, str(operation["operation_id"]), "generation_persist_failed")
                except sqlite3.Error:
                    pass
            raise HTTPException(status_code=500, detail="generation_failed") from None

    def _study_error(error: ValueError, *, default: str, not_found: set[str] | None = None,
                     conflict: set[str] | None = None) -> HTTPException:
        code = str(error)
        if not code or len(code) > 100 or any(ord(char) < 32 for char in code):
            code = default
        if code in (not_found or set()):
            status = 404
        elif code in (conflict or set()):
            status = 409
        else:
            status = 400
        return HTTPException(status_code=status, detail=code)

    @app.get("/api/study/goals")
    def study_goals(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_learning_goals(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/goals", status_code=201)
    def create_study_goal(request: StudyGoalRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_learning_goal(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_goal_create_failed", not_found={"project_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_create_failed") from None

    @app.get("/api/study/goals/{goal_id}")
    def get_study_goal(goal_id: str) -> dict[str, object]:
        if not goal_id or len(goal_id) > 100:
            raise HTTPException(status_code=404, detail="learning_goal_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        if result is None:
            raise HTTPException(status_code=404, detail="learning_goal_not_found")
        return result

    @app.patch("/api/study/goals/{goal_id}")
    def patch_study_goal(goal_id: str, request: StudyGoalRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_goal_update_failed", not_found={"learning_goal_not_found"}, conflict={"learning_goal_archived"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_update_failed") from None

    @app.post("/api/study/goals/{goal_id}/archive")
    def archive_study_goal(goal_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_learning_goal(connection, project_id=app.state.config.project_id, goal_id=goal_id)
        except ValueError as error:
            raise _study_error(error, default="study_goal_archive_failed", not_found={"learning_goal_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_goal_archive_failed") from None

    @app.get("/api/study/modules")
    def study_modules(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_knowledge_modules(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/modules", status_code=201)
    def create_study_module(request: StudyModuleRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_knowledge_module(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_module_create_failed", not_found={"project_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_create_failed") from None

    @app.get("/api/study/modules/{module_id}")
    def get_study_module(module_id: str) -> dict[str, object]:
        if not module_id or len(module_id) > 100:
            raise HTTPException(status_code=404, detail="knowledge_module_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id)
        if result is None:
            raise HTTPException(status_code=404, detail="knowledge_module_not_found")
        return result

    @app.patch("/api/study/modules/{module_id}")
    def patch_study_module(module_id: str, request: StudyModuleRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_module_update_failed", not_found={"knowledge_module_not_found"}, conflict={"knowledge_module_archived"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_update_failed") from None

    @app.post("/api/study/modules/{module_id}/archive")
    def archive_study_module(module_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_knowledge_module(connection, project_id=app.state.config.project_id, module_id=module_id)
        except ValueError as error:
            raise _study_error(error, default="study_module_archive_failed", not_found={"knowledge_module_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_module_archive_failed") from None

    @app.get("/api/study/plans")
    def study_plans(include_archived: bool = False) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_study_plans(connection, project_id=app.state.config.project_id, include_archived=include_archived)

    @app.post("/api/study/plans", status_code=201)
    def create_study_plan_route(request: StudyPlanRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_study_plan(connection, project_id=app.state.config.project_id, goal_id=request.goal_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_plan_create_failed", not_found={"project_not_found"}, conflict={"learning_goal_archived", "study_plan_goal_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_create_failed") from None

    @app.get("/api/study/plans/{plan_id}")
    def get_study_plan_route(plan_id: str) -> dict[str, object]:
        if not plan_id or len(plan_id) > 100:
            raise HTTPException(status_code=404, detail="study_plan_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
        if result is None:
            raise HTTPException(status_code=404, detail="study_plan_not_found")
        return result

    @app.patch("/api/study/plans/{plan_id}")
    def patch_study_plan_route(plan_id: str, request: StudyPlanPatchRequest) -> dict[str, object]:
        if request.title is None and request.description is None:
            raise HTTPException(status_code=400, detail="study_plan_invalid_payload")
        try:
            with connect(app.state.config.database_path) as connection:
                return update_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id, title=request.title, description=request.description)
        except ValueError as error:
            raise _study_error(error, default="study_plan_update_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_update_failed") from None

    def _transition_plan_route(plan_id: str, target: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id, target=target)
        except ValueError as error:
            raise _study_error(error, default="study_plan_transition_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_invalid_state", "study_plan_confirm_required"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_transition_failed") from None

    @app.post("/api/study/plans/{plan_id}/confirm")
    def confirm_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "confirmed")

    @app.post("/api/study/plans/{plan_id}/activate")
    def activate_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "active")

    @app.post("/api/study/plans/{plan_id}/pause")
    def pause_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "paused")

    @app.post("/api/study/plans/{plan_id}/complete")
    def complete_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "completed")

    @app.post("/api/study/plans/{plan_id}/archive")
    def archive_study_plan(plan_id: str) -> dict[str, object]:
        return _transition_plan_route(plan_id, "archived")

    @app.post("/api/study/plans/{plan_id}/items", status_code=201)
    def create_study_plan_item_route(plan_id: str, request: StudyPlanItemRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_create_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_create_failed") from None

    @app.patch("/api/study/plans/{plan_id}/items/{item_id}")
    def patch_study_plan_item_route(plan_id: str, item_id: str, request: StudyPlanItemPatchRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_update_failed", not_found={"study_plan_not_found", "study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_plan_item_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_update_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/archive")
    def archive_study_plan_item_route(plan_id: str, item_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return archive_study_plan_item(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id)
        except ValueError as error:
            raise _study_error(error, default="study_plan_item_archive_failed", not_found={"study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_plan_item_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_item_archive_failed") from None

    @app.post("/api/study/plans/{plan_id}/dependencies", status_code=201)
    def add_study_dependency_route(plan_id: str, request: StudyDependencyRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return add_study_plan_dependency(connection, project_id=app.state.config.project_id, plan_id=plan_id, **request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_plan_dependency_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_dependency_invalid", "study_plan_dependency_cycle", "study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_dependency_failed") from None

    @app.delete("/api/study/plans/{plan_id}/dependencies/{dependency_id}", status_code=204)
    def remove_study_dependency_route(plan_id: str, dependency_id: str) -> Response:
        try:
            with connect(app.state.config.database_path) as connection:
                remove_study_plan_dependency(connection, project_id=app.state.config.project_id, plan_id=plan_id, dependency_id=dependency_id)
        except ValueError as error:
            raise _study_error(error, default="study_plan_dependency_failed", not_found={"study_plan_not_found"}, conflict={"study_plan_dependency_invalid", "study_plan_edit_not_allowed"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_plan_dependency_failed") from None
        return Response(status_code=204)

    @app.get("/api/study/plans/{plan_id}/progress")
    def study_progress_route(plan_id: str, item_id: str | None = None) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                plan = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                if plan is None:
                    raise ValueError("study_plan_not_found")
                return {"plan_id": plan_id, "events": list_study_progress_events(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id), "summary": study_progress_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id)}
        except ValueError as error:
            raise _study_error(error, default="study_progress_read_failed", not_found={"study_plan_not_found"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_progress_read_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/progress", status_code=201)
    def append_study_progress_route(plan_id: str, item_id: str, request: StudyProgressRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                plan = get_study_plan(connection, project_id=app.state.config.project_id, plan_id=plan_id)
                if plan is None:
                    raise ValueError("study_plan_not_found")
                if not any(str(item.get("id")) == item_id for item in plan["items"]):
                    raise ValueError("study_plan_item_not_found")
                event = append_study_progress_event(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, **request.model_dump())
                return {"event": event, "summary": study_progress_summary(connection, project_id=app.state.config.project_id, plan_id=plan_id)}
        except ValueError as error:
            raise _study_error(error, default="study_progress_failed", not_found={"study_plan_not_found", "study_plan_item_not_found"}, conflict={"study_progress_invalid_event", "study_progress_event_duplicate"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_progress_failed") from None

    @app.post("/api/study/modules/{module_id}/sources", status_code=201)
    def create_module_source_route(module_id: str, request: StudySourceLinkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_module_source_link(connection, project_id=app.state.config.project_id, module_id=module_id, payload=request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_source_create_failed", not_found={"knowledge_module_not_found"}, conflict={"knowledge_module_archived", "study_source_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_create_failed") from None

    @app.post("/api/study/plans/{plan_id}/items/{item_id}/sources", status_code=201)
    def create_item_source_route(plan_id: str, item_id: str, request: StudySourceLinkRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_plan_item_source_link(connection, project_id=app.state.config.project_id, plan_id=plan_id, item_id=item_id, payload=request.model_dump())
        except ValueError as error:
            raise _study_error(error, default="study_source_create_failed", not_found={"study_plan_item_not_found"}, conflict={"study_plan_edit_not_allowed", "study_source_invalid"}) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_create_failed") from None

    @app.get("/api/study/sources")
    def study_sources(module_id: str | None = None, plan_id: str | None = None, item_id: str | None = None) -> list[dict[str, object]]:
        if module_id and (plan_id or item_id):
            raise HTTPException(status_code=400, detail="study_source_invalid_scope")
        try:
            with connect(app.state.config.database_path) as connection:
                return get_study_source_links(connection, project_id=app.state.config.project_id, module_id=module_id, plan_id=plan_id, item_id=item_id)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_read_failed") from None

    @app.post("/api/study/sources/refresh")
    def refresh_study_sources() -> dict[str, int]:
        try:
            with connect(app.state.config.database_path) as connection:
                return {"updated": refresh_study_source_links(connection, project_id=app.state.config.project_id)}
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="study_source_refresh_failed") from None

    @app.get("/api/study/decks")
    def study_decks() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_decks(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/decks", status_code=201)
    def create_study_deck(request: DeckRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_deck(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="deck_create_failed") from None

    @app.get("/api/study/decks/{deck_id}")
    def study_deck(deck_id: str) -> dict[str, object]:
        if not deck_id or len(deck_id) > 100: raise HTTPException(status_code=404, detail="deck_not_found")
        with connect(app.state.config.database_path) as connection:
            result = get_deck(connection, project_id=app.state.config.project_id, deck_id=deck_id)
        if result is None: raise HTTPException(status_code=404, detail="deck_not_found")
        return result

    @app.get("/api/study/cards")
    def study_cards(deck_id: str | None = None) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_cards(connection, project_id=app.state.config.project_id, deck_id=deck_id)

    @app.post("/api/study/decks/{deck_id}/cards", status_code=201)
    def create_study_card(deck_id: str, request: CardRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_card(connection, project_id=app.state.config.project_id, deck_id=deck_id, payload=request.model_dump(), card_type=request.card_type, source_revision=request.source_revision)
        except ValueError as error:
            code = str(error); status = 404 if code == "deck_not_found" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_create_failed") from None

    @app.post("/api/study/decks/{deck_id}/generate")
    def generate_study_cards(deck_id: str, request: GenerationRequest,
                             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        if request.exercise_type is not None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="card", container_id=deck_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/cards/{card_id}")
    def update_study_card(card_id: str, request: CardRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_card(connection, project_id=app.state.config.project_id, card_id=card_id, payload=request.model_dump())
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_found" else 409 if code == "card_edit_not_allowed" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_update_failed") from None

    @app.post("/api/study/cards/{card_id}/confirm")
    def confirm_study_card(card_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_card(connection, project_id=app.state.config.project_id, card_id=card_id)
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_found" else 409 if code in {"card_invalid_state", "citation_invalid"} else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_confirm_failed") from None

    @app.post("/api/study/cards/{card_id}/reject")
    def reject_study_card(card_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="rejected")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_reject_failed") from None

    @app.post("/api/study/cards/{card_id}/archive")
    def archive_study_card(card_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_card(connection, project_id=app.state.config.project_id, card_id=card_id, target="archived")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "card_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_archive_failed") from None

    @app.post("/api/study/cards/{card_id}/reviews", status_code=201)
    def review_study_card(card_id: str, request: CardReviewRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return review_card(connection, project_id=app.state.config.project_id, card_id=card_id, result=request.result)
        except ValueError as error:
            code = str(error); status = 404 if code == "card_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="card_review_failed") from None

    @app.get("/api/study/exercise-sets")
    def exercise_sets() -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_exercise_sets(connection, project_id=app.state.config.project_id)

    @app.post("/api/study/exercise-sets", status_code=201)
    def create_study_exercise_set(request: ExerciseSetRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_exercise_set(connection, project_id=app.state.config.project_id, title=request.title, description=request.description)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_set_create_failed") from None

    @app.get("/api/study/exercise-sets/{set_id}")
    def study_exercise_set(set_id: str) -> dict[str, object]:
        with connect(app.state.config.database_path) as connection:
            result = get_exercise_set(connection, project_id=app.state.config.project_id, set_id=set_id)
        if result is None: raise HTTPException(status_code=404, detail="exercise_set_not_found")
        return result

    @app.get("/api/study/exercises")
    def study_exercises(set_id: str | None = None) -> list[dict[str, object]]:
        with connect(app.state.config.database_path) as connection:
            return list_exercises(connection, project_id=app.state.config.project_id, set_id=set_id)

    @app.post("/api/study/exercise-sets/{set_id}/exercises", status_code=201)
    def create_study_exercise(set_id: str, request: ExerciseRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return create_exercise(connection, project_id=app.state.config.project_id, set_id=set_id, exercise_type=request.exercise_type, payload=request.model_dump(), source_revision=request.source_revision, exercise_kind=request.exercise_kind)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_set_not_found" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_create_failed") from None

    @app.post("/api/study/exercise-sets/{set_id}/generate")
    def generate_study_exercises(set_id: str, request: GenerationRequest,
                                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
        if request.exercise_type is None:
            raise HTTPException(status_code=400, detail="generation_invalid_request")
        return generate_draft(artifact_kind="exercise", container_id=set_id, request=request,
                              idempotency_key=idempotency_key)

    @app.patch("/api/study/exercises/{exercise_id}")
    def update_study_exercise(exercise_id: str, request: ExerciseUpdateRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return update_exercise(connection, project_id=app.state.config.project_id,
                                       exercise_id=exercise_id, payload=request.model_dump())
        except ValueError as error:
            code = str(error)
            status = 404 if code == "exercise_not_found" else 409 if code == "exercise_edit_not_allowed" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_update_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/confirm")
    def confirm_study_exercise(exercise_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return confirm_exercise(connection, project_id=app.state.config.project_id, exercise_id=exercise_id)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_not_found" else 409
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_confirm_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/reject")
    def reject_study_exercise(exercise_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_exercise(connection, project_id=app.state.config.project_id,
                                           exercise_id=exercise_id, target="rejected")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "exercise_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_reject_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/archive")
    def archive_study_exercise(exercise_id: str) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return transition_exercise(connection, project_id=app.state.config.project_id,
                                           exercise_id=exercise_id, target="archived")
        except ValueError as error:
            code = str(error)
            raise HTTPException(status_code=404 if code == "exercise_not_found" else 409, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_archive_failed") from None

    @app.get("/api/study/exercises/{exercise_id}/attempts")
    def study_exercise_attempts(exercise_id: str) -> list[dict[str, object]]:
        try:
            with connect(app.state.config.database_path) as connection:
                return list_exercise_attempts(connection, project_id=app.state.config.project_id,
                                              exercise_id=exercise_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="exercise_not_found") from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_attempt_list_failed") from None

    @app.post("/api/study/exercises/{exercise_id}/attempts", status_code=201)
    def attempt_study_exercise(exercise_id: str, request: ExerciseAttemptRequest) -> dict[str, object]:
        try:
            with connect(app.state.config.database_path) as connection:
                return submit_exercise_attempt(connection, project_id=app.state.config.project_id, exercise_id=exercise_id, answer=request.answer)
        except ValueError as error:
            code = str(error); status = 404 if code == "exercise_not_ready" else 400
            raise HTTPException(status_code=status, detail=code) from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail="exercise_attempt_failed") from None

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
<style>*{box-sizing:border-box}body{font-family:system-ui,sans-serif;max-width:1060px;min-width:0;margin:0 auto;padding:32px;color:#17202a;background:#f6f7f9;overflow-wrap:anywhere}main{background:white;border:1px solid #d8dde3;padding:24px;border-radius:8px}h1{margin-top:0}button{background:#1769aa;color:white;border:0;border-radius:4px;padding:9px 14px;cursor:pointer;min-height:40px}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}button:disabled{cursor:not-allowed;opacity:.6}input{margin:12px 0}.status{padding:12px 0;color:#52606d;min-height:24px}.status.error,.error{color:#9a3412}.status.success{color:#166534}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.summary{display:flex;gap:16px;flex-wrap:wrap;color:#52606d}.batch-item{border-top:1px solid #e5e7eb;padding:7px 0}.layout{display:grid;grid-template-columns:320px 1fr;gap:24px;margin-top:24px}.filters{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0 12px}#search-form{display:flex;gap:6px;margin:8px 0}#search{min-width:0;flex:1;margin:0;padding:7px}#search-form button{padding:7px}.filters button{background:#e8edf2;color:#17202a;padding:6px 9px}.filters button.active{background:#1769aa;color:white}.item{display:block;width:100%;text-align:left;border:1px solid #d8dde3;background:#fff;color:#17202a;margin:6px 0}.item:hover{background:#eef5fb}#management{display:flex;gap:8px;margin:14px 0;flex-wrap:wrap}#management button{background:#52606d}.meta{color:#52606d;font-size:14px}.provider-status{border:1px solid #d8dde3;padding:10px;margin:14px 0;background:#fafbfc}.provider-status-error{border-color:#c2410c;background:#fff7ed}.provider-status strong{display:block;margin-bottom:4px}.qa-scope,.qa-history{border:1px solid #d8dde3;padding:10px;margin:10px 0;background:#fafbfc}.qa-scope-list,.qa-history-list{display:grid;gap:5px;max-height:180px;overflow:auto}.qa-scope label{display:flex;gap:7px;align-items:flex-start;overflow-wrap:anywhere}.qa-history button{display:block;width:100%;text-align:left;background:#fff;color:#17202a;border:1px solid #d8dde3;padding:7px}.qa-history button.active{border-color:#1769aa;background:#eef5fb}.qa-message{border-top:1px solid #e5e7eb;padding:10px 0}.qa-message-user{font-weight:600}.qa-message-assistant{white-space:pre-wrap;line-height:1.55}.qa-citation-detail{font-size:13px;color:#52606d;margin-top:5px;overflow-wrap:anywhere}.toast{position:fixed;right:20px;bottom:20px;background:#17202a;color:#fff;padding:10px 14px;border-radius:4px;max-width:min(360px,calc(100vw - 40px));z-index:5}.dialog-backdrop{position:fixed;inset:0;background:rgba(23,32,42,.45);display:grid;place-items:center;padding:20px;z-index:4}.dialog{background:#fff;max-width:560px;width:100%;max-height:80vh;overflow:auto;padding:20px;border:1px solid #d8dde3;border-radius:6px}.search-match{display:inline-block;color:#1769aa;font-size:13px;font-weight:600;margin-top:4px}.search-snippet{display:block;color:#52606d;font-size:14px;line-height:1.45;margin-top:4px;white-space:pre-wrap;overflow-wrap:anywhere}.search-highlight{background:#fff0a8;color:inherit;border-radius:2px;padding:0 1px}.content{white-space:pre-wrap;line-height:1.6;max-height:55vh;overflow:auto;border-top:1px solid #e5e7eb;padding-top:16px}.qa{border-top:1px solid #e5e7eb;margin-top:18px;padding-top:14px}.qa-workspace{display:grid;grid-template-columns:minmax(190px,260px) minmax(0,1fr);gap:14px;margin-top:10px}.qa-panel-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}.qa-panel-heading button{padding:6px 9px}.qa-thread-panel{min-width:0}.qa-thread-panel h4{margin:0 0 4px}.qa-timeline{display:grid;gap:8px;max-height:520px;overflow:auto;padding:4px 2px}.qa-empty{padding:18px 0}.qa-message{border-top:1px solid #e5e7eb;padding:10px 0}.qa-message-user{font-weight:600}.qa-message-assistant{white-space:pre-wrap;line-height:1.55;overflow-wrap:anywhere;min-width:0}.qa-message-failed{border-left:3px solid #c2410c;padding-left:8px}.qa-thread-status{min-height:20px}.qa textarea{box-sizing:border-box;width:100%;min-height:72px;padding:8px;margin:8px 0}.qa-answer{white-space:pre-wrap;line-height:1.55}.qa-citations{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.qa-citations button{background:#e8edf2;color:#17202a;padding:5px 8px}.citation-highlight{background:#fff0a8;color:inherit;border-radius:2px;padding:0 1px}.study{border-top:1px solid #e5e7eb;margin-top:18px;padding-top:14px}.study-grid{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:14px}.study-panel{border:1px solid #d8dde3;padding:12px;background:#fafbfc;min-width:0}.study-panel h4{margin-top:0}.study-list{display:grid;gap:7px;max-height:260px;overflow:auto}.study-list button{background:#fff;color:#17202a;border:1px solid #d8dde3;text-align:left;padding:8px}.study-list button.active{background:#eef5fb;border-color:#1769aa}.study-form{display:grid;gap:7px}.study-form input,.study-form select,.study-form textarea{width:100%;padding:7px;margin:0}.study-detail{white-space:pre-wrap;line-height:1.5}.study-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.study-actions button{padding:6px 9px}.study-state{font-weight:600}.study-draft{color:#9a3412}.study-ready{color:#166534}.study-attempt{border-top:1px solid #d8dde3;padding-top:10px;margin-top:10px}.study-options{display:grid;gap:6px;margin:8px 0}.study-options label{display:flex;gap:6px;align-items:flex-start}.plan{border-top:1px solid #e5e7eb;margin-top:18px;padding-top:14px}.plan-grid{display:grid;grid-template-columns:minmax(200px,280px) minmax(0,1fr);gap:14px}.plan-panel{border:1px solid #d8dde3;padding:12px;background:#fafbfc;min-width:0}.plan-panel h4{margin-top:0}.plan-form{display:grid;gap:7px}.plan-form input,.plan-form select,.plan-form textarea{width:100%;padding:7px;margin:0}.plan-list{display:grid;gap:7px;max-height:240px;overflow:auto}.plan-list button{background:#fff;color:#17202a;border:1px solid #d8dde3;text-align:left;padding:8px}.plan-list button.active{background:#eef5fb;border-color:#1769aa}.plan-items{display:grid;gap:8px;margin-top:12px}.plan-item{border-top:1px solid #e5e7eb;padding:9px 0}.plan-item-fields{display:grid;grid-template-columns:minmax(0,1fr) 90px;gap:6px}.plan-item-fields input{margin:0;padding:7px;width:100%}.plan-actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.plan-actions button{padding:6px 9px}.plan-state{font-weight:600}.plan-draft{color:#9a3412}.plan-active{color:#166534}.plan-warning{color:#9a3412}.plan-progress{border:1px solid #d8dde3;padding:9px;margin-top:12px;background:#fff}.plan-source{font-size:13px;color:#52606d;margin-top:5px;overflow-wrap:anywhere}@media(max-width:700px){body{padding:12px}main{padding:16px}.layout{grid-template-columns:1fr}.qa-workspace{grid-template-columns:1fr}.qa-timeline{max-height:420px;min-width:0}.qa-panel-heading{align-items:flex-start;flex-wrap:wrap}.qa-panel-heading button,.qa-scope button,#management button,#batch-export button{flex:1 1 140px}.qa textarea{min-height:96px}.content{max-height:none;overflow-x:hidden}.dialog-backdrop{padding:12px}.dialog{max-height:calc(100vh - 24px)}} </style></head>
<body><header class="app-header"><h1>StudyBuddy 文件导入与问答</h1><nav aria-label="主要视图"><a href="#materials" id="nav-materials">材料</a><a href="#qa" id="nav-qa">问答</a><a href="#study" id="nav-study">卡片与练习</a><a href="#plans" id="nav-plans">学习计划</a><span id="nav-context" class="meta" aria-live="polite">未选择材料</span></nav></header><main id="main-content"><section id="provider-status" class="provider-status" role="status" aria-live="polite" aria-atomic="true"><strong id="provider-status-title">AI Provider 状态</strong><div id="provider-status-detail" class="meta">正在读取运行配置</div></section><div id="page-status" class="status" role="status" aria-live="polite" aria-atomic="true"></div><form id="form"><label class="sr-only" for="file">选择要导入的文件</label><input id="file" type="file" multiple required><button id="file-import" type="submit">导入文件</button></form><div><label class="sr-only" for="folder">选择要导入的文件夹</label><input id="folder" type="file" webkitdirectory multiple><button id="folder-import" type="button">导入文件夹</button></div><div id="status" class="status" role="status" aria-live="polite" aria-atomic="true"></div><div id="summary" class="summary"></div><div id="batch-items"></div><section class="layout"><aside id="materials-panel" aria-labelledby="materials-heading"><h2 id="materials-heading">材料</h2><div id="views" class="filters" role="group" aria-label="材料视图"><button id="active-view" type="button" aria-current="page">正常材料</button><button id="deleted-view" type="button" aria-current="false">回收站</button></div><form id="search-form" role="search"><label class="sr-only" for="search">搜索材料</label><input id="search" type="search" placeholder="搜索材料" autocomplete="off"><button id="search-submit" type="submit">搜索</button><button id="search-clear" type="button" aria-label="清除输入">清除</button></form><div id="search-summary" class="meta"></div><div id="filters" class="filters"></div><div id="pagination" class="filters"><button id="page-prev" type="button">上一页</button><span id="page-info" class="meta"></span><button id="page-next" type="button">下一页</button></div><div id="batch-export" class="filters"><button id="select-all" type="button">全选当前列表</button><button id="export-selected-originals" type="button">导出选中原文件</button><button id="export-selected-text" type="button">导出选中文本</button><button id="export-selected-bundle" type="button">导出选中全部</button></div><div id="materials"></div></aside><article id="material-detail" aria-labelledby="title"><h2 id="title">选择材料</h2><div id="meta" class="meta" role="status" aria-live="polite"></div><div id="warnings" class="meta" role="alert" aria-live="assertive"></div><div id="spans" class="meta"></div><div id="management"><button id="rename" type="button">重命名</button><button id="delete" type="button">删除</button><button id="restore" type="button">恢复</button><button id="purge" type="button">永久删除</button><button id="download-original" type="button">下载原文件</button><button id="export-text" type="button">导出解析正文</button><button id="open-qa" type="button">进入问答</button></div><div id="content" class="content"></div><section id="qa" class="qa" aria-labelledby="qa-title"><div class="qa-panel-heading"><h3 id="qa-title">材料问答</h3><button id="qa-back-material" type="button">返回材料详情</button></div><div id="qa-status" class="meta" role="status" aria-live="polite" aria-atomic="true">选择已建立 AI 索引的正常材料后可提问</div><div class="qa-workspace"><aside class="qa-history" aria-labelledby="qa-history-title"><div class="qa-panel-heading"><strong id="qa-history-title">问答对话</strong><button id="qa-new-thread" type="button">新建对话</button></div><div id="qa-history-status" class="meta" role="status" aria-live="polite">加载中</div><div id="qa-history-list" class="qa-history-list"></div></aside><div class="qa-thread-panel"><h4 id="qa-thread-title">新对话</h4><div id="qa-thread-status" class="meta">尚未发送问题</div><div class="qa-scope"><strong>问答材料范围</strong><div id="qa-scope-summary" class="meta">默认使用当前材料</div><div id="qa-scope-list" class="qa-scope-list"></div><button id="qa-scope-current" type="button">使用当前材料</button><label for="qa-retrieval-mode">检索模式</label><select id="qa-retrieval-mode"><option value="lexical">词法</option><option value="vector">向量</option><option value="hybrid">混合</option></select><label><input id="qa-allow-fallback" type="checkbox" checked>混合模式允许词法回退</label><button id="qa-index" type="button" disabled>建立选中材料索引</button></div><div id="qa-timeline" class="qa-timeline"><div id="qa-empty" class="meta">新对话尚未有消息</div></div><label for="qa-question">问题</label><textarea id="qa-question" maxlength="1000" placeholder="输入与材料内容匹配的问题" disabled></textarea><div><button id="ai-index" type="button" disabled>建立当前材料索引</button><button id="qa-ask" type="button" disabled>提问</button><button id="qa-retry" type="button" hidden>重试</button></div><div id="qa-answer" class="qa-answer" hidden></div><div id="qa-citations" class="qa-citations" hidden></div></div></div></section><section id="study" class="study" aria-labelledby="study-title"><div class="qa-panel-heading"><h3 id="study-title">卡片与练习</h3><button id="study-use-material" type="button">使用当前材料</button></div><div id="study-status" class="meta" role="status" aria-live="polite">选择正常材料后可建立学习内容</div><div class="study-grid"><aside class="study-panel" aria-label="学习集合"><h4>学习集合</h4><div class="study-form"><label for="deck-title">卡片组名称</label><input id="deck-title" maxlength="200"><button id="deck-create" type="button">新建卡片组</button><div id="deck-list" class="study-list" aria-label="卡片组列表"></div><label for="exercise-set-title">练习集名称</label><input id="exercise-set-title" maxlength="200"><button id="exercise-set-create" type="button">新建练习集</button><div id="exercise-set-list" class="study-list" aria-label="练习集列表"></div></div></aside><div class="study-panel"><h4 id="study-detail-title">选择卡片组或练习集</h4><div id="study-detail" class="study-detail"></div><div id="study-workspace"></div></div></div></section><section id="plans" class="plan" aria-labelledby="plans-title"><div class="qa-panel-heading"><h3 id="plans-title">学习计划</h3><button id="plan-refresh" type="button">刷新计划</button></div><div id="plan-status" class="meta" role="status" aria-live="polite" aria-atomic="true">创建目标后开始计划</div><div class="plan-grid"><aside class="plan-panel" aria-label="学习计划对象"><h4>目标与模块</h4><div class="plan-form"><label for="plan-goal-title">目标名称</label><input id="plan-goal-title" maxlength="400"><button id="plan-goal-create" type="button">新建目标</button><div id="plan-goal-list" class="plan-list" aria-label="目标列表"></div><label for="plan-module-title">模块名称</label><input id="plan-module-title" maxlength="400"><button id="plan-module-create" type="button">新建模块</button><div id="plan-module-list" class="plan-list" aria-label="模块列表"></div><label for="plan-title">计划名称</label><input id="plan-title" maxlength="400"><button id="plan-create" type="button">新建计划草稿</button><div id="plan-list" class="plan-list" aria-label="计划列表"></div></div></aside><div class="plan-panel"><h4 id="plan-detail-title">选择计划</h4><div id="plan-detail" class="plan-detail"></div><div id="plan-workspace"></div></div></div></section></article></section></main><div id="qa-dialog-root"></div><div id="toast-root" aria-live="polite" aria-atomic="true"></div><div id="alert-root" role="alert" aria-live="assertive" aria-atomic="true"></div>
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
let studyKind='card',studyContainerId=null,studyArtifactId=null,studyArtifact=null,studyGeneration=0,studyBusy=false;
function setStudyStatus(message,kind='meta'){const node=document.querySelector('#study-status');node.className=kind==='error'?'meta error':'meta';node.setAttribute('role',kind==='error'?'alert':'status');node.textContent=message}
function studyCurrent(){return {generation:studyGeneration,material:selectedMaterialId,view:viewMode,kind:studyKind,container:studyContainerId}}
function studyStillCurrent(context){return context.generation===studyGeneration&&context.material===selectedMaterialId&&context.view===viewMode&&context.kind===studyKind&&context.container===studyContainerId}
async function studyJson(url,options){const response=await fetch(url,options);let payload=null;try{payload=await readJsonObject(response)}catch(_){}if(!response.ok||!payload)throw Object.assign(Error('study_request_failed'),{code:payload?.detail||'study_request_failed'});return payload}
function setStudyBusy(busy){studyBusy=busy;['deck-create','exercise-set-create','study-generate','study-save','study-confirm','study-reject','study-archive','study-review','study-attempt'].forEach(id=>{const node=document.querySelector('#'+id);if(node)node.disabled=busy})}
function studyCitationButton(citation){const button=document.createElement('button');button.type='button';button.textContent=citation.status==='valid'?'查看引用':'来源不可用';button.disabled=citation.status!=='valid';button.onclick=async()=>{if(citation.status!=='valid'){setStudyStatus('引用来源不可用','error');return}try{await loadMaterial(citation.material_id,true);const quote=typeof citation.quote==='string'?citation.quote:'';const text=selectedMaterial?.text||'';const start=text.indexOf(quote);if(start>=0)renderCitationLocation(text,start,start+quote.length);setStudyStatus('已定位引用来源')}catch(_){setStudyStatus('引用来源不可用','error')}};return button}
function renderStudyArtifact(artifact){studyArtifactId=artifact.id;studyArtifact=artifact;const detail=document.querySelector('#study-detail');const workspace=document.querySelector('#study-workspace');detail.replaceChildren();workspace.replaceChildren();document.querySelector('#study-detail-title').textContent=studyKind==='card'?'卡片详情':'练习详情';detail.append(textNode('div',`study-state study-${artifact.status}`,artifact.status==='draft'?'草稿':'已就绪'));if(studyKind==='card'){detail.append(textNode('div','',`正面：${artifact.front}\n背面：${artifact.back}\n${artifact.explanation?'说明：'+artifact.explanation:''}`));const form=document.createElement('div');form.className='study-form';const front=document.createElement('textarea');front.id='study-card-front';front.value=artifact.front;front.setAttribute('aria-label','卡片正面');const back=document.createElement('textarea');back.id='study-card-back';back.value=artifact.back;back.setAttribute('aria-label','卡片背面');const explanation=document.createElement('textarea');explanation.id='study-card-explanation';explanation.value=artifact.explanation||'';explanation.setAttribute('aria-label','卡片说明');form.append(textNode('label','', '卡片正面'),front,textNode('label','', '卡片背面'),back,textNode('label','', '卡片说明'),explanation);workspace.append(form)}else{detail.append(textNode('div','',`题型：${artifact.exercise_type}\n题目：${artifact.prompt}\n${artifact.explanation?'说明：'+artifact.explanation:''}`));if(artifact.status==='draft'){const form=document.createElement('div');form.className='study-form';const prompt=document.createElement('textarea');prompt.id='study-exercise-prompt';prompt.value=artifact.prompt;prompt.setAttribute('aria-label','练习题目');const explanation=document.createElement('textarea');explanation.id='study-exercise-explanation';explanation.value=artifact.explanation||'';explanation.setAttribute('aria-label','练习说明');form.append(textNode('label','', '练习题目'),prompt,textNode('label','', '练习说明'),explanation);workspace.append(form)}if(artifact.status==='ready'){const attempt=document.createElement('div');attempt.className='study-attempt';attempt.append(textNode('strong','', '作答'));if(artifact.exercise_type==='multiple_choice'||artifact.exercise_type==='true_false'){const options=document.createElement('div');options.className='study-options';(artifact.options||[]).forEach((option,index)=>{const label=document.createElement('label'),input=document.createElement('input');input.type='radio';input.name='study-answer';input.value=String(artifact.exercise_type==='true_false'?index===0:index);label.append(input,textNode('span','',option));options.append(label)});attempt.append(options)}else{const answer=document.createElement('textarea');answer.id='study-answer-text';answer.setAttribute('aria-label','简答答案');attempt.append(answer)}const submit=document.createElement('button');submit.id='study-attempt';submit.type='button';submit.textContent='提交答案';submit.onclick=submitStudyAttempt;attempt.append(submit);workspace.append(attempt)}}const citations=document.createElement('div');citations.className='study-actions';(artifact.citations||[]).forEach(citation=>citations.append(studyCitationButton(citation)));detail.append(citations);const actions=document.createElement('div');actions.className='study-actions';if(artifact.status==='draft'){for(const [id,label,handler] of [['study-save','保存编辑',saveStudyEdit],['study-confirm','确认就绪',()=>studyTransition('confirm')],['study-reject','拒绝草稿',()=>studyTransition('reject')]]){const button=document.createElement('button');button.id=id;button.type='button';button.textContent=label;button.onclick=handler;actions.append(button)}}if(['draft','ready','rejected','stale'].includes(artifact.status)){const button=document.createElement('button');button.id='study-archive';button.type='button';button.textContent='归档';button.onclick=()=>studyTransition('archive');actions.append(button)}if(studyKind==='card'&&artifact.status==='ready'){for(const result of ['again','hard','good','easy']){const button=document.createElement('button');button.type='button';button.textContent=result;button.onclick=()=>reviewStudyCard(result);actions.append(button)}}workspace.append(actions)}
function renderStudyList(items,kind){const root=document.querySelector(kind==='card'?'#deck-list':'#exercise-set-list');root.replaceChildren();items.forEach(item=>{const button=document.createElement('button');button.type='button';button.className=studyKind===kind&&studyContainerId===item.id?'active':'';button.textContent=`${item.title} · ${kind==='card'?(item.cards?.length||0):(item.exercises?.length||item.exercise_count||0)} 项`;button.onclick=()=>selectStudyContainer(kind,item.id);root.append(button)})}
async function refreshStudyLists(){try{const [decks,sets]=await Promise.all([fetch('/api/study/decks').then(r=>r.json()),fetch('/api/study/exercise-sets').then(r=>r.json())]);if(Array.isArray(decks))renderStudyList(decks,'card');if(Array.isArray(sets))renderStudyList(sets,'exercise')}catch(_){setStudyStatus('学习集合加载失败','error')}}
async function selectStudyContainer(kind,id){const generation=++studyGeneration;studyKind=kind;studyContainerId=id;studyArtifactId=null;setStudyStatus('正在加载学习内容');try{const data=await studyJson(kind==='card'?`/api/study/decks/${encodeURIComponent(id)}`:`/api/study/exercise-sets/${encodeURIComponent(id)}`);if(generation!==studyGeneration)return;renderStudyList((await fetch(kind==='card'?'/api/study/decks':'/api/study/exercise-sets').then(r=>r.json()))||[],kind);const items=kind==='card'?data.cards:data.exercises;const workspace=document.querySelector('#study-workspace');workspace.replaceChildren();const generate=document.createElement('div');generate.className='study-form';const topic=document.createElement('input');topic.id='study-topic';topic.maxLength=500;topic.placeholder='输入生成主题';topic.setAttribute('aria-label','生成主题');const count=document.createElement('select');count.id='study-count';[1,2,3].forEach(value=>{const option=document.createElement('option');option.value=String(value);option.textContent=`生成 ${value} 项`;count.append(option)});generate.append(topic,count);if(kind==='exercise'){const type=document.createElement('select');type.id='study-exercise-type';[['multiple_choice','选择题'],['true_false','判断题'],['short_answer','简答题']].forEach(([value,label])=>{const option=document.createElement('option');option.value=value;option.textContent=label;type.append(option)});generate.append(type)}const button=document.createElement('button');button.id='study-generate';button.type='button';button.textContent='生成草稿';button.onclick=generateStudyDraft;generate.append(button);workspace.append(generate);const list=document.createElement('div');list.className='study-list';(items||[]).forEach(item=>{const itemButton=document.createElement('button');itemButton.type='button';itemButton.textContent=`${item.status==='draft'?'草稿':'已就绪'} · ${kind==='card'?item.front:item.prompt}`;itemButton.onclick=()=>renderStudyArtifact(item);list.append(itemButton)});workspace.append(list);document.querySelector('#study-detail-title').textContent=kind==='card'?data.title:data.title;document.querySelector('#study-detail').replaceChildren(textNode('div','meta',items?.length?'选择一项查看或生成新草稿':'尚无内容，可生成草稿'));setStudyStatus('已加载学习内容')}catch(_){if(generation===studyGeneration)setStudyStatus('学习内容加载失败','error')}}
async function createStudyContainer(kind){const input=document.querySelector(kind==='card'?'#deck-title':'#exercise-set-title');const title=input.value.trim();if(!title){setStudyStatus('请输入集合名称','error');return}setStudyBusy(true);try{const data=await studyJson(kind==='card'?'/api/study/decks':'/api/study/exercise-sets',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title})});input.value='';await refreshStudyLists();await selectStudyContainer(kind,data.id);toast('学习集合已创建')}catch(_){setStudyStatus('创建学习集合失败','error')}finally{setStudyBusy(false)}}
async function generateStudyDraft(){if(studyBusy||!studyContainerId||!selectedMaterialId||viewMode!=='active')return;const topic=document.querySelector('#study-topic')?.value.trim();if(!topic){setStudyStatus('请输入生成主题','error');return}const context=studyCurrent();setStudyBusy(true);setStudyStatus('正在生成草稿');const body={topic,material_ids:[selectedMaterialId],count:Number(document.querySelector('#study-count')?.value||1),retrieval_mode:'lexical'};if(studyKind==='exercise')body.exercise_type=document.querySelector('#study-exercise-type').value;try{const data=await studyJson(studyKind==='card'?`/api/study/decks/${studyContainerId}/generate`:`/api/study/exercise-sets/${studyContainerId}/generate`,{method:'POST',headers:{'content-type':'application/json','Idempotency-Key':`study-${crypto.randomUUID?crypto.randomUUID():Date.now()}`},body:JSON.stringify(body)});if(!studyStillCurrent(context))return;setStudyStatus(`已生成 ${data.artifacts.length} 个草稿`);toast('草稿已生成');await selectStudyContainer(studyKind,studyContainerId);if(data.artifacts[0])renderStudyArtifact(data.artifacts[0]);setStudyStatus(`已生成 ${data.artifacts.length} 个草稿`)}catch(error){if(studyStillCurrent(context))setStudyStatus('生成草稿失败，可重试','error')}finally{setStudyBusy(false)}}
async function saveStudyEdit(){if(!studyArtifactId||studyBusy)return;const context=studyCurrent();setStudyBusy(true);try{let body;if(studyKind==='card')body={front:document.querySelector('#study-card-front').value,back:document.querySelector('#study-card-back').value,explanation:document.querySelector('#study-card-explanation').value,tags:[],citations:[]};else body={prompt:document.querySelector('#study-exercise-prompt').value,options:studyArtifact?.options||[],explanation:document.querySelector('#study-exercise-explanation').value,citations:[]};const data=await studyJson(studyKind==='card'?`/api/study/cards/${studyArtifactId}`:`/api/study/exercises/${studyArtifactId}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(studyStillCurrent(context)){renderStudyArtifact(data);setStudyStatus('草稿已保存')}}catch(_){if(studyStillCurrent(context))setStudyStatus('保存草稿失败','error')}finally{setStudyBusy(false)}}
async function studyTransition(action){if(!studyArtifactId||studyBusy)return;const context=studyCurrent();setStudyBusy(true);try{const path=studyKind==='card'?`/api/study/cards/${studyArtifactId}/${action}`:`/api/study/exercises/${studyArtifactId}/${action}`;const data=await studyJson(path,{method:'POST'});if(studyStillCurrent(context)){renderStudyArtifact(data);await selectStudyContainer(studyKind,studyContainerId);renderStudyArtifact(data);setStudyBusy(false);setStudyStatus(action==='confirm'?'内容已确认就绪':action==='reject'?'草稿已拒绝':'内容已归档')}}catch(_){if(studyStillCurrent(context))setStudyStatus('状态更新失败','error')}finally{setStudyBusy(false)}}
async function reviewStudyCard(result){try{await studyJson(`/api/study/cards/${studyArtifactId}/reviews`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({result})});setStudyStatus('复习记录已保存')}catch(_){setStudyStatus('复习记录失败','error')}}
async function submitStudyAttempt(){const artifact=studyArtifactId;if(!artifact)return;let answer;const text=document.querySelector('#study-answer-text');if(text)answer=text.value;else{const checked=document.querySelector('input[name="study-answer"]:checked');if(!checked){setStudyStatus('请选择答案','error');return}answer=checked.value==='true'?true:Number(checked.value)}try{const data=await studyJson(`/api/study/exercises/${artifact}/attempts`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({answer})});setStudyStatus(data.grading_status==='pending_review'?'简答已提交，等待复核':data.is_correct?'回答正确':'回答不正确')}catch(_){setStudyStatus('提交答案失败','error')}}
function enterStudy(){document.querySelector('#study').scrollIntoView({block:'start'});document.querySelector('#nav-study').setAttribute('aria-current','page');document.querySelector('#nav-plans').setAttribute('aria-current','false');document.querySelector('#nav-materials').setAttribute('aria-current','false');document.querySelector('#nav-qa').setAttribute('aria-current','false');setStudyStatus(selectedMaterialId&&viewMode==='active'?'可使用当前材料生成草稿':'请先选择正常材料');refreshStudyLists()}
let planGoalId=null,planModuleId=null,planId=null,planGeneration=0,planBusy=false;
function setPlanStatus(message,kind='meta'){const node=document.querySelector('#plan-status');node.className=kind==='error'?'meta error':'meta';node.setAttribute('role',kind==='error'?'alert':'status');node.textContent=message}
async function planJson(url,options){const response=await fetch(url,options);let payload=null;try{payload=await response.json()}catch(_){}if(!response.ok||payload===null)throw Object.assign(Error('plan_request_failed'),{code:payload&&typeof payload==='object'&&!Array.isArray(payload)?payload.detail:'plan_request_failed'});return payload}
function setPlanBusy(busy){planBusy=busy;['plan-goal-create','plan-module-create','plan-create','plan-item-add','plan-dependency-add','plan-confirm','plan-activate','plan-pause','plan-complete','plan-archive','plan-refresh'].forEach(id=>{const node=document.querySelector('#'+id);if(node)node.disabled=busy})}
function renderPlanButtons(rootId,items,selectedId,label){const root=document.querySelector(rootId);root.replaceChildren();(items||[]).forEach(item=>{const button=document.createElement('button');button.type='button';button.className=item.id===selectedId?'active':'';button.textContent=label(item);button.onclick=()=>{if(rootId==='#plan-goal-list'){planGoalId=item.id;renderPlanButtons('#plan-goal-list',planGoals,planGoalId,labelGoal)}else if(rootId==='#plan-module-list'){planModuleId=item.id;renderPlanButtons('#plan-module-list',planModules,planModuleId,labelModule)}else{selectPlan(item.id)}};root.append(button)})}
let planGoals=[],planModules=[],planPlans=[];
function labelGoal(item){return `${item.title} · ${item.status==='active'?'进行中':'已归档'}`}
function labelModule(item){return `${item.title} · ${item.status==='active'?'可用':'已归档'}`}
function labelPlan(item){return `${item.title} · ${item.status}`}
function renderPlanLists(){renderPlanButtons('#plan-goal-list',planGoals,planGoalId,labelGoal);renderPlanButtons('#plan-module-list',planModules,planModuleId,labelModule);renderPlanButtons('#plan-list',planPlans,planId,labelPlan)}
function planCurrent(){return planGeneration}
function storedPlanId(){try{return localStorage.getItem('studybuddy.plan.id')}catch(_){return null}}
function rememberPlanId(id){try{if(id)localStorage.setItem('studybuddy.plan.id',id);else localStorage.removeItem('studybuddy.plan.id')}catch(_){} }
async function refreshPlans(){const generation=++planGeneration;try{const values=await Promise.all([planJson('/api/study/goals'),planJson('/api/study/modules'),planJson('/api/study/plans')]);if(generation!==planCurrent())return;planGoals=Array.isArray(values[0])?values[0]:[];planModules=Array.isArray(values[1])?values[1]:[];planPlans=Array.isArray(values[2])?values[2]:[];if(planGoalId&&!planGoals.some(item=>item.id===planGoalId))planGoalId=null;if(planModuleId&&!planModules.some(item=>item.id===planModuleId))planModuleId=null;if(!planId)planId=storedPlanId();if(planId&&!planPlans.some(item=>item.id===planId)){planId=null;rememberPlanId(null)}renderPlanLists();if(planId)await selectPlan(planId);else setPlanStatus(planGoals.length?'选择或创建计划草稿':'创建目标后开始计划')}catch(_){if(generation===planCurrent())setPlanStatus('计划加载失败，可重试','error')}}
function planText(value){return typeof value==='string'?value:''}
function renderPlanDetail(plan){const detail=document.querySelector('#plan-detail'),workspace=document.querySelector('#plan-workspace');detail.replaceChildren();workspace.replaceChildren();document.querySelector('#plan-detail-title').textContent=plan.title;const state=document.createElement('div');state.className=`plan-state plan-${plan.status}`;state.textContent=`状态：${plan.status}`;detail.append(state);const progress=plan.progress||{};const summary=document.createElement('div');summary.className='plan-progress';summary.textContent=`进度：${progress.completed_count||0}/${progress.item_count||0} · ${Math.round((progress.completion_ratio||0)*100)}% · 待处理 ${progress.pending_count||0} · 进行中 ${progress.in_progress_count||0}`;detail.append(summary);if((progress.source_warning_count||0)>0){const warning=document.createElement('div');warning.className='plan-warning';warning.textContent=`来源警告：${progress.source_warning_count} 项来源不可用或已过期`;detail.append(warning)}const sourceLinks=plan.source_links||[];const sourceBox=document.createElement('div');sourceBox.className='plan-source';sourceBox.textContent=sourceLinks.length?sourceLinks.map(link=>`来源：${link.status}`).join(' · '):'计划项来源：未添加';detail.append(sourceBox);const actions=document.createElement('div');actions.className='plan-actions';const actionMap={draft:[['plan-confirm','确认草稿','confirmed']],confirmed:[['plan-activate','激活计划','active']],active:[['plan-pause','暂停计划','paused'],['plan-complete','完成计划','completed']],paused:[['plan-activate','恢复计划','active'],['plan-complete','完成计划','completed']]};(actionMap[plan.status]||[]).forEach(([id,label,target])=>{const button=document.createElement('button');button.id=id;button.type='button';button.textContent=label;button.onclick=()=>transitionPlan(target);actions.append(button)});if(plan.status!=='archived'){const archive=document.createElement('button');archive.id='plan-archive';archive.type='button';archive.textContent='归档计划';archive.onclick=()=>transitionPlan('archived');actions.append(archive)}detail.append(actions);const form=document.createElement('div');form.className='plan-form';if(['draft','confirmed'].includes(plan.status)){const title=document.createElement('input');title.id='plan-edit-title';title.value=plan.title;title.setAttribute('aria-label','计划名称');const description=document.createElement('textarea');description.id='plan-edit-description';description.value=plan.description||'';description.setAttribute('aria-label','计划描述');const save=document.createElement('button');save.id='plan-save';save.type='button';save.textContent='保存计划编辑';save.onclick=()=>savePlanEdit();form.append(textNode('label','', '计划名称'),title,textNode('label','', '计划描述'),description,save)}workspace.append(form);if(['draft','confirmed'].includes(plan.status)){const itemForm=document.createElement('div');itemForm.className='plan-form';itemForm.append(textNode('strong','', '添加学习项'));const title=document.createElement('input');title.id='plan-item-title';title.placeholder='学习项名称';title.setAttribute('aria-label','学习项名称');const moduleSelect=document.createElement('select');moduleSelect.id='plan-item-module';const empty=document.createElement('option');empty.value='';empty.textContent='不绑定模块';moduleSelect.append(empty);planModules.forEach(module=>{if(module.status==='active'){const option=document.createElement('option');option.value=module.id;option.textContent=module.title;moduleSelect.append(option)}});const add=document.createElement('button');add.id='plan-item-add';add.type='button';add.textContent='添加学习项';add.onclick=()=>addPlanItem();itemForm.append(title,moduleSelect,add);workspace.append(itemForm)}const itemsRoot=document.createElement('div');itemsRoot.className='plan-items';(plan.items||[]).forEach(item=>{const row=document.createElement('div');row.className='plan-item';row.dataset.id=item.id;const fields=document.createElement('div');fields.className='plan-item-fields';const title=document.createElement('input');title.value=item.title;title.setAttribute('aria-label',`学习项 ${item.title}`);title.disabled=!['draft','confirmed'].includes(plan.status)||['completed','skipped','archived'].includes(item.status);const position=document.createElement('input');position.type='number';position.min='0';position.value=item.position;position.setAttribute('aria-label','学习项排序');position.disabled=title.disabled;fields.append(title,position);row.append(textNode('div','',`${item.status} · ${item.module_id?'已绑定模块':'无来源模块'}`),fields);const rowActions=document.createElement('div');rowActions.className='plan-actions';if(!title.disabled){const save=document.createElement('button');save.type='button';save.textContent='保存学习项';save.onclick=()=>updatePlanItem(item.id,title.value,position.value);rowActions.append(save);const archive=document.createElement('button');archive.type='button';archive.textContent='归档学习项';archive.onclick=()=>archivePlanItem(item.id);rowActions.append(archive)}if(plan.status==='active'&&!['completed','skipped','archived'].includes(item.status)){const complete=document.createElement('button');complete.type='button';complete.className='plan-item-complete';complete.textContent='完成学习项';complete.onclick=()=>progressPlanItem(item.id,'completed');rowActions.append(complete)}row.append(rowActions);itemsRoot.append(row)});workspace.append(itemsRoot);if(['draft','confirmed'].includes(plan.status)&&plan.items.length>=2){const depForm=document.createElement('div');depForm.className='plan-form';depForm.append(textNode('strong','', '添加前置依赖'));const predecessor=document.createElement('select');predecessor.id='plan-dependency-predecessor';const successor=document.createElement('select');successor.id='plan-dependency-successor';plan.items.filter(item=>item.status!=='archived').forEach(item=>{for(const select of [predecessor,successor]){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;select.append(option)}});const depButton=document.createElement('button');depButton.id='plan-dependency-add';depButton.type='button';depButton.textContent='添加依赖';depButton.onclick=()=>addPlanDependency();depForm.append(predecessor,successor,depButton);workspace.append(depForm)}
}
async function selectPlan(id){const generation=++planGeneration;planId=id;rememberPlanId(id);renderPlanLists();setPlanStatus('正在加载计划');try{const plan=await planJson(`/api/study/plans/${encodeURIComponent(id)}`);if(generation!==planCurrent())return;renderPlanDetail(plan);setPlanStatus('计划已加载')}catch(_){if(generation===planCurrent())setPlanStatus('计划加载失败，可重试','error')}}
async function runPlanMutation(action,success){if(planBusy)return;setPlanBusy(true);try{await action();await refreshPlans();setPlanStatus(success)}catch(_){setPlanStatus('计划操作失败，可重试','error')}finally{setPlanBusy(false)}}
async function createPlanGoal(){const title=document.querySelector('#plan-goal-title').value.trim();if(!title){setPlanStatus('请输入目标名称','error');return}await runPlanMutation(async()=>{const result=await planJson('/api/study/goals',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title})});planGoalId=result.id;document.querySelector('#plan-goal-title').value=''},'目标已创建')}
async function createPlanModule(){const title=document.querySelector('#plan-module-title').value.trim();if(!title){setPlanStatus('请输入模块名称','error');return}await runPlanMutation(async()=>{const result=await planJson('/api/study/modules',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title})});planModuleId=result.id;document.querySelector('#plan-module-title').value=''},'模块已创建')}
async function createPlanDraft(){const title=document.querySelector('#plan-title').value.trim();if(!title||!planGoalId){setPlanStatus(!planGoalId?'请先选择目标':'请输入计划名称','error');return}await runPlanMutation(async()=>{const result=await planJson('/api/study/plans',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({goal_id:planGoalId,title})});planId=result.id;rememberPlanId(planId);document.querySelector('#plan-title').value=''},'计划草稿已创建')}
async function savePlanEdit(){const title=document.querySelector('#plan-edit-title')?.value;const description=document.querySelector('#plan-edit-description')?.value;await runPlanMutation(()=>planJson(`/api/study/plans/${encodeURIComponent(planId)}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({title,description})}),'计划编辑已保存')}
async function transitionPlan(target){await runPlanMutation(()=>planJson(`/api/study/plans/${encodeURIComponent(planId)}/${target==='confirmed'?'confirm':target==='active'?'activate':target}` ,{method:'POST'}),target==='confirmed'?'计划草稿已确认':target==='active'?'计划已激活':target==='paused'?'计划已暂停':target==='completed'?'计划已完成':'计划已归档')}
async function addPlanItem(){const title=document.querySelector('#plan-item-title')?.value.trim();if(!title){setPlanStatus('请输入学习项名称','error');return}const module_id=document.querySelector('#plan-item-module')?.value||null;await runPlanMutation(async()=>{await planJson(`/api/study/plans/${encodeURIComponent(planId)}/items`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({title,module_id})})},'学习项已添加')}
async function updatePlanItem(id,title,position){await runPlanMutation(()=>planJson(`/api/study/plans/${encodeURIComponent(planId)}/items/${encodeURIComponent(id)}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({title,position:Number(position)})}),'学习项已保存')}
async function archivePlanItem(id){await runPlanMutation(()=>planJson(`/api/study/plans/${encodeURIComponent(planId)}/items/${encodeURIComponent(id)}/archive`,{method:'POST'}),'学习项已归档')}
async function addPlanDependency(){const predecessor_item_id=document.querySelector('#plan-dependency-predecessor')?.value;const successor_item_id=document.querySelector('#plan-dependency-successor')?.value;if(!predecessor_item_id||!successor_item_id||predecessor_item_id===successor_item_id){setPlanStatus('依赖关系无效','error');return}try{await planJson(`/api/study/plans/${encodeURIComponent(planId)}/dependencies`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({predecessor_item_id,successor_item_id})});await selectPlan(planId);setPlanStatus('依赖已添加')}catch(error){setPlanStatus(error.code==='study_plan_dependency_cycle'?'检测到依赖环，未保存':'依赖添加失败，可重试','error')}}
async function progressPlanItem(id,event_type){await runPlanMutation(()=>planJson(`/api/study/plans/${encodeURIComponent(planId)}/items/${encodeURIComponent(id)}/progress`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event_type})}),'学习进度已保存')}
function enterPlans(){document.querySelector('#plans').scrollIntoView({block:'start'});document.querySelector('#nav-plans').setAttribute('aria-current','page');document.querySelector('#nav-materials').setAttribute('aria-current','false');document.querySelector('#nav-qa').setAttribute('aria-current','false');document.querySelector('#nav-study').setAttribute('aria-current','false');refreshPlans()}

document.querySelector('#study-use-material').onclick=()=>{if(selectedMaterialId&&viewMode==='active'){enterStudy();setStudyStatus(`当前材料：${selectedMaterial.original_name}`)}else setStudyStatus('请先选择正常材料','error')};document.querySelector('#nav-plans').onclick=event=>{event.preventDefault();enterPlans()};document.querySelector('#plan-refresh').onclick=()=>refreshPlans();document.querySelector('#plan-goal-create').onclick=()=>createPlanGoal();document.querySelector('#plan-module-create').onclick=()=>createPlanModule();document.querySelector('#plan-create').onclick=()=>createPlanDraft();document.querySelector('#deck-create').onclick=()=>createStudyContainer('card');document.querySelector('#exercise-set-create').onclick=()=>createStudyContainer('exercise');document.querySelector('#nav-study').onclick=event=>{event.preventDefault();enterStudy()};document.querySelector('#page-prev').onclick=async()=>{if(currentOffset===0)return;currentOffset=Math.max(0,currentOffset-PAGE_SIZE);await loadList()};document.querySelector('#page-next').onclick=async()=>{if(!currentHasMore)return;currentOffset+=PAGE_SIZE;await loadList()};document.querySelector('#select-all').onclick=()=>{const boxes=[...document.querySelectorAll('.material-select')];const checked=boxes.every(box=>box.checked);boxes.forEach(box=>box.checked=!checked);renderQaScope()};document.querySelector('#export-selected-originals').onclick=()=>exportSelected(true,false);document.querySelector('#export-selected-text').onclick=()=>exportSelected(false,true);document.querySelector('#export-selected-bundle').onclick=()=>exportSelected(true,true);document.querySelector('#rename').onclick=renameSelected;document.querySelector('#delete').onclick=deleteSelected;document.querySelector('#restore').onclick=restoreSelected;document.querySelector('#purge').onclick=purgeSelected;document.querySelector('#download-original').onclick=downloadOriginal;document.querySelector('#export-text').onclick=exportText;document.querySelector('#open-qa').onclick=()=>enterQa(true);document.querySelector('#qa-back-material').onclick=returnToMaterial;document.querySelector('#qa-ask').onclick=askQa;document.querySelector('#qa-retrieval-mode').onchange=()=>{document.querySelector('#qa-retry').hidden=true};document.querySelector('#qa-new-thread').onclick=newQaThread;document.querySelector('#ai-index').onclick=indexSelectedForAi;document.querySelector('#qa-index').onclick=indexSelectedForAi;document.querySelector('#qa-retry').onclick=retryQa;document.querySelector('#qa-scope-current').onclick=setQaScopeToCurrent;document.querySelector('#search-form').onsubmit=async event=>{event.preventDefault();await submitSearch()};document.querySelector('#search-clear').onclick=async()=>{document.querySelector('#search').value='';currentQuery='';currentOffset=0;await loadList()};document.querySelector('#active-view').onclick=()=>setView('active');document.querySelector('#deleted-view').onclick=()=>setView('deleted');window.addEventListener('popstate',()=>handleNavigation());clearMaterial();
function filters(){const labels=['全部','成功','空文件','拒绝','失败'];const statuses=['','success','empty','rejected','failed'];filterEl.replaceChildren();labels.forEach((label,i)=>{const button=document.createElement('button');button.textContent=label;button.dataset.status=statuses[i];button.classList.toggle('active',statuses[i]===currentFilter);button.onclick=async()=>{currentFilter=button.dataset.status;filters();await submitSearch()};filterEl.append(button)})}
function setImportBusy(busy){importInFlight=busy;['file-import','folder-import','file','folder'].forEach(id=>document.querySelector('#'+id).disabled=busy)}
function safeRelativeDisplayPath(file){const fallback=file.name;const value=file.webkitRelativePath||fallback;if(typeof value!=='string'||!value||value.includes('\\\\')||value.startsWith('/')||/^[A-Za-z]:/.test(value)||[...value].some(character=>{const code=character.charCodeAt(0);return code===0||code<32||code===127}))return fallback;const parts=value.split('/');return parts.some(part=>!part||part==='.'||part==='..')?fallback:value}
function renderBatchItems(items,displayPaths){batchItemsEl.replaceChildren();items.forEach((item,index)=>{const row=document.createElement('div');row.className='batch-item';const parts=[displayPaths[index]||item.original_name,item.status];if(item.error_code)parts.push(item.error_code);if(item.warnings&&item.warnings.length)parts.push(item.warnings.join(' '));row.textContent=parts.join(' · ');batchItemsEl.append(row)})}
async function importFiles(files,sourceLabel){if(importInFlight)return;if(!files.length){announce(sourceLabel==='folder'?'请选择一个文件夹':'请选择文件','error');return}const isFolder=sourceLabel==='folder';const isBatch=isFolder||files.length>1;const displayPaths=files.map(safeRelativeDisplayPath);setImportBusy(true);announce(isFolder?`正在导入文件夹：${files.length} 个文件`:`正在导入 ${files.length} 个文件`);try{const body=new FormData();if(isBatch)files.forEach(file=>body.append('files',file,file.name.split(/[\\/]/).pop()));else body.append('file',files[0],files[0].name.split(/[\\/]/).pop());const r=await fetch(isBatch?'/api/materials/batch':'/api/materials',{method:'POST',body});let x=null;try{x=await r.json()}catch(_){}if(!r.ok){announce(isFolder?'文件夹导入失败':'导入失败','error');return}currentOffset=0;if(!isBatch){announce(`导入完成：${x.status}，${x.text_length} 字符`,'success');summaryEl.textContent='';batchItemsEl.replaceChildren();await loadList();if(x.material_id)await loadMaterial(x.material_id);return}announce(`${isFolder?'文件夹':'批量'}导入完成：${x.total} 个文件`,'success');summaryEl.textContent=`总数 ${x.total} · 成功 ${x.success} · 空文件 ${x.empty} · 拒绝 ${x.rejected} · 失败 ${x.failed}`;renderBatchItems(x.items,isFolder?displayPaths:x.items.map(item=>item.original_name));await loadList();const first=x.items.find(item=>item.material_id);if(first)await loadMaterial(first.material_id)}catch(_){announce(isFolder?'文件夹导入失败':'导入失败','error')}finally{setImportBusy(false)}}
document.querySelector('#form').onsubmit=async event=>{event.preventDefault();await importFiles([...document.querySelector('#file').files],'file')};document.querySelector('#folder-import').onclick=async()=>{await importFiles([...document.querySelector('#folder').files],'folder')};filters();loadProviderCapabilities();loadList();refreshQaHistory();refreshPlans();handleNavigation(); </script></body></html>"""

app = create_app()
