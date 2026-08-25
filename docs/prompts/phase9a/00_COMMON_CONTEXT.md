# Phase 9A 共用上下文 Prompt


以下内容应作为每一个 9A 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中实现 StudyBuddy Phase 9A 的一个明确子任务。

StudyBuddy 是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 学习材料系统。正式代码只能放在 backend/app/，正式测试只能放在 backend/tests/，长期文档只能放在 docs/。不得复制 Composer、Integration 或历史项目源码作为正式实现；历史项目只能提供需求线索，正式实现必须基于当前源码和已验证 contract 重新实现。

当前已完成的基础能力：
- materials、extractions、text_spans 是原始资料 source of truth；
- material active/deleted/restored/purged 生命周期；
- material_revisions、deterministic chunks、chunk_spans；
- lexical/vector/hybrid retrieval、retrieval_runs/hits、context assembly；
- server-side citation 验证和 citation source lifecycle；
- Q&A、ai_operations、deterministic fake provider，以及精确范围的真实 Provider evidence；
- Phase 8 Cards/Exercises：draft → ready/rejected/archived、citation 生命周期、append-only review/attempt、确定性评分、backup/restore closeout。

Phase 9A 只做“学习领域基础与计划核心”：learning goal、knowledge module、study plan、study plan item、dependency、append-only progress event、progress summary，以及与现有 source revision/citation 的安全关联。不得顺带实现 9B 的资料笔记/学习节奏，9C 的限时练习/错题/冲刺，9D 的报告/OCR/ASR，也不得引入 worker、scheduler、queue、multi-user、cloud sync 或外部 vector DB。

必须遵守：
- 当前 schema version 以源码为准；所有表/字段/索引/约束走 migrations runner；
- migration 连续、幂等、事务化并有 rollback 测试；
- 不得用运行时 CREATE TABLE IF NOT EXISTS；
- AI 生成内容必须先是 draft，不能覆盖用户编辑、确认或完成状态；
- source deleted/purged/stale/unavailable 时不得伪造正文或可用 citation；
- progress 历史不可静默覆盖；
- API/UI/日志不得泄露路径、SQL、正文、secret、provider raw response、原始异常或 traceback；
- 保持单进程/单实例边界，不宣称多进程共享 data_root；
- backup/restore、startup/read 不得自动 repair、rebuild、重新生成或提升 unavailable 状态。

在动手前必须：
1. 读取 AGENTS.md；
2. 读取 docs/PHASE_ROADMAP.md、docs/STATUS.md、docs/TODO.md、docs/PROJECT_PROGRESS_REPORT.md、docs/ai-learning-architecture.md、docs/MIGRATIONS.md、docs/BACKUP_RESTORE.md、docs/CODE_TEST_GOVERNANCE.md；
3. 审计实际的 backend/app/migrations/、repository.py、main.py、backup.py、restore_acceptance.py、Phase 8 repository/API/tests；
4. 查明当前 schema version、事务边界、ID/时间/错误响应约定、测试 fixture 和前端 workspace 结构；
5. 不根据文档猜测实际接口，所有结论给出源码路径和函数/测试名称。

本子任务必须只修改它拥有的范围，并在结束时报告：
- 修改文件；
- 新增/修改测试；
- focused 命令和结果；
- 如涉及 migration/API/UI/backup，必须执行相应完整门禁；
- 未验证边界；
- 状态应使用的准确措辞；
- 后续阻塞项。

如果发现本子任务需要改变已冻结的领域契约，先停止实现并提出契约变更，不要擅自扩大范围。
```

---