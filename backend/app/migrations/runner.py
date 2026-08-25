from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

CURRENT_SCHEMA_VERSION = 12
HISTORY_TABLE = "schema_migrations"


class MigrationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class MigrationResult:
    current_version: int
    applied_versions: tuple[int, ...]
    adopted_legacy: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _objects(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    )}


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _create_history(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )


def _baseline_complete(connection: sqlite3.Connection) -> bool:
    objects = _objects(connection)
    required_core = {"projects", "materials", "extractions", "text_spans"}
    required_ai = {
        "material_revisions", "chunks", "chunk_spans", "embeddings",
        "retrieval_runs", "retrieval_hits", "qa_citations",
        "ai_operations", "qa_threads", "qa_messages", "qa_answers",
        "study_decks", "study_cards", "card_citations", "card_reviews",
        "exercise_sets", "exercises", "exercise_citations", "exercise_attempts",
    }
    if CURRENT_SCHEMA_VERSION >= 9:
        required_ai |= {
            "learning_goals", "knowledge_modules", "study_plans", "study_plan_items",
            "study_plan_dependencies", "study_progress_events", "module_source_links",
            "plan_item_source_links",
        }
    if CURRENT_SCHEMA_VERSION >= 10:
        required_ai |= {
            "notes", "note_blocks", "note_module_links", "note_block_source_links",
            "rhythm_settings", "rhythm_allocations",
        }
    if CURRENT_SCHEMA_VERSION >= 11:
        required_ai |= {
            "practice_sessions", "practice_session_items", "exercise_attempt_reviews",
            "mistake_cases", "mistake_occurrences", "mistake_feedback_events", "cram_goals",
        }
    if CURRENT_SCHEMA_VERSION >= 12:
        required_ai |= {
            "capture_sessions", "transcript_drafts", "transcript_segments",
            "report_snapshots", "report_delivery_attempts",
        }
    if not (required_core | required_ai | {"material_search", "chunks_search"}).issubset(objects):
        return False
    if not {
        "id", "project_id", "original_name", "source_sha256", "stored_path",
        "media_type", "created_at", "updated_at", "deleted_at",
    }.issubset(_columns(connection, "materials")):
        return False
    if not {
        "id", "material_id", "parser_id", "parser_version", "status", "text",
        "warnings_json", "created_at", "error_code",
    }.issubset(_columns(connection, "extractions")):
        return False
    if not {
        "id", "project_id", "title", "created_at", "updated_at", "archived_at",
    }.issubset(_columns(connection, "qa_threads")):
        return False
    if not {
        "id", "thread_id", "role", "content", "created_at", "ai_operation_id",
    }.issubset(_columns(connection, "qa_messages")):
        return False
    if not {
        "provider_request_id", "total_tokens", "finish_reason", "idempotency_key", "retrieval_run_id",
    }.issubset(_columns(connection, "ai_operations")):
        return False
    if not {
        "model_revision", "updated_at", "vector_encoding", "source_revision",
    }.issubset(_columns(connection, "embeddings")):
        return False
    if not {"exercise_kind"}.issubset(_columns(connection, "exercises")):
        return False
    if CURRENT_SCHEMA_VERSION >= 9:
        if not {
            "id", "project_id", "title", "description", "status", "created_at", "updated_at", "archived_at",
        }.issubset(_columns(connection, "learning_goals")):
            return False
        if not {
            "id", "project_id", "goal_id", "title", "description", "status", "user_edited", "created_at",
            "updated_at", "confirmed_at", "activated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "study_plans")):
            return False
        if not {
            "id", "plan_id", "project_id", "title", "description", "position", "status", "user_edited",
            "created_at", "updated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "study_plan_items")):
            return False
    if CURRENT_SCHEMA_VERSION >= 10:
        if not {
            "id", "project_id", "title", "status", "provenance", "user_edited", "generation_operation_id",
            "created_at", "updated_at", "confirmed_at", "archived_at",
        }.issubset(_columns(connection, "notes")):
            return False
        if not {
            "id", "note_id", "project_id", "position", "block_kind", "content", "provenance",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "note_blocks")):
            return False
        if not {"id", "project_id", "note_id", "module_id"}.issubset(_columns(connection, "note_module_links")):
            return False
        if not {
            "id", "project_id", "note_id", "note_block_id", "material_id", "revision_id", "extraction_id",
            "chunk_id", "span_id", "citation_key", "status", "created_at", "updated_at",
        }.issubset(_columns(connection, "note_block_source_links")):
            return False
        if not {
            "id", "project_id", "plan_id", "cadence", "timezone", "period_start", "target_minutes",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "rhythm_settings")):
            return False
        if not {
            "id", "project_id", "plan_id", "item_id", "local_date", "planned_minutes", "created_at", "updated_at",
        }.issubset(_columns(connection, "rhythm_allocations")):
            return False
    if CURRENT_SCHEMA_VERSION >= 11:
        if not {
            "id", "project_id", "session_kind", "cram_goal_id", "status", "title",
            "duration_seconds", "timezone", "local_date", "started_at", "deadline_at",
            "finished_at", "created_at", "updated_at",
        }.issubset(_columns(connection, "practice_sessions")):
            return False
        if not {
            "id", "session_id", "project_id", "exercise_id", "position", "exercise_type",
            "prompt", "options_json", "explanation_snapshot", "exercise_kind", "source_material_id",
            "source_revision", "source_extraction_id", "source_chunk_id", "source_span_id", "citation_key",
            "citation_status", "answer_key_json", "created_at", "updated_at",
        }.issubset(_columns(connection, "practice_session_items")):
            return False
        if not {"session_id", "session_item_id", "submission_key", "submission_sequence"}.issubset(
            _columns(connection, "exercise_attempts")
        ):
            return False
        if not {
            "id", "project_id", "attempt_id", "exercise_id", "decision", "feedback",
            "reviewer_kind", "created_at", "reviewed_at",
        }.issubset(_columns(connection, "exercise_attempt_reviews")):
            return False
        if not {
            "id", "project_id", "exercise_id", "exercise_revision_fingerprint", "status",
            "origin", "created_at", "updated_at", "fixed_at", "archived_at",
        }.issubset(_columns(connection, "mistake_cases")):
            return False
        if not {
            "id", "project_id", "mistake_case_id", "attempt_id", "origin", "reason_code",
            "source_revision", "source_status", "created_at",
        }.issubset(_columns(connection, "mistake_occurrences")):
            return False
        if not {
            "id", "project_id", "mistake_case_id", "event_kind", "content", "provenance", "created_at",
        }.issubset(_columns(connection, "mistake_feedback_events")):
            return False
        if not {
            "id", "project_id", "title", "target_date", "timezone", "target_exercise_count", "status",
            "plan_id", "plan_item_id", "created_at", "updated_at", "completed_at", "archived_at",
        }.issubset(_columns(connection, "cram_goals")):
            return False
    if CURRENT_SCHEMA_VERSION >= 12:
        if not {
            "id", "project_id", "status", "asset_kind", "material_id", "original_name",
            "media_type", "source_status", "created_at", "updated_at", "confirmed_at",
            "rejected_at", "archived_at",
        }.issubset(_columns(connection, "capture_sessions")):
            return False
        if not {
            "id", "project_id", "capture_session_id", "operation_id", "status", "text",
            "language", "quality_status", "edited_by_user", "created_at", "updated_at",
        }.issubset(_columns(connection, "transcript_drafts")):
            return False
        if not {
            "id", "draft_id", "project_id", "ordinal", "text", "confidence", "quality",
            "created_at", "updated_at",
        }.issubset(_columns(connection, "transcript_segments")):
            return False
        if not {
            "id", "project_id", "report_kind", "timezone", "period_start", "period_end",
            "status", "content_version", "aggregation_fingerprint", "safe_payload_json",
            "markdown_content", "error_code", "created_at", "updated_at", "ready_at", "archived_at",
        }.issubset(_columns(connection, "report_snapshots")):
            return False
        if not {
            "id", "project_id", "report_id", "channel", "mode", "target_label",
            "content_fingerprint", "idempotency_key_fingerprint", "status", "error_code",
            "retry_of", "created_at", "finished_at",
        }.issubset(_columns(connection, "report_delivery_attempts")):
            return False
        if "capture_session_id" not in _columns(connection, "ai_operations"):
            return False
    return True


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


