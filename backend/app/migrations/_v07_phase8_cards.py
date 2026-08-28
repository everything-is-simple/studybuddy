"""Migration v7: phase8 cards."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v7 migration."""
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
    
    
