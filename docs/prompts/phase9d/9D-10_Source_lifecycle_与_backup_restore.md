# 9D-10 Source lifecycle 与 backup/restore

```text
执行 Phase 9D-10：完成 S6/S7 的 source lifecycle 与 backup/verify/restore non-repair 专项验收，不做 Phase 9D 最终收口（9D-11）。

使用 ../00_COMMON_CONTEXT.md 和已完成的 9D-2 至 9D-9。验证采集原件、转写、接入 S2 的 material/revision、报告和交付审计在 delete/restore/purge/re-index 后保持正确的 valid / stale / source_deleted / source_unavailable 历史；历史转写、报告和交付审计事实保留，source 状态只降级，不伪造正文、材料名、路径、quote、citation 或收件人隐私。

必须验证 backup/verify/restore non-repair：
- backup → verify → 新空目录 restore 保留新版本（v12 或实际号）表、schema 历史、user_version 与 9D 事实；
- restore/startup/read/verify 不调用 provider、不重新 OCR/ASR、不重算并外发报告、不触发任何真实交付、不自动修复或提升 unavailable 状态；
- 扩展 restore_acceptance.py 的只读 9D checks；不覆盖 live data root，restore 到新空目标。

新增 backend/tests（如 test_phase9d_source_lifecycle.py、test_phase9d_backup_restore.py），覆盖上述降级历史、事实保留、restore 后 schema/历史/状态一致和 non-repair（含不触发交付）。运行专项 focused 与完整 backend，用 C:\\miniconda\\py310\\python.exe -m pytest 报告数字。

只允许修改 restore_acceptance.py 的只读 9D 校验、新增 lifecycle/backup 测试与必要的只读支撑；不改业务语义或做收口文档。验收：source lifecycle 降级正确、事实保留、restore non-repair 且不触发交付通过。状态为 scoped-gates-pass / restore-gates-pass，不代表 9D-11 closeout 或 Phase 9D completed。
```
