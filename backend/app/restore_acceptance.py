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


def _study_checks(connection: sqlite3.Connection) -> dict[str, Any]:
    required_tables = (
        "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
        "study_plan_dependencies", "study_progress_events", "module_source_links",
        "plan_item_source_links", "notes", "note_blocks", "note_module_links",
        "note_block_source_links", "rhythm_settings", "rhythm_allocations",
        "practice_sessions", "practice_session_items", "exercise_attempt_reviews",
        "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals",
    )
    placeholders = ",".join("?" for _ in required_tables)
    present = {
        str(row[0]) for row in connection.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
            required_tables,
        ).fetchall()
    }
    if present != set(required_tables):
        raise AcceptanceError("acceptance_study_schema_missing")

    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in required_tables
    }
    plan_statuses = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM study_plans GROUP BY status ORDER BY status"
        ).fetchall()
    }
    source_statuses = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM ("
            "SELECT status FROM module_source_links "
            "UNION ALL SELECT status FROM plan_item_source_links"
            ") GROUP BY status ORDER BY status"
        ).fetchall()
    }
    summary_rows = connection.execute(
        "SELECT p.id, "
        "SUM(CASE WHEN i.status != 'archived' THEN 1 ELSE 0 END) AS item_count, "
        "SUM(CASE WHEN i.status = 'completed' THEN 1 ELSE 0 END) AS completed_count, "
        "SUM(CASE WHEN i.status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count, "
        "SUM(CASE WHEN i.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_count, "
        "SUM(CASE WHEN i.status = 'pending' THEN 1 ELSE 0 END) AS pending_count "
        "FROM study_plans p LEFT JOIN study_plan_items i ON i.plan_id = p.id "
        "GROUP BY p.id"
    ).fetchall()
    projection = {"pending": "pending", "started": "in_progress", "reopened": "in_progress", "completed": "completed", "skipped": "skipped"}
    item_rows = connection.execute(
        "SELECT i.id, i.status, e.event_type FROM study_plan_items i "
        "LEFT JOIN study_progress_events e ON e.id = ("
        "SELECT e2.id FROM study_progress_events e2 WHERE e2.item_id=i.id "
        "ORDER BY e2.created_at DESC, e2.id DESC LIMIT 1"
        ") ORDER BY i.id"
    ).fetchall()
    for row in item_rows:
        expected_status = projection.get(str(row[2]), "pending") if row[2] is not None else "pending"
        if str(row[1]) != "archived" and str(row[1]) != expected_status:
            raise AcceptanceError("acceptance_study_projection_invalid")
    for row in summary_rows:
        values = [int(row[index] or 0) for index in range(1, 6)]
        if any(value < 0 for value in values) or values[0] != sum(values[1:]):
            raise AcceptanceError("acceptance_study_summary_invalid")
    invalid_valid_links = connection.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT status,material_id FROM module_source_links "
        "UNION ALL SELECT status,material_id FROM plan_item_source_links "
        "UNION ALL SELECT status,material_id FROM note_block_source_links"
        ") WHERE status='valid' AND material_id IS NULL"
    ).fetchone()[0]
    if invalid_valid_links:
        raise AcceptanceError("acceptance_study_source_invalid")
    invalid_note_blocks = connection.execute(
        "SELECT COUNT(*) FROM notes n WHERE NOT EXISTS (SELECT 1 FROM note_blocks b WHERE b.note_id=n.id)"
    ).fetchone()[0]
    if invalid_note_blocks:
        raise AcceptanceError("acceptance_note_blocks_missing")
    invalid_rhythm = connection.execute(
        "SELECT COUNT(*) FROM rhythm_allocations a LEFT JOIN rhythm_settings s ON s.plan_id=a.plan_id "
        "WHERE s.plan_id IS NULL"
    ).fetchone()[0]
    if invalid_rhythm:
        raise AcceptanceError("acceptance_rhythm_settings_missing")
    note_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM notes GROUP BY status ORDER BY status"
        ).fetchall()
    }
    note_source_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM note_block_source_links GROUP BY status ORDER BY status"
        ).fetchall()
    }
    phase9c_source_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT source_status,COUNT(*) FROM mistake_occurrences GROUP BY source_status ORDER BY source_status"
        ).fetchall()
    }
    phase9c_session_statuses = {
        str(row[0]): int(row[1]) for row in connection.execute(
            "SELECT status,COUNT(*) FROM practice_sessions GROUP BY status ORDER BY status"
        ).fetchall()
    }
    invalid_session_items = connection.execute(
        "SELECT COUNT(*) FROM practice_session_items i "
        "JOIN practice_sessions s ON s.id=i.session_id "
        "JOIN exercises e ON e.id=i.exercise_id "
        "WHERE i.project_id != s.project_id OR e.project_id != i.project_id"
    ).fetchone()[0]
    if invalid_session_items:
        raise AcceptanceError("acceptance_phase9c_session_scope_invalid")
    invalid_attempt_links = connection.execute(
        "SELECT COUNT(*) FROM exercise_attempts a "
        "JOIN practice_session_items i ON i.id=a.session_item_id "
        "WHERE a.session_id != i.session_id OR a.exercise_id != i.exercise_id"
    ).fetchone()[0]
    if invalid_attempt_links:
        raise AcceptanceError("acceptance_phase9c_attempt_link_invalid")
    invalid_review_links = connection.execute(
        "SELECT COUNT(*) FROM exercise_attempt_reviews r "
        "JOIN exercise_attempts a ON a.id=r.attempt_id "
        "WHERE r.exercise_id != a.exercise_id"
    ).fetchone()[0]
    if invalid_review_links:
        raise AcceptanceError("acceptance_phase9c_review_link_invalid")
    return {
        "status": "passed",
        "counts": counts,
        "plan_statuses": plan_statuses,
        "source_statuses": source_statuses,
        "note_statuses": note_statuses,
        "note_source_statuses": note_source_statuses,
        "phase9c_source_statuses": phase9c_source_statuses,
        "phase9c_session_statuses": phase9c_session_statuses,
        "rhythm_settings_count": counts["rhythm_settings"],
        "rhythm_allocations_count": counts["rhythm_allocations"],
        "summary_plan_count": len(summary_rows),
        "user_edited_count": int(connection.execute(
            "SELECT COUNT(*) FROM study_plans WHERE user_edited=1"
        ).fetchone()[0]),
        "note_user_edited_count": int(connection.execute(
            "SELECT COUNT(*) FROM notes WHERE user_edited=1"
        ).fetchone()[0]),
    }


