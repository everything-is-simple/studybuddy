# B2 OCR C6 Scoped Closeout Evidence

> Status: `closeout-scoped-pass`.
> This is a bounded Formal closeout for the frozen PaddleOCR scope. It is not a global OCR `real-pass`.

## Gate ledger

| Gate | Status | Evidence |
|---|---|---|
| C3 contract freeze | `contract-frozen` | `docs/contracts/B2_IMAGE_OCR_PROVIDER_CONTRACT.md`, `docs/evidence/B2_OCR_C3_CONTRACT_EVIDENCE.md` |
| C4 Formal implementation | `implemented/backend-pass` | `backend/app/providers/_ocr.py`, `backend/tests/test_phase_b2_ocr_c4.py` |
| C5 Formal acceptance | `implemented/backend-pass` | `docs/evidence/B2_OCR_C5_ACCEPTANCE_EVIDENCE.md`, `backend/tests/browser_b2_ocr_c5.spec.js`, `backend/scripts/run_b2_ocr_c5.py` |
| C6 scoped closeout | `closeout-scoped-pass` | This document and `backend/tests/test_b2_ocr_c6_closeout.py` |

## Verified scope

- PaddleOCR `3.7.0` with PaddlePaddle `3.3.1`.
- `PP-OCRv5_server_det` and `PP-OCRv5_server_rec` with locally pre-provisioned models.
- Windows / Python 3.10 / CPU, local execution, no implicit download.
- Explicit OCR capability gate; images do not fall back to fake or ASR.
- Server-side image input and output safety boundaries, draft-first review, confidence and `clear`/`uncertain` semantics.
- Existing capture/material/revision domain boundary and static capture page behavior in the tested scope.
- Real local smoke on one synthetic, non-sensitive PNG: one segment, confidence range `0.9624397158622742` to `0.9624397158622742`.
- C5 browser scope: image creation/upload, OCR-not-configured failure, review boundary, reload, narrow viewport, keyboard focus, source-deleted label and privacy checks.
- Final backend regression at C6 closeout: `439 passed, 3 skipped`; skipped tests are opt-in real-provider smoke.

## Operational boundaries

- Real OCR remains explicitly opt-in and is not connected to the task runner or automatic scheduling.
- C5 browser tests use safe mocked capability/failure data; they do not claim browser execution of the real provider.
- The smoke result is synthetic and local. The following remain `not_verified`: general OCR accuracy, arbitrary user-image quality, all PNG/JPEG/WebP boundary combinations, multilingual quality, table/layout recognition, concurrency/capacity, reliable cancellation, other operating systems or GPU execution, system-level screen-reader behavior, and global production `real-pass`.
- RapidOCR and Tesseract remain separate candidates and are not automatically admitted to Formal.

## Privacy and evidence boundary

This evidence contains only stable identifiers, counts, status values, confidence summary and bounded environment scope. It excludes original media, recognized body content, local filesystem locations, provider payloads, diagnostic streams, credentials, database statements and internal exception details. Restore/readiness/read paths do not execute OCR or repair source state under the existing tested backup/restore contract.
