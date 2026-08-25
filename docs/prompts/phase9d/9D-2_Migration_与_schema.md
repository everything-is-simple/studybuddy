# 9D-2 Migration 与 schema

```text
执行 Phase 9D-2：只实现 Phase 9D 的连续 migration 与 schema，不实现 repository/domain/API/UI 业务逻辑。

使用 ../00_COMMON_CONTEXT.md 和 9D-1 冻结契约。当前正式 schema 为 v11；本任务通过 backend/app/migrations/runner.py 增加下一个连续版本（v12 `phase9d_extended_learning_schema` 或以源码实际为准的连续号），加入 9D-1 契约所需的最小 schema：capture session、转写/operation 元数据与置信度、report、report 交付审计记录，以及必要的 source/link 与约束。

必须遵守：migration 唯一入口是 runner，禁止运行时 CREATE TABLE；migration 连续、幂等、事务化；正确维护 schema_migrations 与 PRAGMA user_version。schema 只承载 9D-1 契约需要的事实，交付渠道 secret 不入库，raw OCR/ASR/交付 response 不入库。append-only 事实（如转写 operation、交付审计）与可重算 projection 的存储职责按契约划分，并用 SQLite 约束保护关键不变量。

新增 backend/tests 中的 schema/migration 测试，覆盖：new DB 建到新版本、v11 升级到新版本、失败回滚、重复运行幂等、schema_migrations/user_version 一致、以及 backup 记录的 schema version 正确。运行 focused migration 测试与完整 backend 套件确认无回归。

只允许修改 migration runner/迁移文件、必要的 schema 常量与对应测试；不实现 capture/report 业务逻辑、API 或 UI。验收：所有 migration 门禁通过、无运行时建表、backup/restore schema-history 一致。实际命令用 C:\\miniconda\\py310\\python.exe -m pytest 运行并报告数字。状态为 implemented/backend-pass，不代表 repository/domain、API/UI、lifecycle/restore 或 Phase 9D completed。
```
