# 9A-2：Migration 与 schema

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-2：只实现 Phase 9A schema migration 和 migration 测试，不实现业务 repository、API 或 UI。

先确认当前实际 schema version，并按已冻结的 PHASE9A_DOMAIN_CONTRACT 设计连续 migration。至少评估 goals、knowledge_modules、study_plans、study_plan_items、study_plan_dependencies、study_progress_events、plan_source_links/module_source_links/item_source_links 的表拆分；明确外键、CHECK、unique、索引、软删除/归档、级联策略、跨 plan dependency 禁止方式和 append-only event 约束。

所有 schema 变更只能通过 backend/app/migrations/runner.py。禁止 ad-hoc runtime table creation。必须覆盖新库初始化、旧库升级、重复运行幂等、migration 中途失败 rollback、schema_migrations 与 PRAGMA user_version 一致、backup/restore version compatibility。

如果某个跨行约束无法由 SQLite CHECK 表达，必须记录由 repository/domain transaction enforcement，并为后续任务留下测试 contract。不要借 migration 顺便添加 9B/9C/9D 表。

验收：migration focused tests 通过；无业务表运行时创建；迁移失败不留下半成品；当前旧 schema 与新 schema 均能初始化/升级；状态仍是 migration implemented/backend-pass，不是 9A completed。
```