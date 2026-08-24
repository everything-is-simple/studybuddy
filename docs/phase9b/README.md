# Phase 9B Prompt 包：资料学习工作流 S1/S2

本目录保存 Phase 9B 的正式规划与逐子任务执行 prompts。Phase 9B 仍处于 `planned`；本目录中的 prompt、设计和计划不是实现证据。

## 文件

- `00_COMMON_CONTEXT.md`：所有 9B 子任务共用的项目上下文、治理约束和执行规则。
- `00_MASTER_PLAN_PROMPT.md`：Phase 9B 总规划 prompt，只做审计、范围设计、子任务拆分和验收门禁，不实现代码。
- `9B-0_现状审计与范围冻结.md`：审计当前 9A、Phase 8、revision/chunk/retrieval/citation 和前端能力，冻结 9B non-goals。
- `9B-1_正式领域契约与状态机.md`：冻结 S1/S2 领域对象、状态机、不变量、source/citation 规则。
- `9B-2_Migration_与_schema.md`：实现 9B 所需连续 migration 和 schema 测试。
- `9B-3_Repository_与_domain_transaction.md`：实现资料笔记、知识模块和节奏领域事务。
- `9B-4_S2_资料笔记与知识模块工作流.md`：实现 S2 的笔记、知识模块、检索引用和 draft 生成闭环。
- `9B-5_S1_学习节奏工作流.md`：实现 S1 的节奏、学习时段/任务分配和计划视图闭环，不引入后台 scheduler。
- `9B-6_API_contract.md`：将已验收的 S1/S2 domain 能力暴露为安全 API。
- `9B-7_最小工作区_UI.md`：实现 S1/S2 最小 Chromium workspace 和失败路径。
- `9B-8_Source_lifecycle_与_backup_restore.md`：完成 source lifecycle、backup/restore 和 non-repair 验收。
- `9B-9_完整验收_证据与文档收口.md`：完成全量回归、脱敏证据和文档状态收口。
- `EXECUTION_ORDER_AND_GATES.md`：执行顺序、推荐 commit 拆分和 Phase 9B 完成门槛。

## 推荐执行顺序

`9B-0 → 9B-1 → 9B-2 → 9B-3 → 9B-4 → 9B-5 → 9B-6 → 9B-7 → 9B-8 → 9B-9`

每次只执行一个子任务。若发现契约问题，应暂停当前实现并先提出契约变更；不得把多个子任务合并为无法独立验收的大改动。
