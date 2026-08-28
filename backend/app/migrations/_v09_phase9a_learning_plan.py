"""Migration v9: phase9a learning plan."""

from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """Apply v9 migration."""
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
    
    
