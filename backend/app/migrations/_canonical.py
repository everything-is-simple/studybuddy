"""规范化材料 Schema 创建。

本模块创建基础材料管理的核心表结构：
- projects: 项目表
- materials: 材料表（原始文件元数据）
- extractions: 提取记录表（解析结果）
- text_spans: 文本范围表（语义单元）
- material_search: FTS5 全文搜索虚拟表

表关系：
projects 1:N materials 1:N extractions 1:N text_spans
（ON DELETE CASCADE 级联删除）

列兼容性处理：
- 旧数据库可能缺少 updated_at, deleted_at, error_code 列
- 使用 ALTER TABLE 增量添加，避免破坏现有数据
- updated_at 缺失时用 created_at 回填

搜索索引：
- material_search: FTS5 虚拟表
- 索引字段: original_name（材料名）、text（提取文本）
- material_id 不索引（UNINDEXED，仅作为关联键）
- 使用 unicode61 分词器

注意：
- 本模块仅处理基础表（v1 之前的核心结构）
- AI 相关表在 v02+ 迁移中创建
- 使用 CREATE TABLE IF NOT EXISTS 保证幂等性
"""
from __future__ import annotations

import sqlite3

from ._helpers import _columns


def _create_canonical_schema(connection: sqlite3.Connection) -> None:
    """创建规范化材料 Schema（基础表 + FTS 索引）。
    
    执行流程：
    1. 创建核心表（projects, materials, extractions, text_spans）
    2. 检查并补充缺失列（updated_at, deleted_at, error_code）
    3. 创建 FTS5 全文搜索虚拟表
    
    Args:
        connection: SQLite 连接（事务由调用者管理）
    
    注意:
        - 幂等性：重复执行不会重复创建
        - 列补齐时回填 updated_at 避免空值
    """
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


