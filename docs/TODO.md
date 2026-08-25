# StudyBuddy TODO 清单

> 更新：2026-08-30（Phase 9D-5 S7→S2 ingestion backend gate 复核后）
> 当前基线：本地单进程文件材料管理基础系统已可用，正式 schema 为 v12，完整 backend 为 **341 passed, 2 skipped**；整体阶段性完成度约 **55%–60%**。Phase 9D 已部分立项并推进至 9D-5，完整状态见 [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)。
>
> 执行原则：一次只推进一个可验收闭环；每项完成必须有代码、测试、文档和可复现证据。`implemented` 不等于 `real-pass`，后者要求真实用户路径验收。

## 已完成（不再作为待办）

- [x] I1：migration runner、schema version、migration history、原子升级/rollback、v1→v2 升级、backup/restore 版本一致性、operator upgrade runbook。
- [x] I2：backup、verify-backup、restore staging、恢复后 offline/online 验收、保留/轮换策略文档、restore drill 模板、integrity/manifest 失败隔离流程。
- [x] 文件材料管理 v1：导入、批量/文件夹导入、列表、搜索、分页、生命周期、回收站、导出及主要 Chromium 验收。

## 基础设施收尾已完成（v1 时间盒收口）

### P0-I3：最小可观察性与运行边界（必须）

- [x] 定义并实现结构化安全日志：event、level、timestamp、stable error code、request/operation ID。
- [x] 禁止日志、API/UI 输出正文、路径、secret、SQL、原始异常和 traceback。
- [x] HTTP request ID；导入和未来 AI operation ID 的贯通。
- [x] 最小 metrics：请求量、导入成功/失败、耗时、SQLite/recovery/backup 事件。
- [x] 定义 liveness/readiness/degraded 语义与 operator 可见输出。
- [x] 补 startup、audit、recovery、backup/restore 失败的稳定性/脱敏测试。

**状态：已完成（implemented）。** Metrics 是低基数、进程内、重启后归零的 operator snapshot；operation ID 当前仅用于 request-scoped 日志关联，不是持久化 AI operation。

**完成标准：** 失败导入、启动预检失败、backup verify 失败可由稳定 error code/ID 定位，且不泄露敏感内容。

### P0-I4：真实环境与容量基线（时间盒验收完成）

- [x] Windows ACL/只读目录真实拒绝测试（`not_verified`，已作为 v1 运行边界接受，不再阻塞）。
- [x] 受控磁盘空间不足或等效配额测试（`not_verified`，已作为 v1 运行边界接受，不再阻塞）。
- [x] 批量导入、搜索、导出容量和耗时基线（合成 TXT，S0–S3）。
- [x] 有时间上限的生命周期 smoke（40 cycles，无失败）。
- [x] 固化单进程、单实例、local disk 限制；明确禁止多 worker/shared `data_root`。
- [x] 记录可复现命令、环境、结果与未验证边界：`H:\studybuddy-test\scripts\i4_baseline.py`。

证据：`H:\studybuddy-test\artifacts\infrastructure-i4\latest.json` 和 `latest.md`（最近一次基线已重新运行并更新）。当前 backend 全测：`341 passed, 2 skipped`；2 个 skip 为默认关闭的真实 Provider smoke。

**状态：时间盒验收完成（v1）。** S0–S3 和 40-cycle smoke 为 real；ACL、资源耗尽、S4、peak memory、断电/网络盘/硬件损坏为 `not_verified`，并已明确记入 v1 运行边界。

## Phase 4：AI 最小闭环（已完成）

目标：用户选择已导入材料提问，系统以可追溯的检索和验证引用回答。deterministic fake provider 下的完整 Q&A 用户闭环、history、多材料范围、citation 导航、浏览器验收和文档证据均已完成。Phase 5 adapter、精确 Provider smoke 和 Phase 6 P6-A–P6-E fake/default/UI 产品化验收已按对应 evidence 收口；DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 的 P6-E 精确真实 UI gate 也已通过。当前 Phase 7 已在 Mistral `mistral` / `mistral-embed` / `https://api.mistral.ai/v1` 精确配置范围完成；其它 provider/model 的独立验证不阻塞后续 Phase 8。

### 顺序与任务

```text
revision → chunks → retrieval → citations → Q&A
```

- [x] 确定 MVP 用户流程：选择材料 → 提问 → 检索 → 回答 → 查看引用。
- [x] 实现 `material_revisions` 的创建、current/superseded 生命周期；stale 语义留给后续重解析链路。
- [x] 实现 deterministic chunker、Unicode code-point offsets、显式 indexing；现有 text_spans 通过按序文本匹配建立安全 page/slide/document 映射。
- [x] 实现 `chunks` / `chunk_spans` 持久化和 `chunks_search` FTS5 同步；连接时只清理/补齐已有 ready chunks，不自动创建 chunk。
- [x] 实现 lexical retrieval：active/current/ready 过滤、ASCII AND 查询、Unicode substring fallback、top-k、稳定排序、`retrieval_empty`。
- [x] 持久化 `retrieval_runs` / `retrieval_hits`；lexical 阶段不写 provider、embedding 或 rerank 数据。
- [x] 实现 context assembler：token budget 截断、active/current/ready 过滤、dedup、citation key 生成（`ctx-{mid8}-{cid8}`）。
- [x] 实现 citation key 验证：`valid` / `invalid_format` / `source_deleted` / `source_purged` 四态。
- [x] 实现 Provider Protocol、registry、deterministic fake provider、`provider_not_configured` 和 `GET /api/ai/capabilities`。
- [x] 实现 `ai_operations`、Q&A thread/message/answer/citation repository 和同步 `POST /api/qa/ask`。
- [x] 实现最小 Q&A UI：显式 indexing、loading/error/retry、citation 展示与当前材料正文定位。
- [x] 实现 purge 后历史 citation `source_unavailable` 生命周期、Q&A browser E2E 与 AI 表 backup/restore 专项验收。

