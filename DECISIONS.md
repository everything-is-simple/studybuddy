# StudyBuddy Decisions

## 2026-08-19: four-directory boundary

- `H:\studybuddy` is the only formal product directory.
- `H:\studybuddy-composer` stores reference registrations, component cards and independent smoke evidence.
- `H:\studybuddy-test` stores isolated system-test runs and artifacts.
- `H:\studybuddy-integration` validates real component combinations before formal assembly.
- Composer and integration code must not be imported by the formal product.
- No component may be called available before a real test proves it works.

## 2026-08-19: formal file foundation

- Formal parsing is independently reimplemented from the approved Composer contract; Composer and Integration are not runtime dependencies.
- Parser version is `1.0.0`; supported formats are TXT, Markdown, PDF, DOCX and PPTX.
- RTF returns `rejected/unsupported_rtf`; legacy DOC/PPT return `rejected/requires_converter`. OCR, conversion, complex DOCX extraction, crash recovery and stress testing are deferred.
- Parser owns neither original-file storage nor database persistence. The minimal storage boundary uses a configured root, hash-derived paths, traversal-safe names and atomic replacement.
- The minimal SQLite boundary enables foreign keys and WAL. Extraction and spans are written in one transaction; test data belongs under `H:\studybuddy-test`.
- This stage is `implemented`, not `real-pass`: the minimal FastAPI upload path and process restart API readback now pass with synthetic fixtures, but broader browser acceptance, multi-file behavior and failure recovery remain.
- The default per-file upload limit is 50 MiB. It is an application safety setting, not a free-tier or parser-library restriction; operators may override it with `STUDYBUDDY_MAX_UPLOAD_BYTES` after considering disk and memory capacity.
- Chromium browser acceptance now covers all approved fixture outcomes, valid empty DOCX, real file selection, 50 MiB boundary, duplicate hash reuse, database failure cleanup, refresh readback, process restart readback and zero console errors. `formal-file-import` is now a local `real-pass`; this does not elevate the whole StudyBuddy.

## 2026-08-20: multi-file import foundation

- `POST /api/materials/batch` accepts repeated multipart `files` and returns batch counts plus an independent item for every file.
- Each file gets its own temporary upload, size check, SHA-256, hash-derived original reuse, parser call and SQLite material/extraction/span transaction. Batch processing is partial-success by design.
- Single-file over-limit behavior remains HTTP 413. Batch over-limit behavior is HTTP 201 with item-level `rejected` and `file_too_large`; no material, original or temporary file is retained for that item.
- Parser `rejected` and `failed` results remain persisted as inspectable materials. Persistence failures return item-level `failed/material_persist_failed` in batch and clean a newly-created original.
- The material list supports `success`, `empty`, `rejected` and `failed` filtering and deliberately excludes full extraction text. Detail reads return text, parser metadata, warnings and spans.
- The browser page supports real multi-file selection, batch summary, per-file statuses, material selection, detail view, filtering, refresh readback and process restart readback. This stage is `formal-multi-file-import = real-pass`; the whole StudyBuddy remains not real-pass.

## 2026-08-25: folder import user path

- Chromium folder selection uses `webkitdirectory` and `multiple`; the browser provides the selected folder's actual recursive files. There is no server-side directory scanning, local-path API, directory schema, ZIP import or folder export.
- Folder submissions always reuse repeated `files` on `POST /api/materials/batch`, including a one-file folder, so item-level partial-success behavior is unchanged. Existing regular file selection retains its single-file versus multi-file endpoint behavior.
- Only basename is submitted as the multipart filename and persisted in `materials.original_name`. A browser `webkitRelativePath` is neither sent to the backend nor persisted, indexed, exported or included in API responses. It is displayed only for the immediate batch result after rejecting backslashes, absolute/drive prefixes, control characters and `.`/`..` segments; all display uses text nodes.
- A dedicated import busy guard disables both selection paths during a request without changing mutation, export, list or detail guards. A successful import resets the active paging offset and performs the existing single list reload. Nested equal basenames remain separate batch items by response index and have distinct materials when content differs.
- This is `formal-folder-import = real-pass`, not a global StudyBuddy real-pass. Background queues remain deferred.

## 2026-08-20: import recovery consistency

- Startup runs one conservative reconciliation pass after database initialization and before requests are served. It removes only top-level regular `.incoming-*` files; it does not recurse or follow symlinks.
- An orphan original is removable only when it is in the strict hash-derived layout, its content hash matches the directory-derived SHA-256, and no active or deleted material references that hash. Hash mismatch and unexpected-layout files are preserved for investigation.
- Missing referenced originals are detection-only: recovery logs a bounded diagnostic and never deletes or mutates material rows, extraction, spans, search data, or lifecycle state.
- Temporary write, original store, and SQLite persistence failures use safe public error codes. Newly created zero-reference originals and temporary files are cleaned best-effort; shared originals are never removed by persistence-failure cleanup. Batch partial-success and single-file 413 semantics remain unchanged.
- Recovery has no timer, worker, queue, or cross-process lock. Multiple processes sharing one data root are outside this task's support boundary; the whole StudyBuddy remains not global real-pass.
- Import failure tests inject controlled OSError and SQLite failures; they prove safe cleanup and error boundaries but do not claim a real disk-full or network-share stress pass. Shared originals remain protected by creation/reference state.
- SQLite persistence treats materials/extractions as source of truth: material, extraction, spans and FTS row share a transaction; each batch item has an independent transaction. connect idempotently rebuilds missing FTS rows and removes orphan rows, never reverse-creates material data. Rename/search replacement and purge/search deletion are transactional.
- Physical original access requires configured-root containment and regular non-symlink checks. `originals_root`, hash directories and `original` symlinks are never followed; only hash-correct regular originals are reused. Hash mismatch and unexpected layout remain for inspection. Download/export fail safely while text export remains SQLite-backed; purge performs physical cleanup only after DB commit. Controlled path-race monkeypatches are not a real concurrency proof.

