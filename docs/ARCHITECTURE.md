# StudyBuddy Architecture Boundary

> 核心运行入口：`backend/app/main.py:create_app`（FastAPI 应用工厂）和 `backend/app/__main__.py` → `backend/app/cli.py:main`（显式 operator CLI）。业务持久化只能经 `backend/app/repository.py`，schema 只能经 `backend/app/migrations/runner.py`，原文件只能经 `backend/app/storage.py`；启动顺序为 preflight → migration/connect → audit → recovery → ready。

> 当前项目阶段与优先级见 [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)。P6-E 的 DeepSeek/Agnes 精确真实 Provider UI evidence 已通过，Phase 7 已在 Mistral 精确 embedding 配置范围收口；Phase 8、Phase 9A、Phase 9B、Phase 9C 和 Phase 9D 的 9D-0 部分立项范围均已在各自 deterministic fake-provider/loopback、本地单进程 SQLite、Chromium 和 backup/restore 限定范围内完成。当前正式 schema 为 v13（Phase 9D 的历史 persistence baseline 为 v12）；Phase 9D 最终限定范围证据见 [`PHASE9D_ACCEPTANCE_EVIDENCE.md`](PHASE9D_ACCEPTANCE_EVIDENCE.md)。Phase 10 已完成 v13 task/attempt persistence schema、explicit-only single-process task runner/recovery、approved `embedding_index` provider-backed task 接入，以及 safe structured observability/readiness/read-only diagnostics；runner 只由显式 API/CLI 调用，不在 startup、backup、restore 或 read path 自动启动。Q&A、generation、capture transcription、report 和 delivery 未接入；scheduler/worker、多进程执行仍不在支持范围。真实 Provider generation、真实 OCR/ASR、真实 SMTP/飞书外发、人工复核、多进程、多用户和云同步仍未实现或不在支持范围。

## Evolution boundary

StudyBuddy is the formal successor system, but not yet a feature-complete successor product. Compared with KaoBuddy and the prior `ai-studybuddy`/`pi-studybuddy` generations, it has evolved in governance and trust boundaries: formal source-of-truth ownership, Composer/Integration/Test separation, migration-controlled schema changes, local storage safety, backup/restore verification, revision-to-citation traceability, explicit provider evidence, and layered acceptance states. The prior generations still cover more learning-product breadth, including cards, exercises, plans, S1–S7 workflows and some OCR/ASR/report concepts.

Historical capability is reference input, not completion evidence. A prior implementation, component smoke, fake provider, or architecture document cannot mark the formal system implemented or real-pass. Learning work must be reimplemented in `H:/studybuddy`, tested under its own contracts, and accepted through the applicable formal/system-test path.

Phase 9 is therefore a gated learning-program family (9A–9D), not one delivery phase. Each sub-phase owns its own domain contract, migration, API/UI path, failure and source-lifecycle behavior, evidence, and documentation update.

## Runtime target

`127.0.0.1` 本机 Web 应用：FastAPI 后端提供内嵌浏览器 UI，使用 SQLite 和本地文件。当前 AI 用户路径默认使用 deterministic fake provider；Phase 5 已实现通用 OpenAI-compatible adapter、target-gated smoke 和脱敏三次 API acceptance runner。Phase 6 P6-E 已通过 fake Provider 核心工作流和相关 failure/source lifecycle/竞态验收。DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 已分别通过既有 adapter/API/UI synthetic smoke，本轮 P6-E real UI path 也已在精确 gate 下通过；其它 Provider/model 仍待独立验收。不引入 React/Vite、pi、Electron、自动 fallback 或多进程 AgentSession。

## Evidence flow

参考系统/组件 -> `H:\studybuddy-composer` 独立 smoke -> `H:\studybuddy-integration` 组合测试 -> `H:\studybuddy` 正式 Adapter 与用户路径。

系统测试运行根统一位于 `H:\studybuddy-test`。任何目录的测试通过，都不能替代下一层真实测试。

## Formal file foundation

`backend/app/adapters/file_parsers/` 是正式系统自己的解析模块，不导入 Composer、Integration 或 KaoBuddy。`parse_file(Path, declared_media_type, ParseOptions)` 返回版本、hash、状态、错误码、warning 和 document/page/slide spans。当前只实现 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 拒绝。Parser 不保存原文件、不依赖网络、不打印完整正文。

`backend/app/storage.py` 通过配置传入的 root 保存 hash 派生路径下的原文件，并使用临时文件加原子替换。`backend/app/repository.py` 承载 SQLite projects/materials/extractions/text_spans、AI retrieval/Q&A 与已实现的 Phase 8 Cards/Exercises backend 持久化，启用外键和 WAL；material import 的 extraction 与 spans 仍在同一事务中写入。

