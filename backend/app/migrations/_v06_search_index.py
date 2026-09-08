"""迁移 v6: 搜索索引 Schema 契约。

确保两个 FTS5 全文搜索虚拟表存在：
- material_search: 材料级搜索（材料名 + 提取文本）
- chunks_search: 分块级搜索（分块文本 + 标准化文本）

搜索索引是 Schema 对象，必须在迁移事务中创建，
保证新数据库和旧数据库升级后结构一致。
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v6 迁移：确保搜索索引虚拟表存在。
    
    Args:
        connection: SQLite 连接
    """
    # Search indexes are schema objects and must be created transactionally.
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS material_search USING "
        "fts5(material_id UNINDEXED, original_name, text, tokenize='unicode61')"
    )
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_search USING "
        "fts5(id UNINDEXED, text, normalized_text, tokenize='unicode61')"
    )
    
    
