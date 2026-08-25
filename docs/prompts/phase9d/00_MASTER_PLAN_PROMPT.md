# Phase 9D 总体规划 Prompt

```text
请为 H:\\studybuddy 规划 Phase 9D“扩展学习服务（S6 家长观察 / S7 课堂采集，条件性范围）”，先不要修改文件，不实现业务代码。

Phase 9D 是条件性阶段。除了常规审计与契约规划，必须先给出明确的立项（go / no-go）结论：只有在需求真实、隐私边界清晰、数据保留策略明确、真实 OCR/ASR/交付组件有可验证证据、运维成本可承受时才立项。若任一条件不满足，允许并鼓励给出“暂不立项”或“仅立项其中一个子系统”的结论，而不是强行铺开。

先完整审计当前正式源码和权威文档，并为每个结论引用源码路径、函数名或测试名。重点确认：当前 schema/migration version（v11）；materials/extractions/text_spans 与 hash-derived originals 存储和 delete/restore/purge lifecycle；material_revisions/chunks/chunk_spans 摄取与 retrieval/citation 管线；provider registry、ai_operations、fake provider、幂等和安全错误；9A/9B/9C 已有的计划、进度、练习、错题、薄弱点等可聚合派生事实；现有导出、backup/verify/restore/restore_acceptance、错误映射和前端 workspace。不要把历史 s6/s7、ocr-tools、report/delivery 工具或旧项目能力当成已实现证据。

Phase 9D 目标（在立项通过的前提下）：
1. S7 ClassCapture 课堂采集：用户上传课堂录音/图片作为敏感原件，纳入既有 originals 与 material lifecycle；通过 OCR/ASR 产出带置信度、可追溯的转写文本；低置信/uncertain 内容要求用户核对；转写作为 S2 资料来源接入既有 material/revision/chunk 管线，先是 draft，不静默覆盖用户编辑或 confirmed artifact；默认使用 deterministic fake/loopback OCR/ASR，真实 provider 以显式 gate 管理。
2. S6 ParentReport 家长观察：基于 9A/9B/9C 已有派生事实生成只读、强制脱敏的日报/周报/月报/考前提醒聚合；报告不改写学习事实；提供本地生成、预览和导出；对外交付（邮件/飞书）默认关闭，启用需显式配置 + 显式授权 + 收件白名单 + 可审计 dry-run，且不实现自动定时推送。

请先冻结以下决策，不能留给实现者猜测：
- 9D 立项结论与范围裁剪：S6/S7 是否都做、做到哪个层次、哪些明确不做、依赖与运维成本；
- S7 采集会话 owner/scope/status、原件类型与大小边界、与 originals/material/revision 的关系、转写 operation/置信度/uncertain 语义、真实 OCR/ASR 是否排除或以何 gate 接入、raw response 不持久化边界、失败/低置信/超时处理；
- 转写接入 S2 的方式：新建 material 还是新 revision、citation/source 校验、draft → confirm、用户编辑保护；
- S6 报告对象 owner/scope、报告类型（日/周/月/考前）、聚合数据源与派生规则、脱敏白名单与黑名单、快照还是动态、报告状态机；
- 对外交付渠道抽象、配置与 secret 存放（不入库、不入日志、不入 backup 明文）、授权与收件白名单、dry-run vs 真实发送、审计记录、重试与去重、默认关闭与显式开关；真实发送是否排除；
- 是否新增表、哪些事实 append-only、哪些是可重算 projection、SQLite constraint 与 domain transaction 的分工；
- API/status/error/privacy/export、source lifecycle、backup/restore non-repair（不重新 OCR/ASR、不重算外发、不在 restore/startup 触发交付）和测试 artifact 规则；
- S6/S7 与 Phase 10 worker/scheduler、真实 Provider、多用户、云同步的明确依赖和 non-goals。

将 Phase 9D 拆成以下可独立提交、独立验收的任务，并可在必要时指出调整理由：
9D-0 立项评审、现状审计与范围冻结（含 go/no-go）；9D-1 正式领域契约与状态机；9D-2 migration/schema；9D-3 repository/domain transaction；9D-4 S7 课堂采集与 OCR/ASR 转写；9D-5 S7 转写接入 S2 资料管线；9D-6 S6 家长报告聚合与脱敏；9D-7 S6 对外交付（默认关闭 + dry-run + 授权 + 审计）；9D-8 API；9D-9 Chromium workspace；9D-10 source lifecycle 与 backup/restore；9D-11 全量验收、证据和文档收口。

每个任务必须给出：目标、明确不做、前置依赖、允许修改的文件范围、测试范围、失败/隐私/交付安全边界、验收标准、独立提交性、阻塞关系、推荐 commit 和准确状态措辞。给出 Gate A-L、推荐执行顺序、出现契约冲突或立项条件不满足时的停工规则和完成声明。

必须坚持：
- 9D 是条件性阶段，立项条件不满足就明确暂不立项，不用历史存在证明现状能力；
- migration runner 是唯一 schema 入口；
- 采集原件纳入既有 originals/material lifecycle；转写保留置信度和可验证来源；raw OCR/ASR/交付 response 不持久化；
- 报告只读、强制脱敏；答案 key、提交原文、Q&A 原文、原文全文、路径、收件人隐私不能越过安全边界；
- 对外交付默认关闭、需显式授权与白名单、可审计、失败可控、不静默重发、不自动定时推送；
- AI/OCR/ASR 输出先 draft/建议，citation 经服务端复验，绝不覆盖用户状态；
- 不引入 scheduler/worker、多用户、云同步、外部 vector DB；不把真实 OCR/ASR 或真实交付的 opt-in 结果当通用 real-pass；
- 不把 prompt、fake/loopback、局部 backend/browser pass 当 Phase 9D completed；
- 完成声明必须限定在 deterministic fake/loopback / local single-process / SQLite / Chromium / backup-restore / dry-run 交付实际通过的范围。

输出中文规划，目标是可直接转成 docs/prompts/phase9d/ prompt 包、TODO、migration、测试和逐 commit 执行计划；只做规划，不改文件。
```
