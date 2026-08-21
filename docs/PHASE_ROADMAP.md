# StudyBuddy Phase 路线图与进度报告

> 更新：2026-08-25（I4 时间盒收口、基建 v1 基本完工后）  
> 本文是项目按 Phase 管理的长期路线图和优先级记录。实现、测试和验收状态以 `STATUS.md` 为准；可执行勾选项以 `TODO.md` 为准。
>
> `real-pass` 只表示有真实用户路径和验收证据的局部能力通过，**不代表整个 StudyBuddy 已达到全局生产级 real-pass**。

## 基础设施真实状态

基础设施的 I1 migration/schema versioning、I2 backup/restore 运维闭环、I3 最小可观察性与 I4 真实环境/容量基线（时间盒）均已完成；StudyBuddy 本地单进程文件材料基础设施 v1 已基本完工。I1 是 AI Phase 4 的硬前置，已满足；I4 的未验证边界已明确记入 v1 运行限制，并作为已知限制持续记录。准确范围见 [`INFRASTRUCTURE_CLOSEOUT.md`](INFRASTRUCTURE_CLOSEOUT.md)。

## 总体进度

| 评估维度 | 完成度 | 说明 |
|---|---:|---|
| 本地单进程基础设施 | 90%–95% | 导入、SQLite、storage、一致性、恢复、migration、backup/restore 和启动安全已具备；I4 已时间盒验收 |
| 文件材料管理 | 80%–85% | 当前最成熟，核心路径为局部 `real-pass` |
| 前端体验 | 45%–55% | 内嵌可用单页，不是完整产品前端 |
| AI / 学习产品能力 | 25%–35% | 目前仅完成架构设计，未形成用户功能 |
| **项目整体（功能加权估算）** | **45%–50%** | 不是测试通过率，不能标记为全局 `real-pass` |

## 阶段状态（不等于“Phase 已全部完成”）

以下 Phase 只表示其**已定义的第一版范围**已经交付或形成设计结论；它们仍有明确缺口，不能据此宣称基础设施、可靠性、运维或 AI 架构已经最终完成。

### Phase 0：文件材料基础设施（v1 范围已交付）

**状态：v1 范围完成；核心用户路径局部 `real-pass`；不是完整文件平台。**

- 文件解析 Adapter：TXT、Markdown、PDF、DOCX、PPTX。
- RTF、旧 DOC、旧 PPT 明确拒绝。
- SHA-256 内容身份和 hash-derived original storage。
- 临时文件、原子替换、上传大小限制与路径安全。
- SQLite：materials、extractions、text_spans、FTS5 material_search。
- 单文件、多文件 batch、文件夹选择导入。
- 材料列表、详情、状态筛选、稳定分页。
- rename、逻辑 delete、回收站、restore、deleted-only purge。
- FTS5 词法搜索、中文/特殊字符安全 fallback、snippet 隐私边界。
- 单材料原文件/正文导出和批量 ZIP 导出。
- 真实 Chromium 导入、管理、搜索和导出验收。

**明确未包含：** OCR、ASR、ZIP import、旧格式转换、文件夹 export、语义/向量/AI 搜索。

### Phase 1：可靠性、安全与一致性（基础边界已实现）

**状态：基础边界 `implemented`；不是生产级可靠性完成，也不是整体 `real-pass`。**

- startup preflight：拒绝 symlink、非法 data/database topology 和非法配置。
- ready/health 生命周期边界。
- SQLite integrity / foreign key / required object diagnostic audit。
- startup recovery：stale temp、严格 orphan original、missing original detection-only。
- material / extraction / spans / FTS 同事务和 rollback。
- storage containment、regular-file、symlink、hash mismatch 安全边界。
- 同进程 shared-hash keyed lock、purge/import race 防护。
- SQLite write contention 的 controlled `BEGIN IMMEDIATE` 验证。
- controlled subprocess crash/restart recovery。
- lifecycle invariant、API input boundary、frontend mutation/export failure contract。

**明确限制：** 不支持多进程、多 worker 或多实例共享同一个 `data_root`；真实磁盘满、断电、硬件/文件系统损坏、网络盘、真实 ACL、性能或容量极限已记录为 `not_verified`，作为 v1 运行边界接受。

### Phase 2：Operator 备份与恢复（手工基础能力已实现）

**状态：手工基础能力 `implemented`；不是完整备份运维体系。**

- SQLite Online Backup API。
- hash-verified originals snapshot 和 versioned manifest。
- `backup`、`verify-backup`、`restore --confirm` CLI。
- restore staging、恢复前后验证、仅允许不存在或空目标目录。
- 稳定错误码；不自动 repair、rebuild 或启动服务。

**待补：** 定期备份、保留策略、恢复演练、corruption quarantine、read-only mode、管理修复工具。

### Phase 3：AI / 学习架构设计（规划阶段）

**状态：架构设计已记录；`researching / architecture-only`，不属于已实现的产品 Phase，也无真实 AI 功能。**

已定义：

- Provider Protocol、registry、fake provider contract 和稳定错误码。
- material revision、chunk、chunk span 数据模型。
- SQLite FTS5 lexical retrieval first。
- retrieval run/hit、context assembly、citation verification。
- ai operation、Q&A、cards、exercises、study plans 的生命周期和数据模型。
- embedding/hybrid retrieval 的后续演进边界。
- 用户确认的 draft 原则：AI 不得静默覆盖用户内容。

设计依据见 [`ai-learning-architecture.md`](ai-learning-architecture.md)。

## 急需完成的 Phase

### Phase 4：AI 最小闭环

**状态：已开始；revision/chunk 显式 indexing 已实现，当前继续推进 chunk retrieval、citation 和可信 Q&A 业务闭环。**

