"""迁移 v10: Phase 9B 材料学习 Schema。

创建笔记与学习节奏持久化契约（仅结构，领域行为在 9B-3+ 实现）：

笔记体系：
- notes: 笔记（四态，来源溯源 + 完整性约束）
- note_blocks: 笔记块（text/heading/bullet，顺序唯一）
- note_module_links: 笔记-模块关联（多对多）
- note_block_source_links: 笔记块-源材料链接（强关联）

学习节奏：
- rhythm_settings: 节奏设置（每计划唯一，daily/weekly）
- rhythm_allocations: 节奏分配（每项目每日唯一）

设计要点：
- 笔记溯源约束: user_created 必须无生成操作，ai_generated 必须有
- 内容长度约束: 标题 1-400，块内容 1-12000
- 源链接字段全部 NOT NULL + 非空串检查（强关联语义）
- 引用状态: valid/source_deleted/source_unavailable/stale
- 节奏目标: 0-10080 分钟（一周总分钟数上限）
- 分配时长: 1-1440 分钟（单日上限）

索引策略：
- 列表: (project_id, status, updated_at)
- 块排序: (note_id, position, id)
- 源追踪: (material_id, revision_id, status)
- 日期查询: (plan_id, local_date) / (item_id, local_date)

事务说明：
逐条执行 SQL 语句，保持在 migrate() 的 BEGIN IMMEDIATE 内。
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v10 迁移：创建笔记与节奏体系表。
    
    创建 6 个表 + 8 个索引。逐条执行语句以保持在
    migrate() 的事务内。
    
    Args:
        connection: SQLite 连接
    """
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
    
    
