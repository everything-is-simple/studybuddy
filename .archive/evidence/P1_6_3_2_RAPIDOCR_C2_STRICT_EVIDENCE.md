# P1-6-3-2 RapidOCR strict C2 Integration evidence

> Status: `integration_passed / 2026-09-24`

This is isolated Integration evidence only. It does not authorize RapidOCR in
the Formal system and does not change the Formal PaddleOCR-only API boundary.

## Scope

- Windows/Python 3.10/CPU.
- `rapidocr_onnxruntime==1.4.4`, `onnxruntime==1.20.1`.
- PaddleOCR primary: `paddleocr==3.7.0`, `paddlepaddle==3.3.1`.
- Explicit local model roots and sanitized SHA-256 inventory for both engines.
- Synthetic PNG/JPEG/WEBP fixtures only; no user material, provider network, or
  committed model files.

## Gate result

The strict runner passed `12/12` checks. The evidence artifact is maintained
outside the repository at:

`H:/studybuddy-test/artifacts/rapidocr-c2-strict-20260924/rerun.json`

The checks cover:

- real RapidOCR inference for PNG/JPEG/WEBP with confidence bounds;
- real PaddleOCR primary success;
- injected primary timeout followed by exactly one real RapidOCR fallback;
- both-provider failure with no third attempt;
- draft-first provider identity, confirmation, source lifecycle, and rollback;
- backup/restore/read with unchanged OCR call counts;
- bounded subprocess timeout/output and network-disabled execution;
- no raw image, OCR text, stderr, or private path in evidence.

## Boundary

`formal_system_touched=false` and `formal_system_allowed=false` remain in force.
RapidOCR still requires a separate Formal fallback contract/adapter decision,
Formal acceptance, and browser evidence before any product integration.
General OCR accuracy, other environments, concurrency, capacity, and global
`real-pass` remain `not_verified`.
