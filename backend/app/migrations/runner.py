"""迁移执行引擎和注册中心。

本模块是 SQLite Schema 迁移的核心引擎，负责：
- 维护迁移注册表（版本号 → 迁移函数）
- 按顺序执行迁移（严格连续，不允许跳版本）
- 维护 schema_migrations 历史表和 PRAGMA user_version
- 旧数据库（pre-runner）的基线采用
- Schema 版本检查和验证

迁移规则：
- 连续性：版本必须从 current+1 开始，不允许跳跃
- 幂等性：重复执行不会重复应用
- 事务性：每个迁移在事务中执行，失败时回滚
- 一致性：schema_migrations 和 PRAGMA user_version 必须一致

当前版本: 14（对应 v14: fix_revision_fingerprint）

迁移清单：
- v01: canonical_material_schema - 规范化材料 Schema
- v02: ai_phase0_schema - AI 基础 Schema
- v03: phase5_provider_metadata - Provider 元数据
- v04: qa_operation_idempotency - QA 幂等性
- v05: phase7_embedding_schema - Embedding Schema
- v06: search_index_schema_contract - 搜索索引契约
- v07: phase8_cards_exercises_schema - 卡片/练习
- v08: phase8_exercise_provenance - 练习溯源
- v09: phase9a_learning_plan_schema - 学习计划
- v10: phase9b_material_learning_schema - 材料学习
- v11: phase9c_exercise_feedback_schema - 练习反馈
- v12: phase9d_extended_learning_schema - 扩展学习
- v13: phase10_operation_task_schema - 后台任务
- v14: fix_revision_fingerprint_material_id - 修订指纹修复

错误码：
- database_schema_version_unknown: 版本未知或不一致
- database_migration_history_mismatch: 历史记录与注册表不匹配
- database_migration_incomplete: 迁移不完整
- database_migration_failed: 迁移执行失败
- database_schema_unsupported: Schema 不支持（未知表/结构）
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from ._helpers import (
    _now,
    _objects,
    _columns,
    _create_history,
    _baseline_complete,
)
from ._canonical import _create_canonical_schema
from . import (
    _v01_canonical_material as v01,
    _v02_ai_phase0 as v02,
    _v03_phase5_provider as v03,
    _v04_qa_idempotency as v04,
    _v05_phase7_embedding as v05,
    _v06_search_index as v06,
    _v07_phase8_cards as v07,
    _v08_exercise_provenance as v08,
    _v09_phase9a_learning_plan as v09,
    _v10_phase9b_material_learning as v10,
    _v11_phase9c_feedback as v11,
    _v12_phase9d_extended as v12,
    _v13_phase10_tasks as v13,
    _v14_fix_revision_fingerprint as v14,
)

CURRENT_SCHEMA_VERSION = 14
HISTORY_TABLE = "schema_migrations"


class MigrationError(ValueError):
    """迁移错误。
    
    Args:
        code: 错误码（如 'database_migration_failed'）
    """
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MigrationResult:
    """迁移执行结果。
    
    Attributes:
        current_version: 当前 Schema 版本
        applied_versions: 本次应用的版本列表（空表示无迁移）
        adopted_legacy: 是否采用了旧数据库基线
    """
    current_version: int
    applied_versions: tuple[int, ...]
    adopted_legacy: bool = False


_MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
    (1, "canonical_material_schema", v01.migrate),
    (2, "ai_phase0_schema", v02.migrate),
    (3, "phase5_provider_metadata", v03.migrate),
    (4, "qa_operation_idempotency", v04.migrate),
    (5, "phase7_embedding_schema", v05.migrate),
    (6, "search_index_schema_contract", v06.migrate),
    (7, "phase8_cards_exercises_schema", v07.migrate),
    (8, "phase8_exercise_provenance", v08.migrate),
    (9, "phase9a_learning_plan_schema", v09.migrate),
    (10, "phase9b_material_learning_schema", v10.migrate),
    (11, "phase9c_exercise_feedback_schema", v11.migrate),
    (12, "phase9d_extended_learning_schema", v12.migrate),
    (13, "phase10_operation_task_schema", v13.migrate),
    (14, "fix_revision_fingerprint_material_id", v14.migrate),
)

# Compatibility aliases for tests that monkeypatch migration functions
_migration_v9 = v09.migrate
_migration_v10 = v10.migrate
_migration_v11 = v11.migrate
_migration_v12 = v12.migrate
_migration_v13 = v13.migrate
_migration_v14 = v14.migrate


def schema_version(connection: sqlite3.Connection) -> int:
    """读取已记录的最高迁移版本。
    
    Args:
        connection: SQLite 连接
    
    Returns:
        最高版本号（空历史表返回 0）
    
    Raises:
        MigrationError: 历史表不可读时
    """
    try:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchall()
    except sqlite3.Error as exc:
        raise MigrationError("database_schema_version_unknown") from exc
    return int(rows[0][0]) if rows else 0


def _check_history(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()
    expected = [version for version, _, _ in _MIGRATIONS]
    actual = [int(row[0]) for row in rows]
    if actual != expected[:len(actual)] or any(version < 1 for version in actual):
        raise MigrationError("database_schema_version_unknown")
    for row, migration in zip(rows, _MIGRATIONS):
        if row[1] != migration[1]:
            raise MigrationError("database_migration_history_mismatch")
    current = actual[-1] if actual else 0
    if current > CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return current


def migrate(connection: sqlite3.Connection) -> MigrationResult:
    """执行数据库迁移（按需应用所有待执行版本）。
    
    执行流程：
    1. 开启外键约束和 busy_timeout
    2. 检查历史表：
       - 存在且版本已到最新：验证基线完整性后直接返回
       - 不存在：创建历史表，检查旧数据库
    3. 旧数据库处理：
       - 完整基线：采用（adopt），记录完整历史但不重放 ALTER
       - 部分表：验证表集合属于已知核心表
    4. 逐版本执行迁移（严格连续）
    5. 验证基线完整性，更新 PRAGMA user_version
    6. 提交事务
    
    Args:
        connection: SQLite 连接（调用者负责事务边界之外的提交）
    
    Returns:
        MigrationResult 包含当前版本和已应用版本
    
    Raises:
        MigrationError: 历史不匹配、版本跳跃、
                        基线不完整或迁移失败时（事务已回滚）
    
    注意:
        - PRAGMA user_version 在成功后才更新
        - 失败时事务回滚，数据库保持原状
        - 每个 SQLite 连接独立执行，busy_timeout 防锁冲突
    """
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 2000")
    adopted = False
    applied: list[int] = []
    try:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (HISTORY_TABLE,)
        ).fetchone() is not None:
            current = _check_history(connection)
            pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current == CURRENT_SCHEMA_VERSION and pragma == CURRENT_SCHEMA_VERSION:
                if not _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
                    raise MigrationError("database_schema_unsupported")
                return MigrationResult(current, ())
        connection.execute("BEGIN IMMEDIATE")
        _create_history(connection)
        current = _check_history(connection)
        if current == 0 and _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
            # A complete pre-runner database already has the current schema.
            # Adopt it with the full consecutive history; do not replay ALTERs.
            connection.executemany(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                [(version, name, _now()) for version, name, _function in _MIGRATIONS],
            )
            current = CURRENT_SCHEMA_VERSION
            adopted = True
        elif current == 0 and _objects(connection) - {HISTORY_TABLE}:
            # Existing pre-runner databases may have the core tables but lack
            # columns added by the old implicit schema upgrade path.
            known = {"sqlite_sequence", "projects", "materials", "extractions",
                     "text_spans", "material_search",
                     "material_revisions", "chunks", "chunk_spans", "embeddings",
                     "retrieval_runs", "retrieval_hits", "qa_citations",
                     "ai_operations", "qa_threads", "qa_messages", "qa_answers",
                     "chunks_search"}
            if not (_objects(connection) - {HISTORY_TABLE}).issubset(known):
                raise MigrationError("database_schema_unsupported")
        for version, name, function in _MIGRATIONS:
            if version <= current:
                continue
            if version != current + 1:
                raise MigrationError("database_migration_incomplete")
            function(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _now()),
            )
            applied.append(version)
            current = version
        if current != CURRENT_SCHEMA_VERSION:
            raise MigrationError("database_migration_incomplete")
        if not _baseline_complete(connection, CURRENT_SCHEMA_VERSION):
            raise MigrationError("database_schema_unsupported")
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.commit()
        return MigrationResult(current, tuple(applied), adopted)
    except MigrationError:
        connection.rollback()
        raise
    except (sqlite3.Error, OSError) as exc:
        connection.rollback()
        raise MigrationError("database_migration_failed") from exc


def inspect_schema_version(connection: sqlite3.Connection) -> int:
    """验证已记录的迁移历史（不应用迁移、不修改数据库）。
    
    Args:
        connection: SQLite 连接
    
    Returns:
        当前 Schema 版本
    
    Raises:
        MigrationError: 历史不匹配、user_version 不一致
                        或版本低于 1 时
    """
    version = _check_history(connection)
    pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1 or pragma != version:
        raise MigrationError("database_schema_version_unknown")
    return version


def assert_schema_version(connection: sqlite3.Connection) -> int:
    """断言数据库已迁移到当前代码要求的最新版本。
    
    Args:
        connection: SQLite 连接
    
    Returns:
        当前 Schema 版本（必须等于 CURRENT_SCHEMA_VERSION）
    
    Raises:
        MigrationError: 版本不是最新时
    """
    version = inspect_schema_version(connection)
    if version != CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return version
