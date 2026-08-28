"""Canonical material schema creation."""

from __future__ import annotations

import sqlite3

from ._helpers import _columns


def _create_canonical_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS materials (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            stored_path TEXT NOT NULL, media_type TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT, deleted_at TEXT NULL
        );
        CREATE TABLE IF NOT EXISTS extractions (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            parser_id TEXT NOT NULL, parser_version TEXT NOT NULL,
            status TEXT NOT NULL, text TEXT NOT NULL, warnings_json TEXT NOT NULL,
            created_at TEXT NOT NULL, error_code TEXT
        );
        CREATE TABLE IF NOT EXISTS text_spans (
            id TEXT PRIMARY KEY,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL, span_kind TEXT NOT NULL,
            label TEXT NOT NULL, text TEXT NOT NULL
        );
        """
    )
    columns = _columns(connection, "materials")
    if "updated_at" not in columns:
        connection.execute("ALTER TABLE materials ADD COLUMN updated_at TEXT")
        connection.execute("UPDATE materials SET updated_at = created_at WHERE updated_at IS NULL")
    if "deleted_at" not in columns:
        connection.execute("ALTER TABLE materials ADD COLUMN deleted_at TEXT NULL")
    extraction_columns = _columns(connection, "extractions")
    if "error_code" not in extraction_columns:
        connection.execute("ALTER TABLE extractions ADD COLUMN error_code TEXT")
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING "
        "fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
    )


