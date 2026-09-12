"""共享迁移辅助工具。

本模块提供迁移系统使用的底层工具函数：
- 时间戳生成（UTC ISO 格式）
- 数据库对象枚举（表和虚拟表）
- 表列信息查询
- 迁移历史表创建
- 基线完整性验证

基线验证（_baseline_complete）：
- 验证数据库是否具有当前 Schema 版本应有的所有表和关键列
- 用于判断旧数据库是否可以作为基线采用（adopt）
- 按版本递增检查（v9, v10, v11, v12, v13 各自添加的表）
- 检查核心列集合（materials, extractions, qa_threads 等）

核心表分组：
- required_core: 基础表（projects, materials, extractions, text_spans）
- required_ai: AI 相关表（版本递增添加）
- 搜索索引: material_search, chunks_search（虚拟表）

版本递增规则：
- v9+: 学习计划表（learning_goals, study_plans 等）
- v10+: 笔记和节奏表（notes, rhythm_settings 等）
- v11+: 练习反馈表（practice_sessions, mistake_cases 等）
- v12+: 采集报告表（capture_sessions, report_snapshots 等）
- v13+: 后台任务表（operation_tasks, operation_task_attempts）

注意：
- 这些函数以下划线开头，仅供迁移模块内部使用
- 新迁移应使用 _columns() 检查列存在性，避免重复 ALTER
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    """生成 UTC ISO 格式时间戳（用于迁移历史记录）。"""
    return datetime.now(timezone.utc).isoformat()


def _objects(connection: sqlite3.Connection) -> set[str]:
    """枚举数据库中的所有表和虚拟表。
    
    Returns:
        表名集合（包含 sqlite_sequence 等内部表）
    """
    return {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    )}


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """查询表的列名集合。
    
    Args:
        connection: SQLite 连接
        table: 表名
    
    Returns:
        列名集合（表不存在时返回空集合）
    """
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _create_history(connection: sqlite3.Connection) -> None:
    """创建迁移历史表（幂等）。
    
    表结构：
    - version: 版本号（主键）
    - name: 迁移名称
    - applied_at: 应用时间（UTC ISO）
    """
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )


def _baseline_complete(connection: sqlite3.Connection, current_schema_version: int) -> bool:
    """验证数据库基线是否完整（是否可作为旧数据库采用）。
    
    检查项：
    - 当前版本应有的所有表都存在
    - 关键表的核心列齐全
    - 搜索索引虚拟表存在
    
    Args:
        connection: SQLite 连接
        current_schema_version: 目标 Schema 版本
    
    Returns:
        True 表示基线完整，可以作为已迁移到该版本的数据库
    
    注意:
        - 按版本递增检查各阶段添加的表
        - 用于 migrate() 中的旧数据库采用逻辑
    """
    objects = _objects(connection)
    required_core = {"projects", "materials", "extractions", "text_spans"}
    required_ai = {
        "material_revisions", "chunks", "chunk_spans", "embeddings",
        "retrieval_runs", "retrieval_hits", "qa_citations",
        "ai_operations", "qa_threads", "qa_messages", "qa_answers",
        "study_decks", "study_cards", "card_citations", "card_reviews",
        "exercise_sets", "exercises", "exercise_citations", "exercise_attempts",
    }
    if current_schema_version >= 9:
        required_ai |= {
            "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
            "study_plan_dependencies", "study_progress_events", "module_source_links",
            "plan_item_source_links",
        }
    if current_schema_version >= 10:
        required_ai |= {
            "notes", "note_blocks", "note_module_links", "note_block_source_links",
            "rhythm_settings", "rhythm_allocations",
        }
    if current_schema_version >= 11:
        required_ai |= {
            "practice_sessions", "practice_session_items", "exercise_attempt_reviews",
            "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals",
        }
    if current_schema_version >= 12:
        required_ai |= {
            "capture_sessions", "transcript_drafts", "transcript_segments",
            "report_snapshots", "report_delivery_attempts",
        }
    if current_schema_version >= 13:
        required_ai |= {"operation_tasks", "operation_task_attempts"}
    if not (required_core | required_ai | {"material_search", "chunks_search"}).issubset(objects):
        return False
    if not {
        "id", "project_id", "original_name", "source_sha256", "stored_path",
        "media_type", "created_at", "updated_at", "deleted_at",
    }.issubset(_columns(connection, "materials")):
        return False
    if not {
        "id", "material_id", "parser_id", "parser_version", "status", "text",
        "warnings_json", "created_at", "error_code",
    }.issubset(_columns(connection, "extractions")):
        return False
    if not {
        "id", "project_id", "title", "created_at", "updated_at", "archived_at",
    }.issubset(_columns(connection, "qa_threads")):
        return False
    if not {
        "id", "thread_id", "role", "content", "created_at", "ai_operation_id",
    }.issubset(_columns(connection, "qa_messages")):
        return False
    if not {
        "provider_request_id", "total_tokens", "finish_reason", "idempotency_key", "retrieval_run_id",
    }.issubset(_columns(connection, "ai_operations")):
        return False
    if not {
        "model_revision", "updated_at", "vector_encoding", "source_revision",
    }.issubset(_columns(connection, "embeddings")):
        return False
    if not {"exercise_kind"}.issubset(_columns(connection, "exercises")):
        return False
    if current_schema_version >= 9:
        if not {
            "id", "project_id", "title", "description", "status", "created_at", "updated_at", "archived_at",
        }.issubset(_columns(connection, "learning_goals")):
            return False
        if not {
            "id", "project_id", "goal_id", "title", "description", "status", "user_edited", "created_at",
            "updated_at", "confirmed_at", "activated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "study_plans")):
            return False
        if not {
            "id", "plan_id", "project_id", "title", "description", "position", "status", "user_edited",
            "created_at", "updated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "study_plan_items")):
            return False
    if current_schema_version >= 10:
        if not {
            "id", "project_id", "title", "status", "provenance", "user_edited", "generation_operation_id",
            "created_at", "updated_at", "confirmed_at", "archived_at",
        }.issubset(_columns(connection, "notes")):
            return False
        if not {
            "id", "note_id", "project_id", "position", "block_kind", "content", "provenance",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "note_blocks")):
            return False
        if not {"id", "project_id", "note_id", "module_id"}.issubset(_columns(connection, "note_module_links")):
            return False
        if not {
            "id", "project_id", "note_id", "note_block_id", "material_id", "revision_id", "extraction_id",
            "chunk_id", "span_id", "citation_key", "status", "created_at", "updated_at",
        }.issubset(_columns(connection, "note_block_source_links")):
            return False
        if not {
            "id", "project_id", "plan_id", "cadence", "timezone", "period_start", "target_minutes",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "rhythm_settings")):
            return False
        if not {
            "id", "project_id", "plan_id", "item_id", "local_date", "planned_minutes", "created_at", "updated_at",
        }.issubset(_columns(connection, "rhythm_allocations")):
            return False
    if current_schema_version >= 11:
        if not {
            "id", "project_id", "session_kind", "cram_goal_id", "status", "title",
            "duration_seconds", "timezone", "local_date", "started_at", "deadline_at",
            "finished_at", "created_at", "updated_at",
        }.issubset(_columns(connection, "practice_sessions")):
            return False
        if not {
            "id", "session_id", "project_id", "exercise_id", "position", "exercise_type",
            "prompt", "options_json", "explanation_snapshot", "exercise_kind", "source_material_id",
            "source_revision", "source_extraction_id", "source_chunk_id", "source_span_id", "citation_key",
            "citation_status", "answer_key_json", "created_at", "updated_at",
        }.issubset(_columns(connection, "practice_session_items")):
            return False
        if not {"session_id", "session_item_id", "submission_key", "submission_sequence"}.issubset(
            _columns(connection, "exercise_attempts")
        ):
            return False
        if not {
            "id", "project_id", "attempt_id", "exercise_id", "decision", "feedback",
            "reviewer_kind", "created_at", "reviewed_at",
        }.issubset(_columns(connection, "exercise_attempt_reviews")):
            return False
        if not {
            "id", "project_id", "exercise_id", "exercise_revision_fingerprint", "status",
            "origin", "created_at", "updated_at", "fixed_at", "archived_at",
        }.issubset(_columns(connection, "mistake_cases")):
            return False
        if not {
            "id", "project_id", "mistake_case_id", "attempt_id", "origin", "reason_code",
            "source_revision", "source_status", "created_at",
        }.issubset(_columns(connection, "mistake_occurrences")):
            return False
        if not {
            "id", "project_id", "mistake_case_id", "event_kind", "content", "provenance", "created_at",
        }.issubset(_columns(connection, "mistake_feedback_events")):
            return False
        if not {
            "id", "project_id", "title", "target_date", "timezone", "target_exercise_count", "status",
            "plan_id", "plan_item_id", "created_at", "updated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "cram_goals")):
            return False
    if current_schema_version >= 12:
        if not {
            "id", "project_id", "status", "asset_kind", "material_id", "original_name",
            "media_type", "source_status", "created_at", "updated_at", "confirmed_at",
            "rejected_at", "archived_at",
        }.issubset(_columns(connection, "capture_sessions")):
            return False
        if not {
            "id", "project_id", "capture_session_id", "operation_id", "status", "text",
            "language", "quality_status", "edited_by_user", "created_at", "updated_at",
        }.issubset(_columns(connection, "transcript_drafts")):
            return False
        if not {
            "id", "draft_id", "project_id", "ordinal", "text", "confidence", "quality",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "transcript_segments")):
            return False
        if not {
            "id", "project_id", "report_kind", "timezone", "period_start", "period_end",
            "status", "content_version", "aggregation_fingerprint", "safe_payload_json",
            "markdown_content", "error_code", "created_at", "updated_at", "ready_at", "archived_at",
        }.issubset(_columns(connection, "report_snapshots")):
            return False
        if not {
            "id", "project_id", "report_id", "channel", "mode", "target_label",
            "content_fingerprint", "idempotency_key_fingerprint", "status", "error_code",
            "retry_of", "created_at", "finished_at",
        }.issubset(_columns(connection, "report_delivery_attempts")):
            return False
        if "capture_session_id" not in _columns(connection, "ai_operations"):
            return False
    if current_schema_version >= 13:
        if not {
            "id", "project_id", "operation_id", "parent_task_id", "task_kind", "status",
            "input_fingerprint", "idempotency_key_fingerprint", "progress_percent",
            "stage_code", "retry_count", "max_retries", "error_code", "created_at",
            "updated_at", "started_at", "finished_at", "cancel_requested_at",
        }.issubset(_columns(connection, "operation_tasks")):
            return False
        if not {
            "id", "task_id", "project_id", "attempt_number", "status",
            "progress_percent", "stage_code", "error_code", "lease_started_at",
            "lease_expires_at", "heartbeat_at", "created_at", "started_at", "finished_at",
        }.issubset(_columns(connection, "operation_task_attempts")):
            return False
    if current_schema_version >= 15:
        if not {"due_at", "interval_days"}.issubset(_columns(connection, "study_cards")):
            return False
        if "idempotency_key" not in _columns(connection, "card_reviews"):
            return False
    return True


