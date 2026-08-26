from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .migrations.runner import CURRENT_SCHEMA_VERSION, MigrationError, assert_schema_version, inspect_schema_version
from .observability import emit_event, increment

_FORMAT = "studybuddy-backup"
_VERSION = 1
_DB_NAME = "database.sqlite3"


class BackupError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _lstat(path: Path, code: str) -> stat.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise BackupError(code) from None
    except OSError:
        raise BackupError(code) from None
    if stat.S_ISLNK(info.st_mode):
        raise BackupError(code)
    return info


def _regular(path: Path, code: str) -> None:
    if not stat.S_ISREG(_lstat(path, code).st_mode):
        raise BackupError(code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        raise BackupError("backup_read_failed") from None
    return digest.hexdigest()


def _safe_children(root: Path) -> list[Path]:
    try:
        return list(root.iterdir())
    except OSError:
        raise BackupError("backup_scan_failed") from None


def _inside(child: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((os.path.abspath(child), os.path.abspath(parent))) == os.path.abspath(parent)
    except ValueError:
        return False


def _sqlite_header(path: Path, code: str) -> None:
    _regular(path, code)
    try:
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise BackupError(code)
    except BackupError:
        raise
    except OSError:
        raise BackupError(code) from None


def _checks(path: Path, *, require_current: bool) -> tuple[str, str, int]:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA query_only = ON")
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
        try:
            version = assert_schema_version(connection) if require_current else inspect_schema_version(connection)
        except MigrationError:
            raise BackupError("backup_schema_version_invalid") from None
    except BackupError:
        raise
    except (OSError, sqlite3.Error):
        raise BackupError("backup_database_integrity_failed") from None
    finally:
        if connection is not None:
            connection.close()
    return integrity, "ok" if not foreign else "failed", version


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".manifest-", suffix=".tmp", mode="w", encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        if temporary:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        raise BackupError("backup_create_failed") from None


def _copy_atomic(source: Path, target: Path, error: str = "backup_create_failed") -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".copy-", delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle, 1024 * 1024)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        if temporary:
            try: temporary.unlink(missing_ok=True)
            except OSError: pass
        raise BackupError(error) from None


def _referenced_hashes(database: Path) -> tuple[set[str], dict[str, int]]:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute("SELECT source_sha256 FROM materials").fetchall()
        project = connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
        active = connection.execute("SELECT COUNT(*) FROM materials WHERE deleted_at IS NULL").fetchone()[0]
        deleted = connection.execute("SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL").fetchone()[0]
    except (OSError, sqlite3.Error):
        raise BackupError("backup_database_read_failed") from None
    finally:
        if connection is not None:
            connection.close()
    hashes = {str(row[0]).lower() for row in rows}
    if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value) for value in hashes):
        raise BackupError("backup_reference_invalid")
    return hashes, {"material_count": project, "active_material_count": active, "deleted_material_count": deleted, "source_hash_count": len(hashes)}


def _validate_layout(originals: Path, digest: str) -> Path:
    target = originals / digest[:2] / digest[2:] / "original"
    try:
        originals_stat = originals.lstat()
    except OSError:
        raise BackupError("backup_original_missing") from None
    if stat.S_ISLNK(originals_stat.st_mode) or not stat.S_ISDIR(originals_stat.st_mode):
        raise BackupError("backup_original_invalid")
    current = originals
    for part in (digest[:2], digest[2:], "original"):
        current = current / part
        try: info = current.lstat()
        except OSError: raise BackupError("backup_original_missing") from None
        if stat.S_ISLNK(info.st_mode): raise BackupError("backup_original_symlink")
    _regular(target, "backup_original_invalid")
    return target


