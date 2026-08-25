# Phase 9D 共用上下文 Prompt

以下文本应作为每一个 Phase 9D 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中实现 StudyBuddy Phase 9D 的一个明确子任务。

StudyBuddy 是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 学习材料系统。正式代码只能放在 backend/app/，正式测试只能放在 backend/tests/，长期文档只能放在 docs/。不得复制 Composer、Integration 或历史项目源码；历史材料（旧 s6/s7、ocr-tools、report/delivery 工具）只能提供需求线索，正式实现必须基于当前源码和已验证 contract 重新实现。

Phase 9A/9B/9C 已在各自明确范围内完成（当前 schema 为 v11）。Phase 9D 只做 S6 家长观察（ParentReport）和 S7 课堂采集（ClassCapture）两个扩展学习服务，并且是条件性阶段：只有在 9D-0 的需求、隐私、数据保留、真实组件证据和运维成本评审通过并明确立项后才继续实现；不能因为历史版本存在这两个功能就自动纳入正式范围。

Phase 9D 与前序阶段的本质差异，必须在每个子任务中格外谨慎：
- S7 引入真实外部组件（OCR/ASR）。真实识别/转写有失败、低置信、乱码、超时和成本；必须先在 Composer/Integration 验证组件，再由正式系统按已验证 contract 重新实现。默认交付范围仍以 deterministic fake/loopback 组件为可重复路径，真实 OCR/ASR provider 以显式 gate 管理，不得把 opt-in 结果宣称为通用 real-pass。
- S6 引入对外交付（邮件 SMTP / 飞书 webhook 等）。这会把数据发送到第三方端点，且接收方可能是家长、涉及未成年人。默认交付范围只做本地生成/预览/导出与可审计的 dry-run；真实外发必须显式开关、显式授权、可审计、可撤回，且默认关闭。任何真实外发都属于高风险动作，实现前须在 prompt/报告中标注并要求人确认。

必须复用并保护：
- materials/extractions/text_spans source of truth；material active/deleted/restored/purged lifecycle；
- material_revisions、chunks、chunk_spans、lexical/vector/hybrid retrieval、context/citation 验证及 source-unavailable/stale contract；
- Phase 8 exercise/card、append-only exercise_attempts、deterministic grading、answer-key privacy；
- Phase 9A goals/modules/plans/items/dependencies、append-only progress/projection、source links；
- Phase 9B notes/blocks/modules/rhythm；Phase 9C practice/cram session、attempt/review、mistake/weak-point/feedback 事实；
- ai_operations、provider registry、fake provider、幂等和安全错误/导出/backup/restore contract。

S7 与既有能力的关系：ClassCapture 的转写产物应作为 S2 资料来源接入既有 materials/extractions/revision/chunk 管线，不新建平行正文体系；转写文本必须可追溯到采集会话与置信度，低置信/uncertain 内容要求用户核对，AI 不作最终裁决。

S6 与既有能力的关系：ParentReport 是只读聚合视图。只能聚合 9A/9B/9C 已有的计划、进度、练习、错题、薄弱点等派生事实，且必须脱敏：不得包含原文、答案 key、用户提交原文、聊天/Q&A 原文、文件路径或可反推隐私的明细。报告本身不改写任何学习事实。

默认完成范围限定为 deterministic fake/loopback 组件、local single-process、SQLite、本地 Chromium、backup/restore、本地生成/预览/导出与可审计 dry-run 交付。真实 OCR/ASR provider、真实对外交付（SMTP/飞书生产端点）、scheduler/worker/queue/自动定时推送、多用户/认证/云同步/协作、外部 vector DB 不属于默认范围，均须显式 gate 和显式授权。

Phase 9D 的核心安全边界：
- 采集原始音频/图片是敏感原件，纳入既有 hash-derived originals 与 material lifecycle，delete/restore/purge 语义一致；不得在响应/日志中泄露原件路径或原始 secret；
- 真实 OCR/ASR 的 raw provider request/response 不持久化；只保留转写文本、置信度、operation 元数据和可验证来源；低置信/uncertain 标注不可被静默丢弃；
- 转写作为 material/revision 接入时，必须保留 source revision 和可验证 citation，先是 draft/建议，不静默覆盖用户编辑、confirmed artifact、attempt 或 review；
- ParentReport 只读聚合、强制脱敏；答案 key、提交原文、Q&A 原文、原文正文、路径、raw provider response 绝不能越过报告安全边界；
- 对外交付默认关闭；启用需显式配置 + 显式授权 + 收件目标白名单；每次交付可审计（时间、目标、内容摘要、结果），失败可重试但不静默重发；不实现自动定时推送/提醒（无 scheduler/worker）；
- 所有新增 schema 必须走 migrations runner；不得运行时 CREATE TABLE；migration 连续、幂等、事务化并测试 rollback/history/user_version；
- backup/verify/restore/startup/read 不调用 provider、不重新 OCR/ASR、不重算并外发报告、不自动修复或提升 unavailable 状态；不在 restore/startup 触发任何真实外发；
- API/UI/日志不得泄露路径、SQL、traceback、原始异常、secret、provider raw response、answer key、原文全文或收件人隐私；
- 仍是单进程/单实例边界，不宣称多 worker、多实例共享 data_root 或实时断电恢复。

开始前必须：
1. 读取 AGENTS.md；
2. 完整读取 docs/PHASE_ROADMAP.md、STATUS.md、TODO.md、PROJECT_PROGRESS_REPORT.md、ai-learning-architecture.md、MIGRATIONS.md、BACKUP_RESTORE.md、CODE_TEST_GOVERNANCE.md，以及 docs/prompts/HISTORICAL_SCENARIO_REVIEW.md 中 S6/S7 的需求线索；
3. 审计 backend/app/migrations/runner.py、repository.py、main.py、backup.py、restore_acceptance.py，以及 Phase 8/9A/9B/9C tests 和 browser workspace；确认实际 schema version（v11）、材料/revision/chunk 摄取管线、provider registry 和交付/导出现状；
4. 找到实际事务边界、ID/时间/错误/分页/导出约定，以及现有 originals 存储与 lifecycle；
5. 在计划/报告中引用源码路径、函数名或测试名；不能用设计文档或历史项目能力替代实现证据；
6. 只修改当前子任务拥有的范围，不顺手实现下一个任务；发现契约冲突先停止并提交契约变更提案；
7. 若当前子任务涉及真实 OCR/ASR 或真实对外交付，先确认 9D-0 立项结论允许，且默认走 fake/loopback 与 dry-run，真实动作须显式 gate 并请人确认。

结束时必须报告：修改文件、新增/修改测试、focused 命令与结果、相关完整门禁结果、未验证边界（尤其真实 OCR/ASR 与真实外发）、准确状态措辞、后续阻塞项和是否需要独立 fix commit。
```
