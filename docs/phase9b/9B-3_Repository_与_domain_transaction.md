# 9B-3：Repository 与 domain transaction

> 先使用 `00_COMMON_CONTEXT.md`、9B-1 契约和 9B-2 schema。本任务不实现 HTTP 路由和完整 UI。

```text
执行 Phase 9B-3：实现 S1/S2 共用的 repository/domain 最小事务基础。

按冻结契约实现并测试：note/module/block/source-link 的创建、读取、用户编辑、归档/恢复（若契约允许）；AI draft 的保存与显式确认/拒绝；S1 rhythm settings/period/allocation 与 Phase 9A plan/item 的关联；节奏 summary 和 progress projection 的确定性重算；source identity/citation validation；delete/restore/purge/revision re-index 后的显式 refresh；用户编辑、confirmed、completed 状态保护。

每个写操作明确事务边界、输入校验、重复调用语义、rollback、稳定错误码、SQLite lock 行为和 project scope。不得复制正文作为 source of truth；citation 必须来自 server-side retrieval/context 验证。不得静默覆盖用户 note/module、已确认 draft、已有 progress event 或完成 item。

按实际代码新增 focused tests（可拆成 test_phase9b_domain.py、test_phase9b_notes.py、test_phase9b_rhythm.py、test_phase9b_source_lifecycle.py）。覆盖非法状态转移、重复提交、source stale/unavailable、伪造 citation、失败 rollback、锁失败、summary 重算和历史保留。

如果实现 draft generation，只允许使用现有 provider abstraction 和显式 deterministic fake provider；raw prompt/response 不落库，失败只保留安全 operation。真实网络 Provider 不属于本任务。

验收：repository/domain focused tests 通过；所有写入在事务内；无 runtime 建表；状态为 `implemented/backend-pass`；API/UI 留给后续任务。
```