def backup_data(data_root: Path, output: Path, project_id: str = "default") -> dict[str, Any]:
    increment("backup", "started")
    emit_event("backup_started", component="backup", outcome="started")
    data_root, output = Path(data_root), Path(output)
    if output.exists() or output.is_symlink(): raise BackupError("backup_output_exists")
    if _inside(output, data_root): raise BackupError("backup_output_inside_data_root")
    _regular(data_root / "studybuddy.sqlite3", "backup_database_missing")
    _sqlite_header(data_root / "studybuddy.sqlite3", "backup_database_not_sqlite")
    originals = data_root / "originals"
    _lstat(originals, "backup_originals_missing")
    hashes, references = _referenced_hashes(data_root / "studybuddy.sqlite3")
    try:
        output.mkdir(parents=True)
        (output / "originals").mkdir()
    except OSError: raise BackupError("backup_create_failed") from None
    try:
        source = sqlite3.connect(data_root / "studybuddy.sqlite3")
        destination = sqlite3.connect(output / _DB_NAME)
        source.backup(destination)
        destination.close(); source.close()
        integrity, foreign, schema_version = _checks(output / _DB_NAME, require_current=False)
        if integrity != "ok": raise BackupError("backup_database_integrity_failed")
        if foreign != "ok": raise BackupError("backup_foreign_key_check_failed")
        files = []; total = 0
        for digest in sorted(hashes):
            source_file = _validate_layout(originals, digest)
            if _sha256(source_file) != digest: raise BackupError("backup_original_hash_mismatch")
            relative = Path(digest[:2]) / digest[2:] / "original"
            target = output / "originals" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_atomic(source_file, target)
            size = target.stat().st_size
            files.append({"relative_path": str(Path("originals") / relative).replace("\\", "/"), "sha256": digest, "size": size})
            total += size
        manifest = {"format": _FORMAT, "format_version": _VERSION, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "project_id": project_id, "database": {"filename": _DB_NAME, "sha256": _sha256(output / _DB_NAME), "size": (output / _DB_NAME).stat().st_size, "integrity_check": integrity, "foreign_key_check": foreign, "schema_version": schema_version, "current_schema_at_backup": CURRENT_SCHEMA_VERSION}, "originals": {"root": "originals", "count": len(files), "total_bytes": total, "files": files}, "references": references}
        _atomic_json(output / "manifest.json", manifest)
        increment("backup", "succeeded")
        emit_event("backup_completed", component="backup", outcome="succeeded")
        return {"status": "complete", "error_code": None, "original_count": len(files)}
    except BackupError as error:
        increment("backup", "failed")
        emit_event("backup_failed", level=40, error_code=error.code, component="backup", outcome="failed")
        raise
    except (OSError, sqlite3.Error):
        increment("backup", "failed")
        emit_event("backup_failed", level=40, error_code="backup_create_failed", component="backup", outcome="failed")
        raise BackupError("backup_create_failed") from None


def _manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    _regular(path, "backup_manifest_missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError): raise BackupError("backup_manifest_invalid") from None
    if not isinstance(value, dict) or value.get("format") != _FORMAT or value.get("format_version") != _VERSION or value.get("status") != "complete":
        raise BackupError("backup_manifest_invalid")
    return value


def _verify_backup(backup: Path) -> dict[str, Any]:
    increment("backup_verify", "started")
    backup = Path(backup)
    _lstat(backup, "invalid_backup_root")
    if not stat.S_ISDIR(backup.stat().st_mode): raise BackupError("invalid_backup_root")
    manifest = _manifest(backup)
    database = backup / _DB_NAME
    _sqlite_header(database, "backup_database_not_sqlite")
    database_meta = manifest.get("database")
    if not isinstance(database_meta, dict):
        raise BackupError("backup_manifest_invalid")
    if database_meta.get("filename") != _DB_NAME:
        raise BackupError("backup_manifest_invalid")
    if _sha256(database) != database_meta.get("sha256"):
        raise BackupError("backup_database_hash_mismatch")
    if database_meta.get("size") != database.stat().st_size:
        raise BackupError("backup_manifest_invalid")
    integrity, foreign, schema_version = _checks(database, require_current=False)
    if integrity != "ok" or database_meta.get("integrity_check") != "ok":
        raise BackupError("backup_database_integrity_failed")
    if foreign != "ok" or database_meta.get("foreign_key_check") != "ok":
        raise BackupError("backup_foreign_key_check_failed")
    if database_meta.get("schema_version") != schema_version:
        raise BackupError("backup_schema_version_mismatch")
    recorded_current = database_meta.get("current_schema_at_backup")
    if recorded_current is not None and (not isinstance(recorded_current, int) or recorded_current < schema_version):
        raise BackupError("backup_schema_version_mismatch")
    files = manifest.get("originals", {}).get("files", [])
    if not isinstance(files, list): raise BackupError("backup_manifest_invalid")
    for item in files:
        relative = item.get("relative_path") if isinstance(item, dict) else None
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts: raise BackupError("backup_manifest_invalid")
        expected_relative = Path("originals") / str(item.get("sha256", ""))[:2] / str(item.get("sha256", ""))[2:] / "original"
        if Path(relative) != expected_relative: raise BackupError("backup_manifest_invalid")
        target = backup / relative
        if not _inside(target, backup): raise BackupError("backup_manifest_invalid")
        _regular(target, "backup_original_invalid")
        if _sha256(target) != item.get("sha256"): raise BackupError("backup_original_hash_mismatch")
        if target.stat().st_size != item.get("size"): raise BackupError("backup_original_hash_mismatch")
    hashes, _ = _referenced_hashes(database)
    listed = {item.get("sha256") for item in files}
    if hashes != listed: raise BackupError("backup_originals_incomplete")
    increment("backup_verify", "succeeded")
    emit_event("backup_verify_completed", component="backup", outcome="succeeded")
    return {"status": "valid", "error_code": None, "database_integrity": "ok", "foreign_key_check": "ok", "original_count": len(files)}


def verify_backup(backup: Path) -> dict[str, Any]:
    try:
        return _verify_backup(backup)
    except BackupError as error:
        increment("backup_verify", "failed")
        emit_event("backup_verify_failed", level=40, error_code=error.code,
                   component="backup", outcome="failed")
        raise


def _rebase_restored_material_paths(database: Path, data_root: Path) -> None:
    """Repoint internal original references to the explicitly selected restore root."""
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        rows = connection.execute("SELECT id,source_sha256 FROM materials").fetchall()
        for material_id, digest in rows:
            if not isinstance(digest, str) or len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest.lower()
            ):
                raise BackupError("backup_reference_invalid")
            stored_path = data_root / "originals" / digest[:2] / digest[2:] / "original"
            connection.execute(
                "UPDATE materials SET stored_path=? WHERE id=?",
                (str(stored_path), material_id),
            )
        connection.commit()
        connection.close()
        integrity, foreign, _ = _checks(database, require_current=False)
        if integrity != "ok":
            raise BackupError("restore_database_integrity_failed")
        if foreign != "ok":
            raise BackupError("restore_foreign_key_check_failed")
    except BackupError:
        try:
            connection.close()
        except Exception:
            pass
        raise
    except (OSError, sqlite3.Error):
        try:
            connection.close()
        except Exception:
            pass
        raise BackupError("restore_database_update_failed") from None


