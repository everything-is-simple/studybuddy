"""迁移 v8: 练习溯源标记。

为 exercises 表添加 exercise_kind 列，区分练习来源：
- ai_generated: AI 生成草稿
- user_created: 用户手动创建

v7 的原表结构保持不变（已发布迁移不可修改）。
本迁移以独立 ALTER 实现溯源，默认值为 user_created
保证旧行语义不变。
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v8 迁移：添加 exercise_kind 溯源列。
    
    Args:
        connection: SQLite 连接
    """
    # The original v7 table intentionally remains immutable.  This separate
    # migration records whether an exercise came from a user or an AI draft.
    connection.execute(
        "ALTER TABLE exercises ADD COLUMN exercise_kind TEXT NOT NULL "
        "DEFAULT 'user_created' CHECK(exercise_kind IN ('ai_generated','user_created'))"
    )
    
    