## 2026-08-21: material lifecycle foundation

- Rename is metadata-only: `PATCH /api/materials/{material_id}` validates a basename and updates only `materials.original_name` and `updated_at`. It never changes source_sha256, stored_path, extraction, spans or the physical original.
- Delete is logical: `DELETE /api/materials/{material_id}` sets `deleted_at` and returns 204. Active lists and detail reads exclude deleted materials; deleted detail returns 404. Extraction, text_spans and hash-derived originals remain preserved.
- The schema migration adds nullable `materials.updated_at` and `materials.deleted_at` without rebuilding existing databases. Deleted material is not exposed through an include_deleted query, and restore, recycle bin and physical GC are intentionally not implemented.
- Shared hash originals are immutable content objects. Deleting one material never removes an original still referenced by another material. Material management is `real-pass`; the whole StudyBuddy remains not real-pass.

## 2026-08-22: material recycle bin and restore

- `GET /api/materials/deleted` exposes deleted materials as metadata only. It never returns extraction text and is separate from active list status filters.
- `POST /api/materials/{material_id}/restore` restores only the material lifecycle: `deleted_at = NULL` and a new `updated_at` in one SQLite transaction. It does not alter original_name, source_sha256, stored_path, extraction, text_spans or physical original files.
- Restore of an active material returns `404/material_not_deleted`; restore of an unknown material returns `404/material_not_found`; database failures return `500/material_restore_failed` without changing deleted state.
- The page provides a normal-material/recycle-bin switch. Deleted metadata can be selected without reading full text; restore is a real button operation and returns the material to the active list and detail view.
- Paginated list requests use optional limit/offset parameters and return items/total/has_more while legacy unpaged requests retain array responses. Pagination reuses stable SQL ordering and existing search/lifecycle filters; no pagination table or cache is introduced.
- Batch export uses one active-only POST endpoint and Python standard-library ZIP generation; it exports original bytes and/or extraction text without parser calls or database writes, rejects deleted/mixed selections, validates original paths and hashes, and disambiguates duplicate entry names.
- No include_deleted parameter, restore-all or bulk recycle-bin operation is implemented. Explicit single-material purge is allowed only for deleted materials: it removes material/extraction/spans/search rows, uses source_sha256 reference counting before best-effort original deletion, and never deletes a shared original. This stage is `formal-material-recycle-bin = real-pass`; S1-S7, AI, provider, OCR, ASR, legacy conversion, queues and the whole StudyBuddy real-pass remain deferred.

## 2026-08-23: material export foundation

- `GET /api/materials/{material_id}/original` permits active materials only. It resolves the database stored_path, verifies the path remains inside configured originals_root, verifies the target is a file, and verifies SHA-256 equals source_sha256 before returning FileResponse.
- `GET /api/materials/{material_id}/text` permits active materials only and returns extraction.text as UTF-8 plain text with the fixed filename `<original_name>.extracted.txt`. It never invokes Parser or reads the original.
- Deleted materials return 404 from both export endpoints. Restore re-enables both endpoints without changing source_sha256, stored_path, extraction, spans or physical original. Rename changes the download filename but not original bytes or text export content.
- Empty and active rejected/failed parser results export an empty text file with HTTP 200. Missing originals, invalid paths and hash mismatches return explicit 500 errors without exposing stack traces.
- Export is `formal-material-export = real-pass`. Batch download, ZIP, folder export, background queue, physical GC, AI, provider, OCR, ASR and S1-S7 remain deferred.

## 2026-08-24: material search foundation

- SQLite FTS5 is available in the formal Python runtime and supplies a rebuildable `material_search` index over material_id, original_name and extraction.text. It is auxiliary only; materials and extractions remain the source of truth.
- `GET /api/materials?q=...` searches active materials only and composes with the existing status filter. q trims whitespace and tokenizes on whitespace; tokens have AND semantics and case-insensitive matching.
- ASCII alphanumeric tokens use safely quoted FTS5 MATCH as a candidate query, then receive strict substring verification. Chinese and special-character tokens use parameterized SQLite substring matching, which is a conservative fallback rather than advanced Chinese tokenization.
- Search results contain metadata, match_fields and a maximum 160-character plain-text snippet. They never return extraction.text or stored_path. Rename replaces the FTS row in its transaction; delete/restore leave index data intact while active lifecycle filtering controls visibility.
- The embedded browser page renders search `snippet`, `match_fields` and detail content with text nodes, never HTML interpolation, and hides search context outside active search results. Active search detail safely marks the first body match; name-only matches do not fabricate body highlights. Batch filenames, warnings, error codes and filters are also rendered through DOM text nodes. Search summary and list rendering share one active-list response; a monotonically increasing generation prevents stale search, filter or clear responses and their errors from updating the page; this boundary is verified in Chromium. Detail requests use the same generation guard so a late response cannot replace the currently selected material. Rename, delete and restore use a mutation busy guard, invalidate list/detail generations, and restore controls in finally, including active-only export controls. Real Chromium acceptance covers mutation success/failure, duplicate-click protection, stale list/detail responses, and active/deleted boundaries. Backend remains capped at 160 characters and list responses never include full text. Active/deleted lifecycle behavior is unchanged.
- Material search is `formal-material-search = real-pass`. Semantic/vector/AI search, deleted-material search, search history, saved searches, pagination, queues and S1-S7 remain deferred; whole StudyBuddy remains not real-pass.
