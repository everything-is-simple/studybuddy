# Phase 9C S3/S4/S5 Acceptance Evidence

> 状态：**Phase 9C 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成**。
>
> 该完成声明不代表 Phase 9D、真实 Provider generation、scheduler/worker、人工复核、系统级辅助技术或全局 production `real-pass`。本文件只记录当前源码、当前测试和当前限定环境的脱敏证据；prompt、设计文档或历史测试数字不单独构成完成证据。

## 1. Scope and non-goals

本次收口覆盖 Phase 9C 冻结的三条路径：

- **S3 PracticeRunner：限时练习**：复用 Phase 8 exercise/card、attempt 和确定性评分能力，增加显式 practice session、immutable item snapshot、服务端 deadline、逐题 submit/finish/expire/result；不做后台计时器、自动排程或跨 session 提醒。
- **S4 ErrorFixer：错题改错**：从真实 append-only attempt/grading/review 事实产生错题投影；支持错因/反馈、用户显式 mark-mistake、短答人工复核（`reviewed`/`correct`/`incorrect`/`uncertain`）、redo 新 attempt、archive 和 weak-point 实时 projection；不把 AI 建议当事实。
- **S5 ExamCrammer：期末冲刺**：用户显式建立 cram goal/exam session，选择范围和练习形成 snapshot，复用 S3 session/attempt/grading 和 S4 feedback/weak-point，产出结果汇总；不自动改写 9A plan/item/progress/rhythm，不启动 scheduler。

明确不在本次完成声明中：S6/S7、真实 Provider generation acceptance、人工简答复核（S4 仅含本地单用户 review）、提醒/推送/日历、scheduler/worker/queue/cancel、后台 stale scan、跨进程协调、多用户/认证/云同步、OCR/ASR、外部 vector DB、富文本/附件/多媒体、Phase 9D、全局 production `real-pass`。

## 2. Environment, isolation and commands

### Environment

- Repository: `H:\studybuddy`
- Git commit under test: `41066febb860b5b665f72d50b75eca366a2d8167`
- Python: `3.10.19` (`C:/miniconda/py310/python.exe`)
- Node: `v24.14.0`
- Playwright: `1.62.1`
- Browser: Chromium
- Browser workers: `1`; browser specs were run serially as required.
- Backend persistence: SQLite v11, temporary pytest data roots.
- Browser data roots: each spec/scenario owns and removes its isolated `H:\studybuddy-test\runs\formal-*` root; no shared live data root was used.

### Backend commands

