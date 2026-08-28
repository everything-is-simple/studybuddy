"""Migration v11: phase9c feedback."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v11 migration."""
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
    
    
