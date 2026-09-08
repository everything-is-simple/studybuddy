"""数据库审计 - 一次性诊断检查（只读）。

本模块对数据库执行一次性健康检查，发现问题时发出结构化事件。
只诊断、不修复：绝不迁移、修复或重建索引。

检查项（按严重性顺序）：
1. 完整性检查（PRAGMA integrity_check）
2. 外键检查（PRAGMA foreign_key_check）
3. 必需对象存在（5 个核心表/索引）
4. 关系完整性（五项双向引用检查）

关系检查：
- materials ↔ extractions 双向
- text_spans → extractions
- material_search ↔ materials 双向（含搜索行缺失）

事件策略：
- 每个问题发出结构化事件（WARNING 级别）
- 事件不包含数据库路径、ID、SQL、异常文本
- 原因按预定义顺序排序（保证输出稳定）

返回结构：
- status: 'ok' 或 'degraded'
- reasons: 排序后的原因码列表
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from .observability import emit_event, increment

logger = logging.getLogger(__name__)
_REQUIRED = {"projects", "materials", "extractions", "text_spans", "material_search"}
_REASON_ORDER = (
    "database_integrity_check_failed", "database_foreign_key_check_failed",
    "database_required_object_missing", "database_required_object_check_error",
    "database_material_extraction_relation_failed", "database_extraction_material_relation_failed",
    "database_span_extraction_relation_failed", "database_search_material_relation_failed",
    "database_search_row_missing", "database_relation_check_error", "database_audit_close_error",
)


def _event(name: str) -> None:
    # Deliberately no database path, ids, SQL, or exception text.
    increment("audit_events", name)
    emit_event(name, level=logging.WARNING, component="database", outcome="diagnostic")


def _run(connection: sqlite3.Connection, sql: str, event: str, *, expect_rows: bool = False) -> list[sqlite3.Row]:
    try:
        rows = connection.execute(sql).fetchall()
    except Exception:
        _event(event + "_error")
        return []
    if expect_rows and rows:
        _event(event)
    return rows


def _relation_checks(connection: sqlite3.Connection) -> set[str]:
    reasons: set[str] = set()
    checks = (
        ("SELECT 1 FROM materials m LEFT JOIN extractions e ON e.material_id = m.id WHERE e.id IS NULL LIMIT 1", "database_material_extraction_relation_failed"),
        ("SELECT 1 FROM extractions e LEFT JOIN materials m ON m.id = e.material_id WHERE m.id IS NULL LIMIT 1", "database_extraction_material_relation_failed"),
        ("SELECT 1 FROM text_spans s LEFT JOIN extractions e ON e.id = s.extraction_id WHERE e.id IS NULL LIMIT 1", "database_span_extraction_relation_failed"),
        ("SELECT 1 FROM material_search s LEFT JOIN materials m ON m.id = s.material_id WHERE m.id IS NULL LIMIT 1", "database_search_material_relation_failed"),
        ("SELECT 1 FROM materials m LEFT JOIN material_search s ON s.material_id = m.id WHERE s.material_id IS NULL LIMIT 1", "database_search_row_missing"),
    )
    for sql, event in checks:
        if _run(connection, sql, event, expect_rows=True):
            reasons.add(event)
    return reasons


def run_audit(database_path: Path) -> dict[str, object]:
    """运行一次性诊断检查；绝不迁移、修复或重建索引。
    
    执行流程：
    1. 连接数据库（query_only 开启，只读保障）
    2. 执行完整性检查
    3. 执行外键检查
    4. 验证必需对象存在
    5. 执行关系完整性检查
    
    Args:
        database_path: 数据库文件路径
    
    Returns:
        审计字典：
        - status: 'ok' 或 'degraded'
        - reasons: 排序后的原因码列表（空表示无问题）
    
    注意:
        - 连接失败时立即返回降级结果
        - 所有异常都转为事件 + 原因码，不中断
    """
    reasons: set[str] = set()
    try:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA query_only = ON")
    except Exception:
        _event("database_audit_connect_error")
        increment("audit", "failed")
        return {"status": "degraded", "reasons": ["database_audit_connect_error"]}
    increment("audit", "started")
    try:
        integrity = _run(connection, "PRAGMA integrity_check", "database_integrity_check_failed")
        if integrity and str(integrity[0][0]).lower() != "ok":
            _event("database_integrity_check_failed")
            reasons.add("database_integrity_check_failed")
        foreign = _run(connection, "PRAGMA foreign_key_check", "database_foreign_key_check_failed", expect_rows=True)
        if foreign:
            _event("database_foreign_key_check_failed")
            reasons.add("database_foreign_key_check_failed")
        try:
            objects = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')").fetchall()}
            if any(required not in objects for required in _REQUIRED):
                _event("database_required_object_missing")
                reasons.add("database_required_object_missing")
        except Exception:
            _event("database_required_object_check_error")
            reasons.add("database_required_object_check_error")
        try:
            reasons.update(_relation_checks(connection))
        except Exception:
            _event("database_relation_check_error")
            reasons.add("database_relation_check_error")
    finally:
        try:
            connection.close()
            increment("audit", "completed")
        except Exception:
            _event("database_audit_close_error")
            reasons.add("database_audit_close_error")
    ordered = sorted(reasons, key=lambda reason: (
        _REASON_ORDER.index(reason) if reason in _REASON_ORDER else len(_REASON_ORDER), reason
    ))
    return {"status": "degraded" if ordered else "ok", "reasons": ordered}
