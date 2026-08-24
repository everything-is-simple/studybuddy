# Phase 9B 执行顺序、提交拆分与完成门槛

## 推荐顺序

```text
9B-0 审计与范围冻结
  ↓
9B-1 领域契约与状态机冻结
  ↓
9B-2 migration/schema
  ↓
9B-3 repository/domain transaction
  ↓
9B-4 S2 资料笔记与知识模块工作流
  ↓
9B-5 S1 学习节奏工作流
  ↓
9B-6 API contract
  ↓
9B-7 Chromium workspace
  ↓
9B-8 source lifecycle + backup/restore
  ↓
9B-9 acceptance/documentation closeout
```

9B-4 与 9B-5 在契约和 schema 稳定后理论上可并行，但正式执行推荐串行，以便每次只维护一个可验收闭环。

## 推荐 commit

| Commit | 单一责任 |
|---|---|
| `docs: freeze phase 9b audit boundaries` | 9B-0 审计与范围冻结 |
| `docs: define phase 9b material-learning contract` | 9B-1 契约与状态机 |
| `db: add phase 9b schema migration` | 9B-2 migration 与测试 |
| `feat: add phase 9b material-learning domain` | 9B-3 repository/domain |
| `feat: add phase 9b note and knowledge workflow` | 9B-4 S2 |
| `feat: add phase 9b study rhythm workflow` | 9B-5 S1 |
| `feat: expose phase 9b api` | 9B-6 API |
| `feat: add phase 9b material-learning workspace` | 9B-7 UI/Chromium |
| `test: verify phase 9b lifecycle backup restore` | 9B-8 source lifecycle/restore |
| `docs: close phase 9b acceptance` | 9B-9 evidence/status/docs |

如果后续修复前一 gate，使用独立 fix commit，并写明修复的 gate；不得在 closeout 中偷偷扩展范围。

## Gates

- **Gate A：审计与范围**：当前 9A contract、实际源码和 S1/S2 边界有证据；9B/9C/9D/10 non-goals 冻结。
- **Gate B：领域契约**：S1/S2 对象关系、状态转移、节奏计算、笔记编辑保护、citation/source lifecycle、导出和错误语义明确。
- **Gate C：数据库**：migration 连续、幂等、事务化；new DB、旧 DB upgrade、rollback、schema history、`user_version` 和 backup version 一致。
- **Gate D：领域层**：S1/S2 domain transactions、progress/节奏 summary、note/module 版本与编辑保护、citation 验证、失败 rollback 通过。
- **Gate E：S2 工作流**：用户笔记与 knowledge module 创建/编辑/确认；fake-provider draft 只保存可验证 citation；失败和 retry 不污染用户状态。
- **Gate F：S1 工作流**：显式节奏设置、item 分配/调整、时间线/summary、非法日期/工作量/重复操作和 progress 联动通过；无 scheduler。
- **Gate G：API/UI**：S1/S2 API 边界、完整 Chromium happy/failure/narrow/keyboard/reload path 通过，响应不泄露正文全文、路径、secret 或 raw provider data。
- **Gate H：生命周期与恢复**：delete/restore/purge/revision re-index 后 status 正确；backup→verify→新空目录 restore 后历史和 unavailable 状态保留；startup/read/restore 不 repair/rebuild/regenerate。
- **Gate I：收口**：完整 backend、相关 Chromium、Phase 8/9A regression、脱敏 evidence、STATUS/TODO/ROADMAP/PROJECT_PROGRESS/INDEX 同步。

## 完成措辞

只有所有相关 gates 通过后，才允许使用：

> Phase 9B 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表 Phase 9C/9D、真实 Provider generation、scheduler/worker、人工复核或全局 production `real-pass`。

任何单一子任务通过只能使用 `planned`、`contract-frozen`、`implemented/backend-pass`、`browser-pass`、`scoped-gates-pass`、`restore-gates-pass` 等准确局部状态。
