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

## 2026-08-21: material lifecycle foundation

- Rename is metadata-only: `PATCH /api/materials/{material_id}` validates a basename and updates only `materials.original_name` and `updated_at`. It never changes source_sha256, stored_path, extraction, spans or the physical original.
- Delete is logical: `DELETE /api/materials/{material_id}` sets `deleted_at` and returns 204. Active lists and detail reads exclude deleted materials; deleted detail returns 404. Extraction, text_spans and hash-derived originals remain preserved.
- The schema migration adds nullable `materials.updated_at` and `materials.deleted_at` without rebuilding existing databases. Deleted material is not exposed through an include_deleted query, and restore, recycle bin and physical GC are intentionally not implemented.
- Shared hash originals are immutable content objects. Deleting one material never removes an original still referenced by another material. Material management is currently `implemented`; the whole StudyBuddy remains not real-pass. Folder upload, queues, OCR, legacy conversion, provider, AI and S1-S7 remain deferred.