def _migration_v1(connection: sqlite3.Connection) -> None:
    _create_canonical_schema(connection)


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


def _migration_v2(connection: sqlite3.Connection) -> None:
    _create_ai_schema(connection)


def _migration_v3(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN provider_request_id TEXT;
        ALTER TABLE ai_operations ADD COLUMN total_tokens INTEGER;
        ALTER TABLE ai_operations ADD COLUMN finish_reason TEXT;
        """
    )


def _migration_v4(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN idempotency_key TEXT;
        ALTER TABLE ai_operations ADD COLUMN retrieval_run_id TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS ai_operations_idempotency_key_idx
            ON ai_operations(project_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        """
    )


def _migration_v5(connection: sqlite3.Connection) -> None:
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


def _migration_v6(connection: sqlite3.Connection) -> None:
    # Search indexes are schema objects and must be created transactionally.
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING "
        "fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
    )
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_search USING "
        "fts5(id UNINDEXED, text, normalized_text, tokenize='unicode61')"
    )


def _migration_v7(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE study_decks (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('active','archived')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT
        );
        CREATE TABLE study_cards (
            id TEXT PRIMARY KEY, deck_id TEXT NOT NULL REFERENCES study_decks(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            card_type TEXT NOT NULL CHECK(card_type IN ('ai_generated','user_created')),
            status TEXT NOT NULL CHECK(status IN ('draft','ready','rejected','stale','archived')),
            front TEXT NOT NULL, back TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]', source_revision TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            edited_by_user INTEGER NOT NULL DEFAULT 0 CHECK(edited_by_user IN (0,1)),
            generation_operation_id TEXT REFERENCES ai_operations(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, confirmed_at TEXT, archived_at TEXT
        );
        CREATE TABLE card_citations (
            id TEXT PRIMARY KEY, card_id TEXT NOT NULL REFERENCES study_cards(id) ON DELETE CASCADE,
            citation_key TEXT NOT NULL, material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
            revision_id TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            extraction_id TEXT REFERENCES extractions(id) ON DELETE SET NULL,
            chunk_id TEXT REFERENCES chunks(id) ON DELETE SET NULL, span_id TEXT,
            quote TEXT NOT NULL, position INTEGER NOT NULL CHECK(position >= 0),
            status TEXT NOT NULL CHECK(status IN ('valid','source_deleted','source_unavailable','stale','invalid')),
            UNIQUE(card_id, citation_key)
        );
        CREATE TABLE card_reviews (
            id TEXT PRIMARY KEY, card_id TEXT NOT NULL REFERENCES study_cards(id) ON DELETE CASCADE,
            result TEXT NOT NULL CHECK(result IN ('again','hard','good','easy')),
            reviewed_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE exercise_sets (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('active','archived')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT
        );
        CREATE TABLE exercises (
            id TEXT PRIMARY KEY, set_id TEXT NOT NULL REFERENCES exercise_sets(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            exercise_type TEXT NOT NULL CHECK(exercise_type IN ('multiple_choice','true_false','short_answer')),
            status TEXT NOT NULL CHECK(status IN ('draft','ready','rejected','stale','archived')),
            prompt TEXT NOT NULL, options_json TEXT NOT NULL DEFAULT '[]', answer_key_json TEXT NOT NULL,
            explanation TEXT NOT NULL DEFAULT '', source_revision TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            edited_by_user INTEGER NOT NULL DEFAULT 0 CHECK(edited_by_user IN (0,1)),
            generation_operation_id TEXT REFERENCES ai_operations(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, confirmed_at TEXT, archived_at TEXT
        );
        CREATE TABLE exercise_citations (
            id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
            citation_key TEXT NOT NULL, material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
            revision_id TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            extraction_id TEXT REFERENCES extractions(id) ON DELETE SET NULL,
            chunk_id TEXT REFERENCES chunks(id) ON DELETE SET NULL, span_id TEXT,
            quote TEXT NOT NULL, position INTEGER NOT NULL CHECK(position >= 0),
            status TEXT NOT NULL CHECK(status IN ('valid','source_deleted','source_unavailable','stale','invalid')),
            UNIQUE(exercise_id, citation_key)
        );
        CREATE TABLE exercise_attempts (
            id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
            answer_json TEXT NOT NULL, score REAL, is_correct INTEGER CHECK(is_correct IN (0,1)),
            grading_status TEXT NOT NULL CHECK(grading_status IN ('deterministic','pending_review','needs_review','reviewed')),
            submitted_at TEXT NOT NULL, reviewed_at TEXT, feedback TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX study_decks_project_status_idx ON study_decks(project_id, status, updated_at);
        CREATE INDEX study_cards_deck_status_idx ON study_cards(deck_id, status, updated_at);
        CREATE INDEX study_cards_source_revision_idx ON study_cards(source_revision);
        CREATE INDEX card_citations_source_idx ON card_citations(material_id, revision_id, status);
        CREATE INDEX card_reviews_card_time_idx ON card_reviews(card_id, reviewed_at);
        CREATE INDEX exercise_sets_project_status_idx ON exercise_sets(project_id, status, updated_at);
        CREATE INDEX exercises_set_status_idx ON exercises(set_id, status, updated_at);
        CREATE INDEX exercises_source_revision_idx ON exercises(source_revision);
        CREATE INDEX exercise_citations_source_idx ON exercise_citations(material_id, revision_id, status);
        CREATE INDEX exercise_attempts_exercise_time_idx ON exercise_attempts(exercise_id, submitted_at);
    """)


def _migration_v8(connection: sqlite3.Connection) -> None:
    # The original v7 table intentionally remains immutable.  This separate
    # migration records whether an exercise came from a user or an AI draft.
    connection.execute(
        "ALTER TABLE exercises ADD COLUMN exercise_kind TEXT NOT NULL "
        "DEFAULT 'user_created' CHECK(exercise_kind IN ('ai_generated','user_created'))"
    )


def _migration_v9(connection: sqlite3.Connection) -> None:
    """Add only the 9A persistence contract; domain behavior remains in 9A-3+."""
    script = """
        CREATE TABLE learning_goals (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('active','archived')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE knowledge_modules (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('active','archived')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE study_plans (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            goal_id TEXT NOT NULL REFERENCES learning_goals(id) ON DELETE RESTRICT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('draft','confirmed','active','paused','completed','archived')),
            user_edited INTEGER NOT NULL DEFAULT 0 CHECK(user_edited IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT,
            activated_at TEXT,
            completed_at TEXT,
            archived_at TEXT
        );
        CREATE TABLE study_plan_items (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            module_id TEXT REFERENCES knowledge_modules(id) ON DELETE SET NULL,
            deck_id TEXT REFERENCES study_decks(id) ON DELETE SET NULL,
            exercise_set_id TEXT REFERENCES exercise_sets(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL CHECK(position >= 0),
            status TEXT NOT NULL CHECK(status IN ('pending','in_progress','completed','skipped','archived')),
            user_edited INTEGER NOT NULL DEFAULT 0 CHECK(user_edited IN (0,1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            archived_at TEXT,
            UNIQUE(plan_id, position)
        );
        CREATE TABLE study_plan_dependencies (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            predecessor_item_id TEXT NOT NULL REFERENCES study_plan_items(id) ON DELETE RESTRICT,
            successor_item_id TEXT NOT NULL REFERENCES study_plan_items(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            CHECK(predecessor_item_id <> successor_item_id),
            UNIQUE(plan_id, predecessor_item_id, successor_item_id)
        );
        CREATE TABLE study_progress_events (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE RESTRICT,
            item_id TEXT NOT NULL REFERENCES study_plan_items(id) ON DELETE RESTRICT,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL CHECK(event_type IN ('started','completed','skipped','reopened')),
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE module_source_links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            module_id TEXT NOT NULL REFERENCES knowledge_modules(id) ON DELETE CASCADE,
            material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
            revision_id TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            extraction_id TEXT REFERENCES extractions(id) ON DELETE SET NULL,
            chunk_id TEXT REFERENCES chunks(id) ON DELETE SET NULL,
            span_id TEXT,
            citation_key TEXT,
            status TEXT NOT NULL CHECK(status IN ('valid','source_deleted','source_unavailable','stale')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(module_id, citation_key)
        );
        CREATE TABLE plan_item_source_links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            plan_item_id TEXT NOT NULL REFERENCES study_plan_items(id) ON DELETE CASCADE,
            material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
            revision_id TEXT REFERENCES material_revisions(id) ON DELETE SET NULL,
            extraction_id TEXT REFERENCES extractions(id) ON DELETE SET NULL,
            chunk_id TEXT REFERENCES chunks(id) ON DELETE SET NULL,
            span_id TEXT,
            citation_key TEXT,
            status TEXT NOT NULL CHECK(status IN ('valid','source_deleted','source_unavailable','stale')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(plan_item_id, citation_key)
        );
        CREATE INDEX learning_goals_project_status_idx
            ON learning_goals(project_id, status, updated_at);
        CREATE INDEX knowledge_modules_project_status_idx
            ON knowledge_modules(project_id, status, updated_at);
        CREATE INDEX study_plans_project_status_idx
            ON study_plans(project_id, status, updated_at);
        CREATE INDEX study_plans_goal_status_idx
            ON study_plans(goal_id, status, updated_at);
        CREATE INDEX study_plan_items_plan_position_idx
            ON study_plan_items(plan_id, position, id);
        CREATE INDEX study_plan_items_project_status_idx
            ON study_plan_items(project_id, status, updated_at);
        CREATE INDEX study_plan_dependencies_successor_idx
            ON study_plan_dependencies(plan_id, successor_item_id);
        CREATE INDEX study_progress_events_item_time_idx
            ON study_progress_events(item_id, created_at, id);
        CREATE INDEX study_progress_events_plan_time_idx
            ON study_progress_events(plan_id, created_at, id);
        CREATE INDEX module_source_links_source_idx
            ON module_source_links(material_id, revision_id, status);
        CREATE INDEX plan_item_source_links_source_idx
            ON plan_item_source_links(material_id, revision_id, status);
    """
    # sqlite3.Connection.executescript() commits any pending transaction before
    # executing its script. Execute statements individually so v9 stays inside
    # migrate()'s BEGIN IMMEDIATE and can roll back as one unit.
    for statement in script.split(";\n"):
        if statement.strip():
            connection.execute(statement)


def _migration_v10(connection: sqlite3.Connection) -> None:
    """Add the 9B persistence contract; domain behavior remains in 9B-3+."""
    script = """
        CREATE TABLE notes (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 400),
            status TEXT NOT NULL CHECK(status IN ('draft','confirmed','rejected','archived')),
            provenance TEXT NOT NULL CHECK(provenance IN ('user_created','ai_generated')),
            user_edited INTEGER NOT NULL DEFAULT 0 CHECK(user_edited IN (0,1)),
            generation_operation_id TEXT REFERENCES ai_operations(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            confirmed_at TEXT,
            archived_at TEXT,
            CHECK((provenance='user_created' AND generation_operation_id IS NULL) OR
                  (provenance='ai_generated' AND generation_operation_id IS NOT NULL))
        );
        CREATE TABLE note_blocks (
            id TEXT PRIMARY KEY,
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            position INTEGER NOT NULL CHECK(position >= 0),
            block_kind TEXT NOT NULL CHECK(block_kind IN ('text','heading','bullet')),
            content TEXT NOT NULL CHECK(length(trim(content)) BETWEEN 1 AND 12000),
            provenance TEXT NOT NULL CHECK(provenance IN ('user_created','ai_generated')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(note_id, position)
        );
        CREATE TABLE note_module_links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            module_id TEXT NOT NULL REFERENCES knowledge_modules(id) ON DELETE CASCADE,
            UNIQUE(note_id, module_id)
        );
        CREATE TABLE note_block_source_links (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            note_block_id TEXT NOT NULL REFERENCES note_blocks(id) ON DELETE CASCADE,
            material_id TEXT NOT NULL,
            revision_id TEXT NOT NULL,
            extraction_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            span_id TEXT,
            citation_key TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('valid','source_deleted','source_unavailable','stale')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK(length(trim(material_id)) > 0 AND length(trim(revision_id)) > 0 AND
                  length(trim(extraction_id)) > 0 AND length(trim(chunk_id)) > 0 AND
                  length(trim(citation_key)) > 0),
            UNIQUE(note_block_id, citation_key)
        );
        CREATE TABLE rhythm_settings (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
            cadence TEXT NOT NULL CHECK(cadence IN ('daily','weekly')),
            timezone TEXT NOT NULL CHECK(length(trim(timezone)) > 0),
            period_start TEXT NOT NULL CHECK(length(trim(period_start)) > 0),
            target_minutes INTEGER NOT NULL CHECK(target_minutes BETWEEN 0 AND 10080),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(plan_id)
        );
        CREATE TABLE rhythm_allocations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            plan_id TEXT NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES study_plan_items(id) ON DELETE CASCADE,
            local_date TEXT NOT NULL CHECK(length(trim(local_date)) > 0),
            planned_minutes INTEGER NOT NULL CHECK(planned_minutes BETWEEN 1 AND 1440),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(item_id, local_date)
        );
        CREATE INDEX notes_project_status_idx ON notes(project_id, status, updated_at);
        CREATE INDEX note_blocks_note_position_idx ON note_blocks(note_id, position, id);
        CREATE INDEX note_module_links_project_idx ON note_module_links(project_id, note_id, module_id);
        CREATE INDEX note_block_source_links_source_idx ON note_block_source_links(material_id, revision_id, status);
        CREATE INDEX note_block_source_links_block_idx ON note_block_source_links(note_block_id, citation_key);
        CREATE INDEX rhythm_settings_project_plan_idx ON rhythm_settings(project_id, plan_id);
        CREATE INDEX rhythm_allocations_plan_date_idx ON rhythm_allocations(plan_id, local_date);
        CREATE INDEX rhythm_allocations_item_date_idx ON rhythm_allocations(item_id, local_date);
    """
    # Keep all DDL inside migrate()'s BEGIN IMMEDIATE; executescript() would commit it.
    for statement in script.split(";\n"):
        if statement.strip():
            connection.execute(statement)


def _migration_v12(connection: sqlite3.Connection) -> None:
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


def _migration_v11(connection: sqlite3.Connection) -> None:
    """Add the 9C facts and snapshots; domain behavior remains in 9C-3+."""
    # Keep each statement inside migrate()'s BEGIN IMMEDIATE. executescript()
    # would commit before running the DDL and defeat migration rollback.
    statements = [
        """
        CREATE TABLE cram_goals (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200),
            target_date TEXT NOT NULL CHECK(length(trim(target_date)) = 10),
            timezone TEXT NOT NULL CHECK(length(trim(timezone)) > 0),
            target_exercise_count INTEGER NOT NULL CHECK(target_exercise_count BETWEEN 1 AND 200),
            status TEXT NOT NULL CHECK(status IN ('draft','active','completed','archived')),
            plan_id TEXT REFERENCES study_plans(id) ON DELETE SET NULL,
            plan_item_id TEXT REFERENCES study_plan_items(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            archived_at TEXT
        )
        """,
        """
        CREATE TABLE practice_sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            session_kind TEXT NOT NULL CHECK(session_kind IN ('practice','cram')),
            cram_goal_id TEXT REFERENCES cram_goals(id) ON DELETE SET NULL,
            status TEXT NOT NULL CHECK(status IN ('draft','active','finished','expired','archived')),
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200),
            duration_seconds INTEGER NOT NULL CHECK(duration_seconds BETWEEN 60 AND 7200),
            timezone TEXT NOT NULL CHECK(length(trim(timezone)) > 0),
            local_date TEXT NOT NULL CHECK(length(trim(local_date)) = 10),
            started_at TEXT,
            deadline_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK((session_kind = 'practice' AND cram_goal_id IS NULL) OR
                  (session_kind = 'cram' AND cram_goal_id IS NOT NULL))
        )
        """,
        """
        CREATE TABLE practice_session_items (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES practice_sessions(id) ON DELETE CASCADE,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            position INTEGER NOT NULL CHECK(position >= 0),
            exercise_type TEXT NOT NULL CHECK(exercise_type IN ('multiple_choice','true_false','short_answer')),
            prompt TEXT NOT NULL CHECK(length(trim(prompt)) BETWEEN 1 AND 20000),
            options_json TEXT NOT NULL DEFAULT '[]',
            explanation_snapshot TEXT NOT NULL DEFAULT '',
            exercise_kind TEXT NOT NULL CHECK(exercise_kind IN ('ai_generated','user_created')),
            source_material_id TEXT,
            source_revision TEXT,
            source_extraction_id TEXT,
            source_chunk_id TEXT,
            source_span_id TEXT,
            citation_key TEXT,
            citation_status TEXT NOT NULL CHECK(citation_status IN ('valid','source_deleted','source_unavailable','stale')),
            answer_key_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(session_id, position),
            UNIQUE(session_id, exercise_id)
        )
        """,
        """
        CREATE TABLE exercise_attempt_reviews (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id) ON DELETE CASCADE,
            exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            decision TEXT NOT NULL CHECK(decision IN ('correct','incorrect','uncertain')),
            feedback TEXT NOT NULL DEFAULT '' CHECK(length(feedback) <= 4000),
            reviewer_kind TEXT NOT NULL CHECK(reviewer_kind IN ('local_user')),
            created_at TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            UNIQUE(attempt_id)
        )
        """,
        """
        CREATE TABLE mistake_cases (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            exercise_revision_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('open','in_review','fixed','reopened','archived')),
            origin TEXT NOT NULL CHECK(origin IN ('deterministic','human_review','user_reported')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            fixed_at TEXT,
            archived_at TEXT,
            UNIQUE(project_id, exercise_id, exercise_revision_fingerprint)
        )
        """,
        """
        CREATE TABLE mistake_occurrences (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            mistake_case_id TEXT NOT NULL REFERENCES mistake_cases(id) ON DELETE CASCADE,
            attempt_id TEXT NOT NULL REFERENCES exercise_attempts(id) ON DELETE RESTRICT,
            origin TEXT NOT NULL CHECK(origin IN ('deterministic','human_review','user_reported')),
            reason_code TEXT NOT NULL CHECK(reason_code IN ('deterministic_incorrect','review_incorrect','user_marked')),
            source_revision TEXT,
            source_status TEXT NOT NULL CHECK(source_status IN ('valid','source_deleted','source_unavailable','stale')),
            created_at TEXT NOT NULL,
            UNIQUE(attempt_id, reason_code)
        )
        """,
        """
        CREATE TABLE mistake_feedback_events (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            mistake_case_id TEXT NOT NULL REFERENCES mistake_cases(id) ON DELETE CASCADE,
            event_kind TEXT NOT NULL CHECK(event_kind IN ('user_correction','user_note','status_transition')),
            content TEXT NOT NULL CHECK(length(content) <= 12000),
            provenance TEXT NOT NULL CHECK(provenance IN ('user_created')),
            created_at TEXT NOT NULL
        )
        """,
    ]
    for statement in statements:
        connection.execute(statement)
    connection.execute("ALTER TABLE exercise_attempts ADD COLUMN session_id TEXT REFERENCES practice_sessions(id) ON DELETE SET NULL")
    connection.execute("ALTER TABLE exercise_attempts ADD COLUMN session_item_id TEXT REFERENCES practice_session_items(id) ON DELETE SET NULL")
    connection.execute("ALTER TABLE exercise_attempts ADD COLUMN submission_key TEXT")
    connection.execute("ALTER TABLE exercise_attempts ADD COLUMN submission_sequence INTEGER CHECK(submission_sequence >= 0)")
    indexes = [
        "CREATE INDEX practice_sessions_project_status_idx ON practice_sessions(project_id, status, updated_at)",
        "CREATE INDEX practice_sessions_deadline_idx ON practice_sessions(status, deadline_at)",
        "CREATE INDEX practice_session_items_session_position_idx ON practice_session_items(session_id, position)",
        "CREATE INDEX practice_session_items_exercise_idx ON practice_session_items(project_id, exercise_id)",
        "CREATE UNIQUE INDEX exercise_attempts_session_submission_idx ON exercise_attempts(session_item_id) WHERE session_item_id IS NOT NULL",
        "CREATE UNIQUE INDEX exercise_attempts_submission_key_idx ON exercise_attempts(session_id, submission_key) WHERE session_id IS NOT NULL AND submission_key IS NOT NULL",
        "CREATE INDEX exercise_attempts_session_idx ON exercise_attempts(session_id, submitted_at)",
        "CREATE INDEX exercise_attempt_reviews_attempt_idx ON exercise_attempt_reviews(attempt_id, reviewed_at)",
        "CREATE INDEX mistake_cases_project_status_idx ON mistake_cases(project_id, status, updated_at)",
        "CREATE INDEX mistake_occurrences_case_time_idx ON mistake_occurrences(mistake_case_id, created_at)",
        "CREATE INDEX mistake_occurrences_project_time_idx ON mistake_occurrences(project_id, created_at)",
        "CREATE INDEX mistake_feedback_events_case_time_idx ON mistake_feedback_events(mistake_case_id, created_at)",
        "CREATE INDEX cram_goals_project_status_idx ON cram_goals(project_id, status, updated_at)",
        "CREATE INDEX cram_goals_plan_idx ON cram_goals(plan_id, plan_item_id)",
    ]
    for statement in indexes:
        connection.execute(statement)


_MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
    (1, "canonical_material_schema", _migration_v1),
    (2, "ai_phase0_schema", _migration_v2),
    (3, "phase5_provider_metadata", _migration_v3),
    (4, "qa_operation_idempotency", _migration_v4),
    (5, "phase7_embedding_schema", _migration_v5),
    (6, "search_index_schema_contract", _migration_v6),
    (7, "phase8_cards_exercises_schema", _migration_v7),
    (8, "phase8_exercise_provenance", _migration_v8),
    (9, "phase9a_learning_plan_schema", _migration_v9),
    (10, "phase9b_material_learning_schema", _migration_v10),
    (11, "phase9c_exercise_feedback_schema", _migration_v11),
    (12, "phase9d_extended_learning_schema", _migration_v12),
)


def schema_version(connection: sqlite3.Connection) -> int:
    try:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchall()
    except sqlite3.Error as exc:
        raise MigrationError("database_schema_version_unknown") from exc
    return int(rows[0][0]) if rows else 0


def _check_history(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()
    expected = [version for version, _, _ in _MIGRATIONS]
    actual = [int(row[0]) for row in rows]
    if actual != expected[:len(actual)] or any(version < 1 for version in actual):
        raise MigrationError("database_schema_version_unknown")
    for row, migration in zip(rows, _MIGRATIONS):
        if row[1] != migration[1]:
            raise MigrationError("database_migration_history_mismatch")
    current = actual[-1] if actual else 0
    if current > CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return current


def migrate(connection: sqlite3.Connection) -> MigrationResult:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 2000")
    adopted = False
    applied: list[int] = []
    try:
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (HISTORY_TABLE,)
        ).fetchone() is not None:
            current = _check_history(connection)
            pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current == CURRENT_SCHEMA_VERSION and pragma == CURRENT_SCHEMA_VERSION:
                if not _baseline_complete(connection):
                    raise MigrationError("database_schema_unsupported")
                return MigrationResult(current, ())
        connection.execute("BEGIN IMMEDIATE")
        _create_history(connection)
        current = _check_history(connection)
        if current == 0 and _baseline_complete(connection):
            # A complete pre-runner database already has the current schema.
            # Adopt it with the full consecutive history; do not replay ALTERs.
            connection.executemany(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                [(version, name, _now()) for version, name, _function in _MIGRATIONS],
            )
            current = CURRENT_SCHEMA_VERSION
            adopted = True
        elif current == 0 and _objects(connection) - {HISTORY_TABLE}:
            # Existing pre-runner databases may have the core tables but lack
            # columns added by the old implicit schema upgrade path.
            known = {"sqlite_sequence", "projects", "materials", "extractions",
                     "text_spans", "material_search",
                     "material_revisions", "chunks", "chunk_spans", "embeddings",
                     "retrieval_runs", "retrieval_hits", "qa_citations",
                     "ai_operations", "qa_threads", "qa_messages", "qa_answers",
                     "chunks_search"}
            if not (_objects(connection) - {HISTORY_TABLE}).issubset(known):
                raise MigrationError("database_schema_unsupported")
        for version, name, function in _MIGRATIONS:
            if version <= current:
                continue
            if version != current + 1:
                raise MigrationError("database_migration_incomplete")
            function(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _now()),
            )
            applied.append(version)
            current = version
        if current != CURRENT_SCHEMA_VERSION:
            raise MigrationError("database_migration_incomplete")
        if not _baseline_complete(connection):
            raise MigrationError("database_schema_unsupported")
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.commit()
        return MigrationResult(current, tuple(applied), adopted)
    except MigrationError:
        connection.rollback()
        raise
    except (sqlite3.Error, OSError) as exc:
        connection.rollback()
        raise MigrationError("database_migration_failed") from exc


def assert_schema_version(connection: sqlite3.Connection) -> int:
    version = schema_version(connection)
    pragma = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != CURRENT_SCHEMA_VERSION or pragma != CURRENT_SCHEMA_VERSION:
        raise MigrationError("database_schema_version_unknown")
    return version
