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

## 已交付能力与基础设施状态

以下内容是当前项目主 Phase 4 之前已经交付的能力层，不使用独立 Phase 编号，避免与当前项目主路线混用。

### 文件材料基础设施（v1 范围已交付）

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

### 可靠性、安全与一致性（基础边界已实现）

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

### Operator 备份与恢复（手工基础能力已实现）

**状态：手工基础能力 `implemented`；不是完整备份运维体系。**

- SQLite Online Backup API。
- hash-verified originals snapshot 和 versioned manifest。
- `backup`、`verify-backup`、`restore --confirm` CLI。
- restore staging、恢复前后验证、仅允许不存在或空目标目录。
- 稳定错误码；不自动 repair、rebuild 或启动服务。

**待补：** 定期备份、保留策略、恢复演练、corruption quarantine、read-only mode、管理修复工具。

### AI / 学习架构设计（规划和 Phase 4 前置）

**状态：架构设计已记录；其中 Phase 4 所需的 revision/chunk/retrieval/citation/Q&A 设计已经实现，真实 provider 和后续学习能力仍属于后续项目 Phase。**

已定义：

- Provider Protocol、registry、fake provider contract 和稳定错误码。
- material revision、chunk、chunk span 数据模型。
- SQLite FTS5 lexical retrieval first。
- retrieval run/hit、context assembly、citation verification。
- ai operation、Q&A、cards、exercises、study plans 的生命周期和数据模型。
- embedding/hybrid retrieval 的后续演进边界。
- 用户确认的 draft 原则：AI 不得静默覆盖用户内容。

设计依据见 [`ai-learning-architecture.md`](ai-learning-architecture.md)。

## 当前主 Phase 与后续路线

### Phase 4：AI 最小闭环

**状态：已完成；deterministic fake provider 下的可信 Q&A 用户闭环、浏览器验收和文档证据已收口。**

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
9. Q&A API、回答持久化、citation 持久化和最小 UI；同步 `POST /api/qa/ask`、thread/message/answer/citation persistence、当前材料 Q&A UI、citation 定位、purge unavailable lifecycle 与 browser/backup-restore 验收已实现；
10. API/repository/failure/browser 验收和文档同步。

**当前进度：** lexical chunk retrieval、retrieval_runs / retrieval_hits、context assembly、citation contract、deterministic fake provider、同步 Q&A API/persistence、Q&A thread/history API、单材料和多材料 Q&A UI、citation 详情与跨材料定位、purge 后历史 citation unavailable lifecycle、统一 loading/empty/error/success/retry 状态、toast、响应式/键盘基础支持、backend 全套测试和 Chromium E2E 均已实现并验证。

**Phase 4 完成结论：** deterministic fake provider 下已完成导入 → indexing → 检索 → 问答 → citation → 原文定位完整用户路径；citation 可追溯到 material/revision/chunk/span；deleted/stale source 被排除；purge 后历史 citation 标记 `source_unavailable`；未配置 provider 时应用正常启动并安全失败；失败、重复点击和过期响应不破坏 UI；桌面和窄屏路径通过当前浏览器验收。Phase 4 已完成，下一阶段为 Phase 5：真实 Provider 接入。

### Phase 5：真实 Provider 接入

**状态：DeepSeek 官方 API-level 与 Chromium UI/E2E opt-in smoke 已通过；其它 Provider 验证仍待完成。**

- 通用 OpenAI-compatible `LLMProvider` adapter 与 registry 已实现，保留 deterministic fake provider。
- 环境变量配置、URL 校验、API key 内存隔离、timeout、prompt/output 硬上限和默认不 retry 已实现。
- `GET /api/ai/capabilities` 已接入真实配置，不能返回 secret。
- timeout、rate limit、auth、forbidden、unavailable、malformed response、schema mismatch、refusal、output limit 有稳定错误映射。
- provider/model/provider request ID/usage/latency/finish reason 已接入 v3 migration 和 `ai_operations`；v4 增加显式 `Idempotency-Key` 与 retrieval run 关联，用于同步成功 replay。
- mock HTTP、配置脱敏、响应体上限、retry、citation 缺失/伪造和错误边界测试已通过。
- DeepSeek 官方 `deepseek-chat` 已完成三类受控真实 smoke：adapter-level、完整 API-level（synthetic material → indexing → retrieval → Q&A → citation validation → metadata persistence）和 Chromium UI/E2E（回答、citation 展示与原文定位）。
- UI failure contract 已覆盖 timeout、rate-limit、unavailable、retry、重复点击和安全错误渲染。
- 显式 `Idempotency-Key` 已实现同步 Q&A 成功重放、running 冲突、失败后重试和请求触发的 stale recovery：超过 5 分钟 lease 的 `running` operation 被保守标记 `stale/qa_operation_stale`，不删除审计消息，同 key 可重新执行；不将无 key 的相同问题视为重复请求。后台扫描、cancel、跨进程协调和真实断电恢复仍未实现。
- ARK、硅基流动、Agnes AI-Hub、Sub2API 已建立独立脱敏 capability matrix 和 opt-in 验收命令；API/UI smoke 强制 explicit target 与 runtime provider 匹配，避免将默认 Provider 结果错误归因。通用三次 API acceptance runner 会为每次尝试创建独立 temporary data root，达到 2 次 pass/fail 时 early-stop；其 `2/3` 结论不替代 UI evidence，且本次实现未执行新真实验收。Agnes `advanced`/`agnes-2.5-flash` 已通过独立 adapter/API/UI 真实 smoke；`pro`/`agnes-2.5-pro` API 返回 `provider_unavailable`、UI 未运行，仍为 `not_verified`。ARK、硅基流动和 Sub2API 仍待独立验证。

