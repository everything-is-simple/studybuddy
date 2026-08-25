# Phase 9D Prompt 包：扩展学习服务（S6 家长观察 / S7 课堂采集，条件性范围）

本目录保存 Phase 9D 的总体规划、共用上下文、逐子任务执行 prompt、推荐执行顺序和验收门禁。Phase 9D 整体仍为 `planned`，并且是**条件性阶段**：只有在 9D-0 的需求、隐私、数据保留、真实组件证据和运维成本评审通过并明确立项后才继续实现。prompt、契约草案或历史项目类似功能本身不是实现证据，也不代表 Phase 9D 会自动立项。

## 目标范围（立项通过前提下）

- **S7 ClassCapture：课堂采集**：上传课堂录音/图片作为敏感原件并纳入既有 hash-derived originals/material lifecycle，通过 OCR/ASR 产出带置信度和 uncertain 标注的转写文本，并作为 S2 资料来源接入既有 material/revision/chunk 管线；默认使用 deterministic fake/loopback 组件，真实 OCR/ASR 以显式 gate 管理。
- **S6 ParentReport：家长观察**：基于 9A/9B/9C 已有派生事实生成只读、强制脱敏的日报/周报/月报/考前提醒；报告不改写学习事实；提供本地生成、预览、导出；对外交付（邮件/飞书）默认关闭，以可审计 dry-run 为可重复路径，真实发送需显式配置 + 授权 + 白名单，且不做自动定时推送。

## 与前序阶段的本质差异

Phase 9D 引入两个前序阶段刻意回避的高风险元素：真实外部 OCR/ASR 组件，以及对外交付（把数据发往第三方端点，接收方可能涉及未成年人）。因此本包以 go/no-go 立项门槛开头，默认交付范围限定为 fake/loopback 组件与 dry-run 交付，真实动作全部以显式 opt-in gate 和显式授权管理。

## 文件

- `00_COMMON_CONTEXT.md`：每个子任务都必须附带使用的项目基线、治理约束和 Phase 9D non-goals。
- `00_MASTER_PLAN_PROMPT.md`：只做立项评审、审计、契约决策、子任务拆分和验收规划的总体 prompt。
- `9D-0_立项评审_现状审计与范围冻结.md`：立项 go/no-go、审计 Phase 8/9A/9B/9C 实际能力、冻结 S6/S7 边界。
- `9D-1_正式领域契约与状态机.md`：冻结采集/转写/接入、报告/脱敏、交付/授权/审计的关系和状态机。
- `9D-2_Migration_与_schema.md`：实现连续 migration、约束、升级/回滚和 schema 测试。
- `9D-3_Repository_与_domain_transaction.md`：共享领域事务、投影、幂等、脱敏和 append-only 保护。
- `9D-4_S7_课堂采集与OCR_ASR转写.md`：S7 采集/转写 backend 闭环（fake/loopback 默认）。
- `9D-5_S7_转写接入S2资料管线.md`：转写作为 material/revision 安全接入既有管线。
- `9D-6_S6_家长报告聚合与脱敏.md`：只读报告聚合与强制脱敏 backend 闭环。
- `9D-7_S6_对外交付_默认关闭_dry_run_授权_审计.md`：交付层，默认关闭、dry-run、授权、白名单、审计。
- `9D-8_API_contract.md`：S6/S7 安全 API 和隐私/交付边界。
- `9D-9_最小工作区_UI.md`：最小 Chromium workspace 与失败/窄屏/键盘/reload/隐私路径。
- `9D-10_Source_lifecycle_与_backup_restore.md`：source lifecycle、backup/restore non-repair（不触发交付）专项验收。
- `9D-11_完整验收_证据与文档收口.md`：完成 full regression、证据和状态收口。
- `EXECUTION_ORDER_AND_GATES.md`：执行顺序、推荐 commit、Gate A-L、停工规则和准确完成措辞。

## 推荐顺序

`9D-0 → 9D-1 → 9D-2 → 9D-3 → 9D-4 → 9D-5 → 9D-6 → 9D-7 → 9D-8 → 9D-9 → 9D-10 → 9D-11`

9D-0 是硬门槛：立项条件未通过时不进入实现子任务，允许结论为暂不立项或仅立项 S6/S7 之一。每次只执行一个子任务。若发现契约不足，暂停实现并提出契约变更；不得把 S6/S7 合并成不可独立验收的大改动；真实对外交付实现前须标注高风险并请人确认。
