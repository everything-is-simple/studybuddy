"""迁移 v3: Phase 5 Provider 元数据。

为 ai_operations 表添加 Provider 响应追踪字段：
- provider_request_id: 提供商请求 ID（用于对账）
- total_tokens: 总令牌用量
- finish_reason: 完成原因（stop/length/error 等）
"""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v3 迁移：添加 Provider 响应追踪列。
    
    Args:
        connection: SQLite 连接
    """
    connection.executescript(
        """
        ALTER TABLE ai_operations ADD COLUMN provider_request_id TEXT;
        ALTER TABLE ai_operations ADD COLUMN total_tokens INTEGER;
        ALTER TABLE ai_operations ADD COLUMN finish_reason TEXT;
        """
    )
    
    
