# Phase 9B S1/S2 Acceptance Evidence

> 状态：**Phase 9B 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成**。
>
> 该完成声明不代表 Phase 9C/9D、真实 Provider generation、scheduler/worker、人工复核、系统级辅助技术或全局 production `real-pass`。本文件只记录当前源码、当前测试和当前限定环境的脱敏证据；prompt、设计文档或历史测试数字不单独构成完成证据。

## 1. Scope and non-goals

本次收口覆盖 Phase 9B 冻结的两条路径：

- **S1 学习节奏**：复用 Phase 9A plan/item/progress，显式配置 daily/weekly rhythm、IANA timezone、local-date allocation、planned minutes、summary 和手动 progress。没有自动进度、自动重排、提醒、日历、scheduler 或后台任务。
- **S2 资料笔记**：用户笔记、note blocks、knowledge module 组织、deterministic fake-provider `generate_note`、服务端 citation/source-link 验证、draft/confirm/reject/archive、显式 source refresh 和 bounded JSON/Markdown export。
- **生命周期与恢复**：delete/restore/purge/new revision 后的 source status、用户编辑保护、module/rhythm/progress 历史，以及 backup→verify→restore 到新空目录的 non-repair。

明确不在本次完成声明中：S3/S4/S5、S6/S7、真实 Provider generation acceptance、人工简答复核、提醒/推送/日历、scheduler/worker/queue/cancel、后台 stale scan、跨进程协调、多用户/认证/云同步、OCR/ASR、外部 vector DB、富文本/附件/多媒体、note revision/diff/merge、CSV/ICS/PDF 等扩展导出。

## 2. Environment, isolation and commands

### Environment

- Repository: `H:\studybuddy`
- Git commit under test: `87f7e51b9d8f3013e1d58d42235d574538c81a98`
- Python: `3.10.19` (`C:/miniconda/py310/python.exe`)
- Node: `v24.14.0`
- Playwright: `1.62.1`
- Browser: Chromium
- Browser workers: `1`; browser specs were run serially as required.
- Backend persistence: SQLite v10, temporary pytest data roots.
- Browser data roots: each spec/scenario owns and removes its isolated `H:\studybuddy-test\runs\formal-*` root; no shared live data root was used.

### Backend commands

Focused Gate C–H and related regression:

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/test_phase9b_domain.py backend/tests/test_phase9b_notes.py backend/tests/test_phase9b_rhythm.py backend/tests/test_phase9b_api.py backend/tests/test_phase9b_source_lifecycle.py backend/tests/test_phase9b_backup_restore.py backend/tests/test_migrations.py backend/tests/test_restore_acceptance.py backend/tests/test_backup_restore.py backend/tests/test_phase8_closeout.py backend/tests/test_phase9a_source_lifecycle.py backend/tests/test_phase9a_backup_restore.py backend/tests/test_governance_consistency.py -q
```

Result:

```text
58 passed in 15.07s
```

Complete backend regression:

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
```

Result:

```text
298 passed, 2 skipped in 81.80s
```

The two skipped backend tests are the opt-in real-provider smoke tests. They are deliberately outside the Phase 9B completion scope.

### Chromium commands

The following existing specs were each run separately with:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File H:\studybuddy\backend\scripts\test-browser.ps1 -Spec <spec>
```

The script passes `--workers=1 --reporter=line` to Playwright. Results were:

| Spec | Result |
|---|---:|
| `browser_file_import.spec.js` | 1 passed |
| `browser_folder_import.spec.js` | 1 passed |
| `browser_multi_file_import.spec.js` | 1 passed |
| `browser_material_management.spec.js` | 2 passed |
| `browser_material_search.spec.js` | 2 passed |
| `browser_material_pagination.spec.js` | 1 passed |
| `browser_material_recycle_bin.spec.js` | 3 passed |
| `browser_material_export.spec.js` | 2 passed |
| `browser_frontend_failure_contract.spec.js` | 6 passed |
| `browser_qa.spec.js` | 9 passed, 1 skipped |
| `browser_p6d.spec.js` | 2 passed |
| `browser_p6e.spec.js` | 4 passed |
| `browser_phase7.spec.js` | 2 passed |
| `browser_phase8.spec.js` | 3 passed |
| `browser_phase9a.spec.js` | 3 passed |
| `browser_phase9b.spec.js` | 3 passed |
| **Non-real-provider total** | **45 passed, 1 skipped** |

The default-disabled real-provider spec was also checked separately:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File H:\studybuddy\backend\scripts\test-browser.ps1 -Spec browser_p6e_real_provider.spec.js
```

