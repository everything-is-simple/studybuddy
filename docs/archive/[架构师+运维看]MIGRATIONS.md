# Database migrations
<!-- STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->
## 统一执行协议（2026-09-27）

本文件与 `H:\studybuddy\docs\[所有角色看]AI_AGENT_TASK_DIALOGUE_TEMPLATES.md` v2.1 使用同一套执行口径。本文档中早于 2026-09-27 的报告、表格和历史标签保留其原始事实；历史标签只能在原日期、原范围和原证据路径下解释，不能升级为当前全局结论。

### 可执行 Prompt 的必填字段
- **角色**：本次执行者的职责。
- **唯一目标**：一个可判定的结果，不把多个目标合并成“全部处理”。
- **当前阶段**：只能填写 `P0`（边界确认）、`P1`（真实状态读取）、`P2`（真实操作执行）、`P3`（证据核对）、`P4`（交付与结论）之一，并按顺序推进。
- **允许读取/写入**：逐项列出绝对路径、URL、端点、数据根和输入；未列出的对象禁止访问或修改。
- **指定工具/命令/端口/输入**：必须原样执行；对象不可用时返回 `BLOCKED`，不得替换。
- **禁止操作、停止条件和证据路径**：逐项写明；每个结论必须有实际命令/动作、结果和绝对证据路径。

### 统一状态与范围
`PASS`、`FAIL`、`BLOCKED`、`LIMITED`、`NOT_APPLICABLE`、`NOT_VERIFIED` 是本项目当前统一结果状态。`implemented`、`configured`、`available`、测试通过、隔离环境通过只能描述实现或可见性，不能单独写成 `real-pass`。`real-pass` 只能表示本次指定真实目标、真实路径、真实输入和真实动作均有证据；未覆盖范围必须写 `NOT_VERIFIED`。

### 统一路径和运行基线
源码 `H:\studybuddy`；正式数据 `H:\studybuddy-data`；验证证据 `H:\studybuddy-test\verification`；隔离数据 `H:\studybuddy-test\data_root`；真实教材 `H:\studybuddy-ChinaTextbook`（只读）；组件测试 `H:\studybuddy-composer`；组合测试 `H:\studybuddy-integration`；日志 `H:\studybuddy-log`；临时目录 `H:\studybuddy-tmp`；正式地址 `http://127.0.0.1:8787`；首页 `http://127.0.0.1:8787/app/buddy.html`。

正式启动命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-data -Port 8787`。隔离验证命令为：`powershell -ExecutionPolicy Bypass -NoProfile -File H:\studybuddy\backend\scripts\start-studybuddy.ps1 -DataRoot H:\studybuddy-test\data_root -Port 8787`。不得把 `python -m backend.app serve`、其他端口、其他数据根或其他浏览器替换到已指定任务中。

### 强制禁止
不得凭推测输出；不得用 HTML 解析、按钮清单、curl/API 请求、静态检查或 headless 结果冒充可视浏览器点击；不得读取、复制、提交或展示密钥、Token、Cookie、真实教材正文、Provider 原始响应、SQL 或完整 traceback；不得在未授权时调用真实 Provider/OCR/ASR、发送 Email/飞书或扩大文件范围。工具、路径、页面、服务状态或证据不满足前置条件时，立即停止并报告 `BLOCKED`。

<!-- /STUDYBUDDY-UNIFIED-EXECUTION-PROTOCOL -->


Current schema version: **16**.

The authoritative migration history is `schema_migrations`; SQLite `PRAGMA user_version` must match it. The execution engine and public migration API remain at `backend/app/migrations/runner.py`; individual migration bodies are maintained in the adjacent `_vNN_*.py` modules, with shared helpers in `_helpers.py`.

```text
1 | canonical_material_schema
2 | ai_phase0_schema
3 | phase5_provider_metadata
4 | qa_operation_idempotency
5 | phase7_embedding_schema
6 | search_index_schema_contract
7 | phase8_cards_exercises_schema
8 | phase8_exercise_provenance
9 | phase9a_learning_plan_schema
10 | phase9b_material_learning_schema
11 | phase9c_exercise_feedback_schema
12 | phase9d_extended_learning_schema
13 | phase10_operation_task_schema
14 | fix_revision_fingerprint_material_id
15 | card_review_schedule
16 | knowledge_modules_source_evidence
```

## Repository layout

```text
backend/app/migrations/
  runner.py                 # execution engine, registry, history and version checks
  _helpers.py               # schema inspection and shared migration helpers
  _canonical.py             # canonical schema helper
  _ai_schema.py             # shared AI schema helper
  _v01_*.py ... _v16_*.py   # one idempotent body per registered version
