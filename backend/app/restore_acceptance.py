from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .migrations.runner import MigrationError, assert_schema_version


class AcceptanceError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        raise AcceptanceError("acceptance_original_read_failed") from None
    return digest.hexdigest()


def _safe_original(root: Path, stored_path: str, expected_hash: str) -> Path:
    target = Path(stored_path)
    try:
        root_info = root.lstat()
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise AcceptanceError("acceptance_original_root_invalid")
        target.relative_to(root)
        current = root
        for part in target.relative_to(root).parts:
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise AcceptanceError("acceptance_original_symlink")
            if not stat.S_ISREG(info.st_mode) and current == target:
                raise AcceptanceError("acceptance_original_invalid")
        if not stat.S_ISREG(target.lstat().st_mode):
            raise AcceptanceError("acceptance_original_invalid")
    except AcceptanceError:
        raise
    except (OSError, ValueError):
        raise AcceptanceError("acceptance_original_missing") from None
    if _sha256_file(target) != expected_hash:
        raise AcceptanceError("acceptance_original_hash_mismatch")
    return target


def _check_database(data_root: Path) -> tuple[sqlite3.Connection, dict[str, Any]]:
    database = data_root / "studybuddy.sqlite3"
    connection: sqlite3.Connection | None = None
    if database.is_symlink() or not database.is_file():
        raise AcceptanceError("acceptance_database_missing")
    try:
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0]).lower()
        foreign = connection.execute("PRAGMA foreign_key_check").fetchall()
        version = assert_schema_version(connection)
        history_count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        if integrity != "ok":
            raise AcceptanceError("acceptance_database_integrity_failed")
        if foreign:
            raise AcceptanceError("acceptance_foreign_key_check_failed")
        return connection, {"schema_version": version, "history_count": history_count}
    except AcceptanceError:
        if connection is not None:
            connection.close()
        raise
    except (OSError, sqlite3.Error, MigrationError):
        try:
            connection.close()
        except Exception:
            pass
        raise AcceptanceError("acceptance_database_invalid") from None


def _offline(data_root: Path) -> dict[str, Any]:
    connection, metadata = _check_database(data_root)
    checks: dict[str, Any] = {
        "health": {"status": "skipped", "reason": "offline_mode"},
        "active_list": {"status": "passed"},
        "deleted_list": {"status": "passed"},
        "detail": {"status": "skipped", "reason": "no_active_material"},
        "original_download": {"status": "skipped", "reason": "offline_mode"},
        "text_export": {"status": "skipped", "reason": "offline_mode"},
        "integrity": {"status": "passed"},
        "foreign_keys": {"status": "passed"},
        "schema_history": {"status": "passed", "count": metadata["history_count"]},
    }
    try:
        active = connection.execute(
            "SELECT m.id, m.original_name, m.stored_path, m.source_sha256, e.text "
            "FROM materials m JOIN extractions e ON e.material_id = m.id "
            "WHERE m.deleted_at IS NULL ORDER BY m.created_at, m.id"
        ).fetchall()
        deleted_count = connection.execute(
            "SELECT COUNT(*) FROM materials WHERE deleted_at IS NOT NULL"
        ).fetchone()[0]
        checks["active_list"]["count"] = len(active)
        checks["deleted_list"]["count"] = deleted_count
        if active:
            row = active[0]
            target = _safe_original(data_root / "originals", row["stored_path"], row["source_sha256"])
            checks["detail"] = {
                "status": "passed",
                "material_id": str(row["id"]),
                "original_name": str(row["original_name"]),
                "text_sha256": _sha256_bytes(str(row["text"]).encode("utf-8")),
            }
            checks["original_download"] = {
                "status": "passed", "sha256": _sha256_file(target), "size": target.stat().st_size
            }
            checks["text_export"] = {
                "status": "passed", "sha256": _sha256_bytes(str(row["text"]).encode("utf-8")),
                "size": len(str(row["text"]).encode("utf-8")),
            }
        return {"status": "passed", "mode": "offline", **metadata, "checks": checks, "error_code": None}
    finally:
        connection.close()


def _http_json(base_url: str, path: str) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise AcceptanceError("acceptance_http_request_failed") from None


def _http_bytes(base_url: str, path: str) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=5) as response:
            return response.status, {str(k).lower(): str(v) for k, v in response.headers.items()}, response.read()
    except OSError:
        raise AcceptanceError("acceptance_http_request_failed") from None


def _online(data_root: Path, base_url: str) -> dict[str, Any]:
    result = _offline(data_root)
    checks = result["checks"]
    status, health = _http_json(base_url, "/api/health")
    if status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        raise AcceptanceError("acceptance_health_failed")
    checks["health"] = {"status": "passed"}
    status, active = _http_json(base_url, "/api/materials")
    if status != 200 or not isinstance(active, list):
        raise AcceptanceError("acceptance_active_list_failed")
    status, deleted = _http_json(base_url, "/api/materials/deleted")
    if status != 200 or not isinstance(deleted, list):
        raise AcceptanceError("acceptance_deleted_list_failed")
    checks["active_list"]["http_count"] = len(active)
    checks["deleted_list"]["http_count"] = len(deleted)
    if active:
        material_id = str(active[0].get("id", ""))
        status, detail = _http_json(base_url, "/api/materials/" + material_id)
        if status != 200 or not isinstance(detail, dict):
            raise AcceptanceError("acceptance_detail_failed")
        status, headers, original = _http_bytes(base_url, "/api/materials/" + material_id + "/original")
        expected = str(detail.get("source_sha256", ""))
        if status != 200 or _sha256_bytes(original) != expected:
            raise AcceptanceError("acceptance_original_download_failed")
        status, headers, text = _http_bytes(base_url, "/api/materials/" + material_id + "/text")
        if status != 200 or "text/plain" not in headers.get("content-type", "") or not text.decode("utf-8"):
            raise AcceptanceError("acceptance_text_export_failed")
        checks["detail"] = {"status": "passed", "material_id": material_id}
        checks["original_download"] = {"status": "passed", "sha256": _sha256_bytes(original), "size": len(original)}
        checks["text_export"] = {"status": "passed", "sha256": _sha256_bytes(text), "size": len(text)}
    return {**result, "mode": "online"}


def verify_restored_data(data_root: Path, base_url: str | None = None) -> dict[str, Any]:
    try:
        return _online(Path(data_root), base_url) if base_url else _offline(Path(data_root))
    except AcceptanceError as error:
        return {"status": "failed", "mode": "online" if base_url else "offline", "error_code": error.code}