> 真实 provider 很重要，但 revision/chunk/retrieval/citation 才是可信 Q&A 的内部前置条件；不得让厂商 API 接入阻塞 Phase 4 架构验收。

### Phase 6：AI MVP 产品化与整体验收

**状态：P6-A Provider 运行契约和状态可见性、P6-B Q&A Thread 工作区、P6-C 跨材料浏览和引用/导出衔接、P6-D 统一导航/通知/响应式/可访问性已完成；P6-E fake Provider 核心工作流整体验收和失败矩阵已完成，DeepSeek/Agnes 本轮真实 UI 路径未执行。依赖 Phase 4 Q&A 闭环和 Phase 5 真实 Provider 接入。**

P6-A 已明确默认运行状态为 `not_configured`，显式 `fake` 为 deterministic/demo，generic OpenAI-compatible 配置为 `configured` + `unverified`；`GET /api/ai/capabilities` 和 UI 已统一安全状态语义。capabilities 不执行网络 health probe，真实 Provider verified 仍仅按精确 provider/model/gateway 的既有 evidence 判定。

P6-B 已完成 thread 列表/状态、创建/切换/继续提问、用户和回答时间线、citation/source unavailable 展示、scope/request stale-response 防护、显式 Idempotency-Key 传递和非敏感 thread ID 刷新恢复。thread scope 尚未持久化；同步 Provider HTTP 请求不能被真正取消，切换 thread 只忽略旧响应。

P6-C 已完成材料列表/详情进入 Q&A、单材料和多材料 scope 上下文、URL/history 中的非敏感 material/thread/scope/citation 标识、citation 到 revision/chunk/span/正文定位、返回 Q&A、正文/原文件导出连续流程，以及 deleted/purged/stale citation 的 unavailable contract。citation detail 仅返回安全材料名称和定位标识；purge 后材料名称不可恢复并返回 null，不伪造来源。未新增 migration。

P6-D 已完成统一 header/nav、当前材料/thread/scope/view 状态、页面级 status/alert 与补充 toast、Provider/导入/导出/问答失败状态表达、按钮禁用和 retry 反馈、窄屏布局稳定性、可见焦点、键盘视图切换、citation dialog Escape/focus return、landmark/heading/label/button/list/status/alert/dialog 语义。未新增 API 或 migration；使用 Playwright/DOM contract 断言，没有引入 axe。fake Provider 下 P6-D 专项 Chromium 2 passed，完整 backend 200 passed/2 skipped；真实 Provider、系统级 screen reader、长时整批 Chromium 的单次稳定性仍不宣称 real-pass。

P6-E 已完成 fake Provider 的导入 → ready → 显式 indexing → retrieval → thread → Q&A → citation → 正文定位 → 返回材料详情/Q&A → 导出 → refresh/history 连续路径，以及 retrieval empty、未配置 Provider、timeout/retry、duplicate click、in-flight thread stale response、deleted source/export disabled、network/rate-limit/unavailable 和相关安全错误回归。新增 `backend/tests/browser_p6e.spec.js` 与默认 skip 的 `browser_p6e_real_provider.spec.js`；focused P6-E 4 passed，相关 Chromium 19 passed/3 skipped，focused backend 47 passed/2 skipped，完整 backend 200 passed/2 skipped。DeepSeek `deepseek-chat` 和 Agnes `agnes-ai-hub`/`agnes-2.5-flash` 的本轮 P6-E real UI path 因未提供显式运行 gate 为 not_verified；详见 `docs/P6E_ACCEPTANCE_EVIDENCE.md`。未新增 API 或 migration。

Phase 4 已负责 fake provider 下 Q&A 的完整可验收用户路径。Phase 6 不重复定义历史、材料范围、citation 定位或基础 loading/error 任务，而是在真实 Provider 接入后完成产品级整合：

- 真实 provider 下的端到端回归和 provider failure UX 验收；
- 更完整的 Q&A thread 工作区、跨材料浏览和导出衔接；
- 统一应用级组件、导航、通知、可访问性和响应式体验；
- 导入 → 检索 → 问答 → 引用 → 导出核心工作流的整体验收；
- 高延迟、离线、长回答和真实 provider 限制下的前端体验收口。

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
→ Phase 4：AI 最小闭环（fake provider）✅ 已完成
→ Phase 5：真实 provider【当前最高优先级】
→ Phase 6：AI MVP 产品化与整体验收
→ Phase 7：embedding / hybrid retrieval（按需）
→ Phase 8：卡片与练习
→ Phase 9：学习计划 / S1–S7
→ Phase 10：后台任务、生产化、多用户和扩展
```

## 基础设施基本完工声明门槛

完成 I3，且 I4 已形成实测结果或明确未验证边界后，可以宣告：

> 本地单进程文件材料基础设施 v1 基本完工，支持 versioned migration、手工 backup/restore 和已声明的 local-disk/single-instance 运行边界。

这不是全局生产级完成，也不代表真实 Provider、Embedding、Cards、Exercises 或学习计划已实现；当前项目 Phase 4 的 deterministic fake provider Q&A 已按独立完成标准验收。

## 不应作出的当前声明

- 不宣称全局生产级 `real-pass`。
- 不宣称已实现真实 Provider、Embedding、Cards、Exercises、学习计划或 S1–S7；Phase 4 的 deterministic fake provider Q&A 已实现并通过对应验收。
- 不宣称支持多进程、多实例共享 `data_root`。
- 不宣称覆盖真实断电、磁盘损坏、网络盘、真实磁盘满或容量压力。
