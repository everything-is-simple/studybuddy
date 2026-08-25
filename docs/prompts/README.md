# 文档归档目录

本目录存放已被吸收或阶段性完成、不再作为主仓库活跃事实源的参考文档。它们仍可通过 Git 历史访问，不再参与日常导航。

- `AGNES_PROVIDER_RUNBOOK.md`：Agnes launcher 历史 runbook
- `AI_PROVIDER_SETUP.md`：Provider 配置历史说明
- `BACKUP_OPERATIONS.md`：备份保留/轮换操作手册（行为边界已并入 `docs/BACKUP_RESTORE.md`）
- `DECISIONS.md`：架构与产品决策历史记录
- `HISTORICAL_SCENARIO_REVIEW.md`：祖宗版本与前辈版本核心场景回顾
- `INFRASTRUCTURE_CLOSEOUT.md`：I1–I4 基础设施收尾记录（内容已并入 `TODO.md` 与 `STATUS.md`）
- `LOCAL_ENVIRONMENT_MAP.md`：本地目录与远端映射（环境信息，非产品事实）
- `OPERATOR_UPGRADE.md`：operator 升级 runbook（已由 `docs/MIGRATIONS.md` 吸收）
- `P6E_ACCEPTANCE_EVIDENCE.md`：Phase 6 P6-E 精确真实 Provider UI 路径证据（详细 evidence 已并入 `docs/PHASE8_ACCEPTANCE_EVIDENCE.md` 及 `docs/PHASE9X_ACCEPTANCE_EVIDENCE.md`）
- `PHASE7_1_AUDIT_AND_CONTRACT.md`：Phase 7 embedding 现状审计与契约（已由 STATUS / TODO 吸收）
- `PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md`：Phase 7 Mistral 精确配置验收证据（主证据见 `PHASE_ROADMAP.md` 与 `STATUS.md`）
- `PROVIDER_CAPABILITY_MATRIX.md`：Phase 5 各 Provider 独立证据矩阵（已并入 `STATUS.md`）
- `RESTORE_DRILL.md`：恢复演练流程模板（行为边界已并入 `docs/BACKUP_RESTORE.md`）

## 归档原则

- 归档不删除；Git 历史仍完整保留。
- 主文档中的引用保持有效（指向 `docs/` 下的活跃文档）。
- 如需引用归档文档内容，通过 `git show HEAD:docs/<filename>` 读取原始版本。
