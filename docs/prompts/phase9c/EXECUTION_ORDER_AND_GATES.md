# Phase 9C 执行顺序、提交拆分与验收门槛

## 推荐顺序

```text
9C-0 审计与范围冻结
  ↓
9C-1 正式领域契约与状态机
  ↓
9C-2 migration/schema
  ↓
9C-3 repository/domain transaction
  ↓
9C-4 S3 限时练习
  ↓
9C-5 S4 错题改错与人工复核
  ↓
9C-6 S5 期末冲刺
  ↓
9C-7 API
  ↓
9C-8 Chromium workspace
  ↓
9C-9 source lifecycle + backup/restore
  ↓
9C-10 acceptance/documentation closeout
```

9C-4 与 9C-5 在共享契约和领域层通过后理论上可并行；正式执行仍推荐串行。9C-6 必须等 S3/S4 契约和稳定结果模型确定。

## 推荐 commit

| Commit | 单一责任 |
|---|---|
| `docs: freeze phase 9c audit boundaries` | 9C-0 |
| `docs: define phase 9c exercise-feedback contract` | 9C-1 |
| `db: add phase 9c schema migration` | 9C-2 |
| `feat: add phase 9c exercise-feedback domain` | 9C-3 |
| `feat: add phase 9c timed practice workflow` | 9C-4 |
| `feat: add phase 9c mistake review workflow` | 9C-5 |
| `feat: add phase 9c exam cram workflow` | 9C-6 |
| `feat: expose phase 9c api` | 9C-7 |
| `feat: add phase 9c chromium workspace` | 9C-8 |
| `test: verify phase 9c lifecycle backup restore` | 9C-9 |
| `docs: close phase 9c acceptance` | 9C-10 |

## Gates

- **Gate A：审计与范围**：实际 Phase 8/9A/9B 能力、S3/S4/S5 边界和 9D/10 non-goals 有证据。
- **Gate B：领域契约**：session、attempt、grading、review、mistake、weak-point、cram 对象、状态机、时间和隐私语义冻结。
- **Gate C：数据库**：连续、幂等、事务化 migration；new DB、旧库升级、失败 rollback、history/user_version、backup version 通过。
- **Gate D：共享领域层**：scope/ownership、append-only、投影、幂等、原子写入和 answer-key/privacy boundary 通过。
- **Gate E：S3**：限时 session、超时、逐题提交、确定性评分、刷新/重复提交/失败重试和结果反馈通过。
- **Gate F：S4**：错题生成/归并、改错/重做、短答人工复核、反馈建议/事实区分和历史保护通过。
- **Gate G：S5**：冲刺目标/模拟 session、选题快照、结果汇总、S3/S4 衔接和不自动改计划通过。
- **Gate H：API/UI**：安全 HTTP contract 和 desktop/narrow/keyboard/reload/failure Chromium 路径通过。
- **Gate I：生命周期/恢复**：delete/restore/purge/re-index 的 citation 状态正确；backup→verify→新空目录 restore 保留历史且 non-repair。
- **Gate J：收口**：完整 backend、相关 Chromium、脱敏 evidence、STATUS/TODO/ROADMAP/PROJECT_PROGRESS/INDEX 同步。

## 完成措辞

只有 Gate A-J 全部通过，才能写：

> Phase 9C 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表真实 Provider generation、自动 scheduler/worker、OCR/ASR、Phase 9D、人工之外的自动裁决或全局 production `real-pass`。

单一子任务只能使用 `planned`、`audit-draft`、`contract-frozen`、`implemented/backend-pass`、`browser-pass`、`scoped-gates-pass`、`restore-gates-pass` 等局部状态。任何 gate 失败都不得写 Phase 9C completed。
