# StudyBuddy Phase 8：卡片与练习开发总 Prompt

> 文档性质：Phase 8 执行期间的中间任务文件。
>
> 生命周期：Phase 8 完成并完成最终验收、文档吸收后，删除本目录；正式结论只保留在 `docs/STATUS.md`、`docs/TODO.md`、`docs/PHASE_ROADMAP.md`、`docs/PROJECT_PROGRESS_REPORT.md` 和必要的架构/决策文档中。
>
> 当前阶段：Phase 8
>
> 前置阶段：Phase 7 已完成，但仅在明确的 Mistral `mistral / mistral-embed / https://api.mistral.ai/v1` 精确配置范围内完成真实 embedding acceptance。该限制不得扩大解释为全局 real-pass。

## 一、任务目标

在现有 StudyBuddy 可信资料链路之上，正式实现卡片（Cards）和练习（Exercises）的最小可验收产品闭环：

```text
material / extraction
→ material revision
→ deterministic chunks
→ lexical/vector/hybrid retrieval
→ verified citations
→ AI draft card/exercise
→ user edit / review
→ explicit confirmation
→ review or attempt history
```

Phase 8 的核心不是“调用模型生成几段 JSON”，而是建立可追溯、可编辑、可确认、不可静默覆盖的学习产物生命周期。

必须遵守：

- `materials`、`extractions`、`text_spans` 是 source of truth，AI 产物不能覆盖它们；
- 所有 AI 生成的 card/exercise 默认必须是 `draft`；
- `ready` 只能由明确的用户确认或符合契约的 user-created 流程产生；
- AI 生成内容必须保留 source revision 和可验证 citation；
- citation 必须能回到现有 revision/chunk/span，并通过服务端验证；
- 用户编辑过或已确认的内容不得被重新生成静默覆盖；
- deleted、superseded、purged、stale source 必须有明确且可测试的行为；
- card review 和 exercise attempt 是追加历史，不得覆盖既有记录；
- answer key 不得出现在普通 exercise 列表响应；
- 简答题 AI grading 不能伪装成确定性正确，必须标记为待复核或不确定；
- 不引入后台 worker、外部队列、外部 vector database、多进程共享 `data_root` 或多用户部署；
- 不因为 Phase 8 需要而自动索引历史材料、自动 repair 数据或自动生成全部用户内容。

## 二、当前代码与治理上下文

仓库：`H:\studybuddy`。正式代码在 `backend/app/`，正式后端测试在 `backend/tests/`，长期文档在 `docs/`。

必须先阅读：

- `AGENTS.md`
- `docs/PHASE_ROADMAP.md`
- `docs/TODO.md`
- `docs/STATUS.md`
- `docs/PROJECT_PROGRESS_REPORT.md`
- `docs/ai-learning-architecture.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/MIGRATIONS.md`
- `docs/BACKUP_RESTORE.md`
- `docs/CODE_TEST_GOVERNANCE.md`
- 本目录下相关子任务 prompt

现有能力基线：

- 文件导入、材料生命周期、搜索、分页、原文件/正文/ZIP 导出已实现并有局部 real-pass 证据；
- migration runner 当前 schema version 为 v6，新的业务表必须通过连续 migration 增加，预计 Phase 8 使用 v7，具体版本以代码审计为准；
- revision/chunk/indexing/retrieval/citation/Q&A 已实现；
- lexical、vector、hybrid retrieval 和 fallback 已有明确 policy、run/hit metadata 和 source filtering；
- fake LLM provider、OpenAI-compatible LLM adapter、provider capabilities、Q&A operation metadata 已实现；
- embedding provider、fake embedding、SQLite payload、显式 indexing、vector/hybrid retrieval 已实现，但真实 provider evidence 仅限精确 Mistral 配置；
- backup/restore 使用 SQLite Online Backup API，不能自动 rebuild、repair 或重新生成 AI 产物；
- 前端是现有 FastAPI 内嵌单页，已有材料、Q&A、citation 定位、loading/error/retry、响应式和基础可访问性约定；
- 系统边界是单用户、单进程、单实例、本地 SQLite 与本地 storage。

## 三、Phase 8 交付范围

### A. Cards

至少实现：

