# 归档文档索引

本目录包含已完成工程的历史记录、契约文档、证据文档和操作手册，仅供追溯参考，不作为当前事实源。

---

## 📂 目录结构

### contracts/ - 契约文档（24 个）
各个组件和功能的设计契约，定义了接口、行为边界和验收标准。

**主要契约**：
- `B2_IMAGE_OCR_PROVIDER_CONTRACT.md` - OCR 组件契约
- `B3_REPORT_COMPONENT_CONTRACT.md` - 报告组件契约
- `B4_DELIVERY_COMPONENT_CONTRACT.md` - 外发组件契约
- `PHASE10_OPERATION_TASK_CONTRACT.md` - 运维任务契约
- 更多契约文档见目录内完整列表

### evidence/ - 证据文档（40+ 个）
各个 Phase 和切片的验收证据，记录了实现范围、测试结果和已知限制。

**主要证据**：
- `PHASE9A_ACCEPTANCE_EVIDENCE.md` - Phase 9A 验收证据
- `PHASE9B_ACCEPTANCE_EVIDENCE.md` - Phase 9B 验收证据
- `PHASE9C_ACCEPTANCE_EVIDENCE.md` - Phase 9C 验收证据
- `PHASE9D_ACCEPTANCE_EVIDENCE.md` - Phase 9D 验收证据
- `P1_*_EVIDENCE.md` - P1 系列各切片证据
- `P2_*_EVIDENCE.md` - P2 系列各切片证据

### operations/ - 操作手册（5 个）
运维人员必读的操作手册，包括 Provider 配置、备份恢复、升级等。

**运维手册**：
- `AI_PROVIDER_SETUP.md` - AI Provider 配置指南
- `AGNES_PROVIDER_RUNBOOK.md` - Agnes Provider 运行手册
- `BACKUP_OPERATIONS.md` - 备份操作手册
- `OPERATOR_UPGRADE.md` - 升级操作手册
- `LOCAL_ENVIRONMENT_MAP.md` - 本地环境映射

### code-documentation-project/ - 代码注释工程历史文档（18 个）
Phase A-F 的计划、进度更新和完成总结。

**工程成果**：代码注释率从 1.2% 提升至 10%+，完成 Phase A-F 全部计划批次。详见 `../docs/[维护者看]CODE_DOCUMENTATION_PROJECT.md`。

### progress-snapshots/ - 项目进度快照（6 个）
2025-01 会话工作总结和项目进度汇总。

### historical-roadmaps/ - 历史阶段路线图（1 个）
`PHASE_ROADMAP.md` - Phase 1-10 历史路线图与完成情况。

**当前路线图**：见 `../docs/[需求+架构看]ROADMAP_CAPABILITIES.md`。

### frontend/ - 前端盘点与审计历史文档
- `frontend-plan.md` - 前端计划
- `frontend-inventory-report.md` - 前端资源盘点
- `frontend-contract-audit-report.md` - 前端契约审计
- `frontend-static-capability-matrix.md` - 静态能力矩阵
- `frontend-static-failure-retry-matrix.md` - 失败/重试矩阵

### P1_3/ - P1-3 阶段完成文档
- `P1-3-MANUAL-TEST.md` - 手工测试记录
- `P1-3-STATUS.md` - 状态快照
- `P1-3-SUMMARY.md` - 总结报告

### 其他重要归档
- `A2_X_SERIES_SUMMARY.md` - A2.X 系列重构总结
- `P14_P0_05_COMPLETED.md` - P14 P0-05 阶段完成记录
- `PHASE10_AUDIT_AND_SCOPE.md` - Phase 10 审计与范围
- `PHASE9C_AUDIT_AND_SCOPE.md` - Phase 9C 审计与范围
- `PHASE9D_AUDIT_AND_SCOPE.md` - Phase 9D 审计与范围
- `HISTORICAL_SCENARIO_REVIEW.md` - 历史场景回顾

---

## 🔍 使用说明

这些文档记录了项目演进历史，帮助理解决策背景和实现轨迹。当前状态、待办和路线图请查看：

- **当前状态**：`../docs/[需求+所有角色看]STATUS.md`
- **待办清单**：`../docs/[需求看]TODO.md`
- **路线图**：`../docs/[需求+架构看]ROADMAP_CAPABILITIES.md`
- **架构边界**：`../docs/[架构师看]ARCHITECTURE.md`

---

## 📏 归档规则

1. **已完成 Phase 的总结性文档**必须在完成后 7 天内归档
2. **契约文档**在契约冻结后归档，但仍可作为实现参考
3. **证据文档**在验收完成后归档，记录当时的 scoped closeout
4. **操作手册**仍然有效，运维人员必读
5. **历史快照**仅供追溯，不作为当前事实源

---

**维护者**：架构师 + 需求分析师  
**更新频率**：每次归档新文档时更新  
**版本**：v2（2026-09-07，重新组织为 .archive）
