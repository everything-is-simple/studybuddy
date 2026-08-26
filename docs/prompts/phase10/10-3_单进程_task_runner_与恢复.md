# 10-3 单进程 task runner、lease、progress、retry、cancel、恢复

```text
请在 H:\\studybuddy 执行 Phase 10-3。先读取共用上下文、10-1 正式契约、10-2 migration 和实际 repository/observability/启动生命周期。实现最小单进程 task runner，不接入全部业务操作，不做多进程共享 data_root。

实现可审计的 queued→running→terminal 执行路径、有限并发（默认单进程安全策略）、task handler registry、progress 更新、lease renewal、stale reclaim、显式 retry、幂等 replay/conflict、排队 cancel 和执行中 cooperative cancel。定义进程 shutdown 行为：不丢失已持久化事实；未完成任务安全标 stale/failed，重启后只能按明确策略恢复，不能重复不可幂等副作用。handler 异常只转稳定 error code，不泄露 traceback。

任务执行不能阻塞应用启动，也不能让 startup/readiness/backup/restore 自动启动任务。每个 handler 必须在安全边界内访问 repository/provider/storage；禁止 raw payload、secret 和原文进入 task response/log。若底层 HTTP 无法真正 cancel，只记录 cancel_requested/cooperative limitation。保持现有同步路径兼容。

新增 focused backend tests：状态转换、并发/lease、progress 单调性、retry 上限、幂等、cancel、stale/restart、handler failure、shutdown、隐私、SQLite rollback。可新增单进程 runner 模块和测试辅助，不接入 10-4 的具体 indexing/AI/OCR/报告业务。运行 focused 与完整 backend。验收 Gate D 通过。推荐提交：`feat: add single-process task runner and recovery`。准确状态：`implemented/backend-pass`。
```
