# StudyBuddy Phase 路线图与进度报告

> 更新：2026-08-30（Phase 9A acceptance closeout 后）
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
| 前端体验 | 60%–70% | Materials、Q&A 和 Cards/Exercises 的受限工作区已有 Chromium 路径；不是完整产品前端 |
| AI / 学习产品能力 | 40%–50% | Q&A、retrieval 和 Phase 8 fake-provider Cards/Exercises 闭环已完成；真实 Provider generation、计划和后台任务未完成 |
| **项目整体（功能加权估算）** | **55%–60%** | 不是测试通过率，不能标记为全局 `real-pass` |

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

**状态：P6-A Provider 运行契约和状态可见性、P6-B Q&A Thread 工作区、P6-C 跨材料浏览和引用/导出衔接、P6-D 统一导航/通知/响应式/可访问性已完成；P6-E fake Provider 核心工作流、失败矩阵以及 DeepSeek `deepseek-chat` 和 Agnes `agnes-2.5-flash` 的精确真实 UI 路径均已通过。其它 Provider/model 和系统级辅助技术仍未完成独立验收。依赖 Phase 4 Q&A 闭环和 Phase 5 真实 Provider 接入。**

P6-A 已明确默认运行状态为 `not_configured`，显式 `fake` 为 deterministic/demo，generic OpenAI-compatible 配置为 `configured` + `unverified`；`GET /api/ai/capabilities` 和 UI 已统一安全状态语义。capabilities 不执行网络 health probe，真实 Provider verified 仍仅按精确 provider/model/gateway 的既有 evidence 判定。

P6-B 已完成 thread 列表/状态、创建/切换/继续提问、用户和回答时间线、citation/source unavailable 展示、scope/request stale-response 防护、显式 Idempotency-Key 传递和非敏感 thread ID 刷新恢复。thread scope 尚未持久化；同步 Provider HTTP 请求不能被真正取消，切换 thread 只忽略旧响应。

P6-C 已完成材料列表/详情进入 Q&A、单材料和多材料 scope 上下文、URL/history 中的非敏感 material/thread/scope/citation 标识、citation 到 revision/chunk/span/正文定位、返回 Q&A、正文/原文件导出连续流程，以及 deleted/purged/stale citation 的 unavailable contract。citation detail 仅返回安全材料名称和定位标识；purge 后材料名称不可恢复并返回 null，不伪造来源。未新增 migration。

P6-D 已完成统一 header/nav、当前材料/thread/scope/view 状态、页面级 status/alert 与补充 toast、Provider/导入/导出/问答失败状态表达、按钮禁用和 retry 反馈、窄屏布局稳定性、可见焦点、键盘视图切换、citation dialog Escape/focus return、landmark/heading/label/button/list/status/alert/dialog 语义。未新增 API 或 migration；使用 Playwright/DOM contract 断言，没有引入 axe。fake Provider 下 P6-D 专项 Chromium 2 passed，完整 backend 200 passed/2 skipped；真实 Provider、系统级 screen reader、长时整批 Chromium 的单次稳定性仍不宣称 real-pass。

P6-E 已完成 fake Provider 的导入 → ready → 显式 indexing → retrieval → thread → Q&A → citation → 正文定位 → 返回材料详情/Q&A → 导出 → refresh/history 连续路径，以及 retrieval empty、未配置 Provider、timeout/retry、duplicate click、in-flight thread stale response、deleted source/export disabled、network/rate-limit/unavailable 和相关安全错误回归。新增 `backend/tests/browser_p6e.spec.js` 与默认 skip 的 `browser_p6e_real_provider.spec.js`；focused P6-E 4 passed，相关 Chromium 19 passed/3 skipped，focused backend 47 passed/2 skipped，完整 backend 200 passed/2 skipped。DeepSeek `deepseek-chat` 和 Agnes `agnes-ai-hub`/`agnes-2.5-flash` 的本轮 P6-E real UI path 已在各自显式运行 gate 下通过；详见 `docs/P6E_ACCEPTANCE_EVIDENCE.md`。未新增 API 或 migration。

