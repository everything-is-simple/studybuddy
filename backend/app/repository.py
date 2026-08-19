from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters.file_parsers.models import ParseResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS materials (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, original_name TEXT NOT NULL, source_sha256 TEXT NOT NULL, stored_path TEXT NOT NULL, media_type TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS extractions (id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE, parser_id TEXT NOT NULL, parser_version TEXT NOT NULL, status TEXT NOT NULL, text TEXT NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS text_spans (id TEXT PRIMARY KEY, extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE, ordinal INTEGER NOT NULL, span_kind TEXT NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL);
"""


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 2000")
    connection.executescript(SCHEMA)
    return connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_extraction(connection: sqlite3.Connection, material_id: str, result: ParseResult) -> str:
    extraction_id = f"extraction_{uuid.uuid4().hex}"
    with connection:
        connection.execute(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (extraction_id, material_id, result.parser_id, result.parser_version, result.status,
             result.text, json.dumps(result.warnings, ensure_ascii=False), utc_now()),
        )
        connection.executemany(
            "INSERT INTO text_spans VALUES (?, ?, ?, ?, ?, ?)",
            [(f"span_{uuid.uuid4().hex}", extraction_id, span.ordinal, span.kind, span.label, span.text)
             for span in result.spans],
        )
    return extraction_id