**当前进度：** revision/chunk 显式 indexing、chunk lexical retrieval、context assembler、citation contract、deterministic fake provider、Q&A API/persistence、Q&A history、多材料 scope、citation 详情/跨材料导航、统一状态、toast/retry、响应式/基础可访问性和完整 Chromium E2E 均已实现并验证。Phase 4 已完成，Phase 5 adapter 已实现，下一阶段性验收为真实 Provider smoke。

**Phase 4 完成标准：** fake provider 下完成导入 → indexing → 检索 → 问答 → citation → 原文定位；展示 citation 可追溯到 material/revision/chunk/span；deleted/stale 被排除；purge 后历史 citation 正确显示 unavailable；未配置 provider 时应用照常启动并安全失败；失败、重复点击和过期响应不破坏 UI；backend tests、Chromium E2E、文档和验收证据全部同步。

## Phase 4 收尾任务（已完成）

- [x] 完整 Q&A 对话历史浏览 UI
- [x] 多材料范围选择与状态同步
- [x] citation 详情、跨材料切换与原文定位
- [x] 统一 loading / empty / error / success / retry 状态
- [x] toast 通知与可重复执行的 retry interaction
- [x] 响应式布局、键盘操作与基础可访问性
- [x] 完整 Chromium E2E：导入 → indexing → 检索 → 问答 → citation → 定位

## Phase 5：真实 Provider 接入

- [x] 通用 OpenAI-compatible LLM adapter、环境配置、timeout/output limit；Embedding provider 属于后续 Phase 7。
- [x] provider timeout/rate-limit/auth/quota/refusal/malformed response 稳定错误映射。
- [x] capabilities endpoint、usage/latency/provider request metadata，禁止 secret 泄露。
- [x] 同步 Q&A stale transition：每个 Q&A 请求会事务性回收同 project 中超过 5 分钟 lease 的 `running` operation，标记 `stale/qa_operation_stale` 并保留审计消息；同一 Idempotency-Key 可随后创建新 operation。未实现后台扫描、cancel、跨进程协调或真实断电恢复。
- [x] DeepSeek 官方 `deepseek-chat` 真实网络 smoke：adapter-level、完整 API-level synthetic Q&A 和 Chromium UI/E2E 均已通过；Agnes `agnes-2.5-flash` 也已通过精确 adapter/API/UI smoke；其它 Provider/model 仍待独立验收。
- [ ] ARK、硅基流动、Sub2API 及其它 Agnes profiles 逐个完成脱敏 capability matrix 和真实验收（API/UI smoke 强制 target 与 runtime provider 一致；通用三次 API acceptance runner 已实现，每次使用独立临时 data root，`2/3` 仅为 API evidence；Agnes `advanced`/`agnes-2.5-flash` 已通过独立 adapter/API/UI smoke；`pro`/`agnes-2.5-pro` API smoke 返回 `provider_unavailable`，UI 未运行，仍待独立验证）。

**Phase 5 当前状态：** adapter、配置隔离、HTTPS/loopback URL 边界、响应体读取上限、稳定错误映射、timeout/output limit/retry、mock HTTP 测试、provider request/usage/latency metadata、citation 缺失/伪造拒绝、secret redaction、真实 Provider failure UX、retry、重复点击、安全渲染、显式 Idempotency-Key 幂等和请求触发的 stale recovery 已实现并验证。DeepSeek 官方 `deepseek-chat` 与 Agnes `advanced`/`agnes-2.5-flash` 的 adapter/API/UI smoke 均有精确 evidence；ARK、硅基流动、其它 Agnes profiles、Sub2API 仍待独立验证。P6-E 真实 UI path 已在本轮以显式 gate 分别通过；不得将该精确 evidence 扩大解释为所有 Provider/model 的可用性。

## Phase 6：AI MVP 产品化与整体验收

### P6-A：Provider 运行契约和状态可见性

- [x] 明确默认运行状态为 `not_configured`；`fake` 仅在显式环境配置时启用，并在 UI 标记为 deterministic/demo。
- [x] `GET /api/ai/capabilities` 区分 `not_configured`、`invalid_config`、`demo`、`configured`，并以 `verification_status` 区分 generic adapter 的 `unverified`。
- [x] UI 展示 Provider/model、安全配置来源和 demo/unverified/not-configured 语义；不展示 key、Authorization、敏感 URL、raw response、路径或 traceback。
- [x] P6-A 后端状态、错误边界、脱敏和 Chromium UI 测试通过；本任务未执行网络探测，不新增真实 Provider evidence。