Result: `2 skipped`. Its DeepSeek and Agnes tests require explicit provider/model/base URL/key gates and are not Phase 9B acceptance criteria. Separate P6-E provider evidence is maintained by `docs/P6E_ACCEPTANCE_EVIDENCE.md`.

### Artifact and cleanup boundary

- Formal durable evidence is this redacted document and the referenced source/test paths.
- Pytest temporary roots are created by pytest under the host temporary directory and are not repository artifacts.
- Browser scenarios use isolated `H:\studybuddy-test\runs\formal-*` roots and clean them per spec/scenario.
- Playwright diagnostic output, if produced under local `test-results/`, is test-run output, not a committed acceptance artifact.
- No database, original, backup, provider response, API key, browser trace, session HTML, raw prompt or test-run output is committed.

## 3. Gate A–I result

| Gate | Result | Evidence |
|---|---|---|
| A. Audit and scope | **passed** | `docs/phase9b/00_COMMON_CONTEXT.md`, `PHASE9B_DOMAIN_CONTRACT.md`, and the explicit S3–S7/scheduler/worker/provider non-goals |
| B. Domain contract | **passed** | `docs/phase9b/PHASE9B_DOMAIN_CONTRACT.md`; S1/S2 ownership, state transitions, citation/source lifecycle, export and restore boundaries are frozen |
| C. Migration/database | **passed** | `backend/app/migrations/runner.py` v10; `test_migrations.py`; schema/history/user_version/rollback and backup schema-version assertions in the focused run |
| D. Domain transactions | **passed** | `test_phase9b_domain.py`, `test_phase9b_notes.py`, `test_phase9b_rhythm.py`; ownership, limits, state protection, citation validation, rollback and deterministic summary |
| E. S2 workflow | **passed** | `test_phase9b_notes.py`, `test_phase9b_api.py`, `browser_phase9b.spec.js`; user/AI drafts, module organization, edit protection, transitions, source refresh and bounded export |
| F. S1 workflow | **passed** | `test_phase9b_rhythm.py`, `test_phase9b_api.py`, `browser_phase9b.spec.js`; settings, allocation move/delete, summary/progress and reload; no scheduler or auto-progress |
| G. API/UI | **passed** | Phase 9B API tests, Phase 9B Chromium desktop/narrow/keyboard/reload/failure paths, Phase 8/9A Chromium and frontend failure regression |
| H. Lifecycle/restore | **passed** | `test_phase9b_source_lifecycle.py`, `test_phase9b_backup_restore.py`, extended `restore_acceptance.py`; explicit refresh is the only positive source promotion, restore is non-repair |
| I. Full regression/closeout | **passed** | Focused `58 passed`; full backend `298 passed, 2 skipped`; related Chromium `45 passed, 1 skipped`; docs synchronized by this closeout |

## 4. S1 user path

The verified S1 path is:

```text
existing goal/plan/item
  → explicit rhythm settings
  → daily/weekly IANA timezone and period anchor
  → local-date planned-minute allocation
  → deterministic rhythm summary
  → explicit existing 9A progress event
  → reload/read recovery
```

Verified boundaries include settings/allocation input validation, duplicate allocation rejection, item/plan ownership, aggregate workload limits, terminal plan/item edit protection, summary grouping by explicit local date, source-warning visibility, append-only progress preservation, no allocation-to-progress conversion, no host implicit timezone, and no scheduler/auto-replan.