- deck 的创建、列表、详情、归档或安全删除边界；
- card 的创建、列表、详情、编辑、确认、状态展示；
- AI card payload 的严格 schema 校验；
- question/front、answer/back、可选 explanation、tags 或 metadata 的明确字段契约；
- `draft`、`ready`、`rejected`、`stale`、`archived` 等状态的合法流转；
- card 与 source revision 的绑定；
- 独立 `card_citations`，至少保存 citation key、material/revision/chunk/span 定位、quote、status；
- 用户编辑保护：编辑后重新生成必须创建新 draft 或明确拒绝覆盖；
- 用户确认后的 ready card 不得被重新生成直接替换；
- source deleted/purged/stale 后 card 保留历史，但 citation/source 状态必须安全表达；
- review 记录追加写入，不能修改历史 review。

### B. Exercises

至少实现：

- exercise set 的创建、列表、详情、状态展示；
- exercise 类型至少支持 `multiple_choice`、`true_false`、`short_answer`；
- 严格 schema 校验：题干、选项、正确答案、解释、题型必须符合类型契约；
- `draft` → 用户确认 → `ready` 的生命周期；
- 独立 `exercise_citations`，保存并验证 source 定位；
- `exercise_attempts` 追加式记录作答、评分、时间和 grading 状态；
- multiple choice / true false 使用 deterministic grading；
- short answer 只允许 `pending_review`、`needs_review` 或等价明确状态，不得将 AI 判断宣称为 deterministic truth；
- 普通列表和非授权详情不得返回 answer key；
- 用户编辑、确认、再次生成、source lifecycle 和历史 attempt 不变量均需测试。

### C. Generation

AI 生成不是独立于现有 RAG 的捷径，必须复用：

- 显式 retrieval policy；
- context assembly；
- citation candidate 和 server-side citation validation；
- provider/operation metadata；
- input fingerprint、source revision、model/provider metadata；
- 安全错误映射和 provider 未配置行为。

生成失败时：

- 保留安全的 operation failure 状态和稳定 error code；
- 不创建半成品 ready artifact；
- 可重试时只能创建新 draft 或在明确安全边界内重试；
- 不保存 provider 原始响应、secret、路径、SQL、traceback 或原始异常文本。

## 四、推荐执行顺序

```text
8.1 领域契约与 schema
→ 8.2 Cards repository/API/lifecycle
→ 8.3 Exercises repository/API/grading
→ 8.4 AI draft generation integration
→ 8.5 UI 工作区与浏览器路径
→ 8.6 backup/restore、完整回归与文档收口
```

一次只完成一个可验收闭环。每个子任务完成后必须有代码、测试、失败边界和文档状态，不得只提交设计或占位接口。

## 五、统一数据与状态原则

### Source binding

每个 AI 产物必须绑定生成时的 `source_revision`。citation 不是自由文本标签，必须能解析并映射到当前或历史的 material/revision/chunk/span。无法验证的 citation：

- 不能让 artifact 进入 `ready`；
- 必须使用稳定错误码，例如 `citation_invalid` 或 `invalid_card_payload` / `invalid_exercise_schema`；
- 不得伪造可点击来源。

### Lifecycle

建议以显式状态机实现，并在 repository 层拒绝非法跃迁。至少覆盖：

```text
card: draft → ready | rejected | stale | archived
exercise: draft → ready | rejected | stale | archived
```

用户编辑后的 draft、已确认 ready、已完成 review/attempt 的历史都不能被生成接口静默覆盖。source stale/unavailable 是来源状态，不等于删除用户 artifact；是否允许 review/attempt 必须明确并测试。

### User-created 内容

允许显式 user-created/no-source 内容，但必须与 AI-generated 内容区分。不能为了通过 schema 而给 user-created 内容伪造 citation；普通 UI/API 必须显示无来源状态。

## 六、统一安全与隐私边界

- API 不返回 `stored_path`、服务器路径、SQL、异常原文、provider raw response 或 secret；
- 列表响应只返回必要 metadata，不返回 answer key、完整 source text 或不必要的 quote；
- citation quote 采用有界长度；详情返回也必须遵守现有隐私边界；
- 前端动态文本使用安全 DOM 文本节点，不拼接不可信 HTML；
- 输入长度、card/exercise 数量、选项数量、JSON 深度和 payload 大小必须有限制；
- malformed JSON、非法 ID、非法状态、错误 content type、重复点击、过期请求和网络失败都必须安全处理；
- 错误信息使用稳定中文提示或稳定错误码，不显示 backend detail。

