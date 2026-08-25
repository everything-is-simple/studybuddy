# StudyBuddy 项目进度报告

> 更新日期：2026-08-30（Phase 9A acceptance closeout 后）
> 
> 本报告依据当前正式代码、测试证据和项目决策文档整理。`real-pass` 只表示对应局部用户路径和验收证据通过，不代表整个 StudyBuddy 已达到生产级或全局 `real-pass`。

## 一、当前总进度

### 结论

StudyBuddy 的**本地单进程文件材料基础设施 v1 已基本完工**，当前是一个可靠的本地单进程文件材料管理基础系统，可作为 AI MVP 的数据基础；但完整 AI 学习产品尚未实现。

| 评估口径 | 当前完成度 | 结论 |
|---|---:|---|
| 本地单进程基础设施 | 90%–95% | 导入、SQLite、Storage、一致性、恢复、migration、backup/restore 和启动保护已具备；I4 已时间盒验收 |
| 文件材料管理子系统 | 80%–85% | 当前完成度最高，主要用户路径已局部 `real-pass` |
| SQLite/Storage 一致性 | 约 80% | 单机事务、FTS、生命周期和故障边界较完整 |
| 前端用户体验 | 60%–70% | P6-A–P6-E fake/default/narrow/keyboard/accessibility contract 已通过；真实 Provider UI、系统级辅助技术和极端运行条件仍有限制 |
| AI/学习产品能力 | 40%–50% | Q&A、Provider adapter、Phase 7 retrieval，以及 Phase 8 Cards/Exercises 的 fake-provider backend/UI/backup-restore 闭环已完成；真实 Provider generation、计划和后台任务仍未完成 |
| 全项目整体 | 约 55%–60%（阶段性估算） | 该数字为功能加权估算，不是测试通过率；仍不得标记为全局 `real-pass` |

整体进度不应简单按“已通过测试数量”计算：当前可靠性投入较多，而 AI、学习工作流、多用户和运维能力尚未开始，因此产品整体完成度明显低于文件基础设施完成度。

## 二、已交付的阶段性范围

> 下列状态仅表示该阶段当前约定的第一版范围已经交付，或其设计已经沉淀；不表示对应领域已最终完成。特别是可靠性、备份恢复和 AI 架构均仍有后续 Phase。

### 已交付能力 0：工程边界与验证体系 — v1 范围已完成

- 正式产品目录、Composer、Integration、系统测试目录边界已确定。
- 正式实现不得直接依赖参考项目。
- 组件必须经过独立 smoke、组合测试和正式系统验证。
- 已形成架构边界、决策记录和脱敏测试 artifact 约束。

### 已交付能力 A：正式文件解析与存储基础 — v1 范围已完成 / 局部 real-pass

已完成：

- TXT、Markdown、PDF、DOCX、PPTX 解析。
- RTF、旧 DOC、旧 PPT 的明确拒绝及稳定错误码。
- SHA-256 内容身份与 hash-derived original storage。
- 临时文件、原子替换、大小限制和安全路径边界。
- SQLite schema、外键、WAL、busy timeout。
- extraction、text_spans 与 material 的事务写入。

局部 `real-pass` 已覆盖真实 Chromium 文件选择、解析成功/空文件/拒绝/失败、50 MiB 边界、重复 hash、刷新与重启回读。

### 已交付能力 B：文件导入与材料列表 — v1 范围已完成 / 局部 real-pass

- 单文件导入。
- 多文件 batch 导入。
- 每个文件独立事务，支持 partial success。
- 文件夹选择（Chromium `webkitdirectory`），不扫描服务器目录、不保存客户端路径。
- active、success、empty、rejected、failed 列表筛选。
- 材料详情、正文和 spans 回读。
- 分页、稳定排序、total/has_more。

### 已交付能力 C：材料生命周期、搜索与导出 — v1 范围已完成 / 局部 real-pass

- rename：只修改展示名称。
- delete：逻辑删除并进入回收站。
- restore：恢复 deleted material，不重新解析。
- purge：显式永久清理 deleted material，具备 shared hash 引用保护。
- SQLite FTS5 词法搜索、中文/特殊字符安全 fallback、多词 AND。
- 搜索结果 metadata、match_fields 和受限 snippet，不泄露完整正文或 stored_path。
- active 原文件下载、extraction text 导出。
- 批量 original/text/bundle ZIP 导出。
- 搜索、生命周期、分页和导出的真实浏览器验收。

尚未完成：语义搜索、向量检索、AI 搜索、搜索历史和 saved search。

