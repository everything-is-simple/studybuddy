"""Migration v4: qa idempotency."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v4 migration."""
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN idempotency_key TEXT;
        ALTER TABLE ai_operations ADD COLUMN retrieval_run_id TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS ai_operations_idempotency_key_idx
            ON ai_operations(project_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        """
    )
    
    