**目标：** 用户针对已导入材料提问，系统通过可追溯检索返回带可验证来源引用的回答。第一轮可使用 deterministic fake provider，不以接入某家真实模型为前置条件。

推荐依赖顺序：

```text
migration / schema versioning
→ material revision
→ deterministic chunking
→ chunk FTS5 lexical retrieval
→ citation contract + context assembly
→ fake provider
→ Q&A API
→ 最小 Q&A UI
```

必须交付：

1. 已完成 migration runner、schema version、migration history 和失败边界；后续 AI 表变更仍必须继续通过 migration；
2. `material_revisions`、`chunks`、`chunk_spans` 已有 migration 且业务 indexing 已实现；
3. deterministic chunker 已实现，覆盖中文/Unicode offset 和现有 text_spans 的 page/slide/document 顺序映射；
4. chunk FTS5、top-k、确定性排序、active/current/ready 过滤已实现；
5. `retrieval_runs` / `retrieval_hits` 和 `retrieval_empty` 已实现；
6. citation 只能来自 retrieval/context 的可验证 key，不能信任模型自造引用；已实现 `ctx-{mid8}-{cid8}` 格式和 `validate_citation_key`。
7. context token budget 和 source text 不可信边界；已实现 context assembler 截断逻辑。
8. deterministic fake provider、`provider_not_configured`；已实现 provider registry、fake provider 和 capabilities API。
9. Q&A API、回答持久化、citation 持久化和最小 UI；
10. API/repository/failure/browser 验收和文档同步。

**当前进度：** lexical chunk retrieval、retrieval_runs / retrieval_hits、context assembly、citation contract 和 deterministic fake provider 已实现；Q&A 仍未实现。

**完成标准：** fake provider 下完成端到端问答；每个展示的 citation 都能回到 material/chunk/span；deleted/stale source 被排除；purge 后历史 citation 标记 `source_unavailable`；未配置 provider 时应用照常启动且安全失败。

### Phase 5：真实 Provider 接入

**状态：未开始；在 Phase 4 的内部可信链路通过后执行。**

- 正式 `LLMProvider` / `EmbeddingProvider` adapter 与 registry。
- 环境变量配置、timeout、output limits。
- `GET /api/ai/capabilities`，不泄露 secret。
- timeout、rate limit、auth、quota、unavailable、malformed response、refusal 的稳定错误映射。
- provider/model/request ID/usage/latency metadata。
- provider secret 和原始异常不进入日志、数据库、manifest 或前端。

> 真实 provider 很重要，但 revision/chunk/retrieval/citation 才是可信 Q&A 的内部前置条件；不得让厂商 API 接入阻塞 Phase 4 架构验收。

### Phase 6：AI MVP 前端与整体验收

**状态：未开始。**

- Q&A thread、材料范围选择、回答加载/失败/retry。
- citation 来源标记、原文定位和 source unavailable 状态。
- 统一 loading / empty / error / success、toast 和安全错误提示。
- 基础响应式布局、键盘操作、可访问性基线。
- 导入 → 检索 → 问答 → 引用 → 导出等核心 E2E 验收。

### Phase 7：Embedding 与 Hybrid Retrieval

**状态：延后；按规模和质量证据决定。**

- embedding provider、content hash、embedding stale semantics。
- SQLite embedding payload 或明确的外部索引 manifest/rebuild/verify 机制。
- lexical + vector hybrid retrieval、rerank。
- 规模充分前不引入外部 vector database。

### Phase 8：卡片与练习

**状态：延后。**

- AI 卡片和练习只能先生成 draft。
- citation、schema validation、用户编辑保护。
- card review、exercise attempt、deterministic grading。
- 不允许重新生成静默覆盖用户已编辑或已确认状态。

### Phase 9：学习计划与 S1–S7

**状态：延后。**

- study plan / item：draft → confirm → active。
- 进度、依赖、完成记录和 source unavailable。
- 先明确 S1–S7 的产品范围，再分批实现。

### Phase 10：后台任务、生产化与扩展

**状态：未开始；在 MVP 验证后分阶段推进。**

- ai operation worker、任务状态、progress、retry、cancel、长任务恢复。
- structured logging、metrics、request/operation tracing、degraded readiness。
- migration 运维、backup 保留、restore 演练、corruption 流程。
- 真实 ACL、磁盘满、容量、长时间压力和性能验收。
- 多用户、认证授权、项目隔离、跨进程协议、云同步、协作。

## 固定执行顺序

```text
I4：真实环境与容量基线（时间盒） ✅ 已验收
→ 本地单进程基础设施 v1 基本完工 ✅ 已宣告
→ Phase 4：AI 最小闭环（fake provider）【当前最高优先级】
→ Phase 5：真实 provider
→ Phase 6：AI MVP 前端和整体验收
→ Phase 7：embedding / hybrid retrieval（按需）
→ Phase 8：卡片与练习
→ Phase 9：学习计划 / S1–S7
→ Phase 10：后台任务、生产化、多用户和扩展
```

## 基础设施基本完工声明门槛

完成 I3，且 I4 已形成实测结果或明确未验证边界后，可以宣告：

> 本地单进程文件材料基础设施 v1 基本完工，支持 versioned migration、手工 backup/restore 和已声明的 local-disk/single-instance 运行边界。

这不是全局生产级完成，也不代表 AI、Q&A、Cards 或 Exercises 已实现。

## 不应作出的当前声明

- 不宣称全局生产级 `real-pass`。
- 不宣称已实现 AI、RAG、Q&A、卡片、练习、学习计划或 S1–S7。
- 不宣称支持多进程、多实例共享 `data_root`。
- 不宣称覆盖真实断电、磁盘损坏、网络盘、真实磁盘满或容量压力。
