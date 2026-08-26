# 10-5 生产化 observability、health/readiness/degraded

```text
请在 H:\\studybuddy 执行 Phase 10-5。先读取共用上下文、现有 observability.py、startup_preflight.py、main.py、CLI、runner 和测试。把已有最小可观察性提升到本地 v1 operator 可诊断水平，不记录敏感数据。

冻结并实现安全 structured event：timestamp、event、level、request_id、operation/task_id、project scope 的非敏感标识、duration、status、stable error code、retry/lease 信息。统一 request→task→provider operation correlation；禁止正文、文件路径、SQL、secret、Authorization、raw request/response、traceback 和可识别报告内容。定义低基数 metrics（请求、任务状态/耗时、导入、索引、provider 错误、SQLite、backup/restore、recovery），说明进程内、重启归零和不跨进程聚合边界。

实现/校验 liveness、readiness、degraded 语义：startup preflight/migration/audit/recovery 未完成时不可 ready；数据库不可用、配置非法、关键依赖失败时返回稳定安全状态；degraded 不伪造 healthy。提供 operator diagnostics/CLI snapshot，输出版本/schema/task 摘要和建议动作，不输出 SQL/path/raw error。

新增测试覆盖脱敏、request/task correlation、低基数、health 状态转移、startup failure、stale task、backup failure 和 API/UI 错误安全。运行完整 backend；若 UI 状态变化则运行相关 Chromium。验收 Gate F 通过。推荐提交：`feat: productionize observability and readiness`。准确状态：`implemented/backend-pass` 或涉及浏览器时 `browser-pass`。
```
