# 9B-6：API contract

> 先使用 `00_COMMON_CONTEXT.md`、9B-1 契约、9B-3/4/5 domain 实现。本任务把已验收能力暴露为最小安全 API，不实现完整 UI。

```text
执行 Phase 9B-6：为 S1/S2 实现最小 FastAPI API，并保持现有 StudyBuddy API/error/observability 风格。

先审计当前 main.py 路由、safe serialization、request ID、分页、导出和 boundary tests。按实际冻结契约实现 note、note block、knowledge module、source link、S1 rhythm/period/allocation、plan/item 关联、draft generation、confirm/reject/archive、summary、progress 和显式 source refresh 所需的最小 endpoints。逐条定义 method/path/request/response/status/stable error code/idempotency/repeat semantics。

覆盖 malformed JSON、非法 ID、project scope、状态冲突、非法日期/timezone/workload、未索引和空检索、provider_not_configured、timeout/unavailable、伪造 citation、source deleted/purged/stale/unavailable、用户编辑保护、500 后 retry 和导出边界。响应不得返回 stored_path、服务器路径、SQL、traceback、secret、raw provider response、完整正文或未经验证的 quote；只返回 contract 允许的安全 metadata、note content 和已授权/已验证的 citation 内容。

新增 `test_phase9b_api.py` 或按 S1/S2 拆分的 boundary tests。涉及 API 必须运行完整 backend suite。不要为 UI 方便绕过 repository/domain contract，不增加 scheduler、worker 或下一 Phase API。

验收：API 与 domain 行为一致，安全失败和隐私边界通过；状态为 `implemented/backend-pass` 或局部准确措辞，不代表 Phase 9B completed。
```