```

Use `runner.py` as the only public execution entry point. Version modules are internal implementation modules and must not be invoked independently by application startup, backup, restore, or read paths.

## Rules

- Migrations are consecutive, recorded, idempotent, and run inside `BEGIN IMMEDIATE`.
- Schema DDL, migration-history insertion, and `PRAGMA user_version` are committed atomically.
- v11 adds the Phase 9C session/item snapshots, attempt linkage metadata, review/mistake/feedback facts, and cram-goal persistence schema. Domain validation and projections remain outside the migration.
- v12 adds the Phase 9D capture-session, transcript draft/segment, report snapshot, delivery-attempt, and capture-linked operation persistence schema. The approved 9D-0 partial scope now includes 9D-3 shared domain behavior, 9D-4 deterministic fake/loopback capture/transcription, 9D-5 explicit confirmed transcript ingestion into the existing S2 material/revision/chunk/retrieval/citation path, 9D-6 read-only report aggregation/redaction, 9D-7 default-off/allowlisted dry-run delivery audit, 9D-8 API, 9D-9 Chromium workspace, and 9D-10 source lifecycle plus backup/restore non-repair verification. Real OCR/ASR and live SMTP/Feishu delivery remain outside the v12 completion claim.
- v13 adds Phase 10 task envelopes (`operation_tasks`) and append-only task-attempt audit (`operation_task_attempts`). It preserves existing `ai_operations`, does not backfill historical operations or alter legacy synchronous APIs, and never persists raw content, secrets, paths, raw Provider payloads, answer keys, or submitted answers. The 10-3 runner uses the v13 schema but is explicit-only: startup, backup, restore and reads do not start or execute it. Composite project-scoped FKs, status/progress/retry checks, one-task-per-operation and at-most-one-running-attempt indexes provide structural protection; state transitions, progress monotonicity, lease compare-and-set, cancellation and retry policy remain repository/runner behavior.
- v14 fixes P14-P0-05: `revision_fingerprint` now includes `material_id` in its hash, so two materials with identical content get distinct fingerprints. This is an in-place UPDATE migration (no table rebuild, no CASCADE risk). All existing fingerprints are recomputed with the new formula during upgrade. The UNIQUE constraint remains on the same column and continues enforcing one revision per (material, content, parser) combination. Rollback recomputes fingerprints using the old 4-tuple formula (without `material_id`).
- v15 adds card review scheduling (`due_at`, `interval_days`) and per-card review idempotency keys. Review writes are transactional, duplicate retries replay the original result, and reusing a key for a different result is rejected.
- v16 extends existing v9 module identities with S2 source evidence, draft confirmation metadata, FTS search and exercise links. It never creates a competing knowledge module namespace. Mastery is a read-only projection of scored exercise attempts. DDL and triggers remain inside the runner transaction; backup/restore preserves all facts.
- A failure rolls back; the service never becomes ready with a half-upgraded schema.
- Migration history and `PRAGMA user_version` are never edited manually.
- There is no automatic down migration. Preserve the failed database and restore a verified backup into a new empty target when recovery is required.

## Upgrade preflight

升级前必须停止访问 live `data_root` 的所有 StudyBuddy/SQLite writer，先创建并 verify 新的 rollback backup，再执行：

```text
D:/miniconda/py310/python.exe -m app.cli upgrade-preflight \
  --data-root <live-data-root> \
  --backup <verified-backup-root>
```

该命令不执行 migration 或任何写入：检查 database header、integrity、foreign keys、连续 history/`PRAGMA user_version`、hash-derived originals、data root/database ACL access，以及 rollback backup 的重新 verify 和 schema match。`status=ready` 只是明确启动 migration 前的 operator go signal；它不是锁，也不代替 migration runner 的 `BEGIN IMMEDIATE` transaction。

历史 schema backup 只要 history 与 `user_version` 一致即可验证并作为 rollback evidence；restore 保留其版本，不自动升级。恢复后的目标只能由后续显式启动的新版本迁移。直接 current v1 restore target 必须通过 current-schema verify/acceptance。

## Inspecting a database

```text
D:/miniconda/py310/python.exe -m app.cli schema-version \
  --database <data-root>/studybuddy.sqlite3
```

The command validates; it does not migrate or repair.

## Upgrade and recovery

Use [`operations/OPERATOR_UPGRADE.md`](../.archive/operations/OPERATOR_UPGRADE.md) for the stop, backup, verify, preflight, upgrade, acceptance, and failure-recovery procedure. The module split in A2.3 does not change this operator contract: callers use `backend/app/migrations/runner.py`; `_vNN_*.py` files are implementation modules, not independent migration entry points. Backup/restore version checks are described in [`BACKUP_RESTORE.md`]([运维看]BACKUP_RESTORE.md). On any schema/history/integrity/original failure, stop the service, preserve the failed database and verified backup, and restore only into a new empty target. v1 has no runtime read-only serving mode and does not claim real power-loss recovery.
