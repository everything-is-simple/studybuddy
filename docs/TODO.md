# StudyBuddy TODO 清单

> 更新：2026-08-25  
> 当前基线：本地单进程文件材料管理基础系统已可用，整体阶段性完成度约 **45%–50%**。I1 migration/schema versioning 与 I2 backup/restore 运维闭环已完成；完整状态见 [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)。
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

证据：`H:\studybuddy-test\artifacts\infrastructure-i4\latest.json` 和 `latest.md`（最近一次基线已重新运行并更新）。

**状态：时间盒验收完成（v1）。** S0–S3 和 40-cycle smoke 为 real；ACL、资源耗尽、S4、peak memory、断电/网络盘/硬件损坏为 `not_verified`，并已明确记入 v1 运行边界。

## Phase 4：AI 最小闭环（已完成）

目标：用户选择已导入材料提问，系统以可追溯的检索和验证引用回答。deterministic fake provider 下的完整 Q&A 用户闭环、history、多材料范围、citation 导航、浏览器验收和文档证据均已完成。Phase 5 adapter、精确 Provider smoke 和 Phase 6 P6-A–P6-E fake/default/UI 产品化验收已按对应 evidence 收口；下一执行项为显式 gate 下的 P6-E 精确真实 Provider UI evidence，随后进入 Phase 7。

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
- [x] DeepSeek 官方 `deepseek-chat` 真实网络 smoke：adapter-level、完整 API-level synthetic Q&A 和 Chromium UI/E2E 均已通过；其它 Provider 仍待验收。
- [ ] ARK、硅基流动、Agnes AI-Hub、Sub2API 逐个完成脱敏 capability matrix 和真实验收（API/UI smoke 强制 target 与 runtime provider 一致；通用三次 API acceptance runner 已实现，每次使用独立临时 data root，`2/3` 仅为 API evidence；Agnes `advanced`/`agnes-2.5-flash` 已通过独立 adapter/API/UI smoke；`pro`/`agnes-2.5-pro` API smoke 返回 `provider_unavailable`，UI 未运行，仍待独立验证；其它 Agnes profiles 未验证）。

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

- [x] P6-E 导入 → ready → indexing → retrieval → thread → Q&A → citation → 定位 → 返回 → 导出 → refresh/history 核心工作流整体验收；证据：`docs/P6E_ACCEPTANCE_EVIDENCE.md`。
- [x] P6-D 统一应用级导航、当前 material/thread/scope 状态、页面 status/alert 和补充 toast。
- [x] P6-D 桌面/390x844 窄屏布局、键盘视图切换、可见焦点、dialog Escape/focus return 和关键 ARIA/current/status/alert 语义。
- [x] P6-D fake Provider Chromium 专项验收：`backend/tests/browser_p6d.spec.js`，2 passed；未引入 API 或 migration，未引入 axe。
- [x] P6-E fake Provider 核心工作流、empty retrieval、source lifecycle、retry、duplicate click、stale response、refresh/history、导出失败和窄屏路径验收。
- [x] P6-E Provider failure UX 回归：timeout、network failure、rate limit、unavailable、malformed/safe error contract；详见 `docs/P6E_ACCEPTANCE_EVIDENCE.md`。
- [x] DeepSeek `deepseek-chat` 和 Agnes `agnes-ai-hub` / `agnes-2.5-flash` 的 P6-E 真实 UI 路径；已分别使用精确 runtime gate 和临时 synthetic data root 通过，结果见 `docs/P6E_ACCEPTANCE_EVIDENCE.md`。
- [ ] 系统级 screen reader、真实 offline/极端长回答和长时整批 Chromium 稳定性验收。

## 后续学习能力：Cards / Exercises（仅在 Phase 4 Q&A 完成后）

- [ ] 新 migration（不得运行时建表）增加 `study_decks`、`study_cards`、`card_citations`、`card_reviews`。
- [ ] 新 migration 增加 `exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`。
- [ ] AI 生成 card/exercise 默认 `draft`；用户确认后才可 `ready`。
- [ ] citation 必须可验证并关联 revision/chunk/span；无效引用不得 ready。
- [ ] 用户编辑保护、stale/source_unavailable、review/attempt 历史。
- [ ] 选择题/判断题 deterministic grading；简答 AI grading 标记待复核。
- [ ] answer key 不进入普通列表响应。

## Phase 7：Embedding 与 Hybrid Retrieval

### 7.1 现状审计与契约冻结：已完成

- [x] 审计 embeddings、retrieval_runs、retrieval_hits、chunking、repository、migration 和 backup/restore 边界。
- [x] 列出已有/未使用字段、兼容性风险和 v5 migration 要求。
- [x] 冻结 embedding identity、status/stale、provider/model/dimension 和 retrieval policy 语义。
- [x] 冻结 lexical-only、vector-only、hybrid、fallback 与 empty 行为。
- [x] 将正式记录写入 `docs/PHASE7_1_AUDIT_AND_CONTRACT.md`。

**当前限制：** 7.1 契约冻结已完成；7.2 已实现 deterministic fake provider、独立 registry、配置边界和安全 capabilities。真实网络 adapter、hybrid/fallback 和 Q&A 接入仍未完成。

### 后续实现

- [x] v5 embedding schema migration、payload codec 基础和 status/identity semantics。
- [x] deterministic fake embedding、显式 indexing 和 vector-only cosine 最小路径。
- [x] EmbeddingProvider protocol、独立 registry、deterministic fake provider、环境配置、capability 安全扩展和基础稳定错误边界。
- [ ] 真实 provider adapter、完整 indexing/rebuild/verify、stale 判定、失败重试、生命周期和 embedding backup/restore 专项验收。
- [ ] hybrid RRF、fallback policy、完整 retrieval audit metadata 和 Q&A/citation 接入。
- [ ] Study plan / items：draft → confirm → active，完成记录不可静默覆盖。
- [ ] 明确并实现首批 S1–S7。

- [ ] 任务记录、progress、retry/cancel、worker 与长任务恢复（需求明确后）。
- [ ] structured tracing、扩展 metrics、degraded readiness。

## P2：生产化与扩展

- [ ] 多用户、认证、授权、project isolation UI。
- [ ] 多进程/多实例写协议，或继续明确 SQLite 单机路线。
- [ ] 云同步、外部存储、协作。
- [ ] 真实断电/网络盘/文件系统损坏风险评估与容量性能验收。

## 明确暂不做

在 Phase 5 真实 Provider 和后续产品路线明确前，不并行推进：OCR、ASR、ZIP import、文件夹 export、外部 vector database、复杂后台队列、多用户/协作、云同步、订阅/账户系统。

## 每个 TODO 的交付模板

1. 代码实现；
2. 单元/集成测试；
3. API 输入和失败边界；
4. 浏览器用户路径（若有 UI）；
5. 安全性检查；
6. 文档/状态同步；
7. 可复现命令或测试 artifact。
