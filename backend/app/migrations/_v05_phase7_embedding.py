"""迁移 v5: Phase 7 Embedding Schema 重建。

重建 embeddings 表，强化身份标识和状态约束：
- model_revision 变为 NOT NULL（旧行回填空字符串）
- status 严格约束为四态：running/ready/stale/failed
- 新增 updated_at 列
- 唯一约束扩展为八元组（chunk/source/hash/provider/model/revision/dims/encoding）
- 新增查询索引（ready 状态查找）

重建原因：
SQLite 无法通过 ALTER TABLE 添加 CHECK 约束或将可空列改为非空，
因此必须重建表。旧的不合规行保留可诊断性，但绝不静默提升为 ready。

数据迁移规则：
- 合法状态行：running/ready → stale（保守降级，要求重新验证）
- 合法状态行：stale/failed → 保持原状态
- 非法状态行：→ failed，错误码为 embedding_legacy_status
"""
from __future__ import annotations

import sqlite3

from ._helpers import _now


def migrate(connection: sqlite3.Connection) -> None:
    """应用 v5 迁移：重建 embeddings 表。
    
    执行流程：
    1. 重命名旧表为 embeddings_v4
    2. 创建新结构（严格 CHECK 约束和扩展唯一约束）
    3. 迁移数据（回填 model_revision、降级 running/ready 为 stale、
       非法状态标记为 failed）
    4. 删除旧表
    5. 创建查询索引
    
    Args:
        connection: SQLite 连接
    """
    # Rebuild is intentional: SQLite cannot add a CHECK or make a nullable
    # identity component non-null with ALTER TABLE. Unknown legacy rows remain
    # diagnosable but are never silently promoted to ready.
    connection.execute("ALTER TABLE embeddings RENAME TO embeddings_v4")
    connection.executescript("""
        CREATE TABLE embeddings (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL, model_id TEXT NOT NULL,
            model_revision TEXT NOT NULL, dimensions INTEGER NOT NULL,
            vector_encoding TEXT NOT NULL, vector_payload BLOB,
            external_vector_id TEXT, content_hash TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('running','ready','stale','failed')),
            error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(chunk_id, source_revision, content_hash, provider_id, model_id,
                   model_revision, dimensions, vector_encoding)
        );
    """)
    now = _now()
    connection.execute("""INSERT INTO embeddings
        (id,chunk_id,provider_id,model_id,model_revision,dimensions,vector_encoding,
         vector_payload,external_vector_id,content_hash,source_revision,status,error_code,created_at,updated_at)
        SELECT id,chunk_id,provider_id,model_id,COALESCE(model_revision,''),dimensions,vector_encoding,
         vector_payload,external_vector_id,content_hash,source_revision,
         CASE WHEN status IN ('running','ready','stale','failed') THEN
              CASE WHEN status IN ('running','ready') THEN 'stale' ELSE status END
              ELSE 'failed' END,
         CASE WHEN status IN ('running','ready','stale','failed') THEN error_code ELSE 'embedding_legacy_status' END,
         created_at, ? FROM embeddings_v4""", (now,))
    connection.execute("DROP TABLE embeddings_v4")
    connection.execute("CREATE INDEX embeddings_ready_lookup_idx ON embeddings(status, provider_id, model_id, model_revision, dimensions, vector_encoding)")
    
    
