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
- [`ai-learning-architecture.md`](ai-learning-architecture.md)：AI/学习功能架构；仅设计，非已实现功能。
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
- [`STATUS.md`](STATUS.md)：能力状态表和测试证据索引，是实现状态的唯一事实源。

## 文档维护规则

- 根目录只保留 `README.md`、`AGENTS.md` 与项目元数据；架构、状态、运维和过程文档统一位于 `docs/`。
- `TODO.md` 是唯一可勾选的执行清单；不要在其他文档复制另一份待办。
- `PROJECT_PROGRESS_REPORT.md` 描述当前事实；`PHASE_ROADMAP.md` 描述长期顺序；`STATUS.md` 记录能力状态与证据。
- 临时讨论、一次性执行记录和已被上述文档吸收的过程文档不保留在仓库中。
