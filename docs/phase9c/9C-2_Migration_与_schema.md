# 9C-2 Migration 与 schema

```text
执行 Phase 9C-2：只实现 Phase 9C 所需连续 migration/schema 和 migration 测试，不实现 repository/API/UI 工作流。

先读取 9C-1 冻结契约并确认源码当前 schema version。所有新表、字段、索引、CHECK/FK/unique 约束只能进入 backend/app/migrations/runner.py 的连续 migration；严禁 runtime CREATE TABLE。

按契约实现最小 schema，通常可能包含 practice sessions/session items、mistake/error-fix/weak-point、review/feedback、cram goals/sessions/items 等，但不要未经审计复制表名；区分 append-only facts 与可重算 projections，保护 answer key/submitted answer 的存储和读取边界。不要在本任务实现业务聚合、计时或 source refresh。

测试必须覆盖：new DB、当前旧版本升级、重复 migrate 幂等、DDL/约束失败 rollback、schema_migrations 与 PRAGMA user_version 一致、索引/检查约束、backup schema version。使用真实项目 Python 命令：C:\\miniconda\\py310\\python.exe -m pytest backend/tests/test_migrations.py -q，并运行受影响的 backup/governance focused tests。

允许修改 backend/app/migrations/runner.py、backend/tests/test_migrations.py 或新增 migration-focused test、必要的 docs/phase9c 记录；不得改 main.py/repository.py 前置接线。结束报告实际 version、文件、命令、结果和未验证边界。状态为 implemented/backend-pass，除非 focused gate 未通过。
```