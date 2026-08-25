# 9A-7：Backup/restore 与 non-repair

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-7：验证 9A 新增数据的 backup、verify、restore 和 non-repair 行为，不引入自动 repair/rebuild。

确认现有 SQLite Online Backup、manifest、schema version 和 restore acceptance 会覆盖所有 9A 表。若只需数据库快照，记录理由；若 manifest/restore verifier 需要调整，保持脱敏和新空目标目录规则。覆盖 goals/modules/plans/items/dependencies/progress/source links、draft/confirmed/active/paused/completed/archived、valid/stale/unavailable citation、用户编辑保护和 completed history。

必须证明 backup → verify → restore 到新空 data root 后：
- 数据和 migration history 保持一致；
- progress event 与 summary 一致；
- source unavailable 不会被提升为 valid；
- startup/read/verify/restore 不生成计划、不重建 chunk、不调用 Provider、不 repair 业务状态；
- 原有错误和 lifecycle 边界仍安全。

新增 test_phase9a_backup_restore.py，并运行完整 backend suite。必要时新增脱敏 evidence 文档，不提交真实 backup 文件。

验收：restore closeout 通过且证据可复现；明确哪些真实断电/磁盘损坏能力仍 not_verified。
```