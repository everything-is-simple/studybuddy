# StudyBuddy 项目进度报告

> 更新日期：2026-08-27（P6-E fake Provider 核心工作流验收收口后）
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
| AI/学习产品能力 | 35%–45% | Q&A 与 Provider adapter 已实现并验收；cards、练习、计划、embedding 和后台任务仍未实现 |
| 全项目整体 | 约 50%–55%（阶段性估算） | 该数字为功能加权估算，不是测试通过率；仍不得标记为全局 `real-pass` |

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

Phase 4 已完成：完整 Q&A history/multi-material UX、citation 详情与跨材料导航、统一 loading/empty/error/success、toast/retry、响应式与基础可访问性，以及导入→检索→问答→引用的完整 Chromium E2E 均已通过。Phase 5 adapter 已实现，DeepSeek 官方 `deepseek-chat` 的 adapter-level、完整 API-level synthetic Q&A 和 Chromium UI/E2E smoke 已通过；其它 Provider 和后续学习能力仍待验收/实现；cards、练习和学习计划属于后续阶段。

### Phase 7：Embedding 与 Hybrid Retrieval — partial

已通过 v5 migration 将 embedding identity/status/updated_at/唯一约束落库；实现离线 deterministic fake embedding、f32le_v1 payload codec、显式 fake indexing 和 vector-only cosine API，并保留 lexical 回归。尚未实现真实 embedding provider、完整 stale/rebuild/verify、hybrid RRF、fallback、Q&A 接入及 embedding 专项 backup/restore 证据。不可标记为 completed 或 real-pass。

### Phase 5 之后：AI 与学习工作流 — 尚未进入

以下后续核心产品能力尚未形成可用用户路径：

- P6-E 精确真实 Provider UI evidence：DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 已分别通过真实网络 backend/UI gate；证据仅限精确 gateway、model 和 synthetic material。
- hybrid/fallback RAG 扩展、真实 embedding provider 和其它 Provider 独立验证。
- 知识卡片、Quiz/练习。
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

### 当前阶段：P6-E 后的精确 Provider evidence 与后续路线

Phase 4 的 deterministic fake provider Q&A 闭环、Phase 5 adapter/配置/错误边界、Phase 6 P6-A–P6-E fake/default/UI 产品化验收已经完成；尚未达到多 Provider 通用 real-pass，且 P6-E 精确真实 UI evidence 仍需显式运行：

- 通用 OpenAI-compatible LLMProvider adapter 与 registry；
- 环境变量配置、URL 校验、API key 内存隔离、timeout、prompt/output limits；
- provider timeout、rate-limit、auth、forbidden、unavailable、malformed response、schema mismatch、refusal、output limit 的稳定错误映射；
- provider/model/request ID、usage、latency、finish reason metadata，并通过 v3 migration 持久化；
- mock HTTP、secret redaction 和 Phase 4 回归测试已通过；
- DeepSeek 官方 `deepseek-chat` 已通过 adapter-level 和完整 API-level 真实网络 smoke；使用临时 data_root 与 synthetic context，验证了 Q&A 成功、citation 和 operation metadata。
- DeepSeek UI smoke 已验证回答、citation 展示和原文定位；failure UX 已验证 timeout、rate-limit、unavailable、retry、重复点击和安全渲染。
- ARK、硅基流动、Agnes AI-Hub、Sub2API 已建立独立 provider capability matrix 和脱敏 opt-in 验收命令；API/UI smoke 现在要求 explicit target 与 runtime provider 一致。三次 API acceptance runner 已实现：每次独立 temporary data root、串行 early-stop、仅输出稳定错误码；其 `2/3` 结果不替代 UI evidence，且实现时未执行新的真实请求。Agnes `advanced`/`agnes-2.5-flash` 已通过独立 adapter/API/UI 真实 smoke；`pro`/`agnes-2.5-pro` API 返回 `provider_unavailable`、UI 未运行，仍为 `not_verified`。ARK、硅基流动和 Sub2API 仍待独立验证。同步 Q&A 已实现显式 `Idempotency-Key` 成功 replay、running 冲突、失败重试和请求触发的 5 分钟 lease stale recovery；后台扫描、cancel、跨进程协调和真实断电恢复仍未实现。

### 后续阶段：精确 Provider evidence、学习能力和生产化

P6-E 的 DeepSeek/Agnes 精确真实 UI path 已在显式配置下通过；Cards、练习、学习计划、embedding/hybrid retrieval、后台任务、多用户和扩展能力按 [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md) 的 Phase 7–10 顺序推进，不在当前阶段并行承诺。

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
