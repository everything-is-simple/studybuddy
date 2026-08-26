from __future__ import annotations

import sqlite3
import stat
from pathlib import Path
from typing import Any

from .migrations.runner import MigrationError, assert_schema_version

APPLICATION_VERSION = "local-v1"
_TASK_STATUSES = ("queued", "running", "cancel_requested", "succeeded", "failed", "cancelled", "stale")


class DiagnosticError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _readonly_connection(database_path: Path) -> sqlite3.Connection:
    try:
        info = database_path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise DiagnosticError("diagnostic_database_unavailable")
        connection = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except DiagnosticError:
        raise
    except (OSError, ValueError, sqlite3.Error):
        raise DiagnosticError("diagnostic_database_unavailable") from None
    except DiagnosticError:
        return False


def collect_diagnostics(data_root: Path) -> dict[str, Any]:
    """Return a small, safe operator snapshot without paths, SQL, or source data."""
    database_path = Path(data_root) / "studybuddy.sqlite3"
    connection = _readonly_connection(database_path)
    try:
        try:
            schema_version = assert_schema_version(connection)
        except MigrationError as error:
            raise DiagnosticError(error.code) from None
        try:
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0]).lower()
        except sqlite3.Error:
            raise DiagnosticError("diagnostic_database_unavailable") from None
        if quick_check != "ok":
            return {
                "status": "degraded", "application_version": APPLICATION_VERSION,
                "schema_version": schema_version, "task_counts": {status: 0 for status in _TASK_STATUSES},
                "reasons": ["database_integrity_failed"],
                "recommended_actions": ["stop_writes_and_verify_backup"],
            }
        try:
            rows = connection.execute(
                "SELECT status,COUNT(*) AS count FROM operation_tasks GROUP BY status"
            ).fetchall()
        except sqlite3.Error:
            raise DiagnosticError("diagnostic_task_summary_unavailable") from None
        counts = {status: 0 for status in _TASK_STATUSES}
        for row in rows:
            status = str(row["status"])
            if status in counts:
                counts[status] = int(row["count"])
        reasons = ["task_recovery_required"] if counts["stale"] else []
        actions = ["review_stale_tasks_before_explicit_retry"] if counts["stale"] else ["none"]
        return {
            "status": "degraded" if reasons else "ok", "application_version": APPLICATION_VERSION,
            "schema_version": schema_version, "task_counts": counts, "reasons": reasons,
            "recommended_actions": actions,
        }
    finally:
        connection.close()
