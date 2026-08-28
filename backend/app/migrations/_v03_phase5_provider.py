"""Migration v3: phase5 provider."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v3 migration."""
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN provider_request_id TEXT;
        ALTER TABLE ai_operations ADD COLUMN total_tokens INTEGER;
        ALTER TABLE ai_operations ADD COLUMN finish_reason TEXT;
        """
    )
    
    
