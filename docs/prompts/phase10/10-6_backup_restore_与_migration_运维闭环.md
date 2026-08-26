# 10-6 backup/restore/migration 运维闭环与 corruption/read-only 处理

```text
请在 H:\\studybuddy 执行 Phase 10-6。先读取共用上下文、BACKUP_RESTORE.md、MIGRATIONS.md、backup.py、restore_acceptance.py、CLI、当前 schema/task runner 和既有恢复测试。补齐本地 v1 运维闭环，不在启动时自动 backup/restore/repair。

定义并实现（或如已存在则验证）backup 保留/轮换、manifest、schema/migration version、数据库 integrity、original hash/size、verify、恢复到新空目标、恢复后 offline/online smoke、migration upgrade preflight 和失败隔离。为 corruption、missing/mismatch original、不可写 data root、schema 不兼容定义 quarantine/read-only/停机策略；优先保留证据，不覆盖 live data，不自动修复用户数据。

将 task/operation、progress、attempt、report、delivery audit、source lifecycle 历史纳入备份恢复验证。恢复和启动不得调用 provider/OCR/ASR、重新 indexing、重算 report、发送 delivery 或提升 unavailable 状态。备份/日志/CLI 输出不得有 secret、正文、路径和 raw response。若轮换删除旧备份，必须有明确保留策略、失败不破坏现有可验证备份。

新增/更新 operator runbook、restore drill template、focused backup/restore/migration/corruption tests，并运行完整 backend。测试必须使用仓库外临时 data root/artifact。验收 Gate G 通过；未做真实断电只能记 not_verified。推荐提交：`ops: close backup restore and migration runbooks`。准确状态：`scoped-gates-pass` 或 `restore-gates-pass`。
```
