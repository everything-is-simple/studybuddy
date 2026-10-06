# 00 · 文档导航

从这里开始：

1. **产品定位**：[`01-PRD.md`](01-PRD.md) — 为谁而做、解决什么问题、不做什么。
2. **子系统地图**：[`02-SUBSYSTEMS.md`](02-SUBSYSTEMS.md) — S1 Today 到 S7 课堂采集，七个子系统的边界。
3. **架构**：[`03-ARCHITECTURE.md`](03-ARCHITECTURE.md) — 代码布局、数据流、AI 边界、目录。
4. **能力状态**：[`capabilities.json`](capabilities.json) — 唯一状态源，写明实现/验证/证据/缺口。
5. **治理**：[`05-GOVERNANCE.md`](05-GOVERNANCE.md) — 代码、测试、组件、文档规则。
6. **运维**：[`06-OPERATIONS.md`](06-OPERATIONS.md) — 启动、备份恢复、迁移、新机器。
7. **验收计划**：[`07-TEST-PLAN.md`](07-TEST-PLAN.md) — P0 主闭环验收标准与证据存放。
8. **决策记录**：[`08-DECISIONS.md`](08-DECISIONS.md) — 决定了什么、为什么、影响什么。

## 按子系统

- [`subsystems/S1-学习节奏-Today.md`](subsystems/S1-学习节奏-Today.md) — 待办、安排、进度
- [`subsystems/S2-资料笔记-NoteBuilder.md`](subsystems/S2-资料笔记-NoteBuilder.md) — 导入、知识模块、AI 抽取
- [`subsystems/S3-限时练习-PracticeRunner.md`](subsystems/S3-限时练习-PracticeRunner.md) — 生成题目、作答、批改
- [`subsystems/S4-错题改错-ErrorFixer.md`](subsystems/S4-错题改错-ErrorFixer.md) — 错题、复盘、重做
- [`subsystems/S5-期末冲刺-ExamCrammer.md`](subsystems/S5-期末冲刺-ExamCrammer.md) — 备考目标、倒计时
- [`subsystems/S6-家长报告-ParentReport.md`](subsystems/S6-家长报告-ParentReport.md) — 脱敏聚合、外发审计
- [`subsystems/S7-课堂采集-ClassCapture.md`](subsystems/S7-课堂采集-ClassCapture.md) — 音频转录（未实现）
- [`subsystems/X-横切能力.md`](subsystems/X-横切能力.md) — TTS、材料问答、备份恢复

## 历史与参考

- [`archive/legacy-product-references/ai-studybuddy/`](archive/legacy-product-references/ai-studybuddy/) — 第一版骨架（清晰）
- [`archive/legacy-product-references/pi-studybuddy/`](archive/legacy-product-references/pi-studybuddy/) — 第二版（pi 原生）
- `archive/` — 历史证据、契约、运维文档，不在主文档引用链中

## 用户

- [`user/LOCAL_V1_USER_GUIDE.md`](user/LOCAL_V1_USER_GUIDE.md) — 安装、配置、首次启动

## 开发者

- [`05-GOVERNANCE.md`](05-GOVERNANCE.md) §8 — AI 执行任务的门禁
- [`[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md`]([所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md) — 任务模板（已被 AGENTS.md 取代）
- [`[测试看]BROWSER_VERIFICATION_TASK_TEMPLATE.md`]([测试看]BROWSER_VERIFICATION_TASK_TEMPLATE.md) — 浏览器验收模板

## 注意

- 标题里 `[角色看]` 的文档已移入 `archive/`，不再维护。新文档只用编号（00-08）和子系统名。
- 冲突时以 `capabilities.json` 和本次可复现测试输出为准，再修正文档。