### 已交付能力 D：可靠性、安全边界与 Operator 能力 — 基础版已实现（v1 边界内）

- 启动 preflight：配置、data root、originals root、database topology 和 symlink 拒绝。
- ready 生命周期与 health 503 边界。
- 一次性 SQLite diagnostic audit。
- 启动 recovery：stale temp、严格 orphan original 和 missing original detection-only。
- 导入/SQLite 写失败 cleanup 与 transaction rollback。
- process-local 同 hash 锁、生命周期竞态和 SQLite 写锁竞争验证。
- controlled subprocess crash/restart recovery。
- storage containment、symlink、hash mismatch 和 shared original 保护。
- API 输入边界矩阵。
- operator SQLite backup、original snapshot、manifest、verify 和显式 confirm restore。
- 前端 import、mutation、export failure contract、busy recovery 和 stale response protection。

限制：不支持多进程/多实例共用 data_root；真实磁盘满、断电、硬件/文件系统损坏、真实 ACL 和长时间压力等已明确记录为 `not_verified`，作为 v1 运行边界接受，不阻塞基础设施 v1 收口。

### 已交付能力 E：前端基础用户路径 — 部分完成，仍待产品化

已完成一个可用的内嵌单页路径：

- 文件、多文件、文件夹选择。
- 批量结果、列表、筛选、分页、搜索、详情。
- rename/delete/restore/purge。
- 原文件、正文和 ZIP 导出。
- busy guard、stale response guard 和安全 DOM 文本渲染。
- 多项真实 Chromium failure contract。

尚未达到完整产品前端：国际化、上传进度、loading skeleton、系统级 screen reader、真实 offline/极端长回答以及精确真实 Provider 下的 P6-E UI path 仍未全部验证；P6-D 已完成统一导航/通知/响应式/基础可访问性，P6-E 已完成 fake Provider 核心工作流和相关 failure/source lifecycle/竞态/导出 Chromium 验收。

## 三、尚未完成 Phase

### 当前 Phase 4：AI 最小闭环 — 已完成

已完成并由 backend tests 覆盖：

- source of truth、revision、deterministic chunk、chunk FTS5 retrieval、retrieval run/hit、context assembly、citation contract、provider 和 AI operation 的边界。
- deterministic fake provider、未配置 provider 的稳定 `provider_not_configured`，以及 capabilities API。
- 同步 `POST /api/qa/ask`：显式材料范围检索、server-side citation verification、thread/message/answer/citation/operation persistence 与 final-write rollback。
- 当前材料最小 Q&A UI：显式 indexing、loading/error/retry、citation 展示和 chunk offset 定位；purge 后历史 citation 标记 `source_unavailable`，并有 browser 与 backup/restore 验收。

Phase 4 已完成：完整 Q&A history/multi-material UX、citation 详情与跨材料导航、统一 loading/empty/error/success、toast/retry、响应式与基础可访问性，以及导入→检索→问答→引用的完整 Chromium E2E 均已通过。Phase 5 adapter 已实现，DeepSeek 官方 `deepseek-chat` 的 adapter-level、完整 API-level synthetic Q&A 和 Chromium UI/E2E smoke 已通过；Phase 8 已在 fake-provider backend/Chromium/backup-restore 的精确范围完成；真实 Provider generation 与人工简答复核仍待后续完成。

### Phase 7：Embedding 与 Hybrid Retrieval — completed（Mistral 精确配置范围）

7.2 已补齐 EmbeddingProvider protocol、独立 registry、版本化 deterministic fake provider 和独立 OpenAI-compatible embedding adapter；配置、secret 隔离、`/embeddings` 请求契约和稳定 HTTP/timeout/schema/vector/response-size 错误映射均已实现，loopback protocol tests 已通过。7.3 已补齐 canonical identity、f32le_v1 codec、payload malformed boundaries、stale/source-binding 判定和 ready-only vector guard；7.4 已补齐显式增量 indexing、material rebuild/retry、只读 verify、`embedding_index` operation lease、stale reclaim、失败审计和 retry_count；7.5 已补齐 vector cosine、固定 candidate pool、hybrid RRF、score persistence 和显式 lexical fallback；7.6 已将 lexical/vector/hybrid/fallback 接入 Q&A，保留 server-side context/citation verification、operation/retrieval linkage 和 replay metadata；retrieval mode UI/Chromium final acceptance 已覆盖 lexical/vector/hybrid、hybrid fallback 和 vector 不回退；7.7 已完成 fake/backend 最终回归、embedding/retrieval/Q&A metadata backup/restore、损坏生命周期测试和 102/1,002 chunks synthetic benchmark。完整 backend 为 231 passed/2 skipped，Phase 7 专项 Chromium 与 P6-E 回归通过。Mistral `mistral` / `mistral-embed` / `https://api.mistral.ai/v1` 已通过外部真实 embedding direct vector、隔离 indexing、vector retrieval 和审计 metadata gate，返回 1024 维向量；因此 Phase 7 在该精确配置范围 completed。Agnes、ARK、MiniMax、NVIDIA 候选未通过或未形成可验证 embedding evidence，不扩展为通用多-provider 或全局 production real-pass。

