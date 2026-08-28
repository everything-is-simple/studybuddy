"""Migration v5: phase7 embedding."""

from __future__ import annotations

import sqlite3

from ._helpers import _now


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v5 migration."""
    # Rebuild is intentional: SQLite cannot add a CHECK or make a nullable
    # identity component non-null with ALTER TABLE. Unknown legacy rows remain
    # diagnosable but are never silently promoted to ready.
    connection.execute("ALTER TABLE embeddings RENAME TO embeddings_v4")
    connection.executescript("""
        CREATE TABLE embeddings (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL, model_id TEXT NOT NULL,
            model_revision TEXT NOT NULL, dimensions INTEGER NOT NULL,
            vector_encoding TEXT NOT NULL, vector_payload BLOB,
            external_vector_id TEXT, content_hash TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('running','ready','stale','failed')),
            error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(chunk_id, source_revision, content_hash, provider_id, model_id,
                   model_revision, dimensions, vector_encoding)
        );
    """)
    now = _now()
    connection.execute("""INSERT INTO embeddings
        (id,chunk_id,provider_id,model_id,model_revision,dimensions,vector_encoding,
         vector_payload,external_vector_id,content_hash,source_revision,status,error_code,created_at,updated_at)
        SELECT id,chunk_id,provider_id,model_id,COALESCE(model_revision,''),dimensions,vector_encoding,
         vector_payload,external_vector_id,content_hash,source_revision,
         CASE WHEN status IN ('running','ready','stale','failed') THEN
              CASE WHEN status IN ('running','ready') THEN 'stale' ELSE status END
              ELSE 'failed' END,
         CASE WHEN status IN ('running','ready','stale','failed') THEN error_code ELSE 'embedding_legacy_status' END,
         created_at, ? FROM embeddings_v4""", (now,))
    connection.execute("DROP TABLE embeddings_v4")
    connection.execute("CREATE INDEX embeddings_ready_lookup_idx ON embeddings(status, provider_id, model_id, model_revision, dimensions, vector_encoding)")
    
    
