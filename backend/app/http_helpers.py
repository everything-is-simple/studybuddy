from __future__ import annotations

import stat
from pathlib import Path

from fastapi import HTTPException

from .storage import sha256_file
from .services.imports import _valid_filename

def _download_name(original_name: str, suffix: str = "") -> str:
    safe_name = Path(original_name).name.replace('"', "'")
    return f"{safe_name}{suffix}"

def _checked_original_path(config: AppConfig, stored_path: str, expected_hash: str) -> Path:
    root = config.originals_root
    target = Path(stored_path)
    if not target.is_absolute():
        raise HTTPException(status_code=500, detail="original_path_invalid")
    try:
        root_stat = root.lstat()
        if not root.is_dir() or root.is_symlink():
            raise HTTPException(status_code=500, detail="original_path_invalid")
        target.relative_to(root)
        current = root
        for part in target.relative_to(root).parts:
            current = current / part
            if current.is_symlink():
                raise HTTPException(status_code=500, detail="original_path_invalid")
            current.lstat()
    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="original_path_invalid") from exc
    try:
        mode = target.lstat().st_mode
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    import stat
    if not stat.S_ISREG(mode):
        raise HTTPException(status_code=500, detail="original_not_found")
    try:
        actual_hash = sha256_file(target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    if actual_hash != expected_hash:
        raise HTTPException(status_code=500, detail="original_hash_mismatch")
    return target

def _rename_name(raw_name: str) -> str | None:
    name = raw_name.strip()
    if len(name) > 255:
        return None
    return _valid_filename(name)