### Phase 8：Cards / Exercises — completed（deterministic fake-provider scope）

Phase 8.1–8.6 已收口：v7/v8 migration、Cards/Exercises backend、fake-provider citation-safe draft generation、Chromium workspace，以及 backup → verify → 新空目录 restore 证据均已完成。Exercises 支持 set、三种已冻结题型、draft → ready/rejected/archived、draft-only edit、current revision/chunk/span citation revalidation、delete/restore/purge/re-index source lifecycle、append-only attempt history、multiple-choice/true-false deterministic grading 和 short-answer `pending_review`。生成仅接受显式已索引的单材料 scope，经 lexical/vector/hybrid retrieval、context、provider 结构化内存校验和 server-side citation/source revalidation 后，才原子保存 AI draft 与 operation metadata；支持 idempotency、failed retry、malformed/forged citation、rollback 和 stale boundary。普通列表/history 不返回 answer key 或 answer body，raw prompt/provider response 不持久化。closeout 测试证明 restore/startup/read 不生成、repair、rebuild 或将 unavailable citation 提升为 valid。完整证据见 [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)：full backend `250 passed, 2 skipped`，Phase 8 Chromium `3 passed`，相关 UI failure regression `9 passed`。真实 Provider generation evidence、系统级 screen reader/极端内容和简答人工 review 未实现，因此这个 completed 结论不是全局 Cards/Exercises `real-pass`。

### Phase 5 之后：AI 与学习工作流 — 后续工作

以下后续核心产品能力尚未形成可用用户路径：

- P6-E 精确真实 Provider UI evidence：DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 已分别通过真实网络 backend/UI gate；证据仅限精确 gateway、model 和 synthetic material，不能扩展为所有 Provider/model 的通用 real-pass。
- hybrid/fallback RAG 扩展、真实 embedding provider 和其它 Provider 独立验证。
- 真实 Provider 的 Cards/Exercises generation evidence、人工简答复核；Phase 8 fake-provider closeout 已完成。
- 学习计划及 S1–S7。
- OCR、ASR、旧格式转换。
- 后台任务、进度、暂停/取消、retry 和导入历史。

### Phase 6 及以后：产品化、生产化与扩展 — P6-A–P6-E 已完成对应验收，后续能力仍未完成

- I1 migration framework 与 schema versioning 已完成；I2 backup/restore 运维闭环已完成。
- I3 最小可观察性已实现；I4 已时间盒验收，本地单进程基础设施 v1 基本完工。
- 多用户、认证、授权和项目隔离 UI。
- 多进程/多实例写协议。
- 云同步、外部存储和协作。
- metrics、structured logging、tracing、分级 health 和运维报告。
- 备份轮换、恢复演练、corruption quarantine、read-only mode 和管理修复工具。
- 容量、性能、长时间运行和真实故障验收。

## 四、当前急需完成的事项

### P0-I4：基础设施最后收尾 — 已完成（时间盒验收）

1. **I4：真实环境与容量基线（时间盒验收完成）**
   - 已完成 S0–S3 合成 TXT 容量/耗时基线与 40-cycle 生命周期 smoke。
   - ACL、真实资源耗尽、S4、peak memory、断电/网络盘/硬件损坏已明确记录为 `not_verified`，并作为 v1 运行边界接受。

### 当前阶段：Phase 9A 与 Phase 9B 已分别在限定范围内完成，Phase 9C S3/S4/S5 backend/API 已完成，下一阶段为 9C-8 Chromium workspace

