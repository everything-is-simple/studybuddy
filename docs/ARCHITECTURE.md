# StudyBuddy Architecture Boundary

> 当前项目阶段与优先级见 [`PROJECT_PROGRESS_REPORT.md`](PROJECT_PROGRESS_REPORT.md)。当前重点是从文件材料基础设施进入 AI/学习最小闭环；多进程、多用户和云同步仍不在支持范围。

## Runtime target

`127.0.0.1` 本机 Web 应用：FastAPI 后端提供内嵌浏览器 UI，使用 SQLite 和本地文件。当前 AI 用户路径默认使用 deterministic fake provider；Phase 5 已实现通用 OpenAI-compatible adapter，DeepSeek 官方 `deepseek-chat` 已通过 adapter-level 与完整 API-level synthetic smoke，但浏览器 Provider E2E、真实失败 UX 和其它 Provider 验收仍待完成。不引入 React/Vite、pi、Electron、自动 fallback 或多进程 AgentSession。

## Evidence flow

参考系统/组件 -> `H:\studybuddy-composer` 独立 smoke -> `H:\studybuddy-integration` 组合测试 -> `H:\studybuddy` 正式 Adapter 与用户路径。

系统测试运行根统一位于 `H:\studybuddy-test`。任何目录的测试通过，都不能替代下一层真实测试。

## Formal file foundation

`backend/app/adapters/file_parsers/` 是正式系统自己的解析模块，不导入 Composer、Integration 或 KaoBuddy。`parse_file(Path, declared_media_type, ParseOptions)` 返回版本、hash、状态、错误码、warning 和 document/page/slide spans。当前只实现 TXT、Markdown、PDF、DOCX、PPTX；RTF、旧 DOC、旧 PPT 拒绝。Parser 不保存原文件、不依赖网络、不打印完整正文。

`backend/app/storage.py` 通过配置传入的 root 保存 hash 派生路径下的原文件，并使用临时文件加原子替换。`backend/app/repository.py` 只承载 projects/materials/extractions/text_spans 最小 schema，启用外键和 WAL，extraction 与 spans 在同一事务中写入。

正式默认运行路径不指向 fixture；本阶段测试使用 `H:\studybuddy-test\runs`。`backend/app/main.py` 提供最小 FastAPI 用户路径：multipart 文件选择与上传、配置存储根下的原文件保存、Parser 调用、SQLite extraction/span 事务写入、材料列表/详情 API 和同服务的文件选择器页面。默认单文件上传上限为 50 MiB，可由 `STUDYBUDDY_MAX_UPLOAD_BYTES` 调整；这属于正式系统配置，不是免费版或 Parser 能力限制。服务重新启动后，材料详情从 SQLite 回读。

正式文件导入、批量导入、文件夹导入、材料管理、回收站、导出和搜索均已有局部 `real-pass` 证据。该状态不代表整个 StudyBuddy 或 AI 功能已完成。

## Persistence and safety boundary

materials/extractions/text_spans 是当前 source of truth。FTS、revision、chunks、retrieval、citations、AI operations 和学习产物都是派生数据或用户状态，不能静默覆盖 source。

启动顺序为 preflight、SQLite connect/schema/index init、diagnostic audit、recovery、ready。SQLite 使用 WAL、foreign keys、2000 ms busy timeout 和事务边界。storage 操作要求 configured root containment、regular-file 和 non-symlink 校验；hash mismatch、unexpected layout、missing original 和失败清理均使用稳定错误边界。

系统支持 process-local 同 hash coordination、controlled crash/restart recovery、write contention rollback、backup/verify/restore 和 restore acceptance。Observability 提供安全 structured events、`X-Request-ID`、request-scoped operation correlation、`/api/liveness`、readiness health 和有限的 process-local `/api/metrics`；metrics 不持久化、不跨进程聚合。支持范围仍是单进程、单实例、本地磁盘；I4 已有合成 TXT S0–S3 与 bounded lifecycle smoke 证据，但 ACL、资源耗尽、S4、peak memory、断电、网络盘和硬件损坏仍未验证；不支持多个 worker 或多个实例共享 `data_root`。

## AI boundary

AI 当前处于 staged implementation 阶段。当前项目 Phase 4 已完成 revision/chunk/retrieval/context/citation、deterministic fake provider、同步 Q&A API/persistence、Q&A history、多材料范围、citation 详情/定位和完整浏览器验收；Phase 5 通用 OpenAI-compatible adapter、配置隔离、稳定错误映射、响应限制和 mock 验证已实现，DeepSeek 官方 `deepseek-chat` 的 adapter/API-level synthetic smoke 已通过，但 provider UI/E2E、真实失败 UX、其它 Provider 和后续学习能力仍待验收/实现。依赖顺序固定为：

```text
material revision
→ chunks
→ retrieval
→ citations
→ Q&A
→ cards / exercises
```

Phase 4 采用 SQLite FTS5 lexical retrieval first、deterministic fake provider 和可验证 citation。真实 provider、embedding、cards、exercises、plans、worker 和多用户能力必须按路线图逐阶段实现；Phase 4 已完成不等于真实 provider、embedding 或全局产品化已完成，不得因 schema 已预留而宣称功能已可用。
