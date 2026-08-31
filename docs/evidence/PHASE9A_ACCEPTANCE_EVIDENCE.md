# Phase 9A Acceptance Evidence

> 状态：`completed`，范围限定为 deterministic fake-provider / local single-process / SQLite / Chromium / backup-restore。
>
> 准确声明：Phase 9A 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表 Phase 9B–9D、Phase 9 全部完成或全局 production `real-pass`。
>
> Exact statement: Phase 9A completed in the deterministic fake-provider / local single-process / SQLite / Chromium / backup/restore scope.
>
> 本文为脱敏 evidence，不包含数据库、backup 文件、上传原文件、Provider key、私有路径、raw provider response 或测试运行 artifact。

## 1. Scope and gates

已验证的 9A 最小范围：

- learning goal、knowledge module；
- study plan、study plan item；
- same-plan dependency DAG；
- append-only progress event 与可重算 summary；
- module/item source link 与 material revision/chunk/span identity；
- material delete/restore/purge/re-index source lifecycle；
- backup、verify、restore 到新空 data root；
- startup/read/verify/restore non-repair；
- 单进程 SQLite backend、FastAPI API 和本地 Chromium workspace。

Gate 状态：

| Gate | Result | Evidence |
|---|---|---|
| A Contract | pass | `../contracts/PHASE9A_DOMAIN_CONTRACT.md` |
| B Database | pass | v9 migration、history、rollback、idempotency tests |
| C Domain | pass | `test_phase9a_domain.py` |
| D API | pass | `test_phase9a_api.py` |
| E Source lifecycle | pass | `test_phase9a_source_lifecycle.py`、`browser_phase9a.spec.js` |
| F UI | pass | `browser_phase9a.spec.js` |
| G Restore | pass | `test_phase9a_backup_restore.py`、restore acceptance |
| H Closeout | pass | 本文与完整回归结果 |

## 2. Backend evidence

9A focused backend matrix：

```text
python -m pytest \
  backend/tests/test_migrations.py \
  backend/tests/test_phase9a_domain.py \
  backend/tests/test_phase9a_api.py \
  backend/tests/test_phase9a_source_lifecycle.py \
  backend/tests/test_phase9a_backup_restore.py \
  backend/tests/test_backup_restore.py \
  backend/tests/test_restore_acceptance.py -q
```

Result: `36 passed`.

Additional frontend/API/lifecycle focused Python command was attempted with an incorrect non-existent filename and was corrected to the actual Chromium failure contract below; it was not counted as a failed test result.

Full backend：

```text
python -m pytest backend/tests/ -q
```

Result: `272 passed, 2 skipped`.

Skipped tests are default-off real Provider smoke tests only. No default backend test uses real network or commits a database/original/artifact into the repository.

## 3. Chromium evidence

Phase 9A workspace：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  backend/scripts/test-browser.ps1 browser_phase9a.spec.js
```

Result: `3 passed`, one worker. Covered:

- goal → module → draft plan → items → dependency;
- dependency cycle failure;
- confirm → active → completed item → summary → reload;
- explicit source refresh;
- delete → restore → explicit refresh → purge → unavailable;
- active plan warning with preserved progress;
- 500/retry failure contract;
- narrow viewport 390x844;
- keyboard navigation and safe error rendering.

Phase 8 regression：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  backend/scripts/test-browser.ps1 browser_phase8.spec.js
```

Result: `3 passed`.

Related frontend failure contract：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  backend/scripts/test-browser.ps1 browser_frontend_failure_contract.spec.js
```

Result: `6 passed`.

## 4. Restore and non-repair evidence

The existing SQLite Online Backup API snapshots the complete v9 database. No new migration or external index manifest was needed for 9A. `test_phase9a_backup_restore.py` verifies:

- all eight 9A tables and related revision/chunk/embedding/operation rows survive backup and restore;
- draft, confirmed, active, paused, completed and archived plans survive;
- pending, in-progress, completed and archived item projections survive;
- dependencies and append-only progress events survive;
- progress summary and `user_edited` protection survive;
- `valid`, `stale` and `source_unavailable` links remain unchanged;
- unavailable source is not promoted by verify, restore, startup or read;
- restore to a new empty root rebases material `stored_path` to the new hash-derived originals layout;
- restore target confirmation and non-empty target boundaries remain safe;
- manifests remain free of live data root, source text, secrets and raw exceptions.

Restore/read/verify do not create plans, append events, run Provider calls, index revisions, rebuild chunks/FTS/embeddings or repair source lifecycle. The `stored_path` rebase is a restore-target physical reference update, not a business-state repair.

## 5. Current product boundaries

Still not implemented or not verified:

- 9B S1/S2, 9C S3/S4/S5 and conditional 9D S6/S7;
- real Provider plan generation;
- human plan review workflow;
- reminders, scheduler, recurrence, automatic re-plan;
- workers, queues, cancellation and long-task recovery;
- multi-user, authentication, authorization, cloud sync and multi-instance deployment;
- real power-loss, disk-full, disk corruption, hardware/filesystem failure, network filesystem and ACL recovery;
- system-level screen reader, extreme-content and long-duration stability acceptance;
- global production `real-pass`.

These limitations do not invalidate the scoped Phase 9A completion statement.