当前正式 schema 为 v11（Phase 9A closeout 的历史 schema 基线为 v9；Phase 9B 使用 v10，Phase 9C-2 已追加 v11 exercise-feedback schema）。Phase 4 的 deterministic fake provider Q&A 闭环、Phase 5 adapter/配置/错误边界、Phase 6 P6-A–P6-E fake/default/UI 产品化验收、以及 Mistral 精确配置范围的 Phase 7 已完成；DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 的 P6-E 精确真实 UI evidence 也已通过。尚未达到多 Provider 通用 real-pass，Phase 8.6 fake-provider closeout 已完成；Phase 9A 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成。9B-2 完成 v10 persistence schema，9B-3 完成共用 repository/domain transaction，9B-4 完成单材料 deterministic fake-provider S2 note draft workflow，9B-5 完成 S1 同步节奏 backend workflow：显式 daily/weekly IANA-timezone settings、local-date allocation 创建/移动/删除、工作量/重复/跨 plan 保护、确定性 timeline/load/progress/source-warning summary，以及 completed/terminal 保护、rollback 和 SQLite lock 后 retry；9B-6 在此基础上完成 S1/S2 最小安全 FastAPI，覆盖 rhythm、note/block/module/source link、fake-provider draft generation、状态转换、source refresh 和 bounded JSON/Markdown export。API 服务端注入 project scope、执行 citation/source validation 并保持安全错误/隐私边界。S1 不写 progress、不自动重排或启动 scheduler。9B-7 现已在 deterministic fake-provider/local Chromium 范围通过最小 S1/S2 workspace browser gate：S1 设置/分配/summary/progress/reload，S2 user/AI cited draft、module 组织、编辑/状态转换/source refresh/export 和安全失败路径；9B-8 随后完成 delete/restore/purge/new revision 的 note/rhythm/progress source lifecycle 以及 backup→verify→新空目录 restore non-repair：v10 note/block/module/source-link、rhythm/allocation、generation/progress history 和 stale/unavailable tombstone 保留，restore acceptance 不调用 provider/index/refresh/repair。9B-9 现已完成限定范围内 closeout：focused `59 passed`，完整 backend `299 passed, 2 skipped`，相关 Chromium `45 passed, 1 skipped`，默认 real-provider spec `2 skipped`；脱敏证据见 `PHASE9B_ACCEPTANCE_EVIDENCE.md`。Phase 9B 的完成声明仍不包含真实 Provider generation 或完整正式用户路径。既有 9A closeout 的完整 backend 为 `272 passed, 2 skipped`，Phase 9A Chromium 为 `3 passed`，Phase 8 Chromium 为 `3 passed`，frontend failure contract 为 `6 passed`；最终脱敏 evidence 见 `PHASE9A_ACCEPTANCE_EVIDENCE.md`。本次 9B-9 closeout 完整 backend 为 `299 passed, 2 skipped`，相关 Chromium 为 `45 passed, 1 skipped`，默认 real-provider spec 为 `2 skipped`；Gate A-I 已在限定范围内完成。Phase 9A/9B 完成不包含 Phase 9C/9D、真实 Provider plan/note generation、worker、多用户或全局 production `real-pass`。Phase 9C 整体仍为 `planned`；9C-0/9C-1 已完成，9C-2 v11 migration/schema、9C-3 shared repository/domain transaction、9C-4 S3 PracticeRunner、9C-5 S4 ErrorFixer、9C-6 S5 ExamCrammer backend 与 9C-7 最小安全 API 已达到 `implemented/backend-pass`：覆盖 immutable session/item snapshot、服务端 deadline、S3 result、MC/TF deterministic grading、short-answer review、uncertain/user-marked distinction、mistake case/occurrence、redo 新 attempt、cram goal/session/result、weak-point、append-only/idempotency、server project scope、privacy 和 rollback。Chromium UI、lifecycle、restore 和 closeout 尚未完成。总体 prompt、共用上下文、9C-0 至 9C-10 子任务 prompts 和 Gate A-J 已存放于 `docs/phase9c/`，prompt 包不是实现证据。既有 Provider adapter 范围仍为：

