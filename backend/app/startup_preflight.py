"""启动预检 - 验证存储拓扑和配置有效性。

本模块在应用启动前验证配置和文件系统状态，
在问题造成实际损害前拦截。

配置验证（validate_config）：
- max_upload_bytes: 正整数
- project_id: 非空字符串
- host: 仅限本地回环地址
- port: 1024-65535
- task_max_concurrency: 固定值
- log_level: 四个标准级别
- demo_mode: 仅允许 fake provider
- backup_root: 不得在 data_root 内部（防备份递归）

文件系统验证（preflight）：
- data_root: 目录（不存在则创建）
- originals_root: 目录
- database_path: 普通 SQLite 文件（验证文件头）

安全设计：
- 使用 lstat 检查（不跟随符号链接）
- 符号链接视为错误（防路径逃逸）
- 数据库文件验证 SQLite 头（防误连非数据库文件）
- 不删除任何路径

错误码格式：
- {kind}_symlink: 路径是符号链接
- {kind}_invalid: 类型不对（目录/文件）
- {kind}_unavailable: 无法访问
- database_path_not_sqlite: 非 SQLite 文件
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from .config import AppConfig, DEFAULT_HOST, DEFAULT_LOG_LEVEL, DEFAULT_PORT, DEFAULT_TASK_MAX_CONCURRENCY


class StartupPreflightError(ValueError):
    pass


_SQLITE_HEADER = b"SQLite format 3\x00"


def _check_existing(path: Path, kind: str) -> bool:
    """Check a configured path with lstat so links are never followed."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    except OSError:
        raise StartupPreflightError(f"{kind}_unavailable") from None
    if stat.S_ISLNK(mode):
        raise StartupPreflightError(f"{kind}_symlink")
    if kind in {"data_root", "originals_root"} and not stat.S_ISDIR(mode):
        raise StartupPreflightError(f"{kind}_invalid")
    if kind == "database_path":
        if not stat.S_ISREG(mode):
            raise StartupPreflightError("database_path_invalid")
        try:
            with path.open("rb") as database:
                header = database.read(len(_SQLITE_HEADER))
        except OSError:
            raise StartupPreflightError("database_path_unavailable") from None
        if header != _SQLITE_HEADER:
            raise StartupPreflightError("database_path_not_sqlite")
    return True


def validate_config(config: AppConfig) -> None:
    """验证配置字段的有效性。
    
    Args:
        config: 应用配置
    
    Raises:
        StartupPreflightError: 任何字段无效时
    """
    if not isinstance(config.max_upload_bytes, int) or isinstance(config.max_upload_bytes, bool) or config.max_upload_bytes < 1:
        raise StartupPreflightError("invalid_max_upload_bytes")
    if not isinstance(config.project_id, str) or not config.project_id:
        raise StartupPreflightError("invalid_project_id")
    if config.host not in {DEFAULT_HOST, "localhost", "::1"}:
        raise StartupPreflightError("invalid_host")
    if not isinstance(config.port, int) or isinstance(config.port, bool) or not 1024 <= config.port <= 65535:
        raise StartupPreflightError("invalid_port")
    if config.task_max_concurrency != DEFAULT_TASK_MAX_CONCURRENCY:
        raise StartupPreflightError("invalid_task_max_concurrency")
    if config.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise StartupPreflightError("invalid_log_level")
    if config.demo_mode and config.ai_provider_id not in {None, "fake"}:
        raise StartupPreflightError("invalid_demo_configuration")
    if config.backup_root is not None:
        data_root = os.path.abspath(config.data_root)
        backup_root = os.path.abspath(config.backup_root)
        try:
            inside_data_root = os.path.commonpath((data_root, backup_root)) == data_root
        except ValueError:
            raise StartupPreflightError("invalid_backup_root") from None
        if inside_data_root:
            raise StartupPreflightError("backup_root_inside_data_root")


def preflight(config: AppConfig) -> None:
    """验证现有存储拓扑（不跟随、不删除任何路径）。
    
    执行流程：
    1. 验证配置字段
    2. 检查 data_root（不存在则创建，创建后重新验证）
    3. 检查 originals_root
    4. 检查 database_path（含 SQLite 文件头验证）
    
    Args:
        config: 应用配置
    
    Raises:
        StartupPreflightError: 配置无效或文件系统拓扑异常时
    """
    validate_config(config)
    data_root = Path(config.data_root)
    _check_existing(data_root, "data_root")
    try:
        data_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise StartupPreflightError("data_root_create_failed") from None
    _check_existing(data_root, "data_root")
    _check_existing(config.originals_root, "originals_root")
    _check_existing(config.database_path, "database_path")
