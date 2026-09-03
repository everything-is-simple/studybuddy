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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .adapters.file_parsers import ParseOptions, parse_file
from .config import AppConfig, config_from_environment
from .db_audit import run_audit
from .diagnostics import DiagnosticError, collect_diagnostics
from .import_locks import acquire_hash_lock, release_hash_lock
from .instance_lock import InstanceLock, InstanceLockError
from .migrations.runner import MigrationError
from .observability import (correlation, emit_event, increment, metrics_snapshot, new_id, observe_http,
                            record_import, reset_correlation, route_class, set_correlation,
                            valid_request_id)
from .providers import (EmbeddingProviderRegistry, ProviderError, ProviderRequest,
                        provider_registry)
from .delivery import execute_report_delivery
from .embedding import EmbeddingError, FakeEmbeddingProvider
from .recovery import reconcile
from .startup_preflight import StartupPreflightError, preflight
from .repository import (VALID_STATUSES, MAX_CONTEXT_TOKENS, connect, assemble_context, create_or_get_revision, utc_now,
                         create_qa_request, fail_qa_operation, get_material, get_material_index_status,
                         get_idempotent_qa_response, get_qa_citation_detail, get_qa_thread_history, get_spans, index_material_revision, list_qa_threads,
                         list_deleted_materials, list_materials,
                         list_materials_page, list_deleted_materials_page, material_state, persist_qa_answer,
                         purge_material, reclaim_stale_qa_operations, reclaim_stale_embedding_operations,
                         create_embedding_index_operation, create_task_backed_embedding_operation,
                         finish_embedding_index_operation, get_operation_task_public, list_operation_tasks_public, rename_material, restore_material, run_chunk_retrieval,
                         request_operation_task_cancel,
                         run_hybrid_retrieval, run_vector_retrieval, save_material_with_extraction, soft_delete_material,
                         validate_citation_key, qa_request_fingerprint, create_deck, get_deck,
                         list_decks, list_cards, get_card, create_card, update_card, confirm_card, transition_card, review_card,
                         create_exercise_set, list_exercise_sets, get_exercise_set, list_exercises, get_exercise,
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
                         create_module_source_link, create_plan_item_source_link, delete_module_source_link,
                         delete_plan_item_source_link, get_study_source_links, list_study_source_candidates,
                         refresh_study_source_links,
                         get_rhythm_settings, save_rhythm_settings,
                         rhythm_summary, study_weekly_trend, list_rhythm_allocations, create_rhythm_allocation,
                         update_rhythm_allocation, delete_rhythm_allocation, list_notes, get_note,
                         create_user_note, update_note, update_note_blocks, create_note_block,
                         update_note_block, delete_note_block, link_note_module, unlink_note_module,
                         create_note_source_link, delete_note_source_link, confirm_note, transition_note,
                         refresh_note_source_links, generate_note_draft, archive_note, update_note_content,
                         create_practice_session, list_practice_sessions, get_practice_session,
                         create_capture_session, upload_capture_asset, get_capture_session, list_capture_sessions,
                         transcribe_capture_session, edit_transcript_draft, confirm_transcript_draft,
                         reject_transcript_draft, create_report_snapshot, get_report_snapshot,
                         list_report_snapshots, export_report_snapshot, list_report_delivery_attempts,
                         start_practice_session, submit_practice_session_item, finish_practice_session,
                         archive_practice_session, get_practice_result, review_exercise_attempt,
                         mark_mistake_from_attempt, add_mistake_feedback, get_mistake_case,
                         list_mistake_cases, redo_mistake_case, archive_mistake_case, list_weak_points,
                         recommend_practice_exercises,
                         create_cram_goal, list_cram_goals, get_cram_goal, transition_cram_goal,
                         create_cram_session, get_cram_result)
from .task_handlers import build_task_runner, embedding_provider_identity
from .task_runner import TaskRunnerError
from .api.registration import ROUTE_MODULES, register_all_routes
from .api.study_generation import register_routes as _register_generation_routes
from .diagnostics import DiagnosticError, collect_diagnostics
from contextlib import asynccontextmanager
from . import lifespan as lifespan_module
from .http_errors import _phase9d_http_status, _provider_http_status
from .http_helpers import _checked_original_path, _download_name, _rename_name
from .services.imports import _item, _process_file, _valid_filename, store_original
from .schemas import *  # Re-exported through app.main for compatibility.


_ROUTE_DEPENDENCY_MODULES = list(ROUTE_MODULES)


def update_route_dependency(name: str, value: object) -> None:
    """Keep legacy app.main monkeypatch injection effective after A2 splitting."""
    globals()[name] = value
    for module in _ROUTE_DEPENDENCY_MODULES:
        if name in module.__dict__:
            setattr(module, name, value)
    from .services import imports as import_service
    if name in import_service.__dict__:
        setattr(import_service, name, value)
    if name in lifespan_module.__dict__:
        setattr(lifespan_module, name, value)


def create_app(config: AppConfig | None = None, *, index_html: str) -> FastAPI:
    @asynccontextmanager
    async def application_lifespan(application):
        async with lifespan_module.lifespan(application):
            yield

    app = FastAPI(title="StudyBuddy", lifespan=application_lifespan)
    app.state.config = config or config_from_environment()
    app.state.ready = False
    app.state.startup_state = "not_started"
    app.state.audit_reasons = ()

    def readiness_snapshot() -> tuple[str, str | None]:
        if not app.state.ready:
            return "not_ready", "service_not_ready"
        if app.state.audit_reasons:
            reason = str(app.state.audit_reasons[0])
            increment("readiness", "degraded", reason)
            return "degraded", reason
        try:
            diagnostic = collect_diagnostics(app.state.config.data_root)
        except DiagnosticError:
            increment("readiness", "degraded", "database_unavailable")
            return "degraded", "database_unavailable"
        if diagnostic["status"] == "degraded":
            reason = str(diagnostic["reasons"][0]) if diagnostic["reasons"] else "diagnostic_degraded"
            increment("readiness", "degraded", reason)
            return "degraded", reason
        increment("readiness", "ready")
        return "ready", None

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
            if "response" in locals():
                response.headers["X-Request-ID"] = request_id
            reset_correlation(tokens)

    context = dict(globals())
    context.update({"readiness_snapshot": readiness_snapshot, "INDEX_HTML": index_html})
    register_all_routes(app, context)
    static_root = Path(__file__).parent / "static"
    if static_root.is_dir():
        app.mount("/app", StaticFiles(directory=static_root, html=True), name="frontend")
    return app
