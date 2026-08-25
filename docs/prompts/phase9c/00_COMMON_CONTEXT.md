# Phase 9C 共用上下文 Prompt

以下文本应作为每一个 Phase 9C 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中实现 StudyBuddy Phase 9C 的一个明确子任务。

StudyBuddy 是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 学习材料系统。正式代码只能放在 backend/app/，正式测试只能放在 backend/tests/，长期文档只能放在 docs/。不得复制 Composer、Integration 或历史项目源码；历史材料只能提供需求线索，正式实现必须基于当前源码和已验证 contract 重新实现。

Phase 9A 和 9B 已在各自明确范围内完成。Phase 9C 只做 S3 限时练习、S4 错题改错/反馈、S5 期末冲刺。必须先以源码为准审计当前 schema、repository、API、UI 和 tests；当前 schema version、已有表名、实际函数和测试数字不可凭历史文档猜测。

必须复用并保护：
- materials/extractions/text_spans source of truth；material active/deleted/restored/purged lifecycle；
- material_revisions、chunks、chunk_spans、lexical/vector/hybrid retrieval、context/citation 验证及 source-unavailable/stale contract；
- Phase 8 exercise/card：draft → ready/rejected/archived、题型校验、answer-key privacy、append-only exercise_attempts、MC/TF deterministic grading、short_answer pending_review；
- Phase 9A goals/modules/plans/items/dependencies、append-only progress/projection 和 source links；
- Phase 9B notes/modules/rhythm 只作为可选反馈上下文，不能被 S3/S4/S5 静默改写；
- ai_operations、provider registry、fake provider、幂等和安全错误/导出/backup/restore contract。

默认完成范围限定为 deterministic fake-provider、local single-process、SQLite、本地 Chromium、backup/restore。真实 Provider generation、外部真实题库/试卷、scheduler/worker/queue/cancel、自动提醒/推送/自动排程、多用户/认证/云同步/协作、OCR/ASR、外部 vector DB 不属于本阶段。

Phase 9C 的核心安全边界：
- attempt 是 append-only，提交原文、评分结果、人工复核和反馈历史不可覆盖；不得把重做写回旧 attempt；
- answer key、内部评分依据和其他用户敏感答案不得出现在普通 exercise/list/attempt API 或正常 DOM；展示反馈时只返回安全的用户可见结果；
- short_answer 默认进入 pending_review；人工复核必须显式、可审计、不能伪造为 deterministic；不支持自动把 AI 意见当最终裁决；
- session 的计时语义必须由冻结契约定义，服务端不能信任客户端 elapsed/score/finished_at；离线/刷新/重复提交要有明确边界；
- AI 生成的练习、变题、解析或反馈先是 draft/建议，保留 source revision 和可验证 citation；不能静默覆盖用户编辑、confirmed artifact、attempt 或 review；
- source deleted/purged/stale/unavailable 时不得伪造正文、材料名称、路径、quote 或可用 citation；历史 attempt/result 保留，source 状态只降级；
- 所有新增 schema 必须走 migrations runner；不得运行时 CREATE TABLE；migration 连续、幂等、事务化并测试 rollback/history/user_version；
- backup/verify/restore/startup/read 不调用 provider、不重评分、不重建错题/冲刺、不自动修复或提升 unavailable 状态；
- API/UI/日志不得泄露路径、SQL、traceback、原始异常、secret、provider raw response、answer key 或不必要的 source 全文；
- 仍是单进程/单实例边界，不宣称多 worker、多实例共享 data_root 或实时断电恢复。

开始前必须：
1. 读取 AGENTS.md；
2. 完整读取 docs/PHASE_ROADMAP.md、STATUS.md、TODO.md、PROJECT_PROGRESS_REPORT.md、ai-learning-architecture.md、MIGRATIONS.md、BACKUP_RESTORE.md、CODE_TEST_GOVERNANCE.md；
3. 审计 backend/app/migrations/runner.py、repository.py、main.py、backup.py、restore_acceptance.py，以及 Phase 8/9A/9B tests 和 browser workspace；
4. 找到实际 schema version、事务边界、ID/时间/错误/分页/导出约定；
5. 在计划/报告中引用源码路径、函数名或测试名；不能用设计文档替代实现证据；
6. 只修改当前子任务拥有的范围，不顺手实现下一个任务；发现契约冲突先停止并提交契约变更提案。

结束时必须报告：修改文件、新增/修改测试、focused 命令与结果、相关完整门禁结果、未验证边界、准确状态措辞、后续阻塞项和是否需要独立 fix commit。
```