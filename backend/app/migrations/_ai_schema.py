"""AI Schema 创建辅助工具。

本模块创建 AI 能力链的核心表结构（v02 ai_phase0 的主体）：
- material_revisions: 材料修订版本（不可变历史）
- chunks: 文本分块（含生命周期状态）
- chunk_spans: 分块与源范围关联
- chunks_search: FTS5 分块搜索虚拟表
- embeddings: 向量嵌入存储
- retrieval_runs: 检索运行记录
- retrieval_hits: 检索命中记录
- qa_citations: QA 引用记录
- ai_operations: AI 操作记录（幂等基础）
- qa_threads/qa_messages/qa_answers: 问答线程

核心设计：
- 修订链: material_revisions 保留每次解析的新版本，is_current 标记当前版
- 分块状态机: pending → ready → stale/deleted（CHECK 约束）
- 唯一性约束:
  - chunks: UNIQUE(revision_id, chunk_index)
  - embeddings: UNIQUE(chunk_id, provider_id, model_id, model_revision, content_hash)
  - qa_citations: UNIQUE(answer_id, citation_key)
- 嵌入标识: provider/model/revision/content_hash 完整标识，支持失效检测

检索流水线：
- retrieval_runs 记录每次检索（策略版本、嵌入模型）
- retrieval_hits 记录命中（词法分、向量分、重排分）
- selected 标记被选中用于上下文的分块

QA 数据流：
- qa_threads → qa_messages → qa_answers
- qa_citations 关联回材料分块（支持引用验证）
- ai_operations 记录操作（状态机、指纹、令牌用量）

表关系（简化）：
    materials → material_revisions → chunks → embeddings
                    ↓                ↓
              extractions      chunk_spans → text_spans
    
    qa_threads → qa_messages → qa_answers → qa_citations
                                     ↑
    ai_operations (记录所有 AI 操作)

注意：
- 使用 CREATE TABLE IF NOT EXISTS 保证幂等性
- 外键全部 ON DELETE CASCADE
- ai_operations.status 有 CHECK 约束（六种状态）
"""
from __future__ import annotations

import sqlite3

from ._helpers import _columns


def _create_ai_schema(connection: sqlite3.Connection) -> None:
    """创建 AI 能力链核心 Schema（修订/分块/嵌入/检索/QA）。
    
    创建表（按依赖顺序）：
    1. material_revisions: 材料修订历史
    2. chunks + chunks_search: 分块和搜索索引
    3. chunk_spans: 分块-范围关联
    4. embeddings: 向量存储
    5. retrieval_runs + retrieval_hits: 检索记录
    6. qa_citations: 引用记录
    7. ai_operations: AI 操作（幂等基础）
    8. qa_threads + qa_messages + qa_answers: 问答线程
    
    Args:
        connection: SQLite 连接（事务由调用者管理）
    
    注意:
        - 幂等性：重复执行不会重复创建
        - 所有外键级联删除
        - CHECK 约束保证状态值合法
    """
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS material_revisions (
            id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            source_sha256 TEXT NOT NULL,
            extraction_sha256 TEXT NOT NULL,
            parser_id TEXT NOT NULL,
            parser_version TEXT NOT NULL,
            revision_fingerprint TEXT NOT NULL UNIQUE,
            is_current INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            superseded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            revision_id TEXT NOT NULL REFERENCES material_revisions(id) ON DELETE CASCADE,
            extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            token_count_estimate INTEGER,
            overlap_before INTEGER NOT NULL,
            overlap_after INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            chunking_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','ready','failed','stale','deleted')),
            error_code TEXT,
            created_at TEXT NOT NULL,
            superseded_at TEXT,
            UNIQUE(revision_id, chunk_index)
        );
        CREATE TABLE IF NOT EXISTS chunk_spans (
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            span_id TEXT NOT NULL,
            overlap_start INTEGER NOT NULL,
            overlap_end INTEGER NOT NULL,
            PRIMARY KEY(chunk_id, span_id)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_search USING
            fts5(id UNINDEXED, text, normalized_text, tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_revision TEXT,
            dimensions INTEGER NOT NULL,
            vector_encoding TEXT NOT NULL,
            vector_payload BLOB,
            external_vector_id TEXT,
            content_hash TEXT NOT NULL,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(chunk_id, provider_id, model_id, model_revision, content_hash)
        );
        CREATE TABLE IF NOT EXISTS retrieval_runs (
            id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            normalized_query TEXT NOT NULL,
            project_id TEXT NOT NULL,
            thread_id TEXT,
            policy_version TEXT NOT NULL,
            embedding_provider_id TEXT,
            embedding_model_id TEXT,
            status TEXT NOT NULL,
            error_code TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS retrieval_hits (
            run_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            score REAL NOT NULL,
            lexical_score REAL,
            vector_score REAL,
            rerank_score REAL,
            selected INTEGER NOT NULL,
            citation_label TEXT NOT NULL,
            PRIMARY KEY(run_id, chunk_id),
            FOREIGN KEY(run_id) REFERENCES retrieval_runs(id) ON DELETE CASCADE,
            FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS qa_citations (
            id TEXT PRIMARY KEY,
            answer_id TEXT NOT NULL,
            citation_key TEXT NOT NULL,
            material_id TEXT NOT NULL,
            revision_id TEXT,
            extraction_id TEXT,
            chunk_id TEXT,
            span_id TEXT,
            quote TEXT NOT NULL,
            position INTEGER NOT NULL,
            source_revision TEXT,
            status TEXT NOT NULL,
            UNIQUE(answer_id, citation_key)
        );
        CREATE TABLE IF NOT EXISTS ai_operations (
            id TEXT PRIMARY KEY,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled','stale')),
            project_id TEXT NOT NULL,
            material_id TEXT,
            thread_id TEXT,
            input_fingerprint TEXT NOT NULL,
            source_revision TEXT,
            retrieval_policy_version TEXT,
            prompt_version TEXT,
            provider_id TEXT,
            model_id TEXT,
            request_id TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            error_code TEXT,
            output_artifact_id TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            latency_ms INTEGER,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_threads (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES qa_threads(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('system','user','assistant','tool')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ai_operation_id TEXT
        );
        CREATE TABLE IF NOT EXISTS qa_answers (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL REFERENCES qa_messages(id) ON DELETE CASCADE,
            ai_operation_id TEXT NOT NULL REFERENCES ai_operations(id) ON DELETE CASCADE,
            answer_text TEXT NOT NULL,
            answer_format TEXT,
            source_coverage TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('draft','ready','rejected','stale')),
            prompt_version TEXT,
            provider_id TEXT,
            model_id TEXT,
            generated_at TEXT NOT NULL
        );
    """)




