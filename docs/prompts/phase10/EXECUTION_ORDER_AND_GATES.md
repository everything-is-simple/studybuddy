# Phase 10 执行顺序、提交拆分与验收门槛

## 推荐步骤

```text
10-0 上线定义/现状审计/范围冻结
  ↓
10-1 operation/task 契约与状态机
  ↓
10-2 migration/schema 与兼容门禁
  ↓
10-3 单进程 task runner 与恢复
  ↓
10-4 既有长任务接入
  ↓
10-5 observability 与 health/readiness/degraded
  ↓
10-6 backup/restore/migration 运维闭环
  ↓
10-7 安装、启动、停止与安全配置发布
  ↓
10-8 容量/性能/长时/故障时间盒验收
  ↓
10-9 release candidate、上线演练、证据和文档收口
```

10-0 是硬门槛。10-1、10-2 必须串行；10-3 是 10-4 的硬前置。10-5 可在 10-3 后并行，但推荐串行以减少契约漂移。10-6/10-7/10-8 可在核心 runner 稳定后分别执行，最终都阻塞 10-9。每次只执行一个子任务。

## 推荐 commit

| 任务 | 推荐 commit |
|---|---|
| 10-0 | `docs: define local v1 launch scope and phase 10 gates` |
| 10-1 | `docs: freeze operation task contract` |
| 10-2 | `db: add operation task schema migration` |
| 10-3 | `feat: add single-process task runner and recovery` |
| 10-4 | `feat: connect approved long operations to task runner` |
| 10-5 | `feat: productionize observability and readiness` |
| 10-6 | `ops: close backup restore and migration runbooks` |
| 10-7 | `release: add local startup configuration and packaging` |
| 10-8 | `test: establish production boundary and capacity evidence` |
| 10-9 | `docs: close phase 10 release acceptance` |

## Gates

- **Gate A（Launch scope）**：明确本地单机 v1 的用户、安装、支持边界和 non-goals；多用户/云同步不作为隐含前置。
- **Gate B（Contract）**：operation/task 状态、进度、租约、幂等、重试、取消、恢复和错误码冻结。
- **Gate C（Schema）**：连续幂等事务 migration；new DB、v12 upgrade、rollback、history/user_version、backup version 通过。
- **Gate D（Runner）**：单进程并发限制、任务隔离、lease、progress、retry、cooperative cancel、stale/restart recovery 和不重复副作用通过。
- **Gate E（Integration）**：批准的 indexing/embedding/generation/OCR/ASR/report 操作接入；同步兼容、幂等、失败和审计无回归。
- **Gate F（Observability）**：脱敏日志、request/task correlation、metrics、liveness/readiness/degraded 与 operator diagnostics 可用。
- **Gate G（Operations）**：upgrade、backup、verify、restore drill、保留轮换、corruption quarantine/read-only/停机决策有可复现证据。
- **Gate H（Release runtime）**：安全配置、数据目录、锁、启动/停止、版本、健康检查和本地安装/升级路径通过。
- **Gate I（Boundary evidence）**：容量、性能、长时 smoke、权限/资源不足等时间盒结果形成；未验证故障如实登记。
- **Gate J（Release closeout）**：隔离 data root 完成 release candidate 全路径，完整 backend 与相关 Chromium 通过，文档、TODO、STATUS、ROADMAP、README、INDEX 和发布 checklist 一致。

## 停工规则

- 10-0 未定义支持边界或数据保留/恢复责任：停工，不写实现。
- 发现需要多进程共享 data_root、多用户、云同步或真实外发：暂停，另立范围和安全评审。
- operation 状态不能证明幂等、恢复或副作用安全：停在契约/runner，不接入业务。
- migration、backup/restore 或 readiness 有破坏性回归：禁止继续到 release。
- 无法取消不可中断的外部 HTTP 时，只能声明 cooperative/queued cancellation，不能宣称强制取消。
- 真实 provider/OCR/ASR/交付、ACL、磁盘耗尽、断电等未执行：标记 `not_verified`，不得阻塞本地 v1，除非 10-0 将其列为该版本硬要求。

## 最终完成措辞

> Phase 10 已完成，StudyBuddy 已在明确的 local single-process / single-instance / SQLite / local-disk v1 支持范围内完成生产化和上线收口：后台任务基础、任务状态与恢复、可观察性、migration/backup/restore 运维、启动配置、发布演练、边界验收和文档证据均已通过。该声明不代表多用户、认证授权、云同步、协作、多进程共享 data_root、真实断电恢复、所有真实 Provider/OCR/ASR/外发渠道或全局 production real-pass；未验证项目仍按 evidence 标记为 `not_verified`。

若任何 Gate A-J 未通过，只能声明已通过的局部 gate，不得写 Phase 10 completed、上线成功或 production-ready。
