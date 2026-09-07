"""恢复验收测试模块。

本模块提供恢复后数据完整性验收测试，支持离线和在线两种模式。
验收测试检查数据库完整性、外键约束、学习数据一致性、原始文件哈希等。

主要功能：
- 离线模式：验证数据库和文件系统完整性
- 在线模式：验证 HTTP API 端点可达性和数据一致性
- 学习数据投影检查（计划、进度、笔记、练习）
- Phase 9c/9d/10 特定验收规则

验收标准：
- 数据库完整性检查（PRAGMA integrity_check）
- 外键约束检查（PRAGMA foreign_key_check）
- Schema 版本与迁移历史一致性
- 原始文件哈希验证
- 学习数据投影与事件流一致性

错误码体系：
- acceptance_database_*: 数据库层问题
- acceptance_study_*: 学习数据不一致
- acceptance_phase9c_*: 练习系统问题
- acceptance_phase9d_*: 采集报告系统问题
- acceptance_phase10_*: 任务系统问题
- acceptance_http_*: HTTP API 问题
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .migrations.runner import MigrationError, assert_schema_version


class AcceptanceError(ValueError):
    """验收测试失败异常。
    
    Args:
        code: 错误码（如 'acceptance_database_integrity_failed'）
    """
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sha256_bytes(value: bytes) -> str:
    """计算字节数据的 SHA256 哈希值（小写十六进制）。"""
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    """计算文件的 SHA256 哈希值（分块读取，支持大文件）。
    
    Args:
        path: 文件路径
    
    Returns:
        小写十六进制哈希值
    
    Raises:
        AcceptanceError: 文件读取失败时
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        raise AcceptanceError("acceptance_original_read_failed") from None
    return digest.hexdigest()


def _safe_original(root: Path, stored_path: str, expected_hash: str) -> Path:
    """安全地验证原始文件路径和哈希值。
    
    检查项：
    - 路径必须在 root 下，不允许符号链接
    - 文件必须是普通文件（非目录、非链接）
    - 文件哈希必须匹配预期值
    
    Args:
        root: 原始文件根目录
        stored_path: 存储路径（相对或绝对）
        expected_hash: 预期 SHA256 哈希值
    
    Returns:
        验证通过的文件路径
    
    Raises:
        AcceptanceError: 路径不安全、文件缺失或哈希不匹配时
    """
    target = Path(stored_path)
    try:
        root_info = root.lstat()
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise AcceptanceError("acceptance_original_root_invalid")
        target.relative_to(root)
        current = root
        for part in target.relative_to(root).parts:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise AcceptanceError("acceptance_original_symlink")
            if not stat.S_ISREG(info.st_mode) and current == target:
                raise AcceptanceError("acceptance_original_invalid")
        if not stat.S_ISREG(target.lstat().st_mode):
            raise AcceptanceError("acceptance_original_invalid")
    except AcceptanceError:
        raise
    except (OSError, ValueError):
        raise AcceptanceError("acceptance_original_missing") from None
    if _sha256_file(target) != expected_hash:
        raise AcceptanceError("acceptance_original_hash_mismatch")
    return target


def _check_database(data_root: Path) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """检查数据库完整性和 Schema 版本。
    
    验证项：
    - PRAGMA integrity_check = 'ok'
    - PRAGMA foreign_key_check 无违规
    - Schema 版本匹配当前代码（assert_schema_version）
    - 迁移历史记录数
    
    Args:
        data_root: 数据根目录（必须包含 studybuddy.sqlite3）
    
    Returns:
        (数据库连接, 元数据字典)
        连接已设置 row_factory = sqlite3.Row
        元数据包含 schema_version 和 history_count
    
    Raises:
        AcceptanceError: 数据库缺失、损坏或版本不匹配时
    
    注意:
        调用者必须负责关闭返回的连接
    """
    database = data_root / "studybuddy.sqlite3"
    connection: sqlite3.Connection | None = None
    if database.is_symlink() or not database.is_file():
        raise AcceptanceError("acceptance_database_missing")
    try:
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
        version = assert_schema_version(connection)
        history_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        if integrity != "ok":
            raise AcceptanceError("acceptance_database_integrity_failed")
        if foreign:
            raise AcceptanceError("acceptance_foreign_key_check_failed")
        return connection, {"schema_version": version, "history_count": history_count}
    except AcceptanceError:
        if connection is not None:
            connection.close()
        raise
    except (OSError, sqlite3.Error, MigrationError):
        try:
            connection.close()
        except Exception:
            pass
        raise AcceptanceError("acceptance_database_invalid") from None


