"""Migration v13: phase10 tasks."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v13 migration."""
    """Add runner task envelopes and attempt audit without changing legacy operations."""
    statements = [
        "CREATE UNIQUE INDEX ai_operations_project_id_idx ON ai_operations(project_id, id)",
        """
        CREATE TABLE operation_tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            operation_id TEXT NOT NULL,
            parent_task_id TEXT,
            task_kind TEXT NOT NULL CHECK(length(trim(task_kind)) BETWEEN 1 AND 100),
            status TEXT NOT NULL CHECK(status IN ('queued','running','cancel_requested','succeeded','failed','cancelled','stale')),
            input_fingerprint TEXT NOT NULL CHECK(length(trim(input_fingerprint)) BETWEEN 1 AND 200),
            idempotency_key_fingerprint TEXT CHECK(idempotency_key_fingerprint IS NULL OR length(trim(idempotency_key_fingerprint)) BETWEEN 1 AND 200),
            progress_percent INTEGER CHECK(progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100),
            stage_code TEXT CHECK(stage_code IS NULL OR stage_code IN ('queued','reading_source','indexing','provider_call','persisting','finalizing','recovery_required')),
            retry_count INTEGER NOT NULL DEFAULT 0 CHECK(retry_count >= 0),
            max_retries INTEGER NOT NULL DEFAULT 0 CHECK(max_retries >= 0),
            error_code TEXT CHECK(error_code IS NULL OR length(trim(error_code)) BETWEEN 1 AND 100),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            cancel_requested_at TEXT,
            UNIQUE(operation_id),
            FOREIGN KEY(project_id, operation_id) REFERENCES ai_operations(project_id, id) ON DELETE CASCADE,
            FOREIGN KEY(project_id, parent_task_id) REFERENCES operation_tasks(project_id, id) ON DELETE RESTRICT
        )
        """,
        "CREATE UNIQUE INDEX operation_tasks_project_id_idx ON operation_tasks(project_id, id)",
        """
        CREATE TABLE operation_task_attempts (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL CHECK(attempt_number >= 1),
            status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed','cancelled','stale')),
            progress_percent INTEGER CHECK(progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100),
            stage_code TEXT CHECK(stage_code IS NULL OR stage_code IN ('queued','reading_source','indexing','provider_call','persisting','finalizing','recovery_required')),
            error_code TEXT CHECK(error_code IS NULL OR length(trim(error_code)) BETWEEN 1 AND 100),
            lease_started_at TEXT,
            lease_expires_at TEXT,
            heartbeat_at TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            UNIQUE(task_id, attempt_number),
            FOREIGN KEY(project_id, task_id) REFERENCES operation_tasks(project_id, id) ON DELETE CASCADE
        )
        """,
        "CREATE UNIQUE INDEX operation_task_attempts_running_task_idx ON operation_task_attempts(task_id) WHERE status='running'",
        "CREATE INDEX operation_tasks_project_status_idx ON operation_tasks(project_id, status, updated_at)",
        "CREATE INDEX operation_tasks_status_created_idx ON operation_tasks(status, created_at)",
        "CREATE INDEX operation_task_attempts_task_time_idx ON operation_task_attempts(task_id, attempt_number)",
        "CREATE INDEX operation_task_attempts_lease_idx ON operation_task_attempts(status, lease_expires_at)",
    ]
    for statement in statements:
        connection.execute(statement)
    
    