def rotate_backups(backup_root: Path, *, retain: int, confirm: bool = False) -> dict[str, Any]:
    """Delete only older verified backup directories after an explicit confirmation."""
    increment("backup_rotation", "started")
    if retain < 1:
        increment("backup_rotation", "failed")
        emit_event("backup_rotation_failed", level=40, error_code="backup_retention_invalid",
                   component="backup", outcome="failed")
        raise BackupError("backup_retention_invalid")
    root = Path(backup_root)
    _lstat(root, "backup_rotation_root_invalid")
    if not stat.S_ISDIR(root.stat().st_mode):
        raise BackupError("backup_rotation_root_invalid")
    candidates: list[tuple[str, Path]] = []
    for child in _safe_children(root):
        try:
            info = child.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            continue
        try:
            manifest = _manifest(child)
            verify_backup(child)
            created_at = manifest.get("created_at")
            if not isinstance(created_at, str):
                continue
            candidates.append((created_at, child))
        except BackupError:
            # Unknown, incomplete, or invalid artifacts are evidence, not rotation candidates.
            continue
    candidates.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    selected = candidates[retain:]
    if not confirm:
        increment("backup_rotation", "dry_run")
        emit_event("backup_rotation_dry_run", component="backup", outcome="dry_run")
        return {"status": "dry_run", "error_code": None, "verified_count": len(candidates),
                "retain": retain, "delete_count": len(selected)}
    deleted = 0
    try:
        # Validate the complete deletion set before removing anything. This
        # guarantees an invalid/corrupt old artifact cannot turn a rotation
        # failure into a deletion of another verified backup.
        for _created_at, candidate in selected:
            _lstat(candidate, "backup_rotation_candidate_invalid")
            verify_backup(candidate)
        for _created_at, candidate in selected:
            _lstat(candidate, "backup_rotation_candidate_invalid")
            shutil.rmtree(candidate)
            deleted += 1
    except (BackupError, OSError, shutil.Error):
        # Existing verified backups and the live data root remain untouched on a rotation failure.
        increment("backup_rotation", "failed")
        emit_event("backup_rotation_failed", level=40, error_code="backup_rotation_failed",
                   component="backup", outcome="failed")
        raise BackupError("backup_rotation_failed") from None
    increment("backup_rotation", "succeeded")
    emit_event("backup_rotation_completed", component="backup", outcome="succeeded")
    return {"status": "rotated", "error_code": None, "verified_count": len(candidates),
            "retain": retain, "deleted_count": deleted}


