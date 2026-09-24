# StudyBuddy Verification Baseline And Repository Bridge Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Every task must preserve the existing user-visible/API contracts and end with its own verification.

**Goal:** Establish one reproducible backend/browser verification baseline, align governance facts and the 32 KiB source gate, then remove the remaining `_legacy` repository bridge without changing StudyBuddy behavior, and finally reconcile RapidOCR/ASR documentation and canonical paths.

**Architecture:** Keep `backend/app/main.py` and `backend/app/repository.py` as thin compatibility façades while moving ownership into bounded modules. Browser tests receive paths, interpreter, test root, and backend root from one Playwright bootstrap layer; test fixtures remain under `H:\studybuddy-test`, never `H:\studybuddy-data`. Documentation claims are derived from fresh command output and scoped evidence, with `not_verified` retained where runtime proof is absent.

**Tech Stack:** Python 3.10, pytest, FastAPI, SQLite migration runner, Node.js, Playwright 1.62.1, PowerShell, native HTML/JavaScript.

**Spec:** `AGENTS.md`, `docs/[架构师看]ARCHITECTURE.md`, `docs/[架构师+测试看]CODE_TEST_GOVERNANCE.md`, `docs/[需求+架构看]ROADMAP_CAPABILITIES.md`, `docs/[需求+所有角色看]STATUS.md`, `docs/[需求看]TODO.md`.

## Global Constraints

- Support remains local single-process, single-instance, SQLite, and local disk only.
- Do not start the formal service, modify `H:\studybuddy-data`, read real textbook content, or expose secrets.
- Do not change schema, migration history, API paths, stable error codes, response contracts, or user-visible behavior.
- All new or substantially rewritten `.py`, `.js`, `.css`, `.html`, `.ps1`, and `.json` files remain at or below 32 KiB; do not evade the rule by creating a larger compatibility or static file.
- Use `D:\miniconda\py310\python.exe -m pytest backend/tests/` for the formal backend gate and keep browser evidence separate from historical artifacts.
- Each behavior change requires a failing focused test before production implementation, then focused and regression verification.

---

### Task 0: Freeze The Current Baseline And Working-Tree Boundary

**Files:**
- Read: `AGENTS.md`, `README.md`, `docs/INDEX.md`, authority docs listed above.
- Read: current `git status`, `git diff`, untracked files, and test/artifact roots.
- Create: `docs/superpowers/plans/2026-09-24-studybuddy-verification-baseline.md` (this plan).

**Interfaces:**
- Produces a timestamped command record in the task output, not a production artifact.
- Later tasks must preserve all pre-existing tracked and untracked changes.

- [ ] Record `git status --short`, current commit, source-size result, `compileall` result, Playwright `--list` count, and direct liveness/health/readiness status.
- [ ] Record every pre-existing modified/untracked path; never use reset, checkout, clean, or recursive deletion.
- [ ] Establish that all test data paths resolve below `H:\studybuddy-test` and production data remains untouched.
- [ ] Stop and report if a change cannot be isolated from unrelated user work.

Verification: repeat the read-only status and runtime checks after every later task; the baseline record must remain explainable from current files and command output.

### Task 1: Make Browser Test Environment Injection Reproducible

**Files:**
- Modify: `playwright.config.js`.
- Modify: `backend/scripts/test-browser.ps1`.
- Modify: `backend/scripts/browser-source-loader.js` only when a focused test proves the rewrite is incomplete.
- Create/modify: one focused contract test under `backend/tests/` for environment resolution, if no existing test covers it.
- Do not mass-edit browser specs until the compatibility rewrite is proven.

**Interfaces:**
- Environment variables: `STUDYBUDDY_PYTHON`, `STUDYBUDDY_BACKEND_ROOT`, `STUDYBUDDY_TEST_ROOT`.
- Browser specs continue to spawn `uvicorn app.main:app`, but literals resolve through the loader to the injected values.
- Every run uses a unique test data root or an explicit caller-provided non-production root.

- [ ] Write a failing test proving a browser spec with legacy `C:/miniconda/py310/python.exe`, `H:/studybuddy/backend`, and `H:/studybuddy-test/...` literals resolves to injected values.
- [ ] Run that focused test and confirm the expected failure.
- [ ] Implement the minimal loader/config/script changes; preserve existing `workers=1` and no external network behavior.
- [ ] Add explicit validation rejecting `H:\studybuddy-data` as the browser test root and create the test root if absent.
- [ ] Run `npx playwright test --list` and one static browser spec; classify Chromium launch failures as environment evidence, not test passes.

### Task 2: Restore The Backend Gate And Complete The 32 KiB Gate

**Files:**
- Modify: `backend/app/repository.py` and owning domain export modules only for missing public compatibility names.
- Modify: `backend/scripts/check-source-size.py`.
- Modify: `backend/app/templates/*` or other oversized managed source files only through behavior-preserving bounded splits.
- Modify: focused tests under `backend/tests/` for each exported symbol and source-size behavior.

**Interfaces:**
- `app.repository` must expose every symbol imported by `backend/app` and `backend/tests`.
- `check-source-size.py` must enforce `MAX_BYTES = 32 * 1024` over changed, staged, and untracked managed source files, without exempting existing oversized files.
- Legacy HTML assembly must produce the exact pre-split payload hash when a reference hash is supplied.

