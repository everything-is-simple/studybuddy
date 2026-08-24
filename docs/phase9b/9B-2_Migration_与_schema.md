# 9B-2：Migration 与 schema

> 先使用 `00_COMMON_CONTEXT.md` 和冻结后的 `PHASE9B_DOMAIN_CONTRACT.md`。本任务只实现 schema migration 和 migration 测试。

```text
执行 Phase 9B-2：只实现 Phase 9B 所需的连续 migration/schema，不实现 repository、domain、HTTP 路由或 UI。

先确认当前实际 schema version，不得根据历史文档猜测。依据冻结契约决定哪些对象复用 Phase 9A 表、哪些需要新表。至少评估 note、note_blocks、knowledge_module_note_links、note/module source links、rhythm settings/allocations 或等价对象、AI draft provenance 所需字段。避免为同一事实重复建表；不得顺手增加 9C/9D/Phase 10 表。

明确 foreign key、CHECK、UNIQUE、索引、project scope、状态字段、版本/时间字段、软删除/归档和 cascade 策略。跨 note/module/material/revision/citation 的约束如果不能用 SQLite CHECK 表达，记录由 repository/domain transaction enforcement，并为后续测试保留 contract。

所有变更只能进入 `backend/app/migrations/runner.py` 管理的连续 migration。覆盖 new-db、当前旧库升级、重复运行幂等、中途失败 rollback、`schema_migrations` 与 `PRAGMA user_version` 一致、backup/restore schema compatibility。不得使用 runtime `CREATE TABLE IF NOT EXISTS`。

新增 migration focused tests，并说明暂不实现的业务行为。验收状态只能是 `implemented/backend-pass`，不代表 Phase 9B 或 S1/S2 完成。
```