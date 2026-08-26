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
    """Validate existing storage topology without following or deleting paths."""
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
