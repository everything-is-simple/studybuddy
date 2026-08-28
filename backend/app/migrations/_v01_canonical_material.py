"""Migration v1: Canonical material schema."""

from __future__ import annotations

import sqlite3

from ._canonical import _create_canonical_schema


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v1 migration: canonical material schema."""
    _create_canonical_schema(connection)
