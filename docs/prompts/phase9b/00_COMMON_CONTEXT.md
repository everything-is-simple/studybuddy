# Phase 9B 共用上下文 Prompt

以下内容应作为每一个 Phase 9B 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中实现 StudyBuddy Phase 9B 的一个明确子任务。

StudyBuddy 是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 学习材料系统。正式代码只能放在 backend/app/，正式测试只能放在 backend/tests/，长期文档只能放在 docs/。不得复制 Composer、Integration 或历史项目源码作为正式实现；历史项目只能提供需求线索，正式实现必须基于当前源码和已验证 contract 重新实现。

Phase 9A 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium、backup/restore 的明确范围内完成。当前必须以实际源码和权威文档为准，不能仅依据历史测试数字或设计文档猜测接口。Phase 9B 必须复用并扩展已验证的：
- materials、extractions、text_spans source of truth；
- material active/deleted/restored/purged lifecycle；
- material_revisions、deterministic chunks、chunk_spans；
- lexical/vector/hybrid retrieval、retrieval_runs/hits、context assembly；
- server-side citation validation 和 source-unavailable/stale contract；
- Phase 9A 的 goals、knowledge modules、study plans/items、dependency、append-only progress、source links；
- Phase 8 Cards/Exercises 的 draft、用户编辑保护、citation lifecycle、backup/restore 边界；
- 现有 provider registry、deterministic fake provider、ai_operations 和安全错误 contract。

Phase 9B 只实现资料学习工作流：
- S1 学习节奏：在已有 Phase 9A plan/item/progress 基础上提供显式节奏目标、学习时段/工作量分配、时间线或节奏视图；不得实现提醒、推送、后台 scheduler、自动执行或自动重排；
- S2 资料笔记：提供用户笔记、资料证据关联、知识模块整理，以及显式 fake-provider 下 citation-safe 的笔记/知识模块 draft workflow；不得把历史 KnowledgeModule 实现直接视为正式实现；
- S1/S2 都必须保持 source revision/chunk/citation 可追溯，并覆盖 source lifecycle、失败、刷新、导出和恢复边界。

Phase 9B 明确不做：S3/S4/S5 限时练习、错题和期末冲刺；S6/S7 家长报告、课堂采集、OCR、ASR；真实 Provider generation acceptance；人工简答复核；提醒/日历推送/定时任务；worker、queue、cancel、跨进程协调；多用户、认证授权、云同步、协作、外部 vector DB。

必须遵守：
- 当前 schema version 以源码为准；所有表、字段、索引和约束都走 migrations runner；
- migration 连续、幂等、事务化，并有升级、失败 rollback、history/user_version 一致性测试；
- 不得在运行时 ad-hoc CREATE TABLE；
- AI 生成内容必须先是 draft，必须保留 source revision 和可验证 citation；不能静默覆盖用户编辑、confirmed、active 或完成状态；
- 用户笔记和 progress 历史不能被重生成或同步操作静默覆盖；
- source deleted/purged/stale/unavailable 时不得伪造正文、材料名称或可用 citation；
- API/UI/日志不得泄露路径、SQL、正文全文、secret、provider raw response、原始异常或 traceback；
- 保持单进程/单实例边界，不宣称多进程共享 data_root；
- backup/restore、startup/read/verify 不得自动 repair、rebuild、重新生成笔记或提升 unavailable 状态；
- 日期、时区和节奏计算必须由冻结契约明确，不能依赖宿主机本地时区的隐式行为；
- 导出必须复用现有安全下载/导出 contract，不生成未经定义的文件格式或服务器路径。

在动手前必须：
1. 读取 AGENTS.md；
2. 读取 docs/PHASE_ROADMAP.md、docs/STATUS.md、docs/TODO.md、docs/PROJECT_PROGRESS_REPORT.md、docs/ai-learning-architecture.md、docs/MIGRATIONS.md、docs/BACKUP_RESTORE.md、docs/CODE_TEST_GOVERNANCE.md；
3. 审计 backend/app/migrations/、repository.py、main.py、backup.py、restore_acceptance.py，以及实际的 Phase 9A/Phase 8 tests 和前端 workspace；
4. 查明当前 schema version、事务边界、ID/时间/错误/分页/导出约定、测试 fixture 和真实已实现 API；
5. 给所有重要结论标注源码路径、函数名或测试名；
6. 只修改当前子任务拥有的范围；不要顺手实现下一个子任务。

本子任务结束时必须报告：修改文件、新增/修改测试、focused 命令和结果、涉及的完整门禁结果、未验证边界、准确状态措辞、后续阻塞项。如果发现必须改变已冻结的 9B 契约，先停止实现并提出契约变更，不要擅自扩大范围。
```