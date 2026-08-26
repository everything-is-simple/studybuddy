# Phase 10 总体规划 Prompt

```text
请为 H:\\studybuddy 规划 Phase 10“本地生产化、后台任务基础与正式上线收口”。本次只做审计、范围决策、子任务拆分和验收规划，不修改代码、不新增 migration、不运行真实外部发送。

先完整读取 AGENTS.md 和权威文档：docs/STATUS.md、docs/TODO.md、docs/PHASE_ROADMAP.md、docs/PROJECT_PROGRESS_REPORT.md、docs/ARCHITECTURE.md、docs/CODE_TEST_GOVERNANCE.md、docs/MIGRATIONS.md、docs/BACKUP_RESTORE.md、docs/prompts/phase9d/ 相关契约和证据。再审计实际 backend/app、backend/tests、启动入口、CLI、migration runner、repository、storage、observability、provider/embedding、restore acceptance 和现有 Chromium workspace。所有结论必须引用实际源码路径、函数名、测试名或命令；不能把旧项目、设计文档或 prompt 当实现证据。

先回答“什么叫 StudyBuddy 成功上线”：默认将上线定义为 local single-process v1 release，而不是多用户互联网服务。定义支持矩阵、安装/配置方式、启动/停止、升级、备份、恢复、故障报告、数据目录、Provider 可选性和明确不支持项。若要做多用户、认证、云同步、协作、多 worker 或共享 data_root，必须另立项目，不得混入本次完成承诺。

Phase 10 必须围绕以下结果规划：
1. 后台长任务最小可靠基础：统一 operation/task 状态、进度、幂等、重试、取消语义、单进程执行、lease/stale recovery 和重启后可诊断恢复；覆盖 indexing、embedding、AI generation、OCR/ASR、report/delivery 等适合长任务的现有 operation，但不得改变既有同步 API 的兼容性。
2. 可观察性生产化：安全 structured logging、request/operation/task tracing、低基数 metrics、健康/就绪/降级状态、错误码和 operator 诊断；不泄露正文、路径、SQL、secret、raw provider response 或 traceback。
3. 数据运维闭环：migration upgrade preflight、backup 保留/轮换、verify、restore drill、corruption quarantine/read-only 或明确停机策略；恢复必须到新空目标，不自动 repair/rebuild/send。
4. 运行边界和容量证据：本地磁盘、权限、资源不足等可执行测试；批量导入、索引、Q&A、卡片/练习、学习流程、报告等基线和有限长时 smoke；真实断电/硬件损坏等不能验证的项目须明确记录为 not_verified。
5. 发布与上线收口：安全默认配置、Provider/key 配置指南、Windows/本地运行手册、数据目录和备份手册、故障排查、版本与 migration runbook、smoke/rollback/restore 验收、release checklist、已知限制和发布证据。

必须明确冻结：
- 本地 v1 的 supported deployment、单进程锁/端口/数据目录拓扑、是否允许显式 worker 子进程；
- operation/task 数据模型、状态机、progress、retry/cancel、idempotency、lease、失败和 stale recovery；同步请求与后台执行的兼容和迁移策略；
- 哪些现有操作先转后台，哪些继续同步，禁止未评估地把所有流程异步化；
- readiness/liveness/degraded 定义、日志字段、metrics 低基数和隐私脱敏；
- migration、backup/restore、保留/轮换、corruption、read-only/停机处理；
- 安装/启动/停止/升级/回滚/恢复/诊断的 operator contract；
- 性能、容量、长时稳定性、ACL/磁盘不足的测试时间盒和通过阈值；
- release candidate 的阻塞性缺陷等级、版本号、证据 artifact 和 go/no-go；
- 多用户、认证授权、云同步、协作、真实 OCR/ASR、真实外发、scheduler/自动推送、外部 vector DB 的 non-goals 或后续项目边界。

将 Phase 10 拆成以下可独立提交和验收的子任务；若审计发现需要调整，说明理由：
10-0 上线定义、现状审计与范围冻结；
10-1 后台 operation/task 正式契约与状态机；
10-2 migration/schema 与运行兼容；
10-3 单进程 task runner、lease、progress、retry、cancel、stale/restart recovery；
10-4 将必要的 indexing/embedding/generation/9D 操作接入 runner（只接入明确批准项）；
10-5 生产化 observability、health/readiness/degraded/operator diagnostics；
10-6 backup/restore/migration 运维闭环与 corruption/read-only 处理；
10-7 安全配置、启动/停止、数据目录和本地安装发布包；
10-8 容量、性能、长时稳定性和可执行故障边界验收；
10-9 发布候选、端到端上线演练、证据与文档 closeout。

为每个子任务给出：目标、明确不做、依赖、允许修改文件、迁移要求、测试和 artifact、失败/隐私/并发边界、验收标准、推荐 commit、阻塞关系和准确状态词。给出 Gate A-J、严格执行顺序、允许并行但默认串行规则、停工条件、release go/no-go 标准和最终完成声明。

必须坚持：
- migration runner 是唯一 schema 入口；不运行时建表；
- 单进程 runner 不能宣称跨进程协调；若实现子进程，必须有明确锁、生命周期和安全退出证据；
- cancel 必须说明是 cooperative cancellation 还是仅停止排队；不能虚假宣称能取消不可中断 Provider HTTP；
- restore/startup/read 不触发任务；恢复后的 stale/failed/unavailable 状态不能被自动伪造为成功；
- 默认不访问真实网络；真实 provider/OCR/ASR/交付、真实权限、资源耗尽、断电等均需显式 gate 或标记 not_verified；
- 不以测试通过数量代替用户上线证据；
- 只有所有阻塞 Gate 通过、release candidate 在隔离 data root 完成安装→启动→导入→索引→学习→备份→恢复→重启→升级/诊断路径，并且文档和限制同步后，才能称“StudyBuddy 本地单机 v1 已完成上线收口”。这仍不代表多用户互联网 production-ready 或全局 real-pass。

输出中文，形成可直接保存到 docs/prompts/phase10/ 的总规划、共用上下文、逐任务 prompt、执行顺序与验收门禁；只做规划，不改代码。
```
