"""迁移 v9: Phase 9A 学习计划 Schema。

创建学习目标与计划持久化契约（仅结构，领域行为在 9A-3+ 实现）：

目标与模块：
- learning_goals: 学习目标（active/archived）
- knowledge_modules: 知识模块（active/archived）

计划体系：
- study_plans: 学习计划（六态状态机，关联目标）
- study_plan_items: 计划项目（五态，关联模块/卡片组/练习集）
- study_plan_dependencies: 项目依赖（DAG，禁止自依赖）
- study_progress_events: 进度事件（事件溯源）

源链接：
- module_source_links: 模块-源材料链接
- plan_item_source_links: 计划项目-源材料链接

设计要点：
- goal → plan: ON DELETE RESTRICT（防级联丢失）
- item 顺序: UNIQUE(plan_id, position) 保证位置唯一
- 依赖约束: 禁止自依赖，三元组唯一
- 事件类型: started/completed/skipped/reopened
- 源链接状态: valid/source_deleted/source_unavailable/stale
- user_edited 标记用户修改（AI 生成不覆盖）

索引策略：
- 列表: (project_id, status, updated_at)
- 计划内排序: (plan_id, position, id)
- 事件时间线: (item_id/plan_id, created_at, id)

事务说明：
executescript() 会隐式提交待处理事务，因此本迁移逐条执行
SQL 语句，保持在 migrate() 的 BEGIN IMMEDIATE 内，
失败时可整体回滚。
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v9 迁移：创建学习计划体系表。
    
    创建 8 个表 + 11 个索引。逐条执行语句以保持在
    migrate() 的事务内，失败时可整体回滚。
    
    Args:
        connection: SQLite 连接
    """
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
    # 注意: executescript 会隐式提交事务，因此逐条执行以保持原子回滚能力。
    for statement in script.split(";\n"):
        if statement.strip():
            connection.execute(statement)
    
    
