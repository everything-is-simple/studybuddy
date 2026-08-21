# StudyBuddy 项目进度报告

> 更新日期：2026-08-25（I1/I2 收口后）
> 
> 本报告依据当前正式代码、测试证据和项目决策文档整理。`real-pass` 只表示对应局部用户路径和验收证据通过，不代表整个 StudyBuddy 已达到生产级或全局 `real-pass`。

## 一、当前总进度

### 结论

StudyBuddy 当前已经完成了一个**可靠的本地单进程文件材料管理基础系统**，但还不是完整的 AI 学习产品。

| 评估口径 | 当前完成度 | 结论 |
|---|---:|---|
| 本地单进程基础设施 | 85%–90% | 导入、SQLite、Storage、一致性、恢复、migration、backup/restore 和启动保护已具备；I3/I4 收尾中 |
| 文件材料管理子系统 | 80%–85% | 当前完成度最高，主要用户路径已局部 `real-pass` |
| SQLite/Storage 一致性 | 约 80% | 单机事务、FTS、生命周期和故障边界较完整 |
| 前端用户体验 | 45%–55% | 可用的内嵌单页路径，尚未产品化 |
| AI/学习产品能力 | 25%–35% | 主要仍是架构设计，核心学习功能尚未实现 |
| 全项目整体 | 约 45%–50%（阶段性估算） | 该数字为功能加权估算，不是测试通过率；仍不得标记为全局 `real-pass` |

整体进度不应简单按“已通过测试数量”计算：当前可靠性投入较多，而 AI、学习工作流、多用户和运维能力尚未开始，因此产品整体完成度明显低于文件基础设施完成度。

## 二、已交付的阶段性范围

> 下列状态仅表示该阶段当前约定的第一版范围已经交付，或其设计已经沉淀；不表示对应领域已最终完成。特别是可靠性、备份恢复和 AI 架构均仍有后续 Phase。

### Phase 0：工程边界与验证体系 — v1 范围已完成

- 正式产品目录、Composer、Integration、系统测试目录边界已确定。
- 正式实现不得直接依赖参考项目。
- 组件必须经过独立 smoke、组合测试和正式系统验证。
- 已形成架构边界、决策记录和脱敏测试 artifact 约束。

### Phase 1：正式文件解析与存储基础 — v1 范围已完成 / 局部 real-pass

已完成：

- TXT、Markdown、PDF、DOCX、PPTX 解析。
- RTF、旧 DOC、旧 PPT 的明确拒绝及稳定错误码。
- SHA-256 内容身份与 hash-derived original storage。
- 临时文件、原子替换、大小限制和安全路径边界。
- SQLite schema、外键、WAL、busy timeout。
- extraction、text_spans 与 material 的事务写入。

局部 `real-pass` 已覆盖真实 Chromium 文件选择、解析成功/空文件/拒绝/失败、50 MiB 边界、重复 hash、刷新与重启回读。

### Phase 2：文件导入与材料列表 — v1 范围已完成 / 局部 real-pass

- 单文件导入。
- 多文件 batch 导入。
- 每个文件独立事务，支持 partial success。
- 文件夹选择（Chromium `webkitdirectory`），不扫描服务器目录、不保存客户端路径。
- active、success、empty、rejected、failed 列表筛选。
- 材料详情、正文和 spans 回读。
- 分页、稳定排序、total/has_more。

### Phase 3：材料生命周期、搜索与导出 — v1 范围已完成 / 局部 real-pass

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

### Phase 4：可靠性、安全边界与 Operator 能力 — 基础版已实现，仍待生产化

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

限制：不支持多进程/多实例共用 data_root；真实磁盘满、断电、硬件/文件系统损坏、真实 ACL 和长时间压力尚未验收。

### Phase 5：前端基础用户路径 — 部分完成，仍待产品化

已完成一个可用的内嵌单页路径：

- 文件、多文件、文件夹选择。
- 批量结果、列表、筛选、分页、搜索、详情。
- rename/delete/restore/purge。
- 原文件、正文和 ZIP 导出。
- busy guard、stale response guard 和安全 DOM 文本渲染。
- 多项真实 Chromium failure contract。

