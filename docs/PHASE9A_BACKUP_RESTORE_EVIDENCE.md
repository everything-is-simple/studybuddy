# Phase 9A Backup / Restore Evidence

> 状态：`restore-gates-pass`。9A-7 backup/verify/restore 与 non-repair gate 已通过；9A-8 完整 acceptance/documentation closeout 尚未完成，因此不得把 Phase 9A 写成 `completed`。
>
> 本文是脱敏 evidence，不包含数据库、backup 文件、原文件、Provider key、私有路径或测试运行输出。

## Scope

覆盖 9A 八张业务表：

- `learning_goals`
- `knowledge_modules`
- `study_plans`
- `study_plan_items`
- `study_plan_dependencies`
- `study_progress_events`
- `module_source_links`
- `plan_item_source_links`

同时验证与这些对象相关的 material revision、chunk、embedding、AI operation 表在 SQLite snapshot 中保持一致。

## Implementation Boundary

9A 不需要新的 migration、外部 index manifest 或额外 backup 文件。现有 `backend/app/backup.py` 使用 SQLite Online Backup API 快照完整 database，因此 v9 新表随数据库进入 backup。manifest 继续记录 database hash、integrity、foreign-key、schema version 和 originals 引用；`verify_backup()` 不运行 migration、不 rebuild、不 repair。

restore 到新空 data root 时，数据库中的 material `stored_path` 会显式重定位到新目标的 hash-derived `originals/<sha256[:2]>/<sha256[2:]>/original`。这只修正恢复目标的物理路径引用，不生成材料、extraction、revision、chunk、plan 或 source link，也不提升 source 状态。

## Evidence Commands

Focused 9A-7 and related backup/restore acceptance：

```text
C:/miniconda/py310/python.exe -m pytest \
  backend/tests/test_phase9a_backup_restore.py \
  backend/tests/test_backup_restore.py \
  backend/tests/test_ai_backup_restore.py \
  backend/tests/test_restore_acceptance.py -q
```

Result: `13 passed`.

Full backend:

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
```

Result: `272 passed, 2 skipped`. The two skipped tests are default-off real Provider smoke tests.

## Verified Contract

- backup → verify → restore to a new empty root preserves v9 schema, all migration history, `PRAGMA user_version`, all 9A table rows and material/original references.
- draft, confirmed, active, paused, completed and archived plan states survive restore.
- plan items preserve pending, in-progress, completed and archived projections; `user_edited` remains unchanged.
- same-plan dependency rows and append-only progress events survive restore; progress summary returned through API is unchanged.
- source links preserve `valid`, `stale` and `source_unavailable`; unavailable links are never promoted to `valid` by verify, restore, startup or read.
- `verify_backup()`, `restore_backup()` and offline restore acceptance do not call Provider, index material revisions, rebuild chunks/FTS/embeddings, create plans, append progress, or repair source lifecycle.
- non-empty restore targets and missing confirmation are rejected without modifying the target.
- manifests do not contain live data root, stored path, source text, secrets or raw errors.

## Remaining Limitations

- 9A-8 full acceptance/documentation closeout remains pending.
- Real power-loss, disk corruption, hardware/filesystem failure, disk-full, network filesystem, ACL and multi-process/multi-instance restore behavior remain `not_verified`.
- This gate is for the supported local single-process, single-instance SQLite deployment boundary only.
