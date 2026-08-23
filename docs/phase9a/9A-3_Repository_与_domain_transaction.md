# 9A-3：Repository 与 domain transaction

> 先使用 `00_COMMON_CONTEXT.md` 作为前置 prompt，再使用本文件。


```text
执行 Phase 9A-3：实现 9A repository/domain 最小事务闭环，不实现 HTTP 路由和完整 UI。

实现范围按 contract 拆开：goal/module CRUD 或 archive；plan draft 创建；item 增删改/排序；dependency 增删与 DAG cycle detection；draft confirm/active transition；progress event append；summary recompute；source link validation；source lifecycle refresh；用户编辑、confirmed、completed item 保护。

每个操作必须明确事务边界、输入校验、返回值、重复调用语义、失败 rollback、稳定错误码和并发/SQLite lock 行为。progress history 必须 append-only；summary 必须可从事件可靠重算，避免事件与 summary 不一致。source link 必须重新验证 current revision/chunk/span/citation，不能复制正文或信任客户端 citation。

如果实现 AI draft，则只允许显式 fake/provider abstraction 产生 draft，并保留 ai_operation metadata；真实网络 Provider generation 不属于本任务。任何重新规划不得覆盖 user-edited、confirmed 或 completed item。

新增 backend/tests/test_phase9a_domain.py、必要时拆为 test_phase9a_progress.py、test_phase9a_dependencies.py、test_phase9a_source_lifecycle.py。覆盖非法状态转移、重复请求、cycle、rollback、lock failure、source stale/unavailable、completed history 保留。

验收：repository/domain focused tests 通过；所有写入在事务内；没有 runtime CREATE TABLE；API/UI 不在此任务内。
```