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

目标：用户选择已导入材料提问，系统以可追溯的检索和验证引用回答。deterministic fake provider 下的完整 Q&A 用户闭环、history、多材料范围、citation 导航、浏览器验收和文档证据均已完成。Phase 5 adapter 已实现，下一执行项为真实 Provider smoke 验收。

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
- [ ] ARK、硅基流动、Agnes AI-Hub、Sub2API 逐个完成脱敏 capability matrix 和真实验收（API/UI smoke 现强制 target 与 runtime provider 一致；ARK 缺少匹配 model/base URL，硅基流动缺少 matching runtime provider/target/model/base URL，均未发送真实请求，provider-specific real evidence 仍 pending）。

**Phase 5 当前状态：** adapter、配置隔离、HTTPS/loopback URL 边界、响应体读取上限、稳定错误映射、timeout/output limit/retry、mock HTTP 测试、provider request/usage/latency metadata、citation 缺失/伪造拒绝、secret redaction、真实 Provider failure UX、retry、重复点击、安全渲染、显式 Idempotency-Key 幂等和请求触发的 stale recovery 已实现并验证。DeepSeek 官方 `deepseek-chat` 的 adapter-level、完整 API-level synthetic Q&A 和 Chromium UI/E2E smoke 均已通过；ARK、硅基流动、Agnes AI-Hub、Sub2API 的独立验收矩阵已建立，但真实 evidence 仍未完成。

## Phase 6：AI MVP 产品化与整体验收

- [ ] 真实 provider 下的端到端回归和 provider failure UX 验收。
- [ ] 更完整的 Q&A thread 工作区、跨材料浏览和导出衔接。
- [ ] 统一应用级组件、导航、通知、可访问性和响应式体验。
- [ ] 导入 → 检索 → 问答 → 引用 → 导出核心工作流整体验收。
- [ ] 高延迟、离线、长回答和真实 provider 限制下的前端体验收口。

## 后续学习能力：Cards / Exercises（仅在 Phase 4 Q&A 完成后）

- [ ] 新 migration（不得运行时建表）增加 `study_decks`、`study_cards`、`card_citations`、`card_reviews`。
- [ ] 新 migration 增加 `exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`。
- [ ] AI 生成 card/exercise 默认 `draft`；用户确认后才可 `ready`。
- [ ] citation 必须可验证并关联 revision/chunk/span；无效引用不得 ready。
- [ ] 用户编辑保护、stale/source_unavailable、review/attempt 历史。
- [ ] 选择题/判断题 deterministic grading；简答 AI grading 标记待复核。
- [ ] answer key 不进入普通列表响应。

## 后续扩展：学习计划、Embedding 与后台任务

- [ ] Study plan / items：draft → confirm → active，完成记录不可静默覆盖。
- [ ] 明确并实现首批 S1–S7。
- [ ] embedding payload、hybrid retrieval、rerank、rebuild/verify；规模证据充分前不引入外部 vector DB。
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
