# 9C-2 Migration 与 schema

## 执行记录

状态：`implemented/backend-pass`。

- 当前 schema 已从 v10 连续升级到 v11，migration 名称为 `phase9c_exercise_feedback_schema`。
- 新增 practice session/item snapshot、attempt session linkage/submission metadata、attempt review、mistake case/occurrence/feedback event 和 cram goal schema；weak-point 保持实时 projection，不新增事实表。
- 已覆盖 new DB、v10 upgrade、幂等、DDL rollback、SQLite CHECK/UNIQUE/FK 基础约束、`schema_migrations`/`PRAGMA user_version` 和 backup schema version。
- 实际 focused 结果：`test_migrations.py` 通过；相关 backup/restore/governance tests 通过；完整 backend：`299 passed, 2 skipped`。
- 本任务未实现 repository/domain、计时、评分、source refresh、API、UI、Phase 9C lifecycle/restore closeout。


```text
执行 Phase 9C-2：只实现 Phase 9C 所需连续 migration/schema 和 migration 测试，不实现 repository/API/UI 工作流。

先读取 9C-1 冻结契约并确认源码当前 schema version。所有新表、字段、索引、CHECK/FK/unique 约束只能进入 backend/app/migrations/runner.py 的连续 migration；严禁 runtime CREATE TABLE。

按契约实现最小 schema，通常可能包含 practice sessions/session items、mistake/error-fix/weak-point、review/feedback、cram goals/sessions/items 等，但不要未经审计复制表名；区分 append-only facts 与可重算 projections，保护 answer key/submitted answer 的存储和读取边界。不要在本任务实现业务聚合、计时或 source refresh。

测试必须覆盖：new DB、当前旧版本升级、重复 migrate 幂等、DDL/约束失败 rollback、schema_migrations 与 PRAGMA user_version 一致、索引/检查约束、backup schema version。使用真实项目 Python 命令：C:\\miniconda\\py310\\python.exe -m pytest backend/tests/test_migrations.py -q，并运行受影响的 backup/governance focused tests。

允许修改 backend/app/migrations/runner.py、backend/tests/test_migrations.py 或新增 migration-focused test、必要的 docs/phase9c 记录；不得改 main.py/repository.py 前置接线。结束报告实际 version、文件、命令、结果和未验证边界。状态为 implemented/backend-pass，除非 focused gate 未通过。
```