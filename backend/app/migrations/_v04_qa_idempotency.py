"""迁移 v4: QA 操作幂等性。

为 ai_operations 表添加幂等支持：
- idempotency_key: 幂等键（客户端重试时复用相同响应）
- retrieval_run_id: 关联检索运行记录
- 唯一部分索引：同一 project_id 下幂等键唯一（NULL 除外）
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v4 迁移：添加幂等键和检索关联。
    
    创建部分唯一索引（仅约束非 NULL 幂等键），
    允许无幂等键的操作正常写入。
    
    Args:
        connection: SQLite 连接
    """
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN idempotency_key TEXT;
        ALTER TABLE ai_operations ADD COLUMN retrieval_run_id TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS ai_operations_idempotency_key_idx
            ON ai_operations(project_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        """
    )
    
    
