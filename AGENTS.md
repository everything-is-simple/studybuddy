# StudyBuddy Agent Instructions

## Project scope

StudyBuddy is a local, single-process **capability-integration system** for study material: it wires AI providers and local open-source components (OCR, ASR, parsers) into a browser UI backed by FastAPI, SQLite and local hash-derived original storage. It does not train models. Its job is to turn the user's own real material into searchable, answerable, practiceable, schedulable local study assets.

The core scenario is one chain:

```text
采集/导入 → 解析文本 → 切分索引 → 检索问答（带引用）
        → 生成卡片/练习（草稿，需确认） → 计划与节奇
        → 练习/错题/弱点 → 报告复盘
```

Seven capability domains: import/parse, OCR, ASR, index, Q&A, generation, report. Each must be independently observable and independently degradable.

## Delivery principle: usable first (2026-09-01 revision, supersedes evidence-ladder-first)

This revision exists because the previous mode produced audit and evidence documents faster than usable capability. It is binding.

- Every active slice must change **what the user can actually do**. A slice is not complete because a document exists.
- Do not create a new `docs/evidence/*.md` or `docs/contracts/*.md` unless the same slice also changed `backend/app/` or `backend/app/static/` in a way the user can exercise from the browser or CLI.
- Audit-only, contract-only, and status-only slices may not be the active work item unless the user explicitly asks for one.
- Prefer fixing the blocking defect over documenting the blocking defect.
- A blocked component gate (for example an unfinished Composer/Integration gate) blocks *claiming that component verified*. It does not block shipping detection, UI status, configuration, or the rest of the chain.
- Honesty rules stay: `implemented` is not `real-pass`, and unverified dimensions stay labeled `not_verified`. Honest labeling is a reporting duty, never a reason to withhold working capability from the user.

### Out-of-box defaults

- Capabilities must be **discoverable, not hand-configured**. At startup the system probes for required local components; when a component is present and structurally valid, its capability is enabled by default.
- A missing component surfaces as `not_installed` / `not_configured` in the UI. It must never be a silent disable.
- Requiring the user to hand-copy environment variables to switch on an installed local capability is a defect, not a security control.
- Configuration written through the UI must persist under `data_root` outside SQLite, must be excluded from backups and Git, and must not require a restart.
- Outbound network delivery (`report_delivery`) stays default-off and per-use authorized. That one really is a security control.

## Repository rules

- Keep the repository source of truth in `H:\studybuddy`.
- Keep production code under `backend/app/` and formal tests under `backend/tests/`.
- Keep important project documentation in the `docs/` directory.
- Keep the repository root limited to the primary entry documents and project metadata.
- Do not copy implementation code from Composer or Integration projects into the formal system. Re-implement against verified contracts.

## Directory usage规范 (2026-09-18 新增，2026-09-19 修订)

项目使用以下目录结构，各目录用途固定，不得混用：

