# StudyBuddy 文档索引

## 核心入口

- [`../README.md`](../README.md)：项目定位、运行入口与当前能力摘要。
- [`../AGENTS.md`](../AGENTS.md)：贡献和 coding-agent 约束。
- [`ARCHITECTURE.md`](ARCHITECTURE.md)：正式系统架构、支持边界与核心不变量。
- [`CODE_TEST_GOVERNANCE.md`](CODE_TEST_GOVERNANCE.md)：代码边界、测试层级、证据等级和提交门禁。
- [`STATUS.md`](STATUS.md)：实现状态与证据索引的权威来源。
- [`TODO.md`](TODO.md)：唯一可勾选的执行清单。
- [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md)：长期阶段、依赖和完成标准。
- [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)：项目现状摘要。

## 核心设计与运维

- [`ai-learning-architecture.md`](ai-learning-architecture.md)：AI/学习功能架构和实施边界。
- [`MIGRATIONS.md`](MIGRATIONS.md)：schema version、migration runner 与升级规则。
- [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)：backup / verify / restore 行为边界。

## 正式验收证据

- [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)：Cards / Exercises 限定范围验收。
- [`PHASE9A_ACCEPTANCE_EVIDENCE.md`](PHASE9A_ACCEPTANCE_EVIDENCE.md)：学习领域与计划核心验收。
- [`prompts/evidence/PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md`](prompts/evidence/PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md)：9A source lifecycle 辅助证据。
- [`prompts/evidence/PHASE9A_BACKUP_RESTORE_EVIDENCE.md`](prompts/evidence/PHASE9A_BACKUP_RESTORE_EVIDENCE.md)：9A backup / restore 辅助证据。
- [`PHASE9B_ACCEPTANCE_EVIDENCE.md`](PHASE9B_ACCEPTANCE_EVIDENCE.md)：S1/S2 工作流验收。
- [`PHASE9C_ACCEPTANCE_EVIDENCE.md`](PHASE9C_ACCEPTANCE_EVIDENCE.md)：S3/S4/S5 工作流验收。

## 非核心资料

所有规划 prompt、阶段审计、历史决策、provider/运行手册与已完成阶段的辅助证据统一放在 [`prompts/`](prompts/)。其中：

- [`prompts/phase9a/`](prompts/phase9a/)、[`prompts/phase9b/`](prompts/phase9b/)、[`prompts/phase9c/`](prompts/phase9c/)：Phase 9 的任务规划、领域契约和执行门禁；它们不是实现状态证据。
- `prompts/` 根目录：provider、升级、备份演练、基础设施和历史参考资料。

## 文档维护规则

- 根目录只保留 `README.md`、`AGENTS.md` 与项目元数据；活跃文档位于 `docs/`。
- `STATUS.md`、`TODO.md` 与 `PHASE_ROADMAP.md` 分别负责状态、执行清单与长期顺序；发生冲突时先修正这些事实源。
- `docs/` 根目录只保留核心入口、设计、治理、状态、路线、TODO 和正式 acceptance；非核心过程资料、历史决策、规划 prompt 和辅助 evidence 只放在 `docs/prompts/`（辅助 evidence 置于 `docs/prompts/evidence/`），不要再复制到 `docs/` 根目录。
