"""迁移 v2: AI 基础 Schema。

创建 AI 能力链核心表（修订/分块/嵌入/检索/QA/操作记录）。
委托给 _ai_schema._create_ai_schema。
"""
from __future__ import annotations

import sqlite3

from ._ai_schema import _create_ai_schema


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v2 迁移：创建 AI 基础 Schema。
    
    Args:
        connection: SQLite 连接
    """
    _create_ai_schema(connection)
