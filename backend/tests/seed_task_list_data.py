from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (claim_operation_task, connect, create_operation_task,
                            finish_operation_task, request_operation_task_cancel)


def seed(data_root: Path) -> None:
    database = data_root / "studybuddy.sqlite3"
    now = datetime.now(timezone.utc).isoformat()
    with connect(database) as connection:
        project = connection.execute("SELECT id FROM projects LIMIT 1").fetchone()
        if project is None:
            connection.execute(
                "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
                ("default", "Synthetic task fixture", now),
            )
            project = connection.execute("SELECT id FROM projects LIMIT 1").fetchone()
        project_id = str(project[0])
        for index, status in enumerate(["cancelled"] * 30 + ["succeeded", "failed"]):
            task_id = f"filter_seed_task_{index:02d}"
            operation_id = f"filter_seed_operation_{index:02d}"
            fingerprint = f"filter-seed-{index:02d}"
            connection.execute(
                "INSERT INTO ai_operations "
                "(id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
                "VALUES (?,?, 'queued', ?, ?, 0, ?)",
                (operation_id, "embedding_index", project_id, fingerprint, now),
            )
            create_operation_task(
                connection, task_id=task_id, project_id=project_id, operation_id=operation_id,
                task_kind="embedding_index", input_fingerprint=fingerprint,
            )
            if status == "cancelled":
                request_operation_task_cancel(connection, task_id=task_id)
            else:
                connection.commit()
                attempt = claim_operation_task(
                    connection, task_id=task_id, lease_seconds=60,
                    attempt_id=f"filter_seed_attempt_{index:02d}",
                )
                finish_operation_task(
                    connection, task_id=task_id, attempt_id=str(attempt["attempt_id"]),
                    status=status, error_code="task_filter_seed_failed" if status == "failed" else None,
                )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("task_filter_seed_invalid_arguments")
    seed(Path(sys.argv[1]))