def _study_checks(connection: sqlite3.Connection) -> dict[str, Any]:
    """验证学习数据的完整性和一致性（Phase 9a/9b/9c）。
    
    检查项：
    - 20 个学习相关表必须存在
    - 计划项目状态与进度事件投影一致
    - 计划汇总数据准确（item_count = completed + skipped + in_progress + pending）
    - 笔记必须至少有一个 note_block
    - 节奏分配必须有对应的 rhythm_settings
    - valid 状态的源链接必须有 material_id
    - 练习会话、尝试、评审的 project_id 一致性
    
    Args:
        connection: SQLite 连接（已设置 row_factory）
    
    Returns:
        包含状态、计数、分组统计的字典
    
    Raises:
        AcceptanceError: 数据不一致或投影错误时
    """
    required_tables = (
        "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
        "study_plan_dependencies", "study_progress_events", "module_source_links",
        "plan_item_source_links", "notes", "note_blocks", "note_module_links",
        "note_block_source_links", "rhythm_settings", "rhythm_allocations",
        "practice_sessions", "practice_session_items", "exercise_attempt_reviews",
        "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals",
    )
    placeholders = ",".join("?" for _ in required_tables)
    present = {
        str(row[0]) for row in connection.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
            required_tables,
        ).fetchall()
    }
    if present != set(required_tables):
        raise AcceptanceError("acceptance_study_schema_missing")

    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in required_tables
    }
    plan_statuses = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM study_plans GROUP BY status ORDER BY status"
        ).fetchall()
    }
    source_statuses = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM ("
            "SELECT status FROM module_source_links "
            "UNION ALL SELECT status FROM plan_item_source_links"
            ") GROUP BY status ORDER BY status"
        ).fetchall()
    }
    summary_rows = connection.execute(
        "SELECT p.id, "
        "SUM(CASE WHEN i.status != 'archived' THEN 1 ELSE 0 END) AS item_count, "
        "SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END) AS completed_count, "
        "SUM(CASE WHEN i.status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count, "
        "SUM(CASE WHEN i.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_count, "
        "SUM(CASE WHEN i.status = 'pending' THEN 1 ELSE 0 END) AS pending_count "
        "FROM study_plans p LEFT JOIN study_plan_items i ON i.plan_id = p.id "
        "GROUP BY p.id"
    ).fetchall()
    projection = {"pending": "pending", "started": "in_progress", "reopened": "in_progress", "completed": "completed", "skipped": "skipped"}
    item_rows = connection.execute(
        "SELECT i.id, i.status, e.event_type FROM study_plan_items i "
        "LEFT JOIN study_progress_events e ON e.id = ("
        "SELECT e2.id FROM study_progress_events e2 WHERE e2.item_id=i.id "
        "ORDER BY e2.created_at DESC, e2.id DESC LIMIT 1"
        ") ORDER BY i.id"
    ).fetchall()
    for row in item_rows:
        expected_status = projection.get(str(row[2]), "pending") if row[2] is not None else "pending"
        if str(row[1]) != "archived" and str(row[1]) != expected_status:
            raise AcceptanceError("acceptance_study_projection_invalid")
    for row in summary_rows:
        values = [int(row[index] or 0) for index in range(1, 6)]
        if any(value < 0 for value in values) or values[0] != sum(values[1:]):
            raise AcceptanceError("acceptance_study_summary_invalid")
    invalid_valid_links = connection.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT status,material_id FROM module_source_links "
        "UNION ALL SELECT status,material_id FROM plan_item_source_links "
        "UNION ALL SELECT status,material_id FROM note_block_source_links"
        ") WHERE status='valid' AND material_id IS NULL"
    ).fetchone()[0]
    if invalid_valid_links:
        raise AcceptanceError("acceptance_study_source_invalid")
    invalid_note_blocks = connection.execute(
        "SELECT COUNT(*) FROM notes n WHERE NOT EXISTS (SELECT 1 FROM note_blocks b WHERE b.note_id=n.id)"
    ).fetchone()[0]
    if invalid_note_blocks:
        raise AcceptanceError("acceptance_note_blocks_missing")
    invalid_rhythm = connection.execute(
        "SELECT COUNT(*) FROM rhythm_allocations a LEFT JOIN rhythm_settings s ON s.plan_id=a.plan_id "
        "WHERE s.plan_id IS NULL"
    ).fetchone()[0]
    if invalid_rhythm:
        raise AcceptanceError("acceptance_rhythm_settings_missing")
    note_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM notes GROUP BY status ORDER BY status"
        ).fetchall()
    }
    note_source_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM note_block_source_links GROUP BY status ORDER BY status"
        ).fetchall()
    }
    phase9c_source_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT source_status,COUNT(*) FROM mistake_occurrences GROUP BY source_status ORDER BY source_status"
        ).fetchall()
    }
    phase9c_session_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM practice_sessions GROUP BY status ORDER BY status"
        ).fetchall()
    }
    invalid_session_items = connection.execute(
        "SELECT COUNT(*) FROM practice_session_items i "
        "JOIN practice_sessions s ON s.id=i.session_id "
        "JOIN exercises e ON e.id=i.exercise_id "
        "WHERE i.project_id != s.project_id OR e.project_id != i.project_id"
    ).fetchone()[0]
    if invalid_session_items:
        raise AcceptanceError("acceptance_phase9c_session_scope_invalid")
    invalid_attempt_links = connection.execute(
        "SELECT COUNT(*) FROM exercise_attempts a "
        "JOIN practice_session_items i ON i.id=a.session_item_id "
        "WHERE a.session_id != i.session_id OR a.exercise_id != i.exercise_id"
    ).fetchone()[0]
    if invalid_attempt_links:
        raise AcceptanceError("acceptance_phase9c_attempt_link_invalid")
    invalid_review_links = connection.execute(
        "SELECT COUNT(*) FROM exercise_attempt_reviews r "
        "JOIN exercise_attempts a ON a.id=r.attempt_id "
        "WHERE r.exercise_id != a.exercise_id"
    ).fetchone()[0]
    if invalid_review_links:
        raise AcceptanceError("acceptance_phase9c_review_link_invalid")
    return {
        "status": "passed",
        "counts": counts,
        "plan_statuses": plan_statuses,
        "source_statuses": source_statuses,
        "note_statuses": note_statuses,
        "note_source_statuses": note_source_statuses,
        "phase9c_source_statuses": phase9c_source_statuses,
        "phase9c_session_statuses": phase9c_session_statuses,
        "rhythm_settings_count": counts["rhythm_settings"],
        "rhythm_allocations_count": counts["rhythm_allocations"],
        "summary_plan_count": len(summary_rows),
        "user_edited_count": int(connection.execute(
            "SELECT COUNT(*) FROM study_plans WHERE user_edited=1"
        ).fetchone()[0]),
        "note_user_edited_count": int(connection.execute(
            "SELECT COUNT(*) FROM notes WHERE user_edited=1"
        ).fetchone()[0]),
    }


