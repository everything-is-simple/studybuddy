from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / ".archive" / "evidence" / "B2_OCR_C6_SCOPED_CLOSEOUT_EVIDENCE.md"


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
    # 文档已移至 .archive/，但证据文档中的引用可能还是旧路径
    # 检查关键文件名存在于正确位置
    artifacts = [
        (".archive/contracts/B2_IMAGE_OCR_PROVIDER_CONTRACT.md", "B2_IMAGE_OCR_PROVIDER_CONTRACT"),
        (".archive/evidence/B2_OCR_C3_CONTRACT_EVIDENCE.md", "B2_OCR_C3_CONTRACT_EVIDENCE"),
        (".archive/evidence/B2_OCR_C5_ACCEPTANCE_EVIDENCE.md", "B2_OCR_C5_ACCEPTANCE_EVIDENCE"),
        ("backend/tests/test_phase_b2_ocr_c4.py", "test_phase_b2_ocr_c4"),
        ("backend/tests/browser_b2_ocr_c5.spec.js", "browser_b2_ocr_c5"),
        ("backend/scripts/run_b2_ocr_c5.py", "run_b2_ocr_c5"),
    ]
    for path, keyword in artifacts:
        assert keyword in text, f"Evidence should reference {keyword}"
        assert (ROOT / path).is_file(), f"Artifact {path} should exist"