Focused Gate C–I and related regression:

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/test_phase9c_domain.py backend/tests/test_phase9c_api.py backend/tests/test_phase9c_source_lifecycle.py backend/tests/test_phase9c_backup_restore.py backend/tests/test_migrations.py backend/tests/test_restore_acceptance.py backend/tests/test_backup_restore.py backend/tests/test_phase8_closeout.py backend/tests/test_phase9a_source_lifecycle.py backend/tests/test_phase9a_backup_restore.py backend/tests/test_phase9b_source_lifecycle.py backend/tests/test_phase9b_backup_restore.py backend/tests/test_governance_consistency.py -q
```

Result:

```text
59 passed in 18.20s
```

Complete backend regression:

```text
C:/miniconda/py310/python.exe -m pytest backend/tests/ -q
```

Result:

```text
320 passed, 2 skipped in 112.95s
```

The two skipped backend tests are the opt-in real-provider smoke tests. They are deliberately outside the Phase 9C completion scope.

### Chromium commands

Phase 9C focused spec:

```text
cmd /c "cd /d H:\studybuddy && npx playwright test backend/tests/browser_phase9c.spec.js --workers=1"
```

Result:

```text
3 passed (8.2s)
```

Related regression (Phase 8/9A/9B + failure contract, run with `--workers=1`):

| Spec | Result |
|---|---:|
| `browser_frontend_failure_contract.spec.js` | 6 passed |
| `browser_phase8.spec.js` | 3 passed |
| `browser_phase9c.spec.js` | 3 passed |
| **Related Chromium total** | **12 passed** |

Default-disabled real-provider spec:

```text
cmd /c "cd /d H:\studybuddy && npx playwright test backend/tests/browser_p6e_real_provider.spec.js --workers=1"
```

Result: `2 skipped`. Its DeepSeek and Agnes tests require explicit provider/model/base URL/key gates and are not Phase 9C acceptance criteria.

### Artifact and cleanup boundary

- Formal durable evidence is this redacted document and the referenced source/test paths.
- Pytest temporary roots are created by pytest under the host temporary directory and are not repository artifacts.
- Browser scenarios use isolated `H:\studybuddy-test\runs\formal-*` roots and clean them per spec/scenario.
- Playwright diagnostic output, if produced under local `test-results/`, is test-run output, not a committed acceptance artifact.
- No database, original, backup, provider response, API key, browser trace, session HTML, raw prompt or test-run output is committed.

## 3. Gate A–J result

| Gate | Result | Evidence |
|---|---|---|
| A. Audit and scope | **passed** | `prompts/phase9c/9C-0_现状审计与范围冻结.md`, `PHASE9C_AUDIT_AND_SCOPE.md`; S3/S4/S5 boundaries and 9D/Phase 10 non-goals are explicit |
| B. Domain contract | **passed** | `../contracts/PHASE9C_DOMAIN_CONTRACT.md`; S3/S4/S5 ownership, state transitions, submission/idempotency, mistake/feedback/weak-point projection, cram linkage, and privacy boundaries are frozen |
| C. Migration/database | **passed** | `backend/app/migrations/runner.py` v11 (`phase9c_exercise_feedback_schema`); `test_migrations.py`; schema/history/user_version/rollback and backup schema-version assertions |
| D. Domain transactions | **passed** | `test_phase9c_domain.py`; shared domain for practice/cram session, immutable item snapshot, append-only attempt/review/feedback, mistake/weak-point projection, source status downgrade, privacy boundary |
| E. S3 workflow | **passed** | `test_phase9c_domain.py`, `test_phase9c_api.py`, `browser_phase9c.spec.js`; session lifecycle, server deadline, MC/TF deterministic grading, short-answer `pending_review`, duplicate/idempotency replay, expired finish, result summary, source lifecycle read path |
| F. S4 workflow | **passed** | `test_phase9c_domain.py`, `test_phase9c_api.py`, `browser_phase9c.spec.js`; deterministic/review/user-marked mistake fact distinction, case/occurrence dedup, uncertain/archive/reopen, redo creates new attempt, weak-point projection, review privacy, rollback |
| G. S5 workflow | **passed** | `test_phase9c_domain.py`, `test_phase9c_api.py`; cram goal lifecycle (`draft→active→completed/archived`), explicit cram session with item snapshot, S3 attempt/grading/reuse, mistake/weak-point summary, plan/progress/rhythm untouched, selection/project/target boundary |
| H. API/UI | **passed** | `test_phase9c_api.py`; S3/S4/S5 routes with stable 400/404/409/422/500, server project scope injection, Idempotency-Key mapping, privacy (no answer key/submitted answer/source text in list/detail), Chromium desktop/narrow/keyboard/reload/failure/privacy DOM |
| I. Lifecycle/restore | **passed** | `test_phase9c_source_lifecycle.py`, `test_phase9c_backup_restore.py`, extended `restore_acceptance.py`; delete/restore/purge/re-index source status downgrade; backup→verify→new-empty-target restore preserves v11 history/facts/statuses; non-repair verified |
| J. Full regression/closeout | **passed** | Focused `59 passed`; full backend `320 passed, 2 skipped`; related Chromium `12 passed`; docs synchronized by this closeout |

## 4. S3 user path

The verified S3 path is:

```text
confirmed/ready exercise (same project)
  → explicit practice session create (server assigns project scope, status, deadline)
  → session start (server writes started_at/deadline_at)
  → per-item submit (immutable snapshot, server-grade MC/TF or pending_review short-answer)
  → duplicate/key replay or mismatch handled safely
  → session finish or implicit expired finish
  → result summary (score ratio, scored/pending/unanswered/source warnings)
  → reload/read recovery
```

Verified boundaries include server-authoritative time (no client elapsed/score/deadline accepted), first-submit-only append-only attempt, idempotency key replay vs. mismatch conflict, expired session safe finish, immutable snapshot isolation from later exercise edits, privacy (no answer key/submitted answer/source full text in result), and source-deleted/purged read path preserves history with `source_deleted`/`source_unavailable` status.

## 5. S4 user path

The verified S4 path is:

```text
append-only attempts + deterministic grading + human review facts
  → mistake case list/detail (dedup by project/exercise/revision fingerprint)
  → occurrence/feedback history (append-only, no overwrite)
  → short-answer manual review (local_user reviewer, secure feedback)
  → explicit user mark-mistake (separate from deterministic/review facts)
  → review → fixed / archive / reopen lifecycle
  → weak-point projection (derived, not a fact table)
  → redo creates new practice session + new attempt; old facts preserved
