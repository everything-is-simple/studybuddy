# Phase 9D 执行顺序、提交拆分与验收门槛

## 推荐顺序

```text
9D-0 立项评审、审计与范围冻结（go / no-go）
  ↓
9D-1 正式领域契约与状态机
  ↓
9D-2 migration/schema
  ↓
9D-3 repository/domain transaction
  ↓
9D-4 S7 课堂采集与 OCR/ASR 转写
  ↓
9D-5 S7 转写接入 S2 资料管线
  ↓
9D-6 S6 家长报告聚合与脱敏
  ↓
9D-7 S6 对外交付（默认关闭 + dry-run + 授权 + 审计）
  ↓
9D-8 API
  ↓
9D-9 Chromium workspace
  ↓
9D-10 source lifecycle + backup/restore
  ↓
9D-11 acceptance/documentation closeout
```

9D-0 是硬门槛：立项条件未通过时不进入 9D-1，允许结论为暂不立项或仅立项 S6/S7 之一。S7 链（9D-4→9D-5）与 S6 链（9D-6→9D-7）在共享契约和领域层（9D-3）通过后理论上可并行，但正式执行仍推荐串行。每次只执行一个子任务。

## 推荐 commit

| Commit | 单一责任 |
|---|---|
| `docs: freeze phase 9d scope and go/no-go` | 9D-0 |
| `docs: define phase 9d extended-learning contract` | 9D-1 |
| `db: add phase 9d schema migration` | 9D-2 |
| `feat: add phase 9d extended-learning domain` | 9D-3 |
| `feat: add phase 9d class capture transcription` | 9D-4 |
| `feat: ingest phase 9d transcripts into materials` | 9D-5 |
| `feat: add phase 9d parent report aggregation` | 9D-6 |
| `feat: add phase 9d report delivery dry-run` | 9D-7 |
| `feat: expose phase 9d api` | 9D-8 |
| `feat: add phase 9d chromium workspace` | 9D-9 |
| `test: verify phase 9d lifecycle backup restore` | 9D-10 |
| `docs: close phase 9d acceptance` | 9D-11 |

## Gates

- **Gate A：立项与范围**：五项立项条件（需求、隐私、保留、真实组件证据、运维成本）有结论；S6/S7 边界、裁剪和 non-goals 有证据；暂不立项也是合法结论。
- **Gate B：领域契约**：capture session、转写/置信度/uncertain、接入 S2、report 类型/脱敏白名单、交付渠道/授权/审计的对象、状态机、时间和隐私语义冻结。
- **Gate C：数据库**：连续、幂等、事务化 migration；new DB、v11 升级、失败 rollback、history/user_version、backup version 通过；无运行时建表；secret/raw response 不入库。
- **Gate D：共享领域层**：scope/ownership、append-only、投影重算、幂等、原子写入、脱敏和 secret 不泄露通过。
- **Gate E：S7 采集/转写**：采集原件纳入 originals lifecycle、fake/loopback OCR/ASR、置信度/uncertain、失败/超时、幂等、raw response 不持久化通过。
- **Gate F：S7 接入 S2**：转写作为 material/revision 接入、citation 可追溯、draft→confirm、用户编辑保护、检索可用、source lifecycle 降级通过。
- **Gate G：S6 报告**：各类型聚合、强制脱敏白名单/黑名单、只读不改写学习事实、快照/重算、时区/日期边界、导出安全通过。
- **Gate H：S6 交付**：默认关闭只 dry-run、显式授权/白名单、越权拒绝、secret 安全、审计 append-only、失败可控/幂等去重、无自动定时推送通过。
- **Gate I：API/UI**：安全 HTTP contract 和 desktop/narrow/keyboard/reload/failure/privacy Chromium 路径通过；交付默认关闭在 UI 明确可见。
- **Gate J：生命周期/恢复**：delete/restore/purge/re-index 的 source 状态正确降级；历史事实保留；backup→verify→新空目录 restore 保留历史且 non-repair，不触发交付。
- **Gate K：真实组件边界**：真实 OCR/ASR 与真实对外交付均以显式 opt-in gate 管理，默认 skip；未通过通用验证的项如实标注 not_verified。
- **Gate L：收口**：完整 backend、相关 Chromium、脱敏 evidence、STATUS/TODO/ROADMAP/PROJECT_PROGRESS/INDEX 同步。

## 完成措辞

只有 Gate A-L 全部通过（且 9D-0 立项通过），才能写：

> Phase 9D 已在 deterministic fake/loopback 组件、单进程 SQLite、本地 Chromium、backup/restore 与本地 dry-run 交付的明确范围内完成；不代表真实 OCR/ASR provider 通用验证、真实对外交付（SMTP/飞书生产端点）、自动 scheduler/worker/定时推送、多用户/云同步、系统级 screen reader、极端内容、长时稳定性或全局 production `real-pass`。

若 9D-0 结论为部分立项或暂不立项，只能声明实际完成的子集，不得扩大。单一子任务只能使用 `planned`、`audit-draft`、`contract-frozen`、`implemented/backend-pass`、`browser-pass`、`scoped-gates-pass`、`restore-gates-pass` 等局部状态。任何 gate 失败都不得写 Phase 9D completed。

## 停工规则

- 9D-0 立项条件不满足：停在 9D-0，记录暂不立项或部分立项结论，不进入实现子任务。
- 发现契约不足：暂停实现，提出契约变更，不把 S6/S7 合并成不可独立验收的大改动。
- 涉及真实对外交付：属于高风险，实现真实发送前必须标注并请人确认；默认只走 dry-run。
