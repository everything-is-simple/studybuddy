from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

CURRENT_SCHEMA_VERSION = 9
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