## 5. S2 user path

The verified S2 path is:

```text
indexed active material
  → retrieval/context/citation
  → user note or deterministic fake-provider AI draft
  → ordered note blocks and verified block-level source links
  → explicit module organization
  → draft edit protection
  → explicit confirm/reject/archive
  → citation dialog/source refresh/export/reload
```

AI artifacts start as drafts, retain generation operation and citation provenance, and are not allowed to overwrite user edits or terminal note state. User-created notes may be source-free but retain user-created provenance. Confirmed/rejected/archived notes are protected from ordinary patch or regeneration overwrite.

## 6. Source lifecycle

`test_phase9b_source_lifecycle.py` verifies:

- material delete downgrades relevant note links to `source_deleted` without changing confirmed/user-edited note, module, rhythm or progress history;
- material restore does not promote links on ordinary read;
- explicit source refresh can revalidate a fully matching source to `valid`;
- a new current revision leaves retained old identities `stale` rather than rewriting them;
- archived modules preserve existing note-module links and expose a warning;
- purge preserves opaque note source identity and changes links to `source_unavailable`;
- unavailable export does not return original name, stored path, material name, source text or unsafe location data.

## 7. Backup, verify, restore and non-repair

`test_phase9b_backup_restore.py` verifies:

- backup does not mutate the source database;
- manifest schema version is v10 and contains no source path or source body;
- backup verification succeeds;
- restore succeeds only to a new target with explicit confirmation;
- notes, blocks, note-module links, opaque source links/tombstones, generation operations, rhythm settings, allocations and append-only progress survive restore;
- confirmed/user-edited, archived/stale, unavailable and user-created draft states survive restore;
- `verify_restored_data()` performs read-only v10 schema/FK/projection/note/rhythm checks;
- provider, indexing, refresh and repair hooks are forbidden during restore acceptance;
- ordinary reads after restore do not promote stale/unavailable status and do not create new operations/progress/events.

## 8. API/UI failure, privacy and security boundaries

The API and browser evidence covers safe mapping for invalid payloads, not-found/invalid-state/conflict/server/provider failures, provider-not-configured, malformed/network refresh failure, duplicate action protection, stale/unavailable citations, retry/unlock behavior, narrow viewport and keyboard paths. The UI uses safe text rendering and maintains busy/stale guards.

The tested privacy boundary excludes API keys, Authorization headers, provider raw response, traceback, SQL, local data paths, stored paths, source body copies and unsafe material metadata from public errors, exports, unavailable citations and browser-visible content. Export responses are bounded and use the existing safe download contract.

## 9. Unverified boundaries

The following remain explicitly unverified or outside scope:

- real Provider generation for Phase 9B note/rhythm workflow, streaming, provider quality, quota, billing, uptime or global provider availability;
- human short-answer review, teacher/parent approval or collaborative review;
- Phase 9C S3/S4/S5 and Phase 9D S6/S7;
- reminders, calendar/push integration, scheduler, worker, queue, cancel, background stale scanning and cross-process coordination;
- system-level screen reader/AT evidence beyond browser semantics, and full OS/browser matrix;
- rich text, attachments, images/audio/video, OCR/ASR, note revision/diff/merge and expanded export formats;
- long-duration stability, real disk-full behavior, real power-loss recovery, network filesystem, hardware corruption, ACL/permission exhaustion and peak memory/S4 capacity;
- multiple workers/instances sharing a data root, multi-user/authentication/authorization, cloud sync, collaboration and production-scale deployment;
- this evidence does not claim a global production `real-pass`.

## 10. Accurate completion statement

> Phase 9B 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表 Phase 9C/9D、真实 Provider generation、scheduler/worker、人工复核或全局 production real-pass。

Next planned work is Phase 9C/9D only after their own contracts and gates; no Phase 9B scope expansion is implied by this closeout.
