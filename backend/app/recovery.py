from __future__ import annotations

import logging
import os
import stat
from pathlib import Path

from .config import AppConfig
from .observability import emit_event, increment
from .repository import connect
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


def reconcile(config: AppConfig) -> None:
    """Run the one-shot, conservative startup reconciliation pass."""
    increment("recovery", "started")
    _cleanup_stale_incoming(config.data_root)
    _reconcile_originals(config)
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