```

Verified boundaries include strict separation of fact sources (deterministic incorrect ≠ AI suggestion ≠ user guess), pending_review not auto-entering mistake, uncertain review preserved without forcing incorrect, fixed→reopen creating new occurrence rather than modifying history, review not touching original attempt grading, source soft-delete/purge degrading only to safe status, and rollback preserving no half-fact.

## 6. S5 user path

The verified S5 path is:

```text
existing cram goal (draft → active)
  → explicit cram session creation (item snapshot, distinct, same-project, ready exercises, ≤ target count/50 cap)
  → reuse of S3 session/item/attempt/grading/expiry/result via session_kind='cram'
  → result summary (deterministic score, pending review, mistake count, weak-points, source warnings)
  → goal completed only after finished/expired cram session
```

Verified boundaries include goal date/timezone as display coordinates only (no scheduler), selection snapshot enforced at create time, no write to `study_progress_events`/plan/item/rhythm allocations, source unavailable/stale showing safe warnings only, and privacy (no answer key/submitted answer/raw source in result).

## 7. Source lifecycle

`test_phase9c_source_lifecycle.py` verifies:

- material delete downgrades relevant session-item/exercise citation snapshots to `source_deleted` without changing attempt/review/mistake/feedback/cram history;
- material restore does not promote links on ordinary read;
- material purge changes links to `source_unavailable`; export of a purged source does not return name, stored path, body text or unsafe location data;
- new current revision leaves retained identities `stale`;
- session result reads remain valid after source status downgrade, only showing safe warnings.

## 8. Backup, verify, restore and non-repair

`test_phase9c_backup_restore.py` verifies:

- backup does not mutate the source database;
- manifest schema version is v11 and contains no source path or source body;
- backup verification succeeds;
- restore succeeds only to a new target with explicit confirmation;
- `practice_sessions`, `practice_session_items`, `exercise_attempt_reviews`, `mistake_cases`, `mistake_occurrences`, `mistake_feedback_events`, `cram_goals` survive restore with correct statuses;
- session/source status linkage preserved after restore;
- `verify_restored_data()` performs read-only v11 schema/FK/projection/session/mistake/cram checks;
- provider, indexing, refresh and repair hooks are forbidden during restore acceptance;
- ordinary reads after restore do not promote stale/unavailable status and do not create new operations/progress/events.

## 9. API/UI failure, privacy and security boundaries

The API and browser evidence covers safe mapping for invalid payloads, not-found/invalid-state/conflict/server/provider failures, provider-not-configured, malformed/network refresh failure, duplicate action protection, stale/unavailable citations, retry/unlock behavior, narrow viewport and keyboard paths. The UI uses safe text rendering and maintains busy/stale guards.

The tested privacy boundary excludes API keys, Authorization headers, provider raw response, traceback, SQL, local data paths, stored paths, answer key JSON, submitted answer text, source body copies and unsafe material metadata from public errors, exports, session results, attempt detail, browser-visible content and unavailable citations.

## 10. Unverified boundaries

The following remain explicitly unverified or outside scope:

- real Provider generation for S3/S4/S5 workflows, streaming, provider quality, quota, billing, uptime or global provider availability;
- multi-user/authentication/authorization;
- reminders, calendar/push integration, scheduler, worker, queue, cancel, background stale scanning and cross-process coordination;
- system-level screen reader/AT evidence beyond browser semantics, and full OS/browser matrix;
- rich text, attachments, images/audio/video, OCR/ASR;
- long-duration stability, real disk-full behavior, real power-loss recovery, network filesystem, hardware corruption, ACL/permission exhaustion and peak memory/S4 capacity;
- multiple workers/instances sharing a data root, cloud sync, collaboration and production-scale deployment;
- this evidence does not claim a global production `real-pass`.

## 11. Accurate completion statement

> Phase 9C 已在 deterministic fake-provider、单进程 SQLite、本地 Chromium 与 backup/restore 的明确范围内完成；不代表 Phase 9D、真实 Provider generation、scheduler/worker、人工复核、系统级辅助技术或全局 production `real-pass`。

Next planned work is Phase 9D only after its own contract and gates; no Phase 9C scope expansion is implied by this closeout.
