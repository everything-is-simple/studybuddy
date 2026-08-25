# Phase 9C Prompt 包：练习与反馈工作流（S3/S4/S5）

本目录保存 Phase 9C 的总体规划、共用上下文、逐子任务执行 prompt、推荐执行顺序和验收门禁。Phase 9C 整体仍为 `planned`：9C-2/9C-3/9C-4/9C-5/9C-6/9C-7 已分别达到 `implemented/backend-pass`，9C-8 达到 `browser-pass`，但 prompt、契约草案或历史项目类似功能本身不是实现证据，且不得标记 Phase 9C completed。

## 目标范围

- **S3 PracticeRunner：限时练习**：复用 Phase 8 的 exercise/card、attempt 和确定性评分能力，增加显式练习 session、限时边界、结果汇总和用户路径。
- **S4 ErrorFixer：错题改错**：从 append-only attempt/grading/review 事实产生错题投影，支持错因、改错、重做、人工复核和薄弱点/反馈历史；不覆盖原始 attempt。
- **S5 ExamCrammer：期末冲刺**：围绕显式选定的练习/卡片建立冲刺目标与模拟卷/session，复用 S3 session 和 S4 feedback；不实现自动排程、提醒或后台任务。

## 文件

- `00_COMMON_CONTEXT.md`：每个子任务都必须附带使用的项目基线、治理约束和 Phase 9C non-goals。
- `00_MASTER_PLAN_PROMPT.md`：只做审计、契约决策、子任务拆分和验收规划的总体 prompt。
- `9C-0_现状审计与范围冻结.md`：审计 Phase 8/9A/9B 实际能力，冻结 S3/S4/S5 边界。
- `PHASE9C_AUDIT_AND_SCOPE.md`：9C-0 审计产物、Gate A 结论、风险登记和 9C-1 未决问题；状态为 `planned/audit-draft`，不是实现证据。
- `9C-1_正式领域契约与状态机.md`：冻结 session、attempt、grading/review、mistake、weak-point、cram 的关系和状态机。
- `PHASE9C_DOMAIN_CONTRACT.md`：9C-1 Gate B 正式契约产物；状态为 `planned/contract-frozen`，不是实现证据。
- `9C-2_Migration_与_schema.md`：实现连续 migration、约束、升级/回滚和 schema 测试。
- `9C-3_Repository_与_domain_transaction.md`：共享领域事务、投影、幂等、隐私和 append-only 保护；已达到 `implemented/backend-pass`。
- `9C-4_S3_限时练习工作流.md`：S3 session/计时/提交/评分/结果 backend 闭环；已达到 `implemented/backend-pass`。
- `9C-5_S4_错题改错与人工复核.md`：S4 错题、改错、重做、短答人工复核和历史 backend 闭环；已达到 `implemented/backend-pass`。
- `9C-6_S5_期末冲刺工作流.md`：S5 冲刺目标、模拟练习和结果反馈 backend 闭环；已达到 `implemented/backend-pass`。
- `9C-7_API_contract.md`：S3/S4/S5 安全 API 和隐私边界；已达到 `implemented/backend-pass`。
- `9C-8_最小工作区_UI.md`：最小 Chromium workspace 与失败/窄屏/键盘/reload 路径；已达到 `browser-pass`。
- `9C-9_Source_lifecycle_与_backup_restore.md`：验证 citation/source lifecycle、backup/restore 和 non-repair。
- `9C-10_完整验收_证据与文档收口.md`：完成 full regression、证据和状态收口。
- `EXECUTION_ORDER_AND_GATES.md`：执行顺序、推荐 commit、Gate A-J 和准确完成措辞。

## 推荐顺序

`9C-0 → 9C-1 → 9C-2 → 9C-3 → 9C-4 → 9C-5 → 9C-6 → 9C-7 → 9C-8 → 9C-9 → 9C-10`

每次只执行一个子任务。若发现契约不足，暂停实现并提出契约变更；不得把 S3/S4/S5 合并成不可独立验收的大改动。
