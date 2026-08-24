# Phase 9B 总规划 Prompt

```text
请为 StudyBuddy 规划 Phase 9B“资料学习工作流 S1/S2”，不要修改任何文件，不实现业务代码。

先完整审计当前正式源码和权威文档，尤其确认：当前 schema/migration version；Phase 9A goals、knowledge modules、study plans/items、dependencies、progress、source links 的实际 schema/repository/API/UI；Phase 8 Cards/Exercises 的 citation/source lifecycle；materials → revision → chunk → retrieval → citation 链；现有 Q&A、provider、ai_operations、导出和 backup/restore contract；main.py 前端 workspace；现有测试 fixture、browser gate 和错误响应约定。所有结论必须引用源码路径、函数或测试名称，不能把历史版本设计当成实现证据。

Phase 9B 目标是形成两条可验收的正式用户路径：
1. S1 学习节奏：在 Phase 9A 计划核心上显式设置节奏目标、学习时段/工作量、计划 item 分配和节奏视图/summary；不做提醒、推送、后台 scheduler、自动执行或自动重排。
2. S2 资料笔记：用户围绕已导入资料创建、编辑和组织笔记/知识模块；可通过已验证 revision/chunk/retrieval/context/citation 路径生成 citation-safe 的 fake-provider draft；用户必须显式编辑、确认或拒绝；不复制历史 KnowledgeModule 实现，不把 AI 输出直接视为事实。

请先提出并冻结边界决策，至少包括：
- S1 的节奏模型是按日、周还是可配置周期；日期、timezone、截止日期和跨日行为；工作量单位及上限；plan item 如何分配、移动、跳过、完成和重新打开；是否允许无节奏 item；summary 如何从 append-only progress 和节奏数据重算；
- S2 的 note、note block、knowledge module、source link、citation 的关系；用户笔记与 AI draft 的来源和编辑保护；笔记是否允许无 source；一个笔记/模块可否关联多个 revision/material；source citation 绑定 note 还是 block；如何处理 stale、deleted、purged、unavailable；是否允许 active 模块缺失来源但显示 warning；
- S1/S2 是否复用 9A 表还是增加新表；哪些约束由 SQLite 表达、哪些必须由 repository/domain transaction 表达；project scope 和未来 user boundary；
- fake-provider generation 的 operation type、idempotency、retry、失败后残留、结构化输出校验、prompt/provider raw data 的持久化边界；真实 Provider generation 是否明确排除；
- 导出格式和隐私边界；backup/restore、startup/read/verify 是否严格 non-repair；
- 9B 与 9C、9D、Phase 10 的依赖和 non-goals。

请将 Phase 9B 拆成独立、可单独提交和验收的子任务，至少覆盖：
9B-0 现状审计与范围冻结；9B-1 正式领域契约与状态机；9B-2 migration/schema；9B-3 repository/domain transaction；9B-4 S2 资料笔记与知识模块工作流；9B-5 S1 学习节奏工作流；9B-6 API contract；9B-7 最小 Chromium workspace；9B-8 source lifecycle 与 backup/restore；9B-9 全量验收、证据和文档收口。

每个子任务必须给出：目标、明确不做、前置依赖、允许修改的源码范围、测试范围、失败和隐私边界、验收标准、独立提交性、阻塞关系、准确状态措辞。给出推荐执行顺序、Gate A-H 或等价 gate、每个 gate 的通过条件和不可宣称事项。

计划必须坚持：
- 所有 schema 变化进入 migrations runner；
- source of truth 仍是 materials/extractions/text_spans，AI/notes/knowledge modules 是可追溯派生或用户状态；
- AI 内容先 draft，保留 source revision/citation，不能覆盖用户编辑或 confirmed 状态；
- 不引入后台任务、scheduler、多用户、云同步、OCR/ASR、S3/S4/S5、S6/S7；
- 不把 prompt、设计、fake-provider 或局部 browser pass 当成 Phase 9B completed；
- Phase 9B 完成声明只能限定在实际通过的 fake-provider / local single-process / SQLite / Chromium / backup-restore 范围。

输出一份中文规划，可直接转化为 docs/phase9b/ 下的 prompt 包、TODO、migration、测试和逐 commit 实施计划。输出只做规划，不修改文件。
```