def _phase9d_checks(connection: sqlite3.Connection) -> dict[str, Any]:
    required_tables = (
        "capture_sessions", "transcript_drafts", "transcript_segments",
        "report_snapshots", "report_delivery_attempts",
    )
    placeholders = ",".join("?" for _ in required_tables)
    present = {
        str(row[0]) for row in connection.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
            required_tables,
        ).fetchall()
    }
    if present != set(required_tables):
        raise AcceptanceError("acceptance_phase9d_schema_missing")

    invalid_draft_scope = connection.execute(
        "SELECT COUNT(*) FROM transcript_drafts d JOIN capture_sessions c ON c.id=d.capture_session_id "
        "WHERE d.project_id != c.project_id"
    ).fetchone()[0]
    if invalid_draft_scope:
        raise AcceptanceError("acceptance_phase9d_draft_scope_invalid")
    invalid_segment_scope = connection.execute(
        "SELECT COUNT(*) FROM transcript_segments s JOIN transcript_drafts d ON d.id=s.draft_id "
        "WHERE s.project_id != d.project_id"
    ).fetchone()[0]
    if invalid_segment_scope:
        raise AcceptanceError("acceptance_phase9d_segment_scope_invalid")
    invalid_operation_scope = connection.execute(
        "SELECT COUNT(*) FROM ai_operations o LEFT JOIN capture_sessions c ON c.id=o.capture_session_id "
        "WHERE o.capture_session_id IS NOT NULL AND (c.id IS NULL OR o.project_id != c.project_id)"
    ).fetchone()[0]
    if invalid_operation_scope:
        raise AcceptanceError("acceptance_phase9d_operation_scope_invalid")
    invalid_delivery_scope = connection.execute(
        "SELECT COUNT(*) FROM report_delivery_attempts a JOIN report_snapshots r ON r.id=a.report_id "
        "WHERE a.project_id != r.project_id"
    ).fetchone()[0]
    if invalid_delivery_scope:
        raise AcceptanceError("acceptance_phase9d_delivery_scope_invalid")
    invalid_valid_source = connection.execute(
        "SELECT COUNT(*) FROM capture_sessions c LEFT JOIN materials m ON m.id=c.material_id "
        "WHERE c.source_status='valid' AND (m.id IS NULL OR m.project_id != c.project_id OR m.deleted_at IS NOT NULL)"
    ).fetchone()[0]
    if invalid_valid_source:
        raise AcceptanceError("acceptance_phase9d_source_invalid")

    return {
        "status": "passed",
        "counts": {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in required_tables
        },
        "capture_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM capture_sessions GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "capture_source_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT COALESCE(source_status,'unbound'),COUNT(*) FROM capture_sessions "
                "GROUP BY COALESCE(source_status,'unbound') ORDER BY 1"
            ).fetchall()
        },
        "report_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM report_snapshots GROUP BY status ORDER BY status"
            ).fetchall()
        },
        "delivery_statuses": {
            str(row[0]): int(row[1]) for row in connection.execute(
                "SELECT status,COUNT(*) FROM report_delivery_attempts GROUP BY status ORDER BY status"
            ).fetchall()
        },
    }


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
        "study": _study_checks(connection),
        "phase9d": _phase9d_checks(connection),
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
