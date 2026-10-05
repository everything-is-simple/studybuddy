"""v16: S2 metadata extends the canonical v9 module identity.

All DDL stays inside the runner transaction, including FTS triggers.
Source disappearance preserves modules and exercise history for safe degradation.
"""
import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    statements = [
        """CREATE TABLE s2_knowledge_modules (
            id TEXT PRIMARY KEY REFERENCES knowledge_modules(id) ON DELETE CASCADE,
            material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
            source_evidence TEXT NOT NULL CHECK(json_valid(source_evidence)),
            importance INTEGER NOT NULL DEFAULT 1 CHECK(importance BETWEEN 1 AND 5),
            difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
            estimated_minutes INTEGER CHECK(estimated_minutes BETWEEN 1 AND 1440),
            tags TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(tags)),
            lifecycle TEXT NOT NULL CHECK(lifecycle IN ('draft','confirmed','rejected')),
            provenance TEXT NOT NULL CHECK(provenance IN ('user_created','ai_generated')),
            user_edited INTEGER NOT NULL DEFAULT 0 CHECK(user_edited IN (0,1)),
            provider_id TEXT, model_id TEXT, deleted_at TEXT
        )""",
        "CREATE INDEX idx_s2_knowledge_modules_material ON s2_knowledge_modules(material_id) WHERE deleted_at IS NULL",
        """CREATE TABLE s2_module_exercises (
            module_id TEXT NOT NULL REFERENCES knowledge_modules(id) ON DELETE CASCADE,
            exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
            PRIMARY KEY(module_id,exercise_id)
        )""",
        "CREATE INDEX idx_s2_module_exercises_exercise ON s2_module_exercises(exercise_id)",
        "CREATE VIRTUAL TABLE s2_knowledge_modules_fts USING fts5(module_id UNINDEXED,title,description,tags)",
        """CREATE TRIGGER s2_knowledge_modules_fts_insert AFTER INSERT ON s2_knowledge_modules
            WHEN new.deleted_at IS NULL BEGIN
            INSERT INTO s2_knowledge_modules_fts(module_id,title,description,tags)
            SELECT k.id,k.title,k.description,new.tags FROM knowledge_modules k WHERE k.id=new.id;
        END""",
        """CREATE TRIGGER s2_knowledge_modules_fts_update AFTER UPDATE ON s2_knowledge_modules BEGIN
            DELETE FROM s2_knowledge_modules_fts WHERE module_id=old.id;
            INSERT INTO s2_knowledge_modules_fts(module_id,title,description,tags)
            SELECT k.id,k.title,k.description,new.tags FROM knowledge_modules k
            WHERE k.id=new.id AND new.deleted_at IS NULL;
        END""",
        """CREATE TRIGGER s2_knowledge_modules_fts_delete AFTER DELETE ON s2_knowledge_modules BEGIN
            DELETE FROM s2_knowledge_modules_fts WHERE module_id=old.id;
        END""",
        """CREATE TRIGGER s2_knowledge_modules_title_update AFTER UPDATE OF title,description ON knowledge_modules BEGIN
            UPDATE s2_knowledge_modules_fts SET title=new.title,description=new.description WHERE module_id=new.id;
        END""",
    ]
    for statement in statements:
        connection.execute(statement)