Phase 4 已负责 fake Provider 下 Q&A 的完整可验收用户路径。P6-A–P6-E 已完成产品化验收，其中 P6-E 以 fake Provider 为默认可重复路径，并以显式 target/provider/model/gateway gate 管理真实 Provider evidence。DeepSeek 和 Agnes 的精确真实 Provider UI gate 已通过；系统级 screen reader、真实 offline、极端长回答和长时稳定性继续标记为 `not_verified`，不能被宣称为全局 real-pass。

### Phase 7：Embedding 与 Hybrid Retrieval

**状态：completed（精确配置范围）。7.1–7.7 fake/backend 主体、专项 backup/restore、synthetic benchmark、retrieval mode Chromium UI、indexing lease/失败重试/恢复专项，以及 Mistral `mistral-embed` 外部真实 embedding acceptance 均已完成。该 completed 结论仅适用于明确的 provider/model/gateway 配置，不代表通用多 Provider 或全局生产级 real-pass。**

- 已完成：审计 `embeddings`、retrieval run/hit、chunking、migration 和 backup/restore 边界；冻结 embedding identity、status/stale、lexical/vector/hybrid/fallback 语义，以及连续 v5 migration 要求。正式记录见 [`PHASE7_1_AUDIT_AND_CONTRACT.md`](PHASE7_1_AUDIT_AND_CONTRACT.md)。
- 已实现：v5 embedding schema migration、非 NULL model revision、status CHECK/updated_at/完整 identity 唯一约束；版本化离线 deterministic fake embedding、独立 registry、embedding 环境配置、canonical identity/stale 判定、f32 little-endian codec、显式增量 indexing、显式 material rebuild/retry、只读 verify 报告、vector cosine API 最小路径和安全 capabilities 扩展。
- 已实现：Q&A 显式 lexical/vector/hybrid mode、hybrid fallback、retrieval policy/operation/answer linkage、replay metadata 和 citation-safe context path；不新增 migration，复用 v5 embedding 与现有 Q&A/citation schema。
- 已完成：embedding/retrieval/Q&A metadata backup/restore 专项、损坏 payload/lifecycle 验收、102/1,002 chunks synthetic benchmark、完整 backend regression。
- 已完成：独立 OpenAI-compatible embedding adapter、环境配置、secret 隔离、`/embeddings` 请求契约、稳定 HTTP/timeout/schema/vector/response-size 错误映射；loopback protocol tests 已通过，但不等于外部真实 Provider real-pass。
- 已完成：retrieval mode UI/Chromium final acceptance，覆盖 lexical/vector/hybrid、hybrid lexical fallback、vector 不自动 fallback 和安全错误显示。
- 已完成：indexing lease、`embedding_index` operation 审计、stale lease reclaim、失败错误码保留和显式 retry_count/retry 路径；仍是同步单进程流程，不宣称后台 worker、cancel 或跨进程恢复。
- 已完成：Mistral `mistral` / `mistral-embed` / `https://api.mistral.ai/v1` 精确外部真实 embedding gate；直接请求返回 1024 维向量，隔离 StudyBuddy data root 的 indexing 写入 `ready`，vector retrieval 返回 `succeeded`，provider/model/retrieval/index operation 审计一致。证据见 [`PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md`](PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md)。
- 未通过的候选不替代 Mistral gate：Agnes `agnes-2.5-flash` 返回 `embedding_provider_protocol_error`，ARK `deepseek-v4-flash` 返回 `embedding_provider_invalid_config`，MiniMax `embo-01` 返回 `embedding_schema_mismatch`，NVIDIA `nvidia/nv-embedqa-e5-v5` 返回 `embedding_provider_protocol_error`。
- Phase 7 completed 仅表示上述精确配置范围；不宣称其它 embedding model、通用多 Provider、配额/质量/可用性或全局生产级 real-pass。
- 规模充分前不引入外部 vector database。

