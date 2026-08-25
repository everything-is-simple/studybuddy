# Phase 9C 总体规划 Prompt

```text
请为 H:\\studybuddy 规划 Phase 9C“练习与反馈工作流（S3/S4/S5）”，先不要修改文件，不实现业务代码。

先完整审计当前正式源码和权威文档，并为每个结论引用源码路径、函数名或测试名。重点确认：当前 schema/migration version；Phase 8 exercise/card 表、状态、attempt、grading、citation/source lifecycle、generation/ai_operations、隐私响应；Phase 9A plan/module/progress；Phase 9B note/rhythm；现有 FastAPI 路由、前端 workspace、backup/verify/restore、测试 fixture 和错误约定。不要把历史场景文档或旧项目能力当成已实现证据。

Phase 9C 目标：
1. S3 PracticeRunner：用户显式创建限时练习 session，选择已 confirmed/ready 的练习，服务端控制 session 生命周期和截止边界，逐题提交，复用 deterministic grading，产出安全结果和可引用解析；不做后台计时器或自动排程。
2. S4 ErrorFixer：从真实 append-only attempts、deterministic grading、pending_review/reviewed 事实形成错题投影；支持错因/反馈、重做、人工复核、状态变化和历史不可覆盖；不把“错误”直接等同于 AI 猜测。
3. S5 ExamCrammer：用户显式建立冲刺目标/模拟 session，选择范围和练习，复用 S3 session、S4 反馈和 Phase 9A plan/module；形成结果、薄弱点和建议，但不自动改写计划或产生提醒。

请先冻结以下决策，不能留给实现者猜测：
- session 的 owner/scope/status、server-authoritative start/deadline/submit、时区/日期、暂停/恢复/刷新/超时/重复提交语义；
- 练习选择快照还是动态查询，exercise/card 状态和 source/citation 条件；
- attempt 与 session 的关系、重做如何生成新 attempt、MC/TF/short_answer 的评分/人工复核和安全 feedback；
- mistake 的定义、生命周期、重复归并键、用户编辑/override、weak point 的派生规则和是否保存 snapshot；
- S5 cram target、exam/session、选题/范围、结果和 S3/S4 依赖；
- 是否新增表、哪些事实 append-only、哪些是可重算 projection；SQLite constraint 与 domain transaction 的分工；
- AI 生成题目/解析/反馈/变题的 operation、draft、citation、idempotency、retry、raw prompt/response 不持久化边界；真实 Provider 是否排除；
- API/status/error/privacy/export、source lifecycle、backup/restore non-repair 和测试 artifact 规则；
- S3/S4/S5 与 Phase 10 worker、真实 Provider、9D 的明确依赖和 non-goals。

将 Phase 9C 拆成以下可独立提交、独立验收的任务，并可在必要时指出调整理由：
9C-0 审计与范围冻结；9C-1 正式领域契约与状态机；9C-2 migration/schema；9C-3 repository/domain transaction；9C-4 S3 限时练习；9C-5 S4 错题改错与人工复核；9C-6 S5 期末冲刺；9C-7 API；9C-8 Chromium workspace；9C-9 source lifecycle 与 backup/restore；9C-10 全量验收、证据和文档收口。

每个任务必须给出：目标、明确不做、前置依赖、允许修改的文件范围、测试范围、失败/隐私边界、验收标准、独立提交性、阻塞关系、推荐 commit 和准确状态措辞。给出 Gate A-J、推荐执行顺序、出现契约冲突时的停工规则和完成声明。

必须坚持：
- migration runner 是唯一 schema 入口；
- attempt/review/progress 历史 append-only；projection 可重算且不伪造事实；
- answer key、提交原文、provider raw response 和 source 全文不能越过安全边界；
- AI 输出先 draft/建议，citation 经服务端复验，绝不覆盖用户状态；
- 不引入 scheduler/worker、多用户、云同步、OCR/ASR、外部 vector DB 或 S6/S7；
- 不把 prompt、fake-provider、局部 backend/browser pass 当 Phase 9C completed；
- 完成声明必须限定在 deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore 实际通过的范围。

输出中文规划，目标是可直接转成 docs/prompts/phase9c/ prompt 包、TODO、migration、测试和逐 commit 执行计划；只做规划，不改文件。
```