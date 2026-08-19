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
- This stage is `implemented`, not `real-pass`: no formal user upload path or restart readback exists yet.
