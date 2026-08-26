# 10-2 migration/schema 与运行兼容

```text
请在 H:\\studybuddy 执行 Phase 10-2。先读取 00_COMMON_CONTEXT.md、10-0/10-1 契约，并审计 migrations/runner.py、当前 v12 schema、backup/restore 与 restore_acceptance 测试。实现统一 task/operation 所需的最小 schema 变化；不得运行时 CREATE TABLE。

仅通过 backend/app/migrations/runner.py 增加连续 v13（若审计确认 v13 合理）的 migration。表/字段必须服务于已冻结契约，至少保证 project scope、task kind/status、timestamps、progress、retry/lease/cancel/idempotency、稳定 error metadata 和与既有 ai_operations 的兼容关系。不得存储 secret、raw prompt/response、正文、路径、答案 key、用户提交原文。SQLite CHECK、FK、索引、唯一性和 append-only/终态保护要有明确分工；不要把业务逻辑塞进 migration。

覆盖 new DB、v12 upgrade、重复运行幂等、故障 rollback、schema_migrations、PRAGMA user_version、backup manifest/version、空库和旧数据读取。确认启动失败不会留下半迁移状态；确认旧同步 Q&A、Phase 8/9 数据可读。扩展 restore acceptance，但不得让 restore 自动跑 task、provider、index、report 或 delivery。

允许修改 backend/app/migrations/、相关 repository schema introspection、backend/tests/test_migrations.py、backup/restore acceptance tests 和对应 docs；不得实现 runner 或大规模 API。执行 focused migration/restore tests，并因 infrastructure/migration 变化运行完整 backend。验收即 Gate C：全部 migration/history/rollback/backup 版本门禁通过。推荐提交：`db: add operation task schema migration`。准确状态：`implemented/backend-pass`。
```