**P6-A 限制：** capabilities 是本进程配置快照，不是网络 health probe；generic adapter 的 `configured` 不等于 `available` 或 `verified`。DeepSeek `deepseek-chat`、Agnes `agnes-2.5-flash` 的真实证据仍只按 capability matrix 中的精确 provider/model/gateway 范围解释。

- [x] P6-E fake Provider 核心工作流整体验收：`backend/tests/browser_p6e.spec.js`，4 passed。
- [x] P6-E empty retrieval、未配置 Provider、timeout/retry、duplicate click、stale thread、deleted source/export safety 和相关 failure contract。
- [x] P6-E 默认 skip 的 DeepSeek/Agnes real UI gate：精确 target/model/provider 匹配和脱敏 evidence 结构已实现；本轮 DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 已分别真实网络通过。
### P6-B：Q&A Thread 工作区

- [x] thread 列表、标题、更新时间、消息数和 active/empty/failed 状态展示。
- [x] 新建对话、切换 thread、继续提问、用户/assistant/citation 时间线和 source unavailable 展示。
- [x] 当前材料与跨材料 scope 选择保持可见；thread scope 仍是请求级/客户端级状态，不作为持久化 thread scope 声明。
- [x] 请求绑定 thread/scope/UI context；切换 thread、scope 或新建对话后忽略过期响应；显式 Idempotency-Key 保留现有同步 replay/conflict 语义。
- [x] 刷新后通过非敏感 thread ID 尝试恢复服务端 history；恢复失败回到明确状态，不从本地恢复回答或正文。
- [x] Q&A thread 工作区、长回答时间线、键盘焦点、状态语义和窄屏 Chromium 验收通过。

**P6-B 限制：** Q&A 仍是同步请求；切换页面或 thread 只能忽略旧响应，不能真正取消已经发出的 Provider HTTP 请求。没有后台 worker、流式输出、跨进程协调或持久化 thread scope。

### P6-C：跨材料浏览和引用/导出衔接

- [x] 材料列表/详情进入 Q&A，保持单材料或多材料 scope 上下文。
- [x] Q&A scope 显示材料名称、跨分页保留的非敏感材料 ID 和当前列表不可见状态。
- [x] citation detail 返回安全的 material/revision/chunk/span 定位信息；有效 citation 可定位正文，deleted/purged/stale source 显示 unavailable。
- [x] 从 citation/材料详情返回 Q&A，URL/history 保留 material、thread、scope、citation 标识；刷新只重新请求服务端状态。
- [x] 从 citation 关联材料详情导出正文和原文件；复用现有安全下载、文件名和 deleted/missing 错误 contract。
- [x] P6-C API、citation lifecycle、材料 export、Q&A Chromium、材料管理 Chromium 验收通过。

**P6-C 限制：** 不持久化 thread scope；purge 后不能恢复已删除材料名称或正文；同步 Provider 请求仍不能真正取消；未新增批量文件夹导出、导出队列或后台任务。

**P6-D 限制：** 使用 Playwright/DOM contract 断言而非 axe；系统级 screen reader、真实 Provider 下完整体验、真实离线/极端长回答和长时整批 Chromium 单次稳定性仍为 `not_verified`。页面 toast 只是补充，主要错误已同步到页面 status/alert；同步 Provider 请求不能真正取消，只能丢弃 stale response。

- [x] P6-E 导入 → ready → indexing → retrieval → thread → Q&A → citation → 定位 → 返回 → 导出 → refresh/history 核心工作流整体验收；证据：`docs/prompts/P6E_ACCEPTANCE_EVIDENCE.md`。
- [x] P6-D 统一应用级导航、当前 material/thread/scope 状态、页面 status/alert 和补充 toast。
- [x] P6-D 桌面/390x844 窄屏布局、键盘视图切换、可见焦点、dialog Escape/focus return 和关键 ARIA/current/status/alert 语义。
- [x] P6-D fake Provider Chromium 专项验收：`backend/tests/browser_p6d.spec.js`，2 passed；未引入 API 或 migration，未引入 axe。
- [x] P6-E fake Provider 核心工作流、empty retrieval、source lifecycle、retry、duplicate click、stale response、refresh/history、导出失败和窄屏路径验收。
- [x] P6-E Provider failure UX 回归：timeout、network failure、rate limit、unavailable、malformed/safe error contract；详见 `docs/prompts/P6E_ACCEPTANCE_EVIDENCE.md`。
- [x] DeepSeek `deepseek-chat` 和 Agnes `agnes-ai-hub` / `agnes-2.5-flash` 的 P6-E 真实 UI 路径；已分别使用精确 runtime gate 和临时 synthetic data root 通过，结果见 `docs/prompts/P6E_ACCEPTANCE_EVIDENCE.md`。
- [ ] 系统级 screen reader、真实 offline/极端长回答和长时整批 Chromium 稳定性验收。

## Phase 8：Cards / Exercises（仅在 Phase 7 收口后）

