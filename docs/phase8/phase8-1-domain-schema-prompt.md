# Phase 8.1：Cards / Exercises 领域契约与 Migration Prompt

## 目标
在不写业务代码之前冻结 Phase 8 的正式领域模型、状态机、隐私边界和 migration 契约。正式实现必须基于当前 v6 schema 和 `backend/app/migrations/runner.py`，新表不得运行时创建。

## 上下文
现有 source of truth 是 materials/extractions/text_spans；AI 派生链是 revision → chunks → retrieval → citations → Q&A；Phase 7 已提供 embedding/hybrid retrieval。Cards/Exercises 必须保存 source revision 和可验证 citation，但不能修改 source。

## 任务
1. 审计当前 schema、migration、repository、Q&A citation、backup/restore 和 API 错误契约。
2. 冻结并记录至少这些表：`study_decks`、`study_cards`、`card_citations`、`card_reviews`、`exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`。如需 generation/version 表，说明必要性，避免过度建模。
3. 明确 card/exercise/set/deck 的字段、FK、project isolation、timestamps、JSON payload 限制、索引、删除策略。
4. 明确状态机：draft、ready、rejected、stale、archived，以及 user-created/no-source 与 AI-generated 的区别。
5. 明确 citation 状态：valid、source_deleted、source_unavailable、stale、invalid；无效 citation 不得确认 ready。
6. 明确 review/attempt 追加历史、幂等键或重复提交策略，以及 answer key 的 API 隔离方式。
7. 通过连续 migration 实现 schema；测试升级、重复执行、事务 rollback、旧数据库兼容、schema_migrations 与 `PRAGMA user_version` 一致。
8. 更新临时 Phase 8 契约文档或本子任务证据，但不要提前宣称完成。

## 验收
- migration 无运行时建表；
- 所有约束可由 SQLite 和 repository 双重保护；
- 删除/restore/purge、backup/restore 语义已冻结；
- backend migration tests 和新增契约 tests 通过；
- 不泄露 answer key、source text、路径或异常原文。
