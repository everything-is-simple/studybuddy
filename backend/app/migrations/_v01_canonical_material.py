"""迁移 v1: 规范化材料 Schema。

创建基础材料管理表（projects, materials, extractions, text_spans）
和 FTS5 全文搜索索引。委托给 _canonical._create_canonical_schema。
"""
from __future__ import annotations

import sqlite3

from ._canonical import _create_canonical_schema


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v1 迁移：创建规范化材料 Schema。
    
    Args:
        connection: SQLite 连接
    """
    _create_canonical_schema(connection)
