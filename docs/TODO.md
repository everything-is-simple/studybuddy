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

## 当前最高优先级：P0——AI 第一阶段可信 Q&A 最小闭环

目标：用户选择已导入材料提问，系统以可追溯的检索和验证引用回答。第一轮使用 deterministic fake provider，不以真实厂商接入为前置。I1/I2/I3 已完成，I4 已时间盒验收，基础设施 v1 基本完工，现在进入 AI Phase 1。

### 顺序与任务

```text
revision → chunks → retrieval → citations → Q&A
```

- [ ] 确定 MVP 用户流程：选择材料 → 提问 → 检索 → 回答 → 查看引用。
- [x] 实现 `material_revisions` 的创建、current/superseded 生命周期；stale 语义留给后续重解析链路。
- [x] 实现 deterministic chunker、Unicode code-point offsets、显式 indexing；现有 text_spans 通过按序文本匹配建立安全 page/slide/document 映射。
- [x] 实现 `chunks` / `chunk_spans` 持久化和 `chunks_search` FTS5 同步；连接时只清理/补齐已有 ready chunks，不自动创建 chunk。
- [x] 实现 lexical retrieval：active/current/ready 过滤、ASCII AND 查询、Unicode substring fallback、top-k、稳定排序、`retrieval_empty`。
- [x] 持久化 `retrieval_runs` / `retrieval_hits`；lexical 阶段不写 provider、embedding 或 rerank 数据。
- [ ] 实现 context assembler：token budget、不可信 source boundary、可验证 citation key。
- [ ] 实现 citation 验证、`qa_citations` 和 purge 后 `source_unavailable`。
- [ ] 实现 Provider Protocol、registry、deterministic fake provider、`provider_not_configured`。
- [ ] 实现 `ai_operations`、Q&A thread/message/answer repository 和 API。
- [ ] 实现最小 Q&A UI：loading/empty/error/retry、citation 展示与原文定位。
- [ ] 补单元、repository、API failure、browser E2E、backup/restore AI 表测试。
- [ ] 同步 `STATUS.md`、`DECISIONS.md`、AI architecture、roadmap 与 API 文档。

**当前进度：** revision/chunk 显式 indexing 和 chunk lexical retrieval 已实现并由 focused/backend tests 验证；citation、fake provider 和 Q&A 尚未实现。

**完成标准：** fake provider 下端到端问答通过；展示 citation 可追溯到 material/revision/chunk/span；deleted/stale 被排除；purge 后历史 citation 正确显示 unavailable；未配置 provider 时应用照常启动并安全失败。

## P1：AI MVP 体验与真实 Provider

- [ ] Q&A 对话历史、多材料范围选择、citation 详情/原文定位。
- [ ] 统一 loading/empty/error/success、toast、retry、响应式和可访问性基线。
- [ ] 真实 LLM/Embedding provider adapter、环境配置、timeout/output limit。
- [ ] provider timeout/rate-limit/auth/quota/refusal/malformed response 稳定错误映射。
- [ ] capabilities endpoint、usage/latency/request metadata，禁止 secret 泄露。
- [ ] AI operation 同步状态、幂等 fingerprint、stale 语义。

## P1：AI Phase 4——Cards / Exercises（仅在可信 Q&A 后）

- [ ] 新 migration（不得运行时建表）增加 `study_decks`、`study_cards`、`card_citations`、`card_reviews`。
- [ ] 新 migration 增加 `exercise_sets`、`exercises`、`exercise_citations`、`exercise_attempts`。
- [ ] AI 生成 card/exercise 默认 `draft`；用户确认后才可 `ready`。
- [ ] citation 必须可验证并关联 revision/chunk/span；无效引用不得 ready。
- [ ] 用户编辑保护、stale/source_unavailable、review/attempt 历史。
- [ ] 选择题/判断题 deterministic grading；简答 AI grading 标记待复核。
- [ ] answer key 不进入普通列表响应。

## P2：学习计划、Embedding 与后台任务

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

在可信 Q&A 最小闭环完成前，不并行推进：OCR、ASR、ZIP import、文件夹 export、外部 vector database、复杂后台队列、多用户/协作、云同步、订阅/账户系统。

## 每个 TODO 的交付模板

1. 代码实现；
2. 单元/集成测试；
3. API 输入和失败边界；
4. 浏览器用户路径（若有 UI）；
5. 安全性检查；
6. 文档/状态同步；
7. 可复现命令或测试 artifact。
