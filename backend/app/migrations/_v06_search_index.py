"""Migration v6: search index."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v6 migration."""
    # Search indexes are schema objects and must be created transactionally.
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING "
        "fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
    )
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_search USING "
        "fts5(id UNINDEXED, text, normalized_text, tokenize='unicode61')"
    )
    
    