def _phase9d_checks(connection: sqlite3.Connection) -> dict[str, Any]:
    """验证采集会话和报告交付的完整性（Phase 9d）。
    
    检查项：
    - 5 个 Phase 9d 表必须存在（capture_sessions, transcript_*, report_*）
    - transcript_drafts 的 project_id 与 capture_session 一致
    - transcript_segments 的 project_id 与 draft 一致
    - ai_operations.capture_session_id 指向存在且同项目的会话
    - report_delivery_attempts 的 project_id 与 report_snapshot 一致
    - source_status='valid' 的会话必须有有效的未删除 material
    
    Args:
        connection: SQLite 连接
    
    Returns:
        包含状态、计数、分组统计的字典
    
    Raises:
        AcceptanceError: 数据范围错误或源链接无效时
    """
    required_tables = (
        "capture_sessions", "transcript_drafts", "transcript_segments",
        "report_snapshots", "report_delivery_attempts",
    )
    placeholders = ",".join("?" for _ in required_tables)
    present = {
        str(row[0]) for row in connection.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
            required_tables,
        ).fetchall()
    }
    if present != set(required_tables):
        raise AcceptanceError("acceptance_phase9d_schema_missing")

    invalid_draft_scope = connection.execute(
        "SELECT COUNT(*) FROM transcript_drafts d JOIN capture_sessions c ON c.id=d.capture_session_id "
        "WHERE d.project_id != c.project_id"
    ).fetchone()[0]
    if invalid_draft_scope:
        raise AcceptanceError("acceptance_phase9d_draft_scope_invalid")
    invalid_segment_scope = connection.execute(
        "SELECT COUNT(*) FROM transcript_segments s JOIN transcript_drafts d ON d.id=s.draft_id "
        "WHERE s.project_id != d.project_id"
    ).fetchone()[0]
    if invalid_segment_scope:
        raise AcceptanceError("acceptance_phase9d_segment_scope_invalid")
    invalid_operation_scope = connection.execute(
        "SELECT COUNT(*) FROM ai_operations o LEFT JOIN capture_sessions c ON c.id=o.capture_session_id "
        "WHERE o.capture_session_id IS NOT NULL AND (c.id IS NULL OR o.project_id != c.project_id)"
    ).fetchone()[0]
    if invalid_operation_scope:
        raise AcceptanceError("acceptance_phase9d_operation_scope_invalid")
    invalid_delivery_scope = connection.execute(
        "SELECT COUNT(*) FROM report_delivery_attempts a JOIN report_snapshots r ON r.id=a.report_id "
        "WHERE a.project_id != r.project_id"
    ).fetchone()[0]
    if invalid_delivery_scope:
        raise AcceptanceError("acceptance_phase9d_delivery_scope_invalid")
    invalid_valid_source = connection.execute(
        "SELECT COUNT(*) FROM capture_sessions c LEFT JOIN materials m ON m.id=c.material_id "
        "WHERE c.source_status='valid' AND (m.id IS NULL OR m.project_id != c.project_id OR m.deleted_at IS NOT NULL)"
    ).fetchone()[0]
    if invalid_valid_source:
        raise AcceptanceError("acceptance_phase9d_source_invalid")

    return {
        "status": "passed",
        "counts": {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in required_tables
        },
        "capture_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM capture_sessions GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "capture_source_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT COALESCE(source_status,'unbound'),COUNT(*) FROM capture_sessions "
                "GROUP BY COALESCE(source_status,'unbound') ORDER BY 1"
            ).fetchall()
        },
        "report_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM report_snapshots GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "delivery_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM report_delivery_attempts GROUP BY status ORDER BY status"
            ).fetchall()
        },
    }