- [x] v7 migration（不得运行时建表）增加 `study_decks`、`study_cards`、`card_citations`、`card_reviews`、`exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`；v8 追加 `exercise_kind` provenance，保持连续 migration/history/user_version 一致。
- [x] 8.2 Cards backend MVP：deck/card draft → ready、编辑保护、citation 基础校验和 append-only review（已提交）；完整 source lifecycle/UI 仍留在后续 Phase 8 子任务。
- [x] 8.3 Exercises backend MVP：set、`multiple_choice`/`true_false`/`short_answer`、draft → ready/rejected/archived、draft-only edit、attempt history、deterministic grading 与 short-answer `pending_review`。
- [x] AI exercise 必须有 current active source revision 与 valid revision/chunk/span citation；confirm 时重新验证，source delete/restore/purge 与 revision re-index 更新 citation lifecycle。
- [x] answer key 和 submitted answer 不进入普通 exercise/attempt 列表响应；backup/restore 和 restart 保留 exercise/attempt history。
- [x] 8.4 AI draft generation：card/exercise generation 接入显式 indexed single-material lexical/vector/hybrid retrieval、context/citation verification、provider 和 `ai_operations`；结构化输出仅在内存校验，不持久化 raw prompt/response，成功只原子保存 cited draft，失败只保留安全 failed operation。支持 1–10 draft、Idempotency-Key replay/running conflict/failed retry、source-stale、malformed/forged citation、provider failure、rollback 边界；fake provider backend 验收完成，真实 Provider 不在本子任务扩大范围。
- [x] 8.5 Cards/Exercises UI、fake-provider Chromium 用户路径和基础可访问性验收：统一 nav、deck/set、draft generation/list/detail、citation 定位/unavailable、draft edit/save、confirm/reject/archive、card review、exercise attempt、刷新恢复、busy/retry failure、answer-key privacy、390x844 overflow 和键盘 nav；证据为 `backend/tests/browser_phase8.spec.js`。未做真实 Provider generation、系统级 screen reader 或极端长内容验收。
- [x] 8.6 Phase 8 完整 citation source lifecycle、backup/restore、全量回归、正式证据/文档收口：新增 `backend/tests/test_phase8_closeout.py` 覆盖 artifact/citation/review/attempt/operation 的 backup → verify → 新空目录 restore 与 startup/read non-repair；full backend `250 passed, 2 skipped`、Phase 8 Chromium `3 passed`、相关 UI failure regression `9 passed`。证据：[`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)。

## Phase 7：Embedding 与 Hybrid Retrieval

### 7.1 现状审计与契约冻结：已完成

- [x] 审计 embeddings、retrieval_runs、retrieval_hits、chunking、repository、migration 和 backup/restore 边界。
- [x] 列出已有/未使用字段、兼容性风险和 v5 migration 要求。
- [x] 冻结 embedding identity、status/stale、provider/model/dimension 和 retrieval policy 语义。
- [x] 冻结 lexical-only、vector-only、hybrid、fallback 与 empty 行为。
- [x] 将正式记录写入 `docs/prompts/PHASE7_1_AUDIT_AND_CONTRACT.md`。

**当前限制：** 7.1–7.7 fake/backend 验收、embedding/retrieval/Q&A metadata backup/restore、损坏生命周期、102/1,002 chunks synthetic benchmark、retrieval mode UI/Chromium final acceptance、indexing lease/失败重试/恢复专项，以及 Mistral `mistral` / `mistral-embed` / `https://api.mistral.ai/v1` 精确真实 embedding gate 均已通过。Phase 7 已在该精确配置范围完成；其它 provider/model 仍独立处理。

### 后续实现

- [x] v5 embedding schema migration、canonical identity、f32le_v1 payload codec、status/updated_at 和 stale/source-binding semantics。
- [x] deterministic fake embedding、显式 indexing 和 vector-only cosine 最小路径。
- [x] EmbeddingProvider protocol、独立 registry、deterministic fake provider、环境配置、capability 安全扩展和基础稳定错误边界。
- [x] 显式增量 indexing、material rebuild/retry、只读 verify、失败状态基础处理和 active/current/ready 生命周期过滤。
- [x] vector cosine、hybrid RRF、固定 candidate pool/RRF_K/tie-breaker、lexical fallback policy 和 lexical/vector/final score persistence 基础。
- [x] 独立 OpenAI-compatible embedding provider adapter、配置/secret 隔离、`/embeddings` 请求契约和稳定错误映射；Mistral 精确真实网络 acceptance 已通过，loopback evidence 仍作为协议补充。
- [x] embedding/retrieval/Q&A metadata backup/restore 专项验收、损坏生命周期测试和 synthetic benchmark。
- [x] retrieval mode UI/Chromium final acceptance：lexical/vector/hybrid、fallback 和 vector 不回退边界。
- [x] indexing lease、`embedding_index` operation 审计、stale reclaim、失败保留和显式 retry_count/retry 专项。
- [x] 真实 embedding provider 外部网络 acceptance：Mistral `mistral` / `mistral-embed` / `https://api.mistral.ai/v1` 已通过直接向量、隔离 indexing、vector retrieval 和审计 metadata gate；证据见 `docs/prompts/PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md`。
- [ ] 其它 provider/model 的 embedding 独立验证：Agnes `agnes-2.5-flash`、ARK `deepseek-v4-flash`、MiniMax `embo-01`、NVIDIA `nvidia/nv-embedqa-e5-v5` 本轮未通过，不阻塞 Mistral 精确配置范围的 Phase 7 完成。

- [ ] 任务记录、progress、retry/cancel、worker 与长任务恢复（需求明确后）。
- [ ] structured tracing、扩展 metrics、degraded readiness。

**Phase 8 收口结论：** 在 deterministic fake-provider、单进程 SQLite、本地 Chromium 和 backup/restore 的精确范围内 completed。该结论不包含真实 Provider generation、人工简答复核、系统级辅助技术、极端内容或长时稳定性；这些仍为 `not_verified`。下一阶段按 9A（学习领域基础与计划核心）推进，不跳过其独立契约和 migration gate。

## Phase 9：学习产品构建计划

> Phase 9 不能承载一次性完成的全部学习业务。以下 9A–9D 是独立验收阶段，必须按顺序推进；未开始项目不得用设计文档或历史版本证据标记完成。

### Phase 9A：学习领域基础与计划核心

> 充分上下文、总规划 prompt、逐子任务边界、实现 prompt、测试门禁和推荐 commit 拆分见 [`prompts/phase9a/`](prompts/phase9a/)。以下任务仍为 planned，不能把 prompt/设计文档视为实现证据。

- [x] 9A-0：完成现状审计、9A non-goals、9B/9C/9D 边界和风险冻结；初稿见 [`prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md`](prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md)。状态为 `planned/audit-draft`，不代表领域能力实现。
- [x] 9A-1：冻结 learning goal、knowledge module、study plan/item、dependency、progress event、source link 的正式领域契约和状态机；正式契约见 [`prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md`](prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md)。状态为 `planned/contract-frozen`，不代表 schema/API/UI 实现。
- [x] 9A-2：通过连续 v9 migration 增加计划、目标、模块、依赖、进度事件和 source link schema，并完成 new-db/v8-upgrade/rollback/幂等和 backup/restore schema-history 测试；见 [`prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md`](prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md)。状态为 `implemented/backend-pass`，repository/domain 及其后续 API/UI 另由 9A-3 至 9A-5 验收。
- [x] 9A-3：实现 repository/domain 事务、DAG 依赖校验、append-only progress、状态投影、source identity validation、source lifecycle refresh 和用户编辑保护；focused `backend/tests/test_phase9a_domain.py` 8 passed，full backend 通过。状态为 `implemented/backend-pass`，API/UI 另由 9A-4/9A-5 验收。
- [x] 9A-4：实现最小 goal/module/plan/item/dependency/progress/source API、project scope、输入边界和稳定错误 contract；`backend/tests/test_phase9a_api.py` 4 passed，full backend 通过。状态为 `implemented/backend-pass`，UI/Chromium 另由 9A-5 验收，source lifecycle/backup closeout 仍未完成。
- [x] 9A-5：实现 draft → confirm → active → progress → refresh 的最小 Chromium workspace，并覆盖 dependency cycle failure、500/retry、390x844、keyboard 和 reload recovery；`backend/tests/browser_phase9a.spec.js` 2 passed。状态为 `browser-pass`，不代表 real-pass 或 9A completed。
- [x] 9A-6：完成 delete/restore/purge/re-index/source unavailable/stale 的 source lifecycle 集成；scoped backend/browser gates 通过（focused `16 passed`、full backend `270 passed, 2 skipped`、Phase 9A Chromium `3 passed`），并在 9A-8 closeout 中纳入最终 evidence。
- [x] 9A-7：完成 9A 数据 backup/verify/restore、历史保留和 non-repair 验收；`backend/tests/test_phase9a_backup_restore.py` 与既有 backup/restore/restore-acceptance tests 通过，focused `13 passed`，full backend `272 passed, 2 skipped`。状态为 `restore-gates-pass`。证据见 [`prompts/evidence/PHASE9A_BACKUP_RESTORE_EVIDENCE.md`](prompts/evidence/PHASE9A_BACKUP_RESTORE_EVIDENCE.md)。
- [x] 9A-8：完成 full regression、Chromium、脱敏 evidence、STATUS/TODO/ROADMAP 文档收口。状态为 `completed`，准确范围和未验证边界见 [`PHASE9A_ACCEPTANCE_EVIDENCE.md`](PHASE9A_ACCEPTANCE_EVIDENCE.md)。

> 下方为旧版 Phase 9A 概括性条目；详细可执行拆分以 9A-0 至 9A-8 为唯一口径，避免重复清单产生状态漂移。
>
> 9A-0 已完成 `planned/audit-draft`，9A-1 已完成 `planned/contract-frozen`，9A-2/9A-3/9A-4 已完成 `implemented/backend-pass`，9A-5 已完成 `browser-pass`，9A-6 已完成 source lifecycle scoped gate，9A-7 已完成 `restore-gates-pass`，9A-8 已完成限定范围内 `completed` closeout。当前 full backend 为 `272 passed, 2 skipped`，Phase 9A Chromium 为 `3 passed`，Phase 8 Chromium 为 `3 passed`，frontend failure contract 为 `6 passed`。


### Phase 9B：资料学习工作流（S1/S2）

> 当前状态：在限定范围内 `completed`。Phase 9B 的总规划 prompt、共用上下文、9B-0 至 9B-9 子任务 prompts、执行顺序和验收门槛已集中存放于 [`prompts/phase9b/`](prompts/phase9b/)。prompt 包不是实现证据，必须按顺序逐项执行并独立验收。
>
> 当前子任务状态：9B-0 为 `planned/audit-draft`，9B-1 为 `planned/contract-frozen`，9B-2 至 9B-6 为 `implemented/backend-pass`，9B-7 为 `browser-pass`，9B-8 为 `scoped-gates-pass`/`restore-gates-pass`，9B-9 已完成限定范围内 `completed` closeout；审计、正式契约、schema 和最终证据见 [`prompts/phase9b/PHASE9B_DOMAIN_CONTRACT.md`](prompts/phase9b/PHASE9B_DOMAIN_CONTRACT.md) 与 [`PHASE9B_ACCEPTANCE_EVIDENCE.md`](PHASE9B_ACCEPTANCE_EVIDENCE.md)。

- [x] 9B-0：完成现状审计、S1/S2 范围冻结和风险记录；状态为 `planned/audit-draft`，产出见 [`prompts/phase9b/PHASE9B_DOMAIN_CONTRACT.md`](prompts/phase9b/PHASE9B_DOMAIN_CONTRACT.md)。
- [x] 9B-1：冻结 S1/S2 实体关系、cadence/timezone/workload、note/block/module/citation 关系、状态机、不变量、source lifecycle、AI draft、错误码、API resource、导出和 backup/restore non-repair 边界；状态为 `planned/contract-frozen`，不代表实现完成。
- [x] 9B-2：通过连续 v10 `phase9b_material_learning_schema` migration 增加 note/block/module-link/source-tombstone 与 rhythm persistence schema，并覆盖 new-db、v9 upgrade、幂等、failure rollback、history/user_version 和 backup schema-version；状态为 `implemented/backend-pass`，不代表 9B repository/domain、API/UI、source lifecycle 或 restore artifact 验收。
- [x] 9B-3：实现共用 repository/domain transaction：note/block/module link、server-side citation source link validation、source status refresh、rhythm settings/allocation 与 deterministic summary；focused `backend/tests/test_phase9b_domain.py` 通过，状态为 `implemented/backend-pass`。
- [x] 9B-4：在 9B-3 基础上完成 S2 资料笔记、知识模块和 deterministic fake-provider draft backend workflow；覆盖检索/context/citation 复验、idempotency/retry、失败 rollback、source stale 和用户状态保护；状态为 `implemented/backend-pass`。
- [x] 9B-5：在 9B-3 基础上完成 S1 学习节奏 backend workflow：daily/weekly IANA timezone settings、local-date allocation 的创建/移动/删除和重复/超限保护、确定性 timeline/load/progress/source-warning summary、completed/terminal plan 保护、rollback/SQLite lock 后 retry；不写 progress、不自动重排或启动 scheduler。focused `backend/tests/test_phase9b_rhythm.py` 与 9B regressions 通过，状态为 `implemented/backend-pass`；API/UI/export/restore artifact 另由后续任务验收。
- [x] 9B-6：实现 S1/S2 最小安全 FastAPI：rhythm settings/summary/allocation、notes/blocks/modules/source links、draft generation、confirm/reject/archive、source refresh、bounded JSON/Markdown export；服务端注入 project scope，复用 domain contract，覆盖安全错误、citation/source lifecycle、provider failure、idempotency 和隐私边界。focused `backend/tests/test_phase9b_api.py` 与完整 backend 通过，状态为 `implemented/backend-pass`；不代表 browser-pass 或 Phase 9B completed。
- [x] 9B-7：实现 S1/S2 最小 Chromium workspace：S1 rhythm settings、allocation 调整、timeline/load/progress、export/reload；S2 user/AI citation draft、知识模块组织、编辑保护、confirm/reject/archive、source refresh、citation dialog 与 export。`backend/tests/browser_phase9b.spec.js` 串行隔离 data root，覆盖 desktop、390x844、keyboard、reload、duplicate click、provider_not_configured、malformed/network failure、citation unavailable 和安全 DOM。`3 passed`，状态为 `browser-pass`；不代表 restore-gates、real-pass 或 Phase 9B completed。
- [x] 9B-8：验证 S1/S2 source lifecycle 与 backup/restore non-repair：note/block/module/source-link、rhythm/allocation、completed progress 在 delete/restore/purge/new revision 后保留正确 `valid`/`stale`/`source_deleted`/`source_unavailable` 历史；backup→verify→新空目录 restore 保留 v10 表/历史/状态，restore/startup/read/verify 不 provider/index/refresh/repair。新增 `test_phase9b_source_lifecycle.py`、`test_phase9b_backup_restore.py`，并扩展 `restore_acceptance.py` 的只读 v10 checks；当时状态为 `scoped-gates-pass`/`restore-gates-pass`；9B-9 已在此基础上完成限定范围内 Phase 9B closeout。
- [x] 9B-9：完成 Gate A-I 全量验收、脱敏 evidence 与最终文档同步。focused closeout `59 passed`；完整 backend `299 passed, 2 skipped`；相关非真实 Provider Chromium `45 passed, 1 skipped`；默认 real-provider spec `2 skipped`。新增 [`PHASE9B_ACCEPTANCE_EVIDENCE.md`](PHASE9B_ACCEPTANCE_EVIDENCE.md)，同步 STATUS/README/ROADMAP/PROJECT_PROGRESS/INDEX/architecture。状态为限定范围内 `completed`，不代表 Phase 9C/9D、真实 Provider generation、scheduler/worker、人工复核或全局 production `real-pass`。

### Phase 9C：练习与反馈工作流（S3/S4/S5）

> 当前状态：在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内 `completed`；9C-0/9C-1 为 `planned/audit-draft`/`contract-frozen`，9C-2 至 9C-7 为 `implemented/backend-pass`，9C-8 为 `browser-pass`，9C-9 为 `scoped-gates-pass`/`restore-gates-pass`，9C-10 已完成 Gate A-J closeout。Phase 9C 总体 prompt、共用上下文、9C-0 至 9C-10 子任务 prompts、执行顺序和 Gate A-J 已集中存放于 [`prompts/phase9c/`](prompts/phase9c/)。prompt 包不是实现证据；必须逐项执行、测试并独立收口。

- [x] 9C-0：完成现状审计与范围冻结；盘点 Phase 8/9A/9B 实际能力，冻结 S3/S4/S5 与 9D/Phase 10 non-goals。
- [x] 9C-1：完成正式领域契约与状态机冻结；覆盖 session、attempt、grading/review、mistake、weak-point、cram、时间和隐私边界。
- [x] 9C-2：通过连续 v11 `phase9c_exercise_feedback_schema` migration 增加最小 S3/S4/S5 schema，完成 new-db、v10 upgrade、幂等、rollback、history/user_version、约束和 backup version 测试；状态为 `implemented/backend-pass`，不代表 9C repository/domain、API/UI、source lifecycle、restore 或 Phase 9C completed。
- [x] 9C-3：实现 v11 上的共享 repository/domain transaction：practice/cram session 与 immutable item snapshot、服务端 deadline、MC/TF deterministic grading、short-answer pending review、attempt/review/feedback append-only、mistake/weak-point projection、source/privacy boundary、cram 不写 plan/progress 和 rollback；focused `7 passed`、相关 focused regression `46 passed`、完整 backend `306 passed, 2 skipped`。状态为 `implemented/backend-pass`，不代表 API/UI、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-4：完成 S3 PracticeRunner backend 闭环：practice session create/read/list/start/submit/finish/expire/result、immutable snapshot、服务端 deadline、MC/TF deterministic grading、short-answer pending review、append-only attempt、duplicate/idempotency replay/mismatch、只读安全 result、rollback 和 source lifecycle 读路径；focused `8 passed`、相关 focused `39 passed`、完整 backend `307 passed, 2 skipped`。状态为 `implemented/backend-pass`，不代表 S4/S5、API/UI、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-5：完成 S4 ErrorFixer backend：deterministic/review/user-marked 错题事实区分、case/occurrence 归并与幂等、uncertain review、feedback/archive、fixed→reopened、redo 新 session/attempt、weak-point projection、source status 降级、privacy 和 rollback；focused `13 passed`、相关 focused `44 passed`、完整 backend `312 passed, 2 skipped`。状态为 `implemented/backend-pass`，不代表 S5、API/UI、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-6：完成 S5 ExamCrammer backend：cram goal 生命周期、显式 cram session/题目快照、S3 attempt/grading/result 复用、mistake/weak-point summary、selection/project/target/date 边界、privacy、plan/progress/rhythm 不变更和 rollback；focused `15 passed`、相关 focused `46 passed`、完整 backend `314 passed, 2 skipped`。状态为 `implemented/backend-pass`，不代表 API/UI、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-7：完成 S3/S4/S5 最小安全 FastAPI API：practice session、attempt submit/review、mistake/weak-point、cram goal/session/result、server project scope、稳定 400/404/409/422/500 错误、Idempotency-Key、privacy 和生命周期边界；focused `3 passed`、相关 focused `32 passed`、完整 backend `317 passed, 2 skipped`。状态为 `implemented/backend-pass`，不代表 Chromium/UI、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-8：完成最小 Chromium workspace：S3 session/start/submit/finish/result、S4 mistake/feedback/redo、S5 cram goal/session/result、reload、duplicate/idempotency、500/network retry、default-provider safe failure、keyboard/focus、390x844 overflow 和 privacy DOM；focused Chromium `3 passed`，相关 UI failure `9 passed`。状态为 `browser-pass`，不代表 real-pass、9C lifecycle/restore gates 或 Phase 9C completed。
- [x] 9C-9：完成 S3/S4/S5 source lifecycle 与 backup/verify/新空目录 restore non-repair：v11 表/历史事实、session/item linkage、attempt/review/mistake/feedback/cram status 保留，delete/restore/purge/re-index source status 安全降级；专项 `14 passed`、完整 backend `320 passed, 2 skipped`。状态为 `scoped-gates-pass`/`restore-gates-pass`，不代表 9C-10 closeout 或 Phase 9C completed。
- [x] 9C-10：完成 Gate A-J、全量回归、脱敏 evidence、STATUS/TODO/ROADMAP/PROJECT_PROGRESS/INDEX 文档收口；证据见 [`PHASE9C_ACCEPTANCE_EVIDENCE.md`](PHASE9C_ACCEPTANCE_EVIDENCE.md)。

完成声明仅限 deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore；不包含真实 Provider、scheduler/worker、OCR/ASR、Phase 9D 或全局 production `real-pass`。

### Phase 9D：扩展学习服务（S6/S7，部分立项）

> 当前状态：9D-0 为 `planned/audit-draft`，结论是只立项 deterministic fake/loopback OCR/ASR、本地脱敏报告和 delivery dry-run；9D-1 为 `planned/contract-frozen`；9D-2 v12 migration、9D-3 repository/domain transaction、9D-4 S7 capture/transcription backend 和 9D-5 S7→S2 ingestion backend 均为 `implemented/backend-pass`。9D-6 至 9D-11 尚未实现，Phase 9D 不得标记 completed。总规划、契约和 Gate A-L 见 [`prompts/phase9d/`](prompts/phase9d/)。

- [x] 9D-0：完成需求、隐私、数据保留、真实组件证据和运维成本审计；作出部分立项结论并冻结 non-goals。真实 OCR/ASR 与真实 SMTP/飞书外发暂不立项。状态为 `planned/audit-draft`。
- [x] 9D-1：冻结 capture/transcript/report/delivery dry-run 的实体、状态机、幂等、脱敏、source lifecycle 和 non-repair 契约。状态为 `planned/contract-frozen`，不代表 schema/domain/API/UI 实现。
- [x] 9D-2：通过连续 v12 `phase9d_extended_learning_schema` migration 增加 capture session、transcript、report snapshot 和 delivery-attempt schema；new DB、v11 upgrade、幂等、failure rollback、history/user_version、约束和 backup schema-version 测试通过。focused migration/governance `25 passed`，完整 backend `325 passed, 2 skipped`。状态为 `implemented/backend-pass`。
- [x] 9D-3：实现 project scope、capture/transcription operation 与 confidence/uncertain facts、可重算 report projection、append-only delivery audit、幂等、事务 rollback、脱敏、secret/raw-response 排除和 material source 降级。专项 `6 passed`，migration + 9A/9B/9C/9D 相关回归 `49 passed`，完整 backend `331 passed, 2 skipped`。状态为 `implemented/backend-pass`；不代表 OCR/ASR 执行、S2 接入、完整 report/delivery workflow、API/UI 或 lifecycle/restore gates。
- [x] 9D-4：实现 deterministic fake/loopback S7 课堂采集与 OCR/ASR 转写：敏感音频/图片原件上传、hash-derived originals/material lifecycle 绑定、confidence/uncertain、失败/超时/非法输出、幂等 replay/retry、rollback、raw-response 排除和 source lifecycle 安全读路径。专项 `6 passed`，migration + 9A/9B/9C/9D 相关回归 `55 passed`，完整 backend `337 passed, 2 skipped`。状态为 `implemented/backend-pass`；不代表 9D-5 S2 接入、API/UI、完整 lifecycle/restore gates 或真实 OCR/ASR real-pass。
- [x] 9D-5：将确认后的转写接入同一 capture material 的 S2 material/revision/chunk/retrieval/citation 管线：confirmed transcript 创建 `class_capture_transcript` extraction/revision，复用确定性 chunk/FTS retrieval 和服务端 citation identity；支持 draft→显式 edit→confirm/reject、uncertain 保留、用户编辑保护、source 校验和 confirm 原子 rollback。专项 9D-4/9D-5 `10 passed`，相关 9A/retrieval 回归 `26 passed`，完整 backend `341 passed, 2 skipped`。状态为 `implemented/backend-pass`；不代表 9D-6 报告/交付、API/UI、完整 lifecycle/restore gates 或真实 OCR/ASR real-pass。
- [ ] 9D-6：实现 S6 家长报告只读聚合、强制脱敏、快照/重算和安全导出。
- [ ] 9D-7：实现默认关闭、仅 dry-run、显式授权/白名单和 append-only 审计的交付层；不实现 live delivery。
- [ ] 9D-8：实现 Phase 9D 最小安全 API contract。
- [ ] 9D-9：实现 desktop/narrow/keyboard/reload/failure/privacy Chromium workspace。
- [ ] 9D-10：完成 source lifecycle 与 backup/verify/新空目录 restore non-repair 验收；restore 不触发 OCR/ASR、报告生成或交付。
- [ ] 9D-11：完成 Gate A-L、完整回归、脱敏 evidence 和最终文档收口。

真实 OCR/ASR provider 与真实对外交付必须先在 Composer/Integration 获得独立证据并再次评审；当前部分立项不包含这些能力。

### Phase 9 总门槛

- [ ] 只有 9A–9D 中明确立项的子阶段全部完成，才可称为 Phase 9 completed；未立项的 9D 能力不计入“已实现”。
- [ ] Phase 9 完成不等于全局生产级 `real-pass`，也不代表多用户、云同步、OCR/ASR 或后台任务自动完成。

## P2：生产化与扩展

- [ ] 多用户、认证、授权、project isolation UI。
- [ ] 多进程/多实例写协议，或继续明确 SQLite 单机路线。
- [ ] 云同步、外部存储、协作。
- [ ] 真实断电/网络盘/文件系统损坏风险评估与容量性能验收。

## 明确暂不做

在 Phase 7 收口和后续产品路线明确前，不并行推进：OCR、ASR、ZIP import、文件夹 export、外部 vector database、复杂后台队列、多用户/协作、云同步、订阅/账户系统。

## 每个 TODO 的交付模板

1. 代码实现；
2. 单元/集成测试；
3. API 输入和失败边界；
4. 浏览器用户路径（若有 UI）；
5. 安全性检查；
6. 文档/状态同步；
7. 可复现命令或测试 artifact。
