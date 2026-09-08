"""迁移 v13: Phase 10 后台任务 Schema。

创建任务运行器的任务信封和尝试审计表（不改变旧操作表）：

- operation_tasks: 任务信封（七态状态机，关联 ai_operations）
- operation_task_attempts: 尝试审计（租约/心跳/进度）

设计要点：
- 任务与操作一一对应: UNIQUE(operation_id)
- 复合外键: (project_id, operation_id) → ai_operations(project_id, id)
  要求 ai_operations 有 (project_id, id) 唯一索引（本迁移创建）
- 父任务引用: ON DELETE RESTRICT（防级联丢失子任务）
- 状态机: queued → running → succeeded/failed/cancelled/stale
  cancel_requested 为运行中的取消请求状态
- 阶段代码: queued/reading_source/indexing/provider_call/
  persisting/finalizing/recovery_required
- 租约字段: lease_started_at/lease_expires_at/heartbeat_at
- 运行中唯一: 每任务最多一个 running 尝试（部分唯一索引）

索引策略：
- 调度查询: (status, created_at)
- 项目列表: (project_id, status, updated_at)
- 租约回收: (status, lease_expires_at)
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v13 迁移：创建任务信封和尝试审计表。
    
    创建 2 个表 + 5 个索引 + 1 个前置唯一索引。
    语句列表逐条执行以保持事务原子性。
    
    Args:
        connection: SQLite 连接
    """
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
    
    