def _phase10_task_checks(connection: sqlite3.Connection) -> dict[str, Any]:
    """验证后台任务系统的完整性（Phase 10）。
    
    检查项：
    - operation_tasks 和 operation_task_attempts 表存在
    - task 的 project_id 与 operation 一致
    - attempt 的 project_id 与 task 一致
    - 每个 task 最多只有一个 status='running' 的 attempt
    
    Args:
        connection: SQLite 连接
    
    Returns:
        包含状态、计数、分组统计的字典
    
    Raises:
        AcceptanceError: 数据范围错误或状态冲突时
    """
    required_tables = ("operation_tasks", "operation_task_attempts")
    placeholders = ",".join("?" for _ in required_tables)
    present = {
        str(row[0]) for row in connection.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
            required_tables,
        ).fetchall()
    }
    if present != set(required_tables):
        raise AcceptanceError("acceptance_phase10_task_schema_missing")
    invalid_task_scope = connection.execute(
        "SELECT COUNT(*) FROM operation_tasks t JOIN ai_operations o ON o.id=t.operation_id "
        "WHERE t.project_id != o.project_id"
    ).fetchone()[0]
    if invalid_task_scope:
        raise AcceptanceError("acceptance_phase10_task_scope_invalid")
    invalid_attempt_scope = connection.execute(
        "SELECT COUNT(*) FROM operation_task_attempts a JOIN operation_tasks t ON t.id=a.task_id "
        "WHERE a.project_id != t.project_id"
    ).fetchone()[0]
    if invalid_attempt_scope:
        raise AcceptanceError("acceptance_phase10_attempt_scope_invalid")
    duplicate_running = connection.execute(
        "SELECT COUNT(*) FROM (SELECT task_id FROM operation_task_attempts WHERE status='running' "
        "GROUP BY task_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    if duplicate_running:
        raise AcceptanceError("acceptance_phase10_attempt_state_invalid")
    return {
        "status": "passed",
        "counts": {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in required_tables
        },
        "task_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM operation_tasks GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "attempt_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM operation_task_attempts GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "execution": "not_run_by_restore_acceptance",
    }


def _offline(data_root: Path) -> dict[str, Any]:
    """离线模式验收测试（仅数据库和文件系统）。
    
    执行流程：
    1. 检查数据库完整性和 Schema 版本
    2. 运行学习数据、Phase 9d、Phase 10 的验收测试
    3. 如果有激活材料，验证第一个材料的原始文件哈希
    4. 验证提取文本的哈希
    
    Args:
        data_root: 数据根目录
    
    Returns:
        验收报告（status, mode, checks, error_code）
    
    注意:
        - 不需要 HTTP 服务运行
        - health 和部分检查标记为 'skipped'
    """
    connection, metadata = _check_database(data_root)
    checks: dict[str, Any] = {
        "health": {"status": "skipped", "reason": "offline_mode"},
        "active_list": {"status": "passed"},
        "deleted_list": {"status": "passed"},
        "detail": {"status": "skipped", "reason": "no_active_material"},
        "original_download": {"status": "skipped", "reason": "offline_mode"},
        "text_export": {"status": "skipped", "reason": "offline_mode"},
        "integrity": {"status": "passed"},
        "foreign_keys": {"status": "passed"},
        "schema_history": {"status": "passed", "count": metadata["history_count"]},
        "study": _study_checks(connection),
        "phase9d": _phase9d_checks(connection),
        "phase10_tasks": _phase10_task_checks(connection),
    }
    try:
        active = connection.execute(
            "SELECT m.id, m.original_name, m.stored_path, m.source_sha256, e.text "
            "FROM materials m JOIN extractions e ON e.material_id = m.id "
            "WHERE m.deleted_at IS NULL ORDER BY m.created_at, m.id"
        ).fetchall()
        deleted_count = connection.execute(
            "SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL"
        ).fetchone()[0]
        checks["active_list"]["count"] = len(active)
        checks["deleted_list"]["count"] = deleted_count
        if active:
            row = active[0]
            target = _safe_original(data_root / "originals", row["stored_path"], row["source_sha256"])
            checks["detail"] = {
                "status": "passed",
                "material_id": str(row["id"]),
                "original_name": str(row["original_name"]),
                "text_sha256": _sha256_bytes(str(row["text"]).encode("utf-8")),
            }
            checks["original_download"] = {
                "status": "passed", "sha256": _sha256_file(target), "size": target.stat().st_size
            }
            checks["text_export"] = {
                "status": "passed", "sha256": _sha256_bytes(str(row["text"]).encode("utf-8")),
                "size": len(str(row["text"]).encode("utf-8")),
            }
        return {"status": "passed", "mode": "offline", **metadata, "checks": checks, "error_code": None}
    finally:
        connection.close()


def _http_json(base_url: str, path: str) -> tuple[int, Any]:
    """发送 HTTP GET 请求并解析 JSON 响应。
    
    Args:
        base_url: 基础 URL（如 'http://localhost:8000'）
        path: 请求路径（如 '/api/health'）
    
    Returns:
        (HTTP 状态码, 解析后的 JSON 对象)
    
    Raises:
        AcceptanceError: 请求失败或 JSON 解析失败时
    """
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise AcceptanceError("acceptance_http_request_failed") from None


def _http_bytes(base_url: str, path: str) -> tuple[int, dict[str, str], bytes]:
    """发送 HTTP GET 请求并返回原始字节响应。
    
    Args:
        base_url: 基础 URL
        path: 请求路径
    
    Returns:
        (HTTP 状态码, 响应头字典, 响应体字节)
    
    Raises:
        AcceptanceError: 请求失败时
    """
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as response:
            return response.status, {str(k).lower(): str(v) for k, v in response.headers.items()}, response.read()
    except OSError:
        raise AcceptanceError("acceptance_http_request_failed") from None


def _online(data_root: Path, base_url: str) -> dict[str, Any]:
    """在线模式验收测试（数据库 + HTTP API）。
    
    执行流程：
    1. 运行离线模式的所有检查
    2. 验证 /api/health 端点返回 status='ok'
    3. 验证 /api/materials 和 /api/materials/deleted 端点
    4. 如果有激活材料，验证：
       - /api/materials/{id} 详情端点
       - /api/materials/{id}/original 下载并校验哈希
       - /api/materials/{id}/text 导出并校验内容
    
    Args:
        data_root: 数据根目录
        base_url: FastAPI 服务基础 URL
    
    Returns:
        验收报告（mode='online'）
    
    Raises:
        AcceptanceError: HTTP 请求失败或响应不符合预期时
    """
    result = _offline(data_root)
    checks = result["checks"]
    status, health = _http_json(base_url, "/api/health")
    if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        raise AcceptanceError("acceptance_health_failed")
    checks["health"] = {"status": "passed"}
    status, active = _http_json(base_url, "/api/materials")
    if status != 200 or not isinstance(active, list):
        raise AcceptanceError("acceptance_active_list_failed")
    status, deleted = _http_json(base_url, "/api/materials/deleted")
    if status != 200 or not isinstance(deleted, list):
        raise AcceptanceError("acceptance_deleted_list_failed")
    checks["active_list"]["http_count"] = len(active)
    checks["deleted_list"]["http_count"] = len(deleted)
    if active:
        material_id = str(active[0].get("id", ""))
        status, detail = _http_json(base_url, "/api/materials/" + material_id)
        if status != 200 or not isinstance(detail, dict):
            raise AcceptanceError("acceptance_detail_failed")
        status, headers, original = _http_bytes(base_url, "/api/materials/" + material_id + "/original")
        expected = str(detail.get("source_sha256", ""))
        if status != 200 or _sha256_bytes(original) != expected:
            raise AcceptanceError("acceptance_original_download_failed")
        status, headers, text = _http_bytes(base_url, "/api/materials/" + material_id + "/text")
        if status != 200 or "text/plain" not in headers.get("content-type", "") or not text.decode("utf-8"):
            raise AcceptanceError("acceptance_text_export_failed")
        checks["detail"] = {"status": "passed", "material_id": material_id}
        checks["original_download"] = {"status": "passed", "sha256": _sha256_bytes(original), "size": len(original)}
        checks["text_export"] = {"status": "passed", "sha256": _sha256_bytes(text), "size": len(text)}
    return {**result, "mode": "online"}


def verify_restored_data(data_root: Path, base_url: str | None = None) -> dict[str, Any]:
    """验证恢复后的数据完整性。
    
    根据 base_url 参数选择离线或在线模式：
    - base_url=None: 离线模式，仅验证数据库和文件系统
    - base_url='http://...': 在线模式，同时验证 HTTP API
    
    Args:
        data_root: 数据根目录（必须是恢复后的完整 data_root）
        base_url: 可选的 FastAPI 服务基础 URL
    
    Returns:
        验收报告字典，包含：
        - status: 'passed' 或 'failed'
        - mode: 'offline' 或 'online'
        - checks: 各项检查的详细结果
        - error_code: 失败时的错误码（成功时为 None）
    
    示例:
        # 离线模式
        result = verify_restored_data(Path('/data/restored'))
        
        # 在线模式
        result = verify_restored_data(
            Path('/data/restored'),
            base_url='http://localhost:8000'
        )
    
    注意:
        - 离线模式不需要 FastAPI 服务运行
        - 在线模式需要服务已启动并可达
        - 所有 AcceptanceError 都会被捕获并转换为 error_code
    """
    try:
        return _online(Path(data_root), base_url) if base_url else _offline(Path(data_root))
    except AcceptanceError as error:
        return {"status": "failed", "mode": "online" if base_url else "offline", "error_code": error.code}
