# Phase 9A 执行顺序、提交拆分与完成门槛


推荐严格按以下顺序执行：

```text
9A-0 审计与范围冻结
  ↓
9A-1 领域契约与状态机冻结
  ↓
9A-2 migration/schema
  ↓
9A-3 repository/domain
  ↓
9A-4 API
  ↓
9A-5 UI
  ↓
9A-6 source lifecycle 集成
  ↓
9A-7 backup/restore
  ↓
9A-8 acceptance/documentation closeout
```

推荐每个任务单独 commit：

| Commit | 单一责任 |
|---|---|
| `docs: freeze phase 9a audit boundaries` | 9A-0 审计与边界文档 |
| `docs: define phase 9a domain contract` | 9A-1 领域契约与状态机 |
| `db: add phase 9a schema migration` | 9A-2 migration 与 migration tests |
| `feat: add phase 9a plan domain repository` | 9A-3 repository/domain 与 focused tests |
| `feat: expose phase 9a plan api` | 9A-4 API 与 boundary tests |
| `feat: add phase 9a plan workspace` | 9A-5 UI 与 Chromium tests |
| `feat: integrate phase 9a source lifecycle` | 9A-6 source lifecycle tests |
| `test: verify phase 9a backup restore` | 9A-7 backup/restore closeout tests |
| `docs: close phase 9a acceptance` | 9A-8 evidence、状态与 TODO 收口 |

若某任务必须修复前一任务的问题，应使用独立 fix commit，并说明它修复哪个 gate；不得把多个未验收任务压成一个大 commit。

- **Gate A：契约**：领域关系、状态机、不变量、source lifecycle、progress、dependency 规则冻结。
- **Gate B：数据库**：migration 连续、幂等、rollback、schema history 和 backup version 一致。
- **Gate C：领域层**：事务、cycle detection、append-only progress、用户编辑保护通过。
- **Gate D：API**：输入边界、生命周期、稳定错误和隐私 contract 通过。
- **Gate E：Source lifecycle**：delete/restore/purge/re-index 后状态真实、安全且不可伪造。
- **Gate F：UI**：创建→draft→confirm→active→完成→summary→refresh 路径及 failure/narrow/keyboard 通过。
- **Gate G：Restore**：backup→verify→新空目录 restore，non-repair 和历史保留通过。
- **Gate H：收口**：完整 backend、相关 Chromium、evidence、STATUS/TODO/ROADMAP 同步。

在 Gate H 之前，不得写 `Phase 9A completed`。9A 完成后仍必须保留：真实 Provider plan generation、人工计划审核、提醒/调度、S1/S2、S3/S4/S5、S6/S7、后台任务、多用户和全局 production real-pass 为未完成或未验证。