### Phase 8：卡片与练习

**状态：completed（deterministic fake-provider / local Chromium / backup-restore 精确范围）。** v7/v8 migration、Cards/Exercises lifecycle、citation-safe fake-provider draft generation、workspace、append-only review/attempt、deterministic grading、source lifecycle、backup/restore 和完整回归已收口。证据见 [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)。这不表示真实 Provider generation 或全局 Cards/Exercises `real-pass`。

- v7 已通过 migration 增加 Card/Exercise 业务表；v8 记录 exercise provenance，保持 migration history 与 `user_version` 一致。
- Exercises 支持 `multiple_choice`、`true_false`、`short_answer`，draft → ready/rejected/archived、draft-only edit、append-only attempts、MC/TF deterministic grading 和 short-answer `pending_review`。
- AI exercise 必须从 draft 开始，必须绑定 current active revision 和 valid citation；confirm 会重新验证 citation，delete/restore/purge/re-index 会更新 citation lifecycle。
- 普通 exercise 和 attempt history 响应不返回 answer key 或用户提交原文。
- 显式 indexed single-material scope 的 lexical/vector/hybrid retrieval → context → provider → server-side citation revalidation → atomic draft/operation persistence 已实现；结构化 provider output 只在内存校验，raw prompt/response 不持久化，失败只保留安全 operation。fake-provider workspace 与 Chromium 路径覆盖 draft generation/list/detail/edit/confirm/reject/archive、citation location/unavailable、review/attempt、refresh、failure retry、privacy、窄屏和键盘基础 contract。8.6 还验证了 draft/ready/rejected/archived artifact、citation、review、attempt 和 operation 的 backup → verify → 新空目录 restore，且 restore/startup 不 repair、rebuild 或提升 unavailable 状态。真实 Provider generation、系统级 screen reader/极端内容和人工简答复核仍未实现；不允许重新生成静默覆盖用户已编辑或已确认状态。

### Phase 9：学习产品构建计划（拆分为 9A–9D）

**状态：未开始；不得把 Phase 9 作为单一交付承诺。**

Phase 9 原先同时承载学习计划和 S1–S7 七个业务子系统，范围过宽，无法用一个统一的完成标准、数据模型、用户路径或验收周期证明完成。Phase 9 现在是一个路线族，必须按以下独立 gate 顺序推进；每个子阶段都要单独更新代码、migration、测试、浏览器路径、artifact、状态和文档。