## 七、必须覆盖的测试矩阵

### Backend

- migration：v6 → Phase 8、重复执行、事务 rollback、schema/history/version 一致；
- CRUD：deck/card/set/exercise 的合法和非法输入；
- state machine：draft/ready/rejected/stale/archived 合法和非法流转；
- citation：valid、invalid、source deleted、source purged、superseded/stale、越界 quote；
- edit protection：user-edited/confirmed card 或 exercise 不被 regenerate 覆盖；
- grading：multiple choice、true false deterministic；short answer pending review；
- answer-key privacy：列表、详情、错误响应、attempt 响应；
- attempts/reviews：追加、不覆盖、排序和重启后恢复；
- provider：not configured、fake、timeout、malformed/schema mismatch、safe failure；
- transaction：生成失败、确认失败、attempt 写入失败时 rollback；
- lifecycle：material delete/restore/purge、revision supersede、backup/restore；
- API boundaries：method/content-type/ID/status/pagination/body size。

### Browser

至少覆盖一条 fake provider 的完整可重复路径：

```text
导入材料 → 显式 indexing → 生成 card/exercise draft → 查看 citation
→ 编辑 → 保存 → 确认 → review/attempt → 刷新/重启恢复
```

并覆盖：

- 未配置 provider；
- invalid generation payload / citation failure；
- source deleted/purged；
- duplicate click、stale response、网络/500 失败后 retry；
- answer key 不泄露；
- 窄屏、键盘焦点、status/alert 和安全文本渲染。

### Operator / restore

- backup 后恢复到新空目录；
- card/exercise draft、ready、review、attempt、stale citation 和 operation metadata 均保留；
- restore/verify 不自动生成、不自动 repair、不升级 stale 为 ready；
- 完整 backend regression 必须使用项目 Python 环境执行。

## 八、完成门槛

Phase 8 只有在以下条件同时满足后才能标记 completed：

1. 新 schema 通过 migration，且有升级/rollback/backup/restore 证据；
2. Cards 和 Exercises 均有正式 repository、API 和生命周期实现；
3. AI 生成默认 draft，citation 可验证，用户编辑/确认状态受到保护；
4. deterministic grading 和 attempt/review 历史通过测试；
5. answer key 隐私边界通过 API 和浏览器测试；
6. fake provider 下完整真实浏览器用户路径通过；
7. 失败、删除、恢复、purge、stale/source unavailable、重启恢复边界通过；
8. `STATUS.md`、`TODO.md`、`PHASE_ROADMAP.md`、`PROJECT_PROGRESS_REPORT.md` 和必要决策/架构文档同步；
9. 完整 backend suite 和相关 Chromium suite 通过；
10. 限制被诚实记录：不宣称后台 worker、多进程、全局 real-pass、所有 provider 或生产规模支持。

## 九、禁止事项

- 不得运行时 `CREATE TABLE IF NOT EXISTS` 创建 Phase 8 业务表；
- 不得从历史项目复制 cards/exercises 实现到正式系统；
- 不得把 schema 预留字段、fake provider 测试或设计文档写成真实 provider/product real-pass；
- 不得让 AI 生成直接写入 ready；
- 不得重新生成覆盖 user-edited、confirmed、reviewed 或 attempted 内容；
- 不得把 answer key 放进普通列表；
- 不得为 source unavailable 的 citation 伪造名称、正文或定位；
- 不得新增隐式后台任务、自动索引或外部服务依赖；
- 不得删除失败数据库、备份或诊断材料来掩盖失败。

## 十、最终报告要求

完成时报告：

- 实际变更文件和 migration version；
- cards/exercises 的实际状态机和 API；
- citation/source lifecycle 行为；
- grading 与 review/attempt 语义；
- focused/backend/browser/restore 命令及结果；
- real-pass、implemented、not_verified 的精确范围；
- 未完成项目和下一阶段建议。

本 prompt 是执行上下文，不是完成证据。Phase 8 完成后必须删除本目录，并将正式结论吸收到权威文档。
