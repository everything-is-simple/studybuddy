# Phase 10 Prompt 包：本地生产化与上线收口

Phase 10 的目标不是继续无限加功能，而是把当前 Phase 9D 部分立项范围收口为可安装、可启动、可诊断、可升级、可备份恢复、可发布的本地单机 v1。默认上线模型仍是 **single-process / single-instance / SQLite / local disk**；多用户、认证、云同步、协作、多进程共享 data_root 不属于本次隐含范围。

## 文件

- `00_MASTER_PLAN_PROMPT.md`：总体规划 prompt，先审计并定义“成功上线”。
- `00_COMMON_CONTEXT.md`：每个子任务必须附带的共同上下文。
- `10-0_上线定义_现状审计与范围冻结.md` 至 `10-9_发布候选_上线演练与收口.md`：逐任务执行 prompt，一项一项执行。
- `PHASE10_AUDIT_AND_SCOPE.md`：10-0 审计产物；Gate A 已通过，批准进入 10-1。
- `PHASE10_OPERATION_TASK_CONTRACT.md`：10-1 operation/task 正式契约与状态机；Gate B 已通过。
- v13 `phase10_operation_task_schema`：10-2 最小 task/attempt schema；Gate C 已通过。
- `backend/app/task_runner.py`：10-3 explicit-only single-process runner/recovery；Gate D 已通过。
- `PHASE10_TASK_INTEGRATION_EVIDENCE.md`：10-4 approved `embedding_index` task integration；Gate E 已通过，批准进入 10-5。
- `EXECUTION_ORDER_AND_GATES.md`：顺序、推荐 commit、Gate A-J、停工规则和完成措辞。

## 计划步骤

共 **10 步（10-0 至 10-9）**：

1. 定义本地 v1 上线和不支持边界；
2. 冻结 operation/task 契约；
3. 增加并验证任务 schema；
4. 实现单进程 runner 和恢复；
5. 接入批准的现有长任务；
6. 完成 observability、health/readiness/degraded；
7. 完成 backup/restore/migration 运维闭环；
8. 完成安全配置、启动/停止和发布方式；
9. 完成容量、性能、长时和故障边界证据；
10. 完成 release candidate、端到端上线演练和文档收口。

每步必须独立测试、独立提交、独立更新状态；prompt 本身不是实现证据。只有 Gate A-J 全部通过，才能使用本包定义的“Phase 10 已完成、StudyBuddy 本地单机 v1 已上线”措辞。