尚未达到产品前端：独立 React/Vite 应用、统一组件和错误状态体系、可访问性、国际化、移动端体验、上传进度、toast、retry interaction、loading skeleton、完整 E2E 和高延迟/离线体验。

## 三、尚未完成 Phase

### Phase 6：AI / Learning architecture — researching / architecture-only

已完成：

- source of truth、revision、chunk、retrieval、citation、provider、AI operation 的边界设计。
- 第一阶段采用 SQLite FTS5 lexical retrieval first 的方向。
- provider Protocol、deterministic fake provider、citation 可追溯性和 draft 状态原则已记录。

I1 schema/migration 已实现并通过测试，但 AI 业务链路仍未实现：chunk pipeline、retrieval API、真实 provider、Q&A、卡片、练习、学习计划。

### Phase 7：AI 与学习工作流 — 未开始

以下核心产品能力均未开始或未形成可用用户路径：

- AI/provider 配置与调用。
- 材料 chunk/retrieval/RAG。
- 基于引用的问答。
- 知识卡片、Quiz/练习。
- 学习计划及 S1–S7。
- OCR、ASR、旧格式转换。
- 后台任务、进度、暂停/取消、retry 和导入历史。

### Phase 8：生产化与扩展 — 未完成

- I1 migration framework 与 schema versioning 已完成；I2 backup/restore 运维闭环已完成。
- I3 最小可观察性已实现；I4 已完成首轮合成 TXT 容量与生命周期 smoke，但仍为 partial。
- 多用户、认证、授权和项目隔离 UI。
- 多进程/多实例写协议。
- 云同步、外部存储和协作。
- metrics、structured logging、tracing、分级 health 和运维报告。
- 备份轮换、恢复演练、corruption quarantine、read-only mode 和管理修复工具。
- 容量、性能、长时间运行和真实故障验收。

## 四、当前急需完成的事项

### P0-I4：完成基础设施最后收尾

1. **I4：真实环境与容量基线（partial）**
   - 已完成 S0–S3 合成 TXT 容量/耗时基线与 40-cycle 生命周期 smoke。
   - ACL、真实资源耗尽、S4、peak memory、断电/网络盘/硬件损坏仍为 `not_verified`。

### P0：基础设施收尾后实现 AI 第一阶段最小闭环

2. **实现可信 Q&A 最小闭环**
   - 实现 material revision/chunk 数据模型和可追溯 citation。
   - 实现 SQLite FTS5 retrieval API。
   - 实现 provider Protocol 与 deterministic fake provider。
   - 增加一个基于材料引用的 Q&A 用户路径。
   - 未配置 provider 时返回稳定 `provider_not_configured`，不能阻塞应用启动。

3. **明确 S1–S7 的首个可交付范围**
   - 先选择一个最小学习闭环：材料 → 检索 → 引用问答 → 用户确认的卡片/练习。
   - 暂不同时开发卡片、Quiz、计划、OCR、ASR 和云同步，避免范围失控。

3. **把当前前端从“可用测试页面”推进为产品 MVP**
   - 统一 loading/empty/error/success 状态。
   - 添加 retry、toast、上传进度和任务状态。
   - 统一 mutation/export API 错误处理。
   - 建立可访问性和响应式布局基线。

### P1：在 AI 闭环后补齐运行保障

- I1 migration/versioning 与 I2 backup/restore operator 闭环已完成；剩余 I3 可观察性、I4 真实环境与容量验收。
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
- 已具备 AI、RAG、Q&A、卡片、练习或学习计划。
- 已具备 OCR、ASR、ZIP import、文件夹 export 或后台任务队列。
- 已完成多用户、认证授权、云同步和协作。

## 六、权威文档索引

- 当前状态总表：[`STATUS.md`](STATUS.md)
- 项目入口说明：[`README.md`](../README.md)
- 架构边界：[`ARCHITECTURE.md`](ARCHITECTURE.md)
- AI/学习架构：[`ai-learning-architecture.md`](ai-learning-architecture.md)
- 设计决策：[`DECISIONS.md`](DECISIONS.md)
- 备份恢复操作：[`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)
