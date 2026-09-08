"""启动恢复 - 一次性保守的启动对账。

本模块在应用启动时执行一次性对账，清理残留状态、标记中断任务。
只诊断、不修复数据库：不迁移、不修改数据库行。

对账项：
1. 清理残留临时文件（data_root 下的 .incoming-* 文件）
2. 对账原始文件（删除孤立的、哈希不匹配的原始文件）
3. 恢复中断的任务尝试（标记为 stale）
4. 检测缺失的引用原始文件（仅记录，不删除）

安全设计：
- 不删除数据库行
- 不修改 stored_path
- 不处理符号链接（跳过）
- 所有操作记录结构化事件（不含路径、文件名、异常文本）

原始文件对账规则：
- 路径格式：{root}/{hash[:2]}/{hash[2:]}/original
- 哈希不匹配：保留（可能是用户手动替换）
- 未引用且哈希匹配：删除（孤立文件）
- 目录清理：删除后尝试 rmdir（忽略失败）
"""
from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

from .config import AppConfig
from .observability import emit_event, increment
from .repository import connect, recover_active_operation_tasks
from .storage import sha256_file

logger = logging.getLogger(__name__)


def _note(event: str) -> None:
    # Recovery diagnostics deliberately contain no paths, filenames, or exception text.
    increment("recovery_events", event)
    emit_event(event, level=logging.WARNING, component="recovery", outcome="diagnostic")


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _remove(path: Path, event: str) -> bool:
    try:
        path.unlink()
        return True
    except OSError:
        _note(event)
        return False


def _cleanup_stale_incoming(data_root: Path) -> None:
    try:
        entries = list(data_root.iterdir())
    except OSError:
        _note("temp_scan_failed")
        return
    for path in entries:
        # Only top-level, non-symlink regular files are eligible.
        if path.name.startswith(".incoming-") and _regular_file(path):
            _remove(path, "stale_temp_remove_failed")


def _reconcile_originals(config: AppConfig) -> None:
    root = config.originals_root
    try:
        root_stat = root.lstat()
    except OSError:
        return
    if not stat.S_ISDIR(root_stat.st_mode) or root.is_symlink():
        _note("originals_root_invalid")
        return
    try:
        first_level = list(root.iterdir())
    except OSError:
        _note("original_scan_failed")
        return
    try:
        with connect(config.database_path) as connection:
            referenced = {row[0] for row in connection.execute("SELECT DISTINCT source_sha256 FROM materials")}
    except Exception:
        _note("reference_scan_failed")
        return

    for prefix_dir in first_level:
        if prefix_dir.is_symlink() or not prefix_dir.is_dir() or len(prefix_dir.name) != 2:
            continue
        if any(c not in "0123456789abcdefABCDEF" for c in prefix_dir.name):
            continue
        try:
            second_level = list(prefix_dir.iterdir())
        except OSError:
            _note("original_scan_failed")
            continue
        for suffix_dir in second_level:
            if suffix_dir.is_symlink() or not suffix_dir.is_dir() or len(suffix_dir.name) != 62:
                continue
            digest = prefix_dir.name + suffix_dir.name
            if any(c not in "0123456789abcdefABCDEF" for c in digest):
                continue
            candidate = suffix_dir / "original"
            if candidate.is_symlink() or not _regular_file(candidate):
                continue
            try:
                actual = sha256_file(candidate)
            except OSError:
                _note("original_hash_check_failed")
                continue
            if actual.lower() != digest.lower():
                _note("original_hash_mismatch_preserved")
                continue
            if digest.lower() not in {str(value).lower() for value in referenced}:
                if _remove(candidate, "orphan_original_remove_failed"):
                    try:
                        suffix_dir.rmdir()
                    except OSError:
                        pass


def _reconcile_operation_tasks(config: AppConfig) -> None:
    """Mark interrupted task attempts stale; startup never queues or executes a task."""
    try:
        with connect(config.database_path) as connection:
            recovered = recover_active_operation_tasks(connection)
        if recovered:
            increment("recovery_events", "task_recovery_required", str(min(recovered, 9)))
            emit_event("task_recovery_required", level=logging.WARNING,
                       error_code="task_recovery_required", component="recovery", outcome="stale")
    except Exception:
        _note("task_recovery_check_failed")


def reconcile(config: AppConfig) -> None:
    """运行一次性、保守的启动对账。
    
    执行流程：
    1. 清理残留临时文件
    2. 对账原始文件（删除孤立文件）
    3. 恢复中断的任务尝试
    4. 检测缺失的引用原始文件（仅记录）
    
    Args:
        config: 应用配置
    
    注意:
        - 缺失的引用原始文件仅记录事件，不删除数据库行
        - 所有异常都转为事件，不中断对账流程
    """
    increment("recovery", "started")
    _cleanup_stale_incoming(config.data_root)
    _reconcile_originals(config)
    _reconcile_operation_tasks(config)
    # Missing referenced originals are intentionally detection-only.  Do not use
    # stored_path for deletion or mutate database rows here.
    try:
        with connect(config.database_path) as connection:
            missing = 0
            for row in connection.execute("SELECT source_sha256 FROM materials"):
                digest = str(row[0])
                target = config.originals_root / digest[:2] / digest[2:] / "original"
                if not target.is_file() or target.is_symlink():
                    missing += 1
            if missing:
                _note("referenced_original_missing")
    except Exception:
        _note("missing_original_check_failed")
    finally:
        increment("recovery", "completed")
