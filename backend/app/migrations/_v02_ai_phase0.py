"""Migration v2: AI phase0 schema."""

from __future__ import annotations

import sqlite3

from ._ai_schema import _create_ai_schema


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v2 migration."""
    _create_ai_schema(connection)
