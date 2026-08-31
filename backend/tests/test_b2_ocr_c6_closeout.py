from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "B2_OCR_C6_SCOPED_CLOSEOUT_EVIDENCE.md"


def test_b2_ocr_c6_evidence_is_complete_and_redacted():
    text = EVIDENCE.read_text(encoding="utf-8")
    for required in (
        "C3", "C4", "C5", "C6", "scoped closeout", "PaddleOCR",
        "draft-first", "synthetic", "local", "not_verified", "real-pass",
        "no implicit download",
    ):
        assert required.lower() in text.lower()
    for forbidden in (
        "stored_path", "raw provider response", "traceback", "secret",
        "H:/PaddleOCR", "H:\\PaddleOCR", "OCR C5 2026",
    ):
        assert forbidden.lower() not in text.lower()


def test_b2_ocr_c6_evidence_points_to_existing_c4_c5_artifacts():
    text = EVIDENCE.read_text(encoding="utf-8")
    for relative in (
        "docs/contracts/B2_IMAGE_OCR_PROVIDER_CONTRACT.md",
        "docs/evidence/B2_OCR_C3_CONTRACT_EVIDENCE.md",
        "docs/evidence/B2_OCR_C5_ACCEPTANCE_EVIDENCE.md",
        "backend/tests/test_phase_b2_ocr_c4.py",
        "backend/tests/browser_b2_ocr_c5.spec.js",
        "backend/scripts/run_b2_ocr_c5.py",
    ):
        assert relative in text
        assert (ROOT / relative).is_file()