- **H:\studybuddy**：正式源码仓库，包含生产代码、正式测试和必要文档
- **H:\studybuddy-data**：正式运行数据根目录（data_root），存放SQLite数据库、hash-derived原文件、配置文件
- **H:\studybuddy-composer**：组件独立测试目录，组件必须先在此完成独立测试
- **H:\studybuddy-integration**：组件组合测试目录，通过Composer测试的组件在此完成组合测试
- **H:\studybuddy-test**：测试artifacts和fixtures目录，存放合成fixture、测试运行结果和脱敏artifact
- **H:\studybuddy-ChinaTextbook**：真实教材与学习资料目录（`小学教材\<年级>\<科目>\`、`基础性作业\`、下载脚本、`教材清单.md`；`智慧教育token.txt` 为密钥，永不清扫）

各目录"必须保留 / 可清理"边界与清扫操作规范见 [`docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md`](docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md)（权威来源），本文与其冲突时以该文档为准。

**目录内部结构补充（2026-09-19）**：

- `H:\studybuddy-data` 的**根目录**才是当前活跃 data_root（`studybuddy.sqlite3`、`config/settings.json`、`originals/`、`logs/`）。其下的 `live/` 是**已废弃的历史 data_root 残留**（业务表已归零，仅剩孤立 original 与 FTS 碎片）；**禁止**把 `STUDYBUDDY_DATA_ROOT` 指向 `H:\studybuddy-data\live`。`config/settings.json` 含明文 Provider / SMTP 凭据，不得复制、提交或纳入备份证据。
- `H:\studybuddy-e2e-test`、`H:\studybuddy-e2e-test-<时间戳>` 这类**一次性临时 data_root** 不属于上述六个正式目录；确认无进程占用、无文档引用后可整目录删除，无需备份。

**重要原则**：
- 不得从Composer或Integration项目直接复制源码到正式系统
- 测试使用studybuddy-test下的数据，不写入正式仓库的运行数据
- 正式运行使用studybuddy-data作为data_root
- 不要将data_root放在OneDrive/网盘同步目录、网络盘或Git仓库内
- 不要让多个StudyBuddy实例共用同一个data_root
- Do not commit databases, uploaded originals, generated artifacts, secrets, provider keys, paths containing private data, or test-run output.
- New or substantially rewritten code files (`.py`, `.js`, `.css`, `.html`, `.ps1`, `.json`) must not exceed 100 KB; target a reasonable, maintainable size. A larger file requires explicit user approval before creation. Documentation files (`.md`) are exempt from this size limit. (2026-09-13 revision: the former 32 KiB limit was relaxed to 100 KB by user decision; it repeatedly blocked legitimate A/B review spec files.)
- Do not create or relocate a large compatibility, legacy, static, or inline-content file to bypass this limit. `backend/app/main.py` is the temporary oversized legacy exception while it retains the existing inline UI until the separately approved A3 migration. Existing oversized legacy files are grandfathered; the source-size script does not impose a no-growth comparison on them.
- Run `python backend/scripts/check-source-size.py` before reporting structural work complete.

## Documentation structure

- `README.md`: project entry point and concise current status.
- `AGENTS.md`: instructions for coding agents and contributors.
- `docs/`: architecture, decisions, roadmap, status, migration, backup/restore, operator, and TODO documents.
- Avoid creating temporary or duplicate root-level Markdown files. Put new durable documentation in `docs/`.

## Database and migration rules

- SQLite schema changes must go through `backend/app/migrations/runner.py`.
- Never add business tables at runtime with an ad-hoc `CREATE TABLE IF NOT EXISTS` outside a migration.
- Keep `schema_migrations` and `PRAGMA user_version` consistent.
- Migrations must be consecutive, idempotent, transactional, and covered by rollback tests.
- Backup/restore must preserve schema version and migration history.
- Do not manually edit migration history or version numbers in an operator workflow.

## AI development order

Use this dependency order:

```text
material revision
→ chunks
→ retrieval
→ citations
→ Q&A
→ cards / exercises
```

AI-generated cards and exercises must start as drafts, retain source revision and citation links, and never silently overwrite user edits or confirmed state.

## Testing

Use the project Python environment:

```text
C:\miniconda\py310\python.exe -m pytest backend/tests/
```

Before reporting a change complete:

1. Run focused tests for the changed area.
2. Run the complete backend test suite when infrastructure, migrations, storage, or API behavior changes.
3. Update `docs/STATUS.md` and `docs/TODO.md` only. Do not add a new evidence document for a slice that shipped no user-visible change.
4. Report limitations honestly; `implemented` is not the same as `real-pass`.

## Safety and deployment boundaries

- Supported deployment is single-process, single-instance, local storage.
- Do not claim support for multiple workers, shared `data_root`, cloud sync, multi-user deployment, real power-loss recovery, or production-scale capacity without dedicated evidence.
- Do not expose file paths, SQL, tracebacks, provider secrets, raw provider errors, or source text through logs or failure responses.
- Preserve failed databases and verified backups for diagnosis. Restore to a new empty target; do not overwrite a live data root with an unverified copy.
