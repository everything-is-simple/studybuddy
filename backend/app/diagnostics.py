"""运行时诊断 - 安全的操作员快照。

本模块收集数据库健康状态的简报，供 /api/health 和运维检查使用。

诊断内容：
- Schema 版本验证（必须与代码一致）
- 数据库完整性快速检查（PRAGMA quick_check）
- 后台任务状态汇总（按七种状态计数）

安全设计：
- 只读连接（mode=ro），绝不写入
- 不泄露路径、SQL、源数据
- 返回稳定的错误码和推荐操作

状态判定：
- ok: 版本匹配 + 完整性通过 + 无 stale 任务
- degraded: 完整性失败或存在 stale 任务
- 异常: 抛出 DiagnosticError（数据库不可用等）

推荐操作示例：
- database_integrity_failed → stop_writes_and_verify_backup
- stale 任务存在 → review_stale_tasks_before_explicit_retry
"""
from __future__ import annotations

import sqlite3
import stat
from pathlib import Path
from typing import Any

from .migrations.runner import MigrationError, assert_schema_version

APPLICATION_VERSION = "local-v1"
_TASK_STATUSES = ("queued", "running", "cancel_requested", "succeeded", "failed", "cancelled", "stale")


class DiagnosticError(ValueError):
    """诊断错误。
    
    Args:
        code: 错误码（如 'diagnostic_database_unavailable'）
    """
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _readonly_connection(database_path: Path) -> sqlite3.Connection:
    try:
        info = database_path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise DiagnosticError("diagnostic_database_unavailable")
        connection = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except DiagnosticError:
        raise
    except (OSError, ValueError, sqlite3.Error):
        raise DiagnosticError("diagnostic_database_unavailable") from None
    except DiagnosticError:
        return False


def collect_diagnostics(data_root: Path) -> dict[str, Any]:
    """收集安全的操作员快照（不含路径、SQL、源数据）。
    
    执行流程：
    1. 以只读模式连接数据库
    2. 验证 Schema 版本
    3. 执行 PRAGMA quick_check
    4. 统计任务状态分布
    
    Args:
        data_root: 数据根目录
    
    Returns:
        诊断字典：
        - status: 'ok' 或 'degraded'
        - application_version: 应用版本
        - schema_version: 当前 Schema 版本
        - task_counts: 按状态的任务计数
        - reasons: 降级原因列表
        - recommended_actions: 推荐操作列表
    
    Raises:
        DiagnosticError: 数据库不可用、版本不匹配
                        或任务汇总不可读时
    """
    database_path = Path(data_root) / "studybuddy.sqlite3"
    connection = _readonly_connection(database_path)
    try:
        try:
            schema_version = assert_schema_version(connection)
        except MigrationError as error:
            raise DiagnosticError(error.code) from None
        try:
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0]).lower()
        except sqlite3.Error:
            raise DiagnosticError("diagnostic_database_unavailable") from None
        if quick_check != "ok":
            return {
                "status": "degraded", "application_version": APPLICATION_VERSION,
                "schema_version": schema_version, "task_counts": {status: 0 for status in _TASK_STATUSES},
                "reasons": ["database_integrity_failed"],
                "recommended_actions": ["stop_writes_and_verify_backup"],
            }
        try:
            rows = connection.execute(
                "SELECT status,COUNT(*) AS count FROM operation_tasks GROUP BY status"
            ).fetchall()
        except sqlite3.Error:
            raise DiagnosticError("diagnostic_task_summary_unavailable") from None
        counts = {status: 0 for status in _TASK_STATUSES}
        for row in rows:
            status = str(row["status"])
            if status in counts:
                counts[status] = int(row["count"])
        reasons = ["task_recovery_required"] if counts["stale"] else []
        actions = ["review_stale_tasks_before_explicit_retry"] if counts["stale"] else ["none"]
        return {
            "status": "degraded" if reasons else "ok", "application_version": APPLICATION_VERSION,
            "schema_version": schema_version, "task_counts": counts, "reasons": reasons,
            "recommended_actions": actions,
        }
    finally:
        connection.close()
