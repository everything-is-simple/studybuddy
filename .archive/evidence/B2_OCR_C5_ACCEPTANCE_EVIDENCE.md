# B2 OCR C5 Formal Acceptance Evidence

> Status: `implemented/backend-pass` with explicit local real-provider smoke passed.
> Scope: PaddleOCR 3.7.0 / PaddlePaddle 3.3.1, PP-OCRv5_server_det + PP-OCRv5_server_rec, Windows/Python 3.10/CPU, pre-provisioned local models, synthetic non-sensitive PNG only.

## Gates

- C4 focused backend: passed; independent Formal adapter, explicit OCR gate, image-only provider selection and existing draft boundary are covered by `backend/tests/test_phase_b2_ocr_c4.py`.
- C5 backend focused: passed; capture validation, lifecycle, failure, retry and API boundaries are covered by `test_phase9d_capture.py`, `test_phase9d_api.py`, and the C4 suite.
- C5 static capture browser: `2 passed`; `backend/tests/browser_b2_ocr_c5.spec.js` covers image creation, MIME accept list, OCR-not-configured failure, review boundary, reload, narrow viewport, keyboard focus, source-deleted label and privacy checks.
- C5 real local provider smoke: passed with an isolated synthetic PNG. The redacted runner is `backend/scripts/run_b2_ocr_c5.py` and requires `STUDYBUDDY_RUN_REAL_OCR_C5=1`; it records no OCR text, model path, original bytes, provider response or stderr.
- C5 full backend regression: `not_recorded_in_this_evidence` until the final post-change run completes.

## Real smoke result

- Provider: `paddleocr`
- Model identity: `PP-OCRv5_server_det+PP-OCRv5_server_rec`
- Result: `real_passed`
- Segment count: `1`
- Uncertain count: `0`
- Confidence range: `0.9624397158622742` to `0.9624397158622742`
- Fixture identity: SHA-256 prefix `1422e0eedc9d`
- Execution: local model, offline, Windows/Python 3.10/CPU

## Not verified

This evidence does not establish general OCR accuracy, all image formats, multilingual quality, table/layout recognition, arbitrary user images, concurrency/capacity, cancellation guarantees, other operating systems, or global production `real-pass`. C5 browser coverage uses safe mocked capability/failure data and does not claim browser execution of the real provider.
