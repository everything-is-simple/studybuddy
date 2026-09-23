# StudyBuddy Agent Instructions

StudyBuddy is a local, single-process FastAPI + SQLite capability-integration system for user-owned study material; it does not train models.

## Delivery
- An active slice must change what a user can do in the browser or CLI; audit/contract/status-only work requires explicit request.
- `implemented` is not `real-pass`; keep unverified scope labeled `not_verified`. Capabilities must be discoverable; missing components surface as `not_installed` or `not_configured`.
- `report_delivery` is default-off and per-use authorized.

## Boundaries
- Source: `H:\studybuddy`; production: `backend/app/`; formal tests: `backend/tests/`; durable docs: `docs/`.
- Active data root: `H:\studybuddy-data`; never use retired `H:\studybuddy-data\live`. Tests/artifacts: `H:\studybuddy-test`.
- Test components in `H:\studybuddy-composer`, then `H:\studybuddy-integration`; reimplement against verified contracts—never copy their source into the formal system.
- Real material is in `H:\studybuddy-ChinaTextbook`; its token is a secret: never expose, copy, commit, or clean it.
- Never commit databases, originals, artifacts, secrets, provider keys, private paths, or test output; never expose paths, SQL, source text, tracebacks, raw provider errors, or secrets.
- Workspace retain/clean rules: [`docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md`](docs/[架构师+运维看]WORKSPACE_DIRECTORIES.md).

## Engineering
- Schema changes use `backend/app/migrations/runner.py`; migrations are consecutive, idempotent, transactional, and rollback-tested.
- Follow `revision → chunks → retrieval → citations → Q&A → cards/exercises`; generated content starts as a cited draft and never overwrites confirmed edits.
- New/substantially rewritten `.py`, `.js`, `.css`, `.html`, `.ps1`, `.json` files are ≤100 KB unless explicitly approved.
- Test with `D:\miniconda\py310\python.exe -m pytest backend/tests/`; run focused tests first, full backend tests after infrastructure/migration/storage/API changes, and `python backend/scripts/check-source-size.py` before structural completion.
- For completed slices update [`STATUS.md`](docs/[需求+所有角色看]STATUS.md) and [`TODO.md`](docs/[需求看]TODO.md); do not add evidence/contracts unless the slice also ships user-exercisable capability.

## Support And Authority
- Support only local single-process, single-instance, local storage; do not claim shared `data_root`, multi-worker, cloud, multi-user, real power-loss recovery, or production-scale support without evidence.
- Start with [`README.md`](README.md), [`docs/INDEX.md`](docs/INDEX.md), [`ARCHITECTURE.md`](docs/[架构师看]ARCHITECTURE.md), [`CODE_TEST_GOVERNANCE.md`](docs/[架构师+测试看]CODE_TEST_GOVERNANCE.md), and [`MIGRATIONS.md`](docs/[架构师+运维看]MIGRATIONS.md).
