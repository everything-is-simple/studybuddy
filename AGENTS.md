# StudyBuddy Agent Instructions

## Project scope

StudyBuddy is a local, single-process study-material management system built around FastAPI, SQLite, local hash-derived original storage, and a browser UI. AI and learning features are implemented only when the relevant roadmap gate is explicitly complete.

## Repository rules

- Keep the repository source of truth in `H:\studybuddy`.
- Keep production code under `backend/app/` and formal tests under `backend/tests/`.
- Keep important project documentation in the `docs/` directory.
- Keep the repository root limited to the primary entry documents and project metadata.
- Do not copy implementation code from Composer or Integration projects into the formal system. Re-implement against verified contracts.
- Do not commit databases, uploaded originals, generated artifacts, secrets, provider keys, paths containing private data, or test-run output.

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
D:\miniconda\py310\python.exe -m pytest backend/tests/
```

Before reporting a change complete:

1. Run focused tests for the changed area.
2. Run the complete backend test suite when infrastructure, migrations, storage, or API behavior changes.
3. Update the relevant documentation and TODO status.
4. Report limitations honestly; `implemented` is not the same as `real-pass`.

## Safety and deployment boundaries

- Supported deployment is single-process, single-instance, local storage.
- Do not claim support for multiple workers, shared `data_root`, cloud sync, multi-user deployment, real power-loss recovery, or production-scale capacity without dedicated evidence.
- Do not expose file paths, SQL, tracebacks, provider secrets, raw provider errors, or source text through logs or failure responses.
- Preserve failed databases and verified backups for diagnosis. Restore to a new empty target; do not overwrite a live data root with an unverified copy.