def upgrade_preflight(data_root: Path, verified_backup: Path) -> dict[str, Any]:
    """Non-mutating upgrade decision check; it never migrates, repairs, or writes."""
    increment("upgrade_preflight", "started")
    root = Path(data_root)
    database = root / "studybuddy.sqlite3"
    try:
        _lstat(root, "upgrade_data_root_invalid")
        if not stat.S_ISDIR(root.stat().st_mode):
            raise BackupError("upgrade_data_root_invalid")
        _sqlite_header(database, "upgrade_database_missing")
        # This is only an ACL/access preflight, not a substitute for the later
        # SQLite transaction. It lets an operator stop before a known unwritable root.
        if not os.access(root, os.W_OK) or not os.access(database, os.W_OK):
            raise BackupError("upgrade_data_root_not_writable")
        integrity, foreign, schema_version = _checks(database, require_current=False)
        if integrity != "ok":
            raise BackupError("upgrade_database_integrity_failed")
        if foreign != "ok":
            raise BackupError("upgrade_foreign_key_check_failed")
        originals = root / "originals"
        originals_info = _lstat(originals, "upgrade_originals_missing")
        if not stat.S_ISDIR(originals_info.st_mode):
            raise BackupError("upgrade_originals_invalid")
        hashes, _references = _referenced_hashes(database)
        for digest in hashes:
            source_file = _validate_layout(originals, digest)
            if _sha256(source_file) != digest:
                raise BackupError("upgrade_original_hash_mismatch")
        backup_result = verify_backup(verified_backup)
        backup_database = Path(verified_backup) / _DB_NAME
        _backup_integrity, _backup_foreign, backup_schema_version = _checks(
            backup_database, require_current=False
        )
        if backup_schema_version != schema_version:
            raise BackupError("upgrade_backup_schema_mismatch")
        result = {
            "status": "ready", "error_code": None, "database_schema_version": schema_version,
            "backup_schema_version": backup_schema_version,
            "target_schema_version": CURRENT_SCHEMA_VERSION,
            "migration_required": schema_version != CURRENT_SCHEMA_VERSION,
            "backup_verified": backup_result["status"] == "valid",
        }
        increment("upgrade_preflight", "ready")
        emit_event("upgrade_preflight_completed", component="operator", outcome="ready")
        return result
    except BackupError as error:
        increment("upgrade_preflight", "failed")
        emit_event("upgrade_preflight_failed", level=40, error_code=error.code,
                   component="operator", outcome="failed")
        raise


def restore_backup(data_root: Path, backup: Path, confirm: bool = False) -> dict[str, Any]:
    increment("restore", "started")
    emit_event("restore_started", component="backup", outcome="started")
    if not confirm:
        increment("restore", "failed")
        emit_event("restore_failed", level=40, error_code="restore_confirmation_required",
                   component="backup", outcome="failed")
        raise BackupError("restore_confirmation_required")
    data_root, backup = Path(data_root), Path(backup)
    if data_root.exists() or data_root.is_symlink():
        _lstat(data_root, "restore_target_symlink")
        if not stat.S_ISDIR(data_root.stat().st_mode): raise BackupError("restore_target_invalid")
        if _safe_children(data_root): raise BackupError("restore_target_not_empty")
    verify_backup(backup)
    staging = data_root.parent / (data_root.name + ".restore-staging")
    if staging.exists() or staging.is_symlink(): raise BackupError("restore_staging_failed")
    connection: sqlite3.Connection | None = None
    try:
        staging.mkdir(parents=True)
        shutil.copy2(backup / _DB_NAME, staging / _DB_NAME)
        shutil.copy2(backup / "manifest.json", staging / "manifest.json")
        shutil.copytree(backup / "originals", staging / "originals")
        verify_backup(staging)
        (staging / _DB_NAME).rename(staging / "studybuddy.sqlite3")
        (staging / "manifest.json").unlink()
        _rebase_restored_material_paths(staging / "studybuddy.sqlite3", data_root)
        if data_root.exists():
            data_root.rmdir()
        staging.rename(data_root)
    except BackupError as error:
        try: shutil.rmtree(staging, ignore_errors=True)
        except OSError: pass
        increment("restore", "failed")
        emit_event("restore_failed", level=40, error_code=error.code, component="backup", outcome="failed")
        raise
    except (OSError, shutil.Error, sqlite3.Error):
        try: shutil.rmtree(staging, ignore_errors=True)
        except OSError: pass
        increment("restore", "failed")
        emit_event("restore_failed", level=40, error_code="restore_replace_failed", component="backup", outcome="failed")
        raise BackupError("restore_replace_failed") from None
    increment("restore", "succeeded")
    emit_event("restore_completed", component="backup", outcome="succeeded")
    return {"status": "restored", "error_code": None}
