# StudyBuddy 文档索引

## 项目入口

- [`../README.md`](../README.md)：项目简介、当前能力和运行入口。
- [`../AGENTS.md`](../AGENTS.md)：AI coding agent 与贡献者工作约束。
- [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)：当前总体进度与已完成/未完成范围。
- [`TODO.md`](TODO.md)：唯一的可执行任务清单与优先级。
- [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md)：阶段路线图、依赖和完成标准。

## 架构与决策

- `ARCHITECTURE.md`：系统架构边界。
- `DECISIONS.md`：架构和产品决策记录。
- [`ai-learning-architecture.md`](ai-learning-architecture.md)：AI/学习功能架构与已实现的 Phase 4–7、Phase 8 fake-provider 范围；不是完整学习产品完成声明。
- [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)：Phase 8 fake-provider backend/Chromium/backup-restore 收口证据与限制。
- [`phase9a/`](phase9a/)：Phase 9A 总规划 prompt、共用上下文、9A-0 至 9A-8 子任务 prompts、执行顺序和验收门槛；prompt 目录不是实现证据，Phase 9A 完成证据见 `PHASE9A_ACCEPTANCE_EVIDENCE.md`。
- [`phase9b/`](phase9b/)：Phase 9B 总规划 prompt、共用上下文、9B-0 至 9B-9 子任务 prompts、执行顺序和验收门槛；9B-2 至 9B-6 已达到 `implemented/backend-pass`，9B-7 已达到 `browser-pass`，9B-8 已达到 `scoped-gates-pass`/`restore-gates-pass`，9B-9 已完成限定范围内 closeout。最终实现证据见 [`PHASE9B_ACCEPTANCE_EVIDENCE.md`](PHASE9B_ACCEPTANCE_EVIDENCE.md)；prompt 目录本身不是实现证据。
- [`phase9c/`](phase9c/)：Phase 9C S3/S4/S5 总规划、共用上下文、9C-0 至 9C-10 子任务、执行顺序和 Gate A-J；9C-2/9C-3 已达 `implemented/backend-pass`，Phase 9C 整体仍为 `planned`，目录中的 prompt/契约本身不是实现证据。
- [`phase9a/PHASE9A_DOMAIN_CONTRACT.md`](phase9a/PHASE9A_DOMAIN_CONTRACT.md)：9A-0/9A-1 契约、9A-2 v9 schema、9A-3 repository/domain、9A-4 API、9A-5 browser-pass、9A-6 scoped-gates-pass、9A-7 restore-gates-pass 和 9A-8 closeout 记录。
- [`PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md`](PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md)：9A-6 source lifecycle 的脱敏 evidence 草案、测试结果和剩余限制。
- [`PHASE9A_BACKUP_RESTORE_EVIDENCE.md`](PHASE9A_BACKUP_RESTORE_EVIDENCE.md)：9A-7 backup/verify/restore/non-repair 的脱敏 evidence 和限制。
- [`PHASE9A_ACCEPTANCE_EVIDENCE.md`](PHASE9A_ACCEPTANCE_EVIDENCE.md)：Phase 9A 最终 acceptance、全量回归、用户路径、范围和未验证边界。
- [`PHASE9B_ACCEPTANCE_EVIDENCE.md`](PHASE9B_ACCEPTANCE_EVIDENCE.md)：Phase 9B S1/S2 Gate A-I 最终 acceptance、全量回归、生命周期/恢复、隐私边界和未验证范围。
- [`PROVIDER_CAPABILITY_MATRIX.md`](PROVIDER_CAPABILITY_MATRIX.md)：Phase 5 各 OpenAI-compatible Provider 的独立证据矩阵和 opt-in 验收命令。
- [`AI_PROVIDER_SETUP.md`](AI_PROVIDER_SETUP.md)：StudyBuddy Provider 配置边界、密钥安全规则和三次 API acceptance runner。
- [`AGNES_PROVIDER_RUNBOOK.md`](AGNES_PROVIDER_RUNBOOK.md)：Agnes AI-Hub 独立本地 launcher、smoke gate 和运维边界。

## 数据库与运维

- `MIGRATIONS.md`：schema version、migration runner、升级规则。
- [`OPERATOR_UPGRADE.md`](OPERATOR_UPGRADE.md)：operator 数据库升级 runbook。
- `BACKUP_RESTORE.md`：backup / verify / restore 行为边界。
- [`BACKUP_OPERATIONS.md`](BACKUP_OPERATIONS.md)：备份存放、保留、轮换与失败隔离。
- [`RESTORE_DRILL.md`](RESTORE_DRILL.md)：恢复演练流程和记录模板。

## 基础设施与治理

- [`CODE_TEST_GOVERNANCE.md`](CODE_TEST_GOVERNANCE.md)：代码边界、测试分层、状态证据和提交门禁；统一测试入口见 `backend/scripts/`。
- [`INFRASTRUCTURE_CLOSEOUT.md`](INFRASTRUCTURE_CLOSEOUT.md)：I1/I2/I3 完成，I4 时间盒验收，基础设施 v1 基本完工。
- [`LOCAL_ENVIRONMENT_MAP.md`](LOCAL_ENVIRONMENT_MAP.md)：全部本地目录、远端、Git 状态和治理关系。
- [`HISTORICAL_SCENARIO_REVIEW.md`](HISTORICAL_SCENARIO_REVIEW.md)：祖宗版本与两个前辈版本的核心场景设计回顾。
- [`STATUS.md`](STATUS.md)：能力状态表和测试证据索引，是实现状态的唯一事实源；Phase 8 fake-provider closeout 在此记录。

## 文档维护规则

- 根目录只保留 `README.md`、`AGENTS.md` 与项目元数据；架构、状态、运维和过程文档统一位于 `docs/`。
- `TODO.md` 是唯一可勾选的执行清单；不要在其他文档复制另一份待办。
- `PROJECT_PROGRESS_REPORT.md` 描述当前事实；`PHASE_ROADMAP.md` 描述长期顺序；`STATUS.md` 记录能力状态与证据。
- 临时讨论、一次性执行记录和已被上述文档吸收的过程文档不保留在仓库中。
