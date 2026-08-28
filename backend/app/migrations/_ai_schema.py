"""AI schema creation helper."""

from __future__ import annotations

import sqlite3

from ._helpers import _columns


def _create_ai_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS material_revisions (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            source_sha256 TEXT NOT NULL,
            extraction_sha256 TEXT NOT NULL,
            parser_id TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            revision_fingerprint TEXT NOT NULL UNIQUE,
            is_current INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            superseded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            revision_id TEXT NOT NULL REFERENCES material_revisions(id) ON DELETE CASCADE,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            token_count_estimate INTEGER,
            overlap_before INTEGER NOT NULL,
            overlap_after INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            chunking_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','ready','failed','stale','deleted')),
            error_code TEXT,
            created_at TEXT NOT NULL,
            superseded_at TEXT,
            UNIQUE(revision_id, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS chunk_spans (
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            span_id TEXT NOT NULL,
            overlap_start INTEGER NOT NULL,
            overlap_end INTEGER NOT NULL,
            PRIMARY KEY(chunk_id, span_id)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_search USING
            fts5(id UNINDEXED, text, normalized_text, tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_revision TEXT,
            dimensions INTEGER NOT NULL,
            vector_encoding TEXT NOT NULL,
            vector_payload BLOB,
            external_vector_id TEXT,
            content_hash TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(chunk_id, provider_id, model_id, model_revision, content_hash)
        );
        CREATE TABLE IF NOT EXISTS retrieval_runs (
            id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            normalized_query TEXT NOT NULL,
            project_id TEXT NOT NULL,
            thread_id TEXT,
            policy_version TEXT NOT NULL,
            embedding_provider_id TEXT,
            embedding_model_id TEXT,
            status TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS retrieval_hits (
            run_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            score REAL NOT NULL,
            lexical_score REAL,
            vector_score REAL,
            rerank_score REAL,
            selected INTEGER NOT NULL,
            citation_label TEXT NOT NULL,
            PRIMARY KEY(run_id, chunk_id),
            FOREIGN KEY(run_id) REFERENCES retrieval_runs(id) ON DELETE CASCADE,
            FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS qa_citations (
            id TEXT PRIMARY KEY,
            answer_id TEXT NOT NULL,
            citation_key TEXT NOT NULL,
            material_id TEXT NOT NULL,
            revision_id TEXT,
            extraction_id TEXT,
            chunk_id TEXT,
            span_id TEXT,
            quote TEXT NOT NULL,
            position INTEGER NOT NULL,
            source_revision TEXT,
            status TEXT NOT NULL,
            UNIQUE(answer_id, citation_key)
        );
        CREATE TABLE IF NOT EXISTS ai_operations (
            id TEXT PRIMARY KEY,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled','stale')),
            project_id TEXT NOT NULL,
            material_id TEXT,
            thread_id TEXT,
            input_fingerprint TEXT NOT NULL,
            source_revision TEXT,
            retrieval_policy_version TEXT,
            prompt_version TEXT,
            provider_id TEXT,
            model_id TEXT,
            request_id TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            output_artifact_id TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            latency_ms INTEGER,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_threads (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES qa_threads(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('system','user','assistant','tool')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ai_operation_id TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_answers (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL REFERENCES qa_messages(id) ON DELETE CASCADE,
            ai_operation_id TEXT NOT NULL REFERENCES ai_operations(id) ON DELETE CASCADE,
            answer_text TEXT NOT NULL,
            answer_format TEXT,
            source_coverage TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('draft','ready','rejected','stale')),
            prompt_version TEXT,
            provider_id TEXT,
            model_id TEXT,
            generated_at TEXT NOT NULL
        );
    """)




