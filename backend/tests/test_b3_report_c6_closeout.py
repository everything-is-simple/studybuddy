from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSER = Path("H:/studybuddy-composer")
INTEGRATION = Path("H:/studybuddy-integration")
EVIDENCE = ROOT / ".archive" / "evidence" / "B3_REPORT_C6_SCOPED_CLOSEOUT_EVIDENCE.md"


def test_b3_c6_evidence_is_complete_redacted_and_keeps_delivery_blocked():
    text = EVIDENCE.read_text(encoding="utf-8")
    for required in (
        "B3 C0", "B3 C1", "B3 C2", "B3 C3", "B3 C4", "B3 C5", "B3 C6",
        "scoped closeout", "JSON", "Markdown", "delivery=off", "B4", "not_verified",
        "Composer", "Integration", "Formal", "449 passed, 3 skipped", "10 passed",
    ):
        assert required.lower() in text.lower()
    for forbidden in (
        "stored_path", "safe_payload_json", "answer_key", "raw provider response",
        "traceback", "secret", "H:/studybuddy-composer", "H:\\studybuddy-composer",
        "H:/studybuddy-integration", "H:\\studybuddy-integration",
    ):
        assert forbidden.lower() not in text.lower()
    assert "B3 does not authorize B4 delivery" in text
    assert "live delivery remains blocked" in text


def test_b3_c6_evidence_points_to_existing_gate_artifacts_and_keeps_isolation():
    text = EVIDENCE.read_text(encoding="utf-8")
    # 文档已移至 .archive/，但证据文档中的引用可能还是旧路径
    # 检查关键文件名存在于正确位置
    artifacts = [
        (".archive/contracts/B3_REPORT_COMPONENT_CONTRACT.md", "B3_REPORT_COMPONENT_CONTRACT"),
        (".archive/evidence/B3_REPORT_C0_AUDIT_AND_SCOPE.md", "B3_REPORT_C0_AUDIT_AND_SCOPE"),
        (".archive/evidence/B3_REPORT_C3_CONTRACT_EVIDENCE.md", "B3_REPORT_C3_CONTRACT_EVIDENCE"),
        (".archive/evidence/B3_REPORT_C4_IMPLEMENTATION_EVIDENCE.md", "B3_REPORT_C4_IMPLEMENTATION_EVIDENCE"),
        (".archive/evidence/B3_REPORT_C5_ACCEPTANCE_EVIDENCE.md", "B3_REPORT_C5_ACCEPTANCE_EVIDENCE"),
        ("backend/tests/test_b3_report_c4.py", "test_b3_report_c4"),
        ("backend/tests/test_b3_report_c5_acceptance.py", "test_b3_report_c5_acceptance"),
        ("backend/tests/browser_b3_report_c5.spec.js", "browser_b3_report_c5"),
    ]
    for path, keyword in artifacts:
        assert keyword in text, f"Evidence should reference {keyword}"
        assert (ROOT / path).is_file(), f"Artifact {path} should exist"

    catalog = json.loads((COMPOSER / "manifests/b0-catalog.json").read_text(encoding="utf-8"))
    report = next(item for item in catalog["candidates"] if item["id"] == "report-core")
    integration = json.loads((INTEGRATION / "results/report-core-c2/integration.json").read_text(encoding="utf-8"))
    assert report["status"] == "integration_passed"
    assert report["formal_system_allowed"] is False
    assert integration["status"] == "integration_passed"
    assert integration["checks"]["formal_system_touched"] is False
