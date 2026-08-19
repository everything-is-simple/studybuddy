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
- Chromium browser acceptance now covers real file selection, TXT/PDF/DOCX/PPTX success display, RTF rejection, refresh readback, process restart readback and zero console errors. The import path remains `implemented` until the complete browser failure matrix, crash recovery and stress boundaries are covered.
