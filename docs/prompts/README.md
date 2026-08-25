# 非核心文档目录

本目录统一存放规划 prompt、阶段审计、历史决策、provider/运行手册和辅助 evidence。文件仍保留在当前仓库中并可直接引用，但不作为当前实现状态的权威事实源；日常导航从 `docs/INDEX.md` 进入。

- `AGNES_PROVIDER_RUNBOOK.md`：Agnes launcher 历史 runbook
- `AI_PROVIDER_SETUP.md`：Provider 配置历史说明
- `BACKUP_OPERATIONS.md`：备份保留/轮换操作手册（行为边界已并入 `docs/BACKUP_RESTORE.md`）
- `DECISIONS.md`：架构与产品决策历史记录
- `HISTORICAL_SCENARIO_REVIEW.md`：祖宗版本与前辈版本核心场景回顾
- `INFRASTRUCTURE_CLOSEOUT.md`：I1–I4 基础设施收尾记录（内容已并入 `TODO.md` 与 `STATUS.md`）
- `evidence/`：已完成阶段的辅助 evidence；正式 acceptance 仍以 `docs/PHASE*_ACCEPTANCE_EVIDENCE.md` 为准。
- `LOCAL_ENVIRONMENT_MAP.md`：本地目录与远端映射（环境信息，非产品事实）
- `OPERATOR_UPGRADE.md`：operator 升级 runbook（已由 `docs/MIGRATIONS.md` 吸收）
- `P6E_ACCEPTANCE_EVIDENCE.md`：Phase 6 P6-E 精确真实 Provider UI 路径辅助证据
- `PHASE7_1_AUDIT_AND_CONTRACT.md`：Phase 7 embedding 现状审计与契约（已由 STATUS / TODO 吸收）
- `PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md`：Phase 7 Mistral 精确配置验收证据（主证据见 `PHASE_ROADMAP.md` 与 `STATUS.md`）
- `PROVIDER_CAPABILITY_MATRIX.md`：Phase 5 各 Provider 独立证据矩阵（已并入 `STATUS.md`）
- `RESTORE_DRILL.md`：恢复演练流程模板（行为边界已并入 `docs/BACKUP_RESTORE.md`）

## 维护原则

- 非核心资料不删除，Git 历史保持完整。
- `docs/` 根目录只保留 `docs/INDEX.md` 定义的核心入口、设计、治理、状态、路线、TODO 和正式 acceptance。
- 当前能力事实以 `docs/STATUS.md` 为准，执行项以 `docs/TODO.md` 为准；本目录中的历史陈述不得覆盖这些事实源。
- 辅助 evidence 统一放在 `evidence/`；阶段规划分别放在 `phase9a/`、`phase9b/`、`phase9c/`。
