# 9B-8：Source lifecycle 与 backup/restore

> 先使用 `00_COMMON_CONTEXT.md`、9B contract、domain/API/UI 实现。本任务专门完成资料来源生命周期和恢复验收，不引入自动 repair。

```text
执行 Phase 9B-8：验证 S1/S2 artifact、note、module、source link、citation、rhythm 和 progress 在 material delete/restore/purge、新 extraction/new revision、chunk re-index 后的状态和历史行为。

明确并测试 valid、stale、source_deleted、source_unavailable 的映射。已确认/用户编辑/已归档 note/module 以及已完成 plan item 的历史必须保留；purge 不得恢复材料名称、正文或可点击 source；restore 后是否恢复 valid 必须遵守契约并通过显式 refresh，不能由 startup/read/verify 自动提升。不得复制正文到 source link 作为替代，也不得自动调用 Provider、重建 chunk 或重新生成 note/module。

验证 backup → verify → restore 到新空 data root：
- 所有 9B 表、外键关系、版本和 migration history 保留；
- notes、blocks、modules、citations/source links、draft/confirmed/archived 状态、rhythm 配置、progress history/summary 保留；
- unavailable/stale 状态不被提升；用户编辑保护保留；
- restore/startup/read/verify 不创建 artifact、不运行 provider、不 repair/rebuild；
- manifest、错误和日志不泄露路径、正文、secret、raw exception。

新增 `test_phase9b_source_lifecycle.py`、`test_phase9b_backup_restore.py` 或等价 focused tests，并运行完整 backend、相关 browser 和现有 restore acceptance。不要提交数据库、backup 文件或真实上传原件。

验收：source lifecycle 和 restore gates 通过；准确状态为 `scoped-gates-pass`/`restore-gates-pass`，不代表 Phase 9B completed。真实断电、磁盘满、网络盘、硬件损坏、多进程等继续保持 `not_verified`。
```