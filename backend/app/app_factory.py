"""应用工厂模块 - FastAPI 应用创建和配置。

本模块负责创建和配置完整的 FastAPI 应用实例，包括：
- 配置加载和分层合并（环境 > 设置 > 检测）
- 生命周期管理（启动预检、实例锁、任务运行器）
- HTTP 中间件（请求 ID、可观测性跟踪）
- API 路由注册（所有端点通过 api.registration 模块加载）
- 静态文件服务（前端 SPA）

主要组件：
- create_app(config, index_html): 主入口，创建 FastAPI 实例
- update_route_dependency(name, value): 为 API 模块注入依赖
- readiness_snapshot(): 就绪状态检查（ready/degraded/not_ready）
- refresh_config(): 重新加载配置（UI 更新后无需重启）

生命周期：
1. 启动预检：data_root 存在性、数据库 schema 版本、实例锁
2. 数据库迁移（如需）
3. 后台任务运行器启动（嵌入和 AI 生成任务）
4. 就绪状态设置为 ready
5. 关闭：任务运行器停止、实例锁释放

可观测性：
- 每个 HTTP 请求分配 request_id 和 operation_id
- 计量指标：http_requests(按 method/route/status)
- 直方图：HTTP 请求时长
- 事件日志：http_request, startup_complete, shutdown_begin 等

就绪状态：
- ready: 服务正常，数据库完整，无审计警告
- degraded: 服务运行但有警告（审计问题、迁移挂起等）
- not_ready: 服务未就绪（启动中或预检失败）

配置刷新：
- refresh_config() 重新加载 settings.json
- 无需重启服务，下次请求生效
- 仅刷新存储设置和检测结果，不重读环境变量

路由注册：
- 所有 API 路由通过 api.registration.register_all_routes() 加载
- 包含 15 个 API 模块：材料、AI、学习、系统等
- 静态文件挂载到 /app（前端 SPA）

关联模块：
- config: 配置加载
- capabilities: 能力解析
- lifespan: 生命周期管理
- api.registration: 路由注册中心
- observability: 可观测性基础设施
"""
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
from .capabilities import capability_snapshot, resolve_config
from .capability_detect import detect_all
from .config import AppConfig, config_from_environment
from .local_settings import SettingsError, clear_settings, load_settings, public_settings, save_settings
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
from .connection_test import (
    ConnectionTestError,
    provider_llm_connection_test,
    provider_embedding_connection_test,
    smtp_connection_test,
    feishu_connection_test,
)
from .schemas.connection_test import (
    ProviderConnectionTestRequest,
    EmailConnectionTestRequest,
)
from .schemas.local_settings import LocalSettingsClearRequest, LocalSettingsRequest
from .services.imports import _item, _process_file, _valid_filename, store_original
from .schemas import *  # Re-exported through app.main for compatibility.


_ROUTE_DEPENDENCY_MODULES = list(ROUTE_MODULES)


def update_route_dependency(name: str, value: object) -> None:
    """保持传统 app.main monkeypatch 注入在 A2 拆分后的有效性。
    
    用于在 API 模块和服务中更新全局依赖项（如测试中注入 mock）。
    
    Args:
        name: 变量名（如 'provider_registry'）
        value: 新值（如 mock 对象）
    
    注意:
        这是为了保持与历史代码兼容，新代码应通过 FastAPI 依赖注入
    """
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
    """创建和配置 FastAPI 应用实例。
    
    执行流程：
    1. 初始化 FastAPI 实例，注册生命周期管理器
    2. 加载配置：环境变量 > 存储设置 > 自动检测
    3. 检测本地组件（OCR/ASR，如启用）
    4. 注册 HTTP 中间件（可观测性跟踪）
    5. 注册所有 API 路由
    6. 挂载静态文件服务（前端 SPA）
    
    Args:
        config: 可选的配置实例（默认从环境加载）
        index_html: 前端 index.html 内容（用于 / 路由）
    
    Returns:
        完全配置的 FastAPI 应用实例
    
    应用状态（app.state）：
        base_config: 环境配置（不可变）
        detection: 本地组件检测结果（只读）
        config: 合并后的有效配置（可通过 refresh_config 刷新）
        ready: 就绪状态（bool）
        startup_state: 启动阶段（'not_started'/'running'/'completed'）
        audit_reasons: 审计警告列表（空表示无问题）
    
    HTTP 中间件：
        - 为每个请求生成 request_id 和 operation_id
        - 记录请求指标和耗时
        - 在响应头中返回 X-Request-ID
    
    就绪状态：
        - 通过 readiness_snapshot() 检查
        - ready: 服务正常
        - degraded: 服务运行但有警告
        - not_ready: 服务未就绪
    
    配置刷新：
        - refresh_config() 重新加载 settings.json
        - 无需重启，UI 配置变更立即生效
    
    示例：
        >>> app = create_app(index_html="<html>...</html>")
        >>> # 使用 uvicorn 启动：
        >>> # uvicorn app.main:app --host 0.0.0.0 --port 8787
    
    注意：
        - 检测只运行一次（每进程），结果缓存在 app.state.detection
        - 检测失败不阻止启动，detection 设为 None
        - 生命周期管理在 lifespan_module 中实现
    """
    @asynccontextmanager
    async def application_lifespan(application):
        async with lifespan_module.lifespan(application):
            yield

    app = FastAPI(title="StudyBuddy", lifespan=application_lifespan)
    base_config = config or config_from_environment()
    app.state.base_config = base_config
    # Detection runs once per process; it is read-only and does not touch the network.
    try:
        app.state.detection = detect_all(
            ocr_model_root=base_config.ocr_model_root,
            asr_runtime=base_config.asr_runtime_path,
            asr_model=base_config.asr_model_path,
            preferred_base=base_config.data_root,
        ) if base_config.auto_detect_enabled else None
    except OSError:
        app.state.detection = None
    app.state.config = resolve_config(base_config, detection=app.state.detection)
    app.state.ready = False
    app.state.startup_state = "not_started"
    app.state.audit_reasons = ()

    def refresh_config() -> AppConfig:
        """Re-layer stored settings so UI configuration applies without a restart."""
        app.state.config = resolve_config(app.state.base_config, detection=app.state.detection)
        return app.state.config

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
    context.update({"readiness_snapshot": readiness_snapshot, "INDEX_HTML": index_html,
                    "refresh_config": refresh_config})
    register_all_routes(app, context)
    static_root = Path(__file__).parent / "static"
    if static_root.is_dir():
        app.mount("/app", StaticFiles(directory=static_root, html=True), name="frontend")
    return app