- [ ] Write failing import-contract tests for `study_weekly_trend` and `PHASE9D_REPORT_MAX_EXPORT_BYTES`, and failing source-size tests for an oversized managed file.
- [ ] Run them and confirm failures identify missing exports and the wrong threshold/exception behavior.
- [ ] Add the missing exports in the correct owning façade; do not restore `dir(_legacy)` wholesale.
- [ ] Split any remaining oversized managed source into ordered bounded fragments without changing assembled bytes or behavior.
- [ ] Run focused import/governance tests, `git diff --check`, source-size, `compileall`, then the full backend gate.

### Task 3: Make Governance Facts Single-Source And Current

**Files:**
- Modify: `docs/[需求+所有角色看]STATUS.md`.
- Modify: `docs/[需求看]TODO.md`.
- Modify: `docs/[需求+架构看]ROADMAP_CAPABILITIES.md`.
- Modify: `docs/[架构师看]AI_LEARNING_ARCHITECTURE.md`.
- Modify: `docs/[架构师看]ARCHITECTURE.md`.
- Modify: `docs/[架构师+测试看]CODE_TEST_GOVERNANCE.md`.
- Modify: `backend/tests/test_governance_consistency.py` only to assert stable facts rather than stale historical numbers or wording variants.

**Interfaces:**
- Current backend counts come only from the latest reproducible command output.
- Historical evidence remains explicitly historical.
- RapidOCR remains C2 Integration only unless a Formal contract/evidence exists; ASR canonical path is exactly `H:\Whisper`.

- [ ] Add/adjust failing governance assertions for the current count, scoped browser `not_verified`, RapidOCR C2-only status, and canonical ASR path.
- [ ] Run the governance test and confirm it fails on stale wording/counts.
- [ ] Update the minimum authoritative facts and remove contradictory active claims; do not rewrite archived evidence as current.
- [ ] Run governance tests and a text scan for old counts, `H:\WhisperCli`, and contradictory RapidOCR statements.

### Task 4: Remove The `_legacy` Repository Bridge Incrementally

**Files:**
- Modify: `backend/app/repositories/_legacy_part_*.py` and new bounded domain modules as needed.
- Modify: `backend/app/repositories/materials.py`, `plans.py`, `practice.py`, `capture.py`, `reports.py`, `ai.py`, `tasks.py`.
- Modify: `backend/app/repository.py` only to preserve a thin import/patch façade.
- Add focused tests beside existing domain tests; do not alter production schema.

**Interfaces:**
- Public imports from `app.repository` remain stable.
- Domain modules own their constants and functions; `_legacy` is not the implementation registry for migrated domains.
- Existing monkeypatch targets (`_create_retrieval_run`, `_insert_search_row`, and documented patch points) remain supported until their tests are migrated.

- [ ] Inventory each symbol imported by app/tests and map it to one owning domain module.
- [ ] For one domain at a time, write a failing ownership/import test showing the domain module works without a corresponding `_legacy` lookup.
- [ ] Extract the minimal implementation and preserve transaction/error semantics.
- [ ] Run that domain's focused tests, then the complete backend suite before starting the next domain.
- [ ] Remove only dead bridge exports after all callers and monkeypatch contracts have moved; never delete `_legacy` code based on unused-looking names alone.

### Task 5: Final Runtime And Media-Path Reconciliation

**Files:**
- Read/modify only if contradicted: `docs/[需求+所有角色看]STATUS.md`, `docs/[需求+架构看]ROADMAP_CAPABILITIES.md`, `docs/[需求看]TODO.md`, `docs/[架构师看]ARCHITECTURE.md`, `docs/[架构师看]AI_LEARNING_ARCHITECTURE.md`.
- Read: `backend/app/providers/`, Composer/Integration manifests and evidence, without opening secret-bearing material.

**Interfaces:**
- No production service start is required for this audit slice.
- Runtime claims require direct process/port plus liveness/health/readiness evidence.
- Media claims distinguish `configured`, `available`, `integration_passed`, `implemented`, `verified`, `real-pass`, and `not_verified`.

- [ ] Verify ASR references consistently use `H:\Whisper` and do not expose model/token content.
- [ ] Verify RapidOCR references consistently say strict C2 Integration passed but Formal fallback is not installed/verified.
- [ ] Re-run the final backend gate, browser list, one browser spec, source-size, compileall, and direct runtime checks.
- [ ] Update only the current fact ledger; keep the goal active until every required gate has authoritative evidence.

## Completion Criteria

- The formal backend command completes without collection/import errors and its count is recorded from that run.
- Browser test configuration is portable across the configured Python/test roots; full browser status is either freshly passed or explicitly `not_verified` with the exact environment blocker.
- The 32 KiB gate rejects oversized changed/staged/untracked managed source and the existing template payload remains behavior-equivalent after splitting.
- Active governance docs agree on current counts, scoped capability status, RapidOCR status, and `H:\Whisper`.
- `_legacy` is no longer the implementation ownership point for the migrated repository domains, while public imports and required monkeypatch contracts remain intact.
- No production database, service, credentials, real textbook content, or unrelated user changes were modified.
