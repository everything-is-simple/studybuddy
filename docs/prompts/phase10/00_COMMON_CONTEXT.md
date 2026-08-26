# Phase 10 共用上下文 Prompt

以下文本应作为每一个 Phase 10 子任务的前置 prompt：

```text
你正在 H:\\studybuddy 仓库中执行 StudyBuddy Phase 10 的一个明确子任务。先完整读取并遵守 AGENTS.md；再读取 docs/STATUS.md、docs/TODO.md、docs/PHASE_ROADMAP.md、docs/PROJECT_PROGRESS_REPORT.md、docs/ARCHITECTURE.md、docs/CODE_TEST_GOVERNANCE.md、docs/MIGRATIONS.md、docs/BACKUP_RESTORE.md，以及本目录的 00_COMMON_CONTEXT.md、00_MASTER_PLAN_PROMPT.md、EXECUTION_ORDER_AND_GATES.md。

StudyBuddy 当前是本地、单进程、单实例的 FastAPI + SQLite + 本地 hash-derived originals 系统，正式 schema 为 v13；v13 仅提供 task/attempt persistence schema，不代表 runner 已实现。Phase 4–8 及 Phase 9A/9B/9C、Phase 9D 部分立项范围已在各自限定范围完成，但项目尚未全局 production real-pass。当前支持边界是单进程、单实例、本地磁盘；不得把 Phase 10 自动解释为多 worker、多实例、多用户、云同步或互联网 SaaS。

Phase 10 的默认目标是：把现有可用能力收敛成可安装、可启动、可备份、可恢复、可诊断、可升级、可验证的“本地单机生产版 v1”，并补齐必要的后台长任务基础。目标不是无限扩展功能。只有经过独立证据，才能使用“发布候选”“上线”“production-ready”等措辞；没有证据的项目必须标为 not_verified。

必须保护的现有边界：
- schema 变化只能通过 backend/app/migrations/runner.py 的连续、幂等、事务化 migration；不得运行时 ad-hoc CREATE TABLE。
- repository.py 负责业务持久化和事务；storage.py 负责 hash-derived originals、路径 containment、临时文件和 hash 校验；启动顺序必须保持 preflight → migration/connect → audit → recovery → ready。
- materials/extractions/text_spans 是 source of truth；revision/chunk/retrieval/citation、AI operation、Cards/Exercises 和 9A–9D 学习事实不得被后台任务静默覆盖。
- AI 生成、OCR/ASR 和报告交付必须保留 operation/audit、稳定错误、幂等和隐私边界；raw prompt、raw provider response、secret、正文全文、答案 key、用户提交原文、路径和收件人隐私不得进入日志/API/备份明文。
- backup/verify/restore/startup/read 不自动生成、修复、重建索引、发送报告或调用外部 provider；恢复到新空目标，不覆盖 live data root。
- 默认测试不访问真实网络、不使用真实 provider、不在仓库写数据库、originals、secret 或生成 artifact。真实 provider、真实 OCR/ASR、真实外发、压力和故障测试必须是显式 opt-in，且证据限定到精确配置。
- 不引入多用户、认证授权、云同步、协作、外部 vector database 或共享 data_root 的多进程协议，除非先提出独立范围变更并获得确认；它们不是本次本地 v1 上线的隐含前置。

实施规则：一次只执行一个子任务；只修改该子任务拥有的文件范围；发现契约冲突、数据破坏风险、需要扩大部署边界或需要真实外部动作时先停工并提交变更提案。每个实现任务必须有 focused tests；涉及基础设施、migration、storage、backup、operation 或 API 时运行完整 backend；涉及 UI 时串行运行对应 Chromium spec；必须同步准确状态、证据和未验证边界。

结束报告必须包含：修改文件、测试文件、focused 命令及结果、完整门禁结果、启动/升级/备份/恢复或真实动作的边界、没有验证的事项、准确状态措辞、后续阻塞项和是否需要独立 fix commit。不得把 implemented/backend-pass/browser-pass 写成 production real-pass。
```