正式默认运行路径不指向 fixture；本阶段测试使用 `H:\studybuddy-test\runs`。`backend/app/main.py` 提供最小 FastAPI 用户路径：multipart 文件选择与上传、配置存储根下的原文件保存、Parser 调用、SQLite extraction/span 事务写入、材料列表/详情 API 和同服务的文件选择器页面。默认单文件上传上限为 50 MiB，可由 `STUDYBUDDY_MAX_UPLOAD_BYTES` 调整；这属于正式系统配置，不是免费版或 Parser 能力限制。服务重新启动后，材料详情从 SQLite 回读。

正式文件导入、批量导入、文件夹导入、材料管理、回收站、导出和搜索均已有局部 `real-pass` 证据；Phase 4 fake Provider Q&A、Phase 5 精确 Provider smoke 和 Phase 6 P6-A–P6-E 的对应 evidence 分别记录在状态与验收文档中。该状态不代表整个 StudyBuddy 或所有 Provider/model 已完成。

## Persistence and safety boundary

materials/extractions/text_spans 是当前 source of truth。FTS、revision、chunks、retrieval、citations、AI operations 和学习产物都是派生数据或用户状态，不能静默覆盖 source。

启动顺序为 preflight、SQLite connect/schema/index init、diagnostic audit、recovery、ready。SQLite 使用 WAL、foreign keys、2000 ms busy timeout 和事务边界。storage 操作要求 configured root containment、regular-file 和 non-symlink 校验；hash mismatch、unexpected layout、missing original 和失败清理均使用稳定错误边界。

系统支持 process-local 同 hash coordination、controlled crash/restart recovery、write contention rollback、backup/verify/restore 和 restore acceptance。Observability 提供安全 structured events、`X-Request-ID`、request→operation→task correlation、`/api/liveness`、`/api/health`、`/api/readiness`、显式 read-only `diagnostics` 和有限的 process-local `/api/metrics`；metrics 不持久化、不跨进程聚合。liveness 只表示 process 可响应，audit/runtime database/stale task 降级时 health/readiness 不伪造 healthy；diagnostics 不迁移、repair、rebuild 或执行任务。支持范围仍是单进程、单实例、本地磁盘；I4 已有合成 TXT S0–S3 与 bounded lifecycle smoke 证据，但 ACL、资源耗尽、S4、peak memory、断电、网络盘和硬件损坏仍未验证；不支持多个 worker 或多个实例共享 `data_root`。

## AI boundary

AI 当前处于 staged implementation 阶段。当前项目 Phase 4 已完成 revision/chunk/retrieval/context/citation、deterministic fake provider、同步 Q&A API/persistence、Q&A history、多材料范围、citation 详情/定位和完整浏览器验收；Phase 5 通用 OpenAI-compatible adapter、配置隔离、稳定错误映射、响应限制、mock 验证和脱敏三次 API acceptance runner 已实现；Phase 6 P6-A–P6-E 已完成对应 fake/default/UI 产品化验收，P6-E evidence 见 [`prompts/P6E_ACCEPTANCE_EVIDENCE.md`](prompts/P6E_ACCEPTANCE_EVIDENCE.md)。DeepSeek `deepseek-chat` 与 Agnes `agnes-2.5-flash` 的既有 adapter/API/UI synthetic smoke 以及本轮 P6-E real UI path 已分别通过精确 gate；其它 Provider/model 仍按精确 gate 记录为 `not_verified`。依赖顺序固定为:

```text
material revision
→ chunks
→ retrieval
→ citations
→ Q&A
→ cards / exercises
```

Phase 4 采用 SQLite FTS5 lexical retrieval first、deterministic fake provider 和可验证 citation；Phase 7 已在 Mistral 精确 embedding 配置范围完成。Phase 8 已在 deterministic fake-provider 范围收口：schema、Cards/Exercises lifecycle、citation-safe draft generation、workspace、三种冻结题型、draft/ready/rejected/archived、append-only attempts、可验证 citation/source lifecycle、MC/TF deterministic grading、short-answer `pending_review`，以及 backup → verify → 新空目录 restore 均有证据。generation 要求显式已索引的 single-material scope，经 retrieval/context/provider 结构化内存校验和服务端 citation 重验后才原子保存 draft/operation；restore/startup 不自动生成、repair、rebuild 或提升 unavailable citation。详细范围见 [`PHASE8_ACCEPTANCE_EVIDENCE.md`](PHASE8_ACCEPTANCE_EVIDENCE.md)。Phase 9A/9B/9C 与 Phase 9D 部分立项范围的限定完成声明分别记录于 `PHASE9A_ACCEPTANCE_EVIDENCE.md`、`PHASE9B_ACCEPTANCE_EVIDENCE.md`、`PHASE9C_ACCEPTANCE_EVIDENCE.md` 与 `PHASE9D_ACCEPTANCE_EVIDENCE.md`。真实 Provider generation evidence（除单独记录的精确 P6-E 路径外）、真实 OCR/ASR、真实外发、系统级辅助技术/极端内容、人工简答复核、Q&A/generation/capture/report/delivery 的 runner 接入、worker 和多用户能力仍须按路线图逐阶段实现；当前证据不等于 Phase 9 全部能力或全局 `real-pass`。
