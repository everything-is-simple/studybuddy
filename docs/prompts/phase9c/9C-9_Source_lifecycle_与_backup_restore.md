# 9C-9 Source lifecycle 与 backup/restore

## 执行记录

状态：`scoped-gates-pass` / `restore-gates-pass`。

- 扩展 `backend/app/restore_acceptance.py:_study_checks()` 覆盖 v11 的 `practice_sessions`、`practice_session_items`、`exercise_attempt_reviews`、`mistake_cases`、`mistake_occurrences`、`mistake_feedback_events` 和 `cram_goals`，并检查 session/item project scope、attempt/session-item/exercise linkage、review/attempt linkage、session/source status 和 migration history。
- 新增 `test_phase9c_source_lifecycle.py`：material delete/restore/purge 后 session/attempt history 保留，普通 read/restore 不新建 attempt、不改写结果；purge 后不返回 stored path/answer key。
- 新增 `test_phase9c_backup_restore.py`：backup→verify→新空目录 restore 保留 S3/S4/S5 事实计数、cram/session status、stale source status 和 schema v11；monkeypatch 证明 restore acceptance/startup/read 路径不调用 provider/index/repair；覆盖非空目标、未确认 restore、manifest version mismatch。
- restore acceptance 保持只读；不重新评分、不重建 mistake、不重跑 cram、不自动 promotion `stale`/`source_deleted`/`source_unavailable`。
- 实际命令与结果：9C-9/既有 backup/lifecycle focused `14 passed`；完整 backend `320 passed, 2 skipped`。两个 skip 是 opt-in real-provider smoke，不构成 9C 证据。
- 本任务未实现 Phase 9C-10 closeout、全套 API/UI 重新验收或真实断电/磁盘损坏/多进程恢复；这些边界仍未验证。


```text
执行 Phase 9C-9：完成 S3/S4/S5 citation/source lifecycle 和 backup/verify/restore non-repair 专项验收，不新增未冻结业务能力。

审计并补齐 material delete/restore/purge、新 revision、chunk re-index 后 practice session snapshot、exercise/card citation、mistake/feedback、weak-point、cram result 的实际状态。历史 attempt/session/result 保留；source link 只能成为 valid/source_deleted/source_unavailable/stale 等服务端状态，restore 不自动 promotion，必须显式 refresh/relink（若契约允许）。不得返回 purge 后名称、正文、路径或可点击伪造定位。

扩展 backup/restore/restore_acceptance.py 的只读检查，测试 backup→verify→新空目录 restore：保留 schema history、所有 append-only facts、review/mistake/cram artifacts、operation 状态和不可用状态；startup/read/verify/restore 不调用 provider、不重评分、不重建、不修复、不自动生成。覆盖失败备份、空目标和版本不一致边界。

允许修改 backend/app/backup.py、restore_acceptance.py、lifecycle integration 和 tests/test_phase9c_source_lifecycle.py、test_phase9c_backup_restore.py；如发现业务代码缺陷用独立 fix commit，不扩大范围。运行 focused backup/restore 及完整 backend 门禁。状态为 scoped-gates-pass/restore-gates-pass。
```