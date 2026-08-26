# Phase 10-8 Boundary and Capacity Evidence

> Gate I status: `scoped-gates-pass` for the declared local single-process, single-instance, SQLite, local-disk v1 envelope. This evidence is a bounded synthetic/local acceptance record, not a global production-capacity or `real-pass` claim.

## Scope and safety

The runner is [`backend/scripts/phase10_boundary.py`](../../../backend/scripts/phase10_boundary.py). It creates all data under a system temporary directory, uses `TestClient`, SQLite, deterministic fake AI/embedding providers, and deletes the temporary directory on exit. It prints only timings, counts, sizes, statuses, and fixed environment labels. It does not print source text, original names from the generated payload, paths, secrets, SQL, provider payloads, or raw exceptions.

The time-box thresholds are intentionally local v1 acceptance thresholds, not universal hardware promises:

| Check | Threshold |
|---|---:|
| First startup | 5,000 ms |
| Single material import | 2,000 ms |
| Batch import of 20 materials | 10,000 ms |
| Search | 2,000 ms |
| Export | 5,000 ms |
| Revision/chunk/index + fake embedding | 10,000 ms |
| Q&A with deterministic fake provider | 5,000 ms |
| Cards/Exercises setup | 5,000 ms |
| 9A–9C learning setup | 5,000 ms |
| 9D capture/report setup | 5,000 ms |
| Task enqueue | 2,000 ms |
| Task execution | 10,000 ms |
| One lifecycle cycle | 2,000 ms |
| Backup / verify / restore | 10,000 ms each |
| Synthetic database size | 32 MiB |
| Python peak working set | 256 MiB |

## Reproducible command

```text
C:\miniconda\py310\python.exe backend\scripts\phase10_boundary.py
C:\miniconda\py310\python.exe -m pytest backend/tests/test_phase10_boundary.py -q -p no:cacheprovider
```

The runner covers:

- first startup, health and readiness;
- single and 20-file batch synthetic import;
- lexical material search and ZIP export;
- revision, deterministic chunks and fake embedding index;
- fake-provider Q&A with citation-bearing indexed source;
- Cards/Exercises creation and exercise confirmation;
- minimal 9A goal/plan/item and 9C practice-session setup;
- minimal 9D capture-session/report setup;
- explicit `embedding_index` task enqueue/run, progress reaching 100%;
- deterministic task failure, explicit retry, second attempt and success;
- ten bounded import → rename → delete → restore → purge lifecycle cycles;
- backup → verify → restore to a new target without migration or provider calls;
- database table counts, database size and peak working-set measurement.

## Latest runner result

Latest Windows run:

```text
status: passed
environment: synthetic/local/single-process/single-instance/SQLite/fake-provider
startup: 336.399 ms
single_import: 25.074 ms
batch_import_20: 378.108 ms
search: 16.713 ms
export: 13.316 ms
revision_chunk_index: 27.287 ms
qa: 24.717 ms
cards_exercises: 18.093 ms
learning_9a_9c: 68.932 ms
capture_report_9d: 34.603 ms
task_enqueue: 18.886 ms
task_run: 54.903 ms
task_retry_progress: passed, attempt_count=2, progress_percent=100
lifecycle: 10 cycles, max_cycle_ms=156.709
backup: 45.661 ms
verify: 20.110 ms
restore: 77.822 ms
database_bytes: 1,265,664
python_maxrss_bytes: 82,034,688
backup_restore: verified=true, restored_schema_preserved=true
```

All measured checks were below the local thresholds. The runner's report is intentionally ephemeral; no benchmark output is committed as an artifact.

## Automated evidence

- `test_phase10_boundary.py`: `2 passed`.
- Full backend regression: `412 passed, 2 skipped`; skips are opt-in real-provider smoke tests.
- Serial Chromium regression relevant to existing learning paths:
  - `browser_qa.spec.js`: `9 passed, 1 skipped`;
  - `browser_phase8.spec.js`: `3 passed`;
  - `browser_phase9b.spec.js`: `3 passed`.
- No Phase 10-8 UI code was added, so no new UI behavior is claimed. The browser runs are regression evidence only.

## Boundary and failure results

The following are deliberately **not verified** and are not inferred from the synthetic run:

- Windows ACL configuration/permission denial and read-only directory behavior;
- real quota or disk-full behavior;
- power loss, abrupt host failure, hardware damage or filesystem corruption;
- network filesystem semantics;
- multi-process or multi-instance contention on one `data_root`;
- all Provider/model combinations, real OCR/ASR, and live external delivery;
- universal Windows installer/MSI, service manager integration and unattended upgrade;
- peak memory under large S4 scale, unbounded long-running service load, and real production traffic.

These items are outside the local v1 hard requirement accepted in Phase 10-0. They remain deployment risks and require a separate evidence package before any wider support claim. The supported v1 boundary remains one process, one instance, one local data root, one SQLite database, and explicit operator task execution.

## Gate I conclusion

Within the declared time box, all reproducible local checks passed, the existing serial browser regression passed, and no blocking failure remains inside the accepted local v1 scope. Gate I is therefore `scoped-gates-pass`. This does not change the project-wide statement that StudyBuddy is not globally `production real-pass`.