- 通用 OpenAI-compatible LLMProvider adapter 与 registry；
- 环境变量配置、URL 校验、API key 内存隔离、timeout、prompt/output limits；
- provider timeout、rate-limit、auth、forbidden、unavailable、malformed response、schema mismatch、refusal、output limit 的稳定错误映射；
- provider/model/request ID、usage、latency、finish reason metadata，并通过 v3 migration 持久化；
- mock HTTP、secret redaction 和 Phase 4 回归测试已通过；
- DeepSeek 官方 `deepseek-chat` 已通过 adapter-level 和完整 API-level 真实网络 smoke；使用临时 data_root 与 synthetic context，验证了 Q&A 成功、citation 和 operation metadata。
- DeepSeek UI smoke 已验证回答、citation 展示和原文定位；failure UX 已验证 timeout、rate-limit、unavailable、retry、重复点击和安全渲染。
- ARK、硅基流动、Agnes AI-Hub、Sub2API 已建立独立 provider capability matrix 和脱敏 opt-in 验收命令；API/UI smoke 现在要求 explicit target 与 runtime provider 一致。三次 API acceptance runner 已实现：每次独立 temporary data root、串行 early-stop、仅输出稳定错误码；其 `2/3` 结果不替代 UI evidence，且实现时未执行新的真实请求。Agnes `advanced`/`agnes-2.5-flash` 已通过独立 adapter/API/UI 真实 smoke；`pro`/`agnes-2.5-pro` API 返回 `provider_unavailable`、UI 未运行，仍为 `not_verified`。ARK、硅基流动和 Sub2API 仍待独立验证。同步 Q&A 已实现显式 `Idempotency-Key` 成功 replay、running 冲突、失败重试和请求触发的 5 分钟 lease stale recovery；后台扫描、cancel、跨进程协调和真实断电恢复仍未实现。

### 后续阶段：精确 Provider evidence、学习能力和生产化

P6-E 的 DeepSeek/Agnes 精确真实 UI path 已在显式配置下通过；Phase 7 已在 Mistral 精确 embedding 配置范围完成。Phase 8.6 fake-provider closeout 已完成；当前按 [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md) 从 9A 开始，再按 9B–9D、10 顺序推进，不在当前阶段并行承诺。

### 与祖宗/前两代版本的治理结论

StudyBuddy 已经是正式系统层面的进化：相对于 `kaobuddy-remote-audit`、`ai-studybuddy`、`AIStudyBuddy` 和 `pi-studybuddy`，它在正式 source of truth、Composer/Integration/Test 分层、migration 控制、原文件与 SQLite 安全、backup/restore、revision → chunk → retrieval → citation 可追溯链、Provider evidence 边界和分层验收状态上更成熟。

但它还不是功能宽度上的全面替代品。前代版本仍覆盖更多学习业务，例如 cards、exercises、study plans、S1–S7、OCR/ASR、报告或桌面工作流。历史代码、设计、组件 smoke、fake Provider 或前代用户路径只能作为需求和契约参考，不能作为正式系统完成证据。当前完成度约 55%–60% 的主要含义正是：可靠基础、可信 Q&A 和受限的 Cards/Exercises 闭环已形成，但学习计划和更广泛学习产品上层尚未完成。

Phase 9 原计划同时承载学习计划和全部 S1–S7，范围过大，不能作为一个统一可验收阶段。现改为 9A 学习领域与计划基础、9B S1/S2 资料学习、9C S3/S4/S5 练习反馈、条件性 9D S6/S7 扩展服务；每个子阶段必须独立完成领域契约、migration、API/UI、失败与 source lifecycle、浏览器和恢复证据。

### P1：在 AI 闭环后补齐运行保障

- I1 migration/versioning、I2 backup/restore operator 闭环、I3 可观察性与 I4 真实环境/容量基线（时间盒）已完成。
- 后台任务与可观察的任务状态；需要时再引入队列。
- structured logging、metrics、trace/request id 和 readiness 分级。
- 真实 ACL、磁盘满、长时间压力和容量测试。

### P2：产品验证通过后再做架构扩展

- 多用户/认证授权。
- 多进程、多实例和服务端部署协议。
- 云同步、外部存储、协作。
- 向量检索、真实 embedding 和 provider 扩展。

## 五、当前明确不应宣称的能力

- 全局生产级 `real-pass`。
- 多进程或多 Uvicorn worker 共享同一 data_root。
- 真实断电、磁盘损坏、网络文件系统恢复。
- 不宣称所有真实 Provider、RAG、Cards、Exercises 或学习计划已具备；DeepSeek `deepseek-chat` 和 Agnes `agnes-2.5-flash` 已有各自精确 API/UI smoke evidence；其它 Provider/model 仍需独立验证。Phase 4 fake Provider Q&A 和 P6-E fake 核心工作流已通过对应验收。
- 已具备 OCR、ASR、ZIP import、文件夹 export 或后台任务队列。
- 已完成多用户、认证授权、云同步和协作。

## 六、权威文档索引

- 当前状态总表：[`STATUS.md`](STATUS.md)
- 项目入口说明：[`README.md`](../README.md)
- 架构边界：[`ARCHITECTURE.md`](ARCHITECTURE.md)
- AI/学习架构：[`ai-learning-architecture.md`](ai-learning-architecture.md)
- 设计决策：[`DECISIONS.md`](DECISIONS.md)
- 备份恢复操作：[`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)
