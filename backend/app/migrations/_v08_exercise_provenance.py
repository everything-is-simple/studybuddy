"""Migration v8: exercise provenance."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v8 migration."""
    # The original v7 table intentionally remains immutable.  This separate
    # migration records whether an exercise came from a user or an AI draft.
    connection.execute(
        "ALTER TABLE exercises ADD COLUMN exercise_kind TEXT NOT NULL "
        "DEFAULT 'user_created' CHECK(exercise_kind IN ('ai_generated','user_created'))"
    )
    
    