- **Phase 9A：学习领域基础与计划核心**：状态为 `completed`，范围限定为 deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore。9A-0 `planned/audit-draft`、9A-1 `planned/contract-frozen`、9A-2/9A-3/9A-4 `implemented/backend-pass`、9A-5 `browser-pass`、9A-6 `scoped-gates-pass`、9A-7 `restore-gates-pass` 和 9A-8 closeout 均已形成证据。v9 schema、repository/domain transactions、DAG、append-only progress/projection、source identity validation、最小 API、稳定错误、输入边界、本地 Chromium 计划 workspace、delete/restore/purge/re-index source lifecycle 和 backup/verify/restore non-repair 已通过各自 scoped gates。该完成声明不包含 Phase 9B–9D、Phase 9 全部能力或全局 production `real-pass`；最终证据见 [`PHASE9A_ACCEPTANCE_EVIDENCE.md`](PHASE9A_ACCEPTANCE_EVIDENCE.md)。充分上下文、总规划、子任务切分和逐任务执行 prompts 见 [`phase9a/`](phase9a/)。
- **Phase 9B：资料学习工作流（S1/S2）**：总体仍为 `planned`；9B-0 已完成 `planned/audit-draft`，9B-1 已完成 `planned/contract-frozen`，9B-2 与 9B-3 已完成 `implemented/backend-pass`。正式契约见 [`phase9b/PHASE9B_DOMAIN_CONTRACT.md`](phase9b/PHASE9B_DOMAIN_CONTRACT.md)：连续 v10 `phase9b_material_learning_schema` 已增加 note/block/module-link/source-tombstone 与 rhythm persistence schema，并通过 new-db、v9-upgrade、rollback、history/user_version 和 backup schema-version focused tests。9B-3 已在 `backend/app/repository.py` 实现共用 domain transaction 基础，并由 `backend/tests/test_phase9b_domain.py` focused gate 验证。API、UI、fake-provider generation workflow、导出、restore artifact acceptance 或正式用户路径仍未实现；schema/prompt/contract/domain 基础不是完整功能证据。实施时必须先复用已验证的 revision/chunk/retrieval/citation，不得把历史版本的 `KnowledgeModule` 设计直接视为正式实现。
- **Phase 9C：练习与反馈工作流（S3/S4/S5）**：限时练习、错题改错、期末冲刺。依赖 Phase 8 的 exercise/card 生命周期、attempt 历史和确定性评分边界；每个子系统仍需独立验收。
- **Phase 9D：扩展学习服务（S6/S7，条件性范围）**：家长报告、课堂采集/OCR/ASR。只有在用户需求、隐私边界、真实组件证据和运维成本明确后才立项；不因历史版本存在就自动纳入正式范围。

Phase 9A 已在明确范围内完成；Phase 9B–9D 仍是独立的 planned work。每个后续子阶段完成后才能进入下一个；Phase 9 全部完成也不等于全局生产级 `real-pass`。

### Phase 10：后台任务、生产化与扩展

**状态：未开始；在 MVP 和学习业务边界验证后分阶段推进。**

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
→ Phase 5：真实 provider adapter 与精确 smoke evidence ✅ 已完成既有 DeepSeek/Agnes 精确证据
→ Phase 6：AI MVP 产品化与整体验收（P6-A–P6-E）✅ fake/default/UI acceptance 已完成，精确 P6-E real UI path 按 gate 运行
→ Phase 7：embedding / hybrid retrieval（按需，下一产品阶段）
→ Phase 8：卡片与练习
→ Phase 9A：学习领域基础与计划核心
→ Phase 9B：资料学习工作流（S1/S2）
→ Phase 9C：练习与反馈工作流（S3/S4/S5）
→ Phase 9D：扩展学习服务（S6/S7，条件性）
→ Phase 10：后台任务、生产化、多用户和扩展
```

## 基础设施基本完工声明门槛

完成 I3，且 I4 已形成实测结果或明确未验证边界后，可以宣告：

> 本地单进程文件材料基础设施 v1 基本完工，支持 versioned migration、手工 backup/restore 和已声明的 local-disk/single-instance 运行边界。

这不是全局生产级完成，也不代表真实 Provider、Embedding、Cards、Exercises 或学习计划已实现；当前项目 Phase 4 的 deterministic fake provider Q&A 已按独立完成标准验收。

## 不应作出的当前声明

- 不宣称全局生产级 `real-pass`。
- 不宣称所有真实 Provider、Embedding、Cards、Exercises、学习计划或 S1–S7 已实现；DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 已有各自精确 API/UI smoke evidence；其它 Provider/model 仍需独立验证。Phase 4 fake Provider Q&A 与 P6-E fake 核心工作流已通过对应验收。
- 不宣称支持多进程、多实例共享 `data_root`。
- 不宣称覆盖真实断电、磁盘损坏、网络盘、真实磁盘满或容量压力。
- 不宣称历史版本已有的学习功能已经被正式系统吸收；当前 StudyBuddy 在治理、可靠性、资料生命周期和可信 Q&A 基础上进化，但产品功能宽度仍未全面超过前代版本。
- 不把 Phase 9 作为单一“大业务建设阶段”；9A–9D 必须分别立项、实现和验收。
