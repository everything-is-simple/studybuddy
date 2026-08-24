# 9C-9 Source lifecycle 与 backup/restore

```text
执行 Phase 9C-9：完成 S3/S4/S5 citation/source lifecycle 和 backup/verify/restore non-repair 专项验收，不新增未冻结业务能力。

审计并补齐 material delete/restore/purge、新 revision、chunk re-index 后 practice session snapshot、exercise/card citation、mistake/feedback、weak-point、cram result 的实际状态。历史 attempt/session/result 保留；source link 只能成为 valid/source_deleted/source_unavailable/stale 等服务端状态，restore 不自动 promotion，必须显式 refresh/relink（若契约允许）。不得返回 purge 后名称、正文、路径或可点击伪造定位。

扩展 backup/restore/restore_acceptance.py 的只读检查，测试 backup→verify→新空目录 restore：保留 schema history、所有 append-only facts、review/mistake/cram artifacts、operation 状态和不可用状态；startup/read/verify/restore 不调用 provider、不重评分、不重建、不修复、不自动生成。覆盖失败备份、空目标和版本不一致边界。

允许修改 backend/app/backup.py、restore_acceptance.py、lifecycle integration 和 tests/test_phase9c_source_lifecycle.py、test_phase9c_backup_restore.py；如发现业务代码缺陷用独立 fix commit，不扩大范围。运行 focused backup/restore 及完整 backend 门禁。状态为 scoped-gates-pass/restore-gates-pass。
```