"""Migration v12: phase9d extended."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v12 migration."""
    """Add the 9D capture/transcript/report facts; domain behavior remains in 9D-3+."""
    # Keep every statement inside migrate()'s BEGIN IMMEDIATE. executescript()
    # would commit before the DDL and defeat migration rollback.
    statements = [
        """
        CREATE TABLE capture_sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('draft','uploaded','transcribing','review_required','confirmed','rejected','failed','archived')),
            asset_kind TEXT NOT NULL CHECK(asset_kind IN ('audio','image')),
            material_id TEXT,
            original_name TEXT NOT NULL CHECK(length(trim(original_name)) BETWEEN 1 AND 255),
            media_type TEXT NOT NULL CHECK(length(trim(media_type)) BETWEEN 1 AND 100),
            source_status TEXT CHECK(source_status IS NULL OR source_status IN ('valid','source_deleted','source_unavailable','stale')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT,
            rejected_at TEXT,
            archived_at TEXT
        )
        """,
        """
        CREATE TABLE transcript_drafts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            capture_session_id TEXT NOT NULL REFERENCES capture_sessions(id) ON DELETE CASCADE,
            operation_id TEXT,
            status TEXT NOT NULL CHECK(status IN ('draft','rejected','confirmed','superseded')),
            text TEXT NOT NULL CHECK(length(text) <= 200000),
            language TEXT CHECK(language IS NULL OR length(language) BETWEEN 1 AND 32),
            quality_status TEXT NOT NULL CHECK(quality_status IN ('clear','uncertain')),
            edited_by_user INTEGER NOT NULL DEFAULT 0 CHECK(edited_by_user IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE transcript_segments (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL REFERENCES transcript_drafts(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
            text TEXT NOT NULL CHECK(length(text) <= 20000),
            confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
            quality TEXT NOT NULL CHECK(quality IN ('clear','uncertain')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(draft_id, ordinal)
        )
        """,
        """
        CREATE TABLE report_snapshots (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            report_kind TEXT NOT NULL CHECK(report_kind IN ('daily','weekly','monthly','exam_alert')),
            timezone TEXT NOT NULL CHECK(length(trim(timezone)) BETWEEN 1 AND 100),
            period_start TEXT NOT NULL CHECK(length(period_start) = 10),
            period_end TEXT NOT NULL CHECK(length(period_end) = 10 AND period_start < period_end),
            status TEXT NOT NULL CHECK(status IN ('draft','ready','failed','archived')),
            content_version TEXT NOT NULL CHECK(length(trim(content_version)) BETWEEN 1 AND 100),
            aggregation_fingerprint TEXT NOT NULL CHECK(length(trim(aggregation_fingerprint)) BETWEEN 1 AND 200),
            safe_payload_json TEXT NOT NULL DEFAULT '{}' CHECK(length(safe_payload_json) <= 200000),
            markdown_content TEXT NOT NULL DEFAULT '' CHECK(length(markdown_content) <= 200000),
            error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ready_at TEXT,
            archived_at TEXT
        )
        """,
        """
        CREATE TABLE report_delivery_attempts (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            report_id TEXT NOT NULL REFERENCES report_snapshots(id) ON DELETE CASCADE,
            channel TEXT NOT NULL CHECK(channel IN ('smtp','feishu')),
            mode TEXT NOT NULL CHECK(mode IN ('off','dry_run','live')),
            target_label TEXT NOT NULL CHECK(length(trim(target_label)) BETWEEN 1 AND 200),
            content_fingerprint TEXT NOT NULL CHECK(length(trim(content_fingerprint)) BETWEEN 1 AND 200),
            idempotency_key_fingerprint TEXT,
            status TEXT NOT NULL CHECK(status IN ('blocked','dry_run','succeeded','failed')),
            error_code TEXT,
            retry_of TEXT,
            created_at TEXT NOT NULL,
            finished_at TEXT
        )
        """,
    ]
    for statement in statements:
        connection.execute(statement)
    connection.execute("ALTER TABLE ai_operations ADD COLUMN capture_session_id TEXT")
    indexes = [
        "CREATE UNIQUE INDEX capture_sessions_material_idx ON capture_sessions(project_id, material_id) WHERE material_id IS NOT NULL",
        "CREATE INDEX capture_sessions_project_status_idx ON capture_sessions(project_id, status, updated_at)",
        "CREATE INDEX capture_sessions_material_idx_lookup ON capture_sessions(material_id, source_status)",
        "CREATE INDEX transcript_drafts_session_status_idx ON transcript_drafts(capture_session_id, status, updated_at)",
        "CREATE INDEX transcript_drafts_operation_idx ON transcript_drafts(operation_id)",
        "CREATE INDEX transcript_segments_draft_ordinal_idx ON transcript_segments(draft_id, ordinal)",
        "CREATE INDEX report_snapshots_project_period_idx ON report_snapshots(project_id, report_kind, period_start, period_end, created_at)",
        "CREATE UNIQUE INDEX report_snapshots_fingerprint_idx ON report_snapshots(project_id, report_kind, period_start, period_end, content_version, aggregation_fingerprint)",
        "CREATE INDEX report_delivery_attempts_report_time_idx ON report_delivery_attempts(report_id, created_at)",
        "CREATE INDEX report_delivery_attempts_project_status_idx ON report_delivery_attempts(project_id, status, created_at)",
        "CREATE UNIQUE INDEX report_delivery_attempts_idempotency_idx ON report_delivery_attempts(project_id, report_id, channel, mode, idempotency_key_fingerprint) WHERE idempotency_key_fingerprint IS NOT NULL",
        "CREATE INDEX ai_operations_capture_session_idx ON ai_operations(capture_session_id, created_at)",
    ]
    for statement in indexes:
        connection.execute(statement)
    
    
