from __future__ import annotations

import stat
from pathlib import Path

from .config import AppConfig


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
