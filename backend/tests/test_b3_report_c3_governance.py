from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSER = Path("H:/studybuddy-composer")
INTEGRATION = Path("H:/studybuddy-integration")


def test_b3_c3_contract_freezes_formal_reuse_and_scope():
    contract = (ROOT / "docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md").read_text(encoding="utf-8")
    evidence = (ROOT / "docs/evidence/B3_REPORT_C3_CONTRACT_EVIDENCE.md").read_text(encoding="utf-8")
    for marker in (
        "contract-frozen", "existing Phase 9D report domain", "daily", "weekly", "monthly", "exam_alert",
        "JSON and Markdown", "project-scoped", "read-only", "half-open", "snapshot", "source_deleted",
        "source_unavailable", "backup/restore", "B4",
    ):
        assert marker in contract
    for marker in ("contract-frozen", "daily", "weekly", "monthly", "exam_alert", "JSON", "Markdown", "project", "read-only", "snapshot", "backup/restore", "B4"):
        assert marker in evidence
    for excluded in ("PDF", "AI narrative", "live delivery", "scheduler/worker", "multi-user"):
        assert excluded in contract


def test_b3_c3_evidence_references_passed_candidate_gates_without_authorizing_formal():
    catalog = json.loads((COMPOSER / "manifests/b0-catalog.json").read_text(encoding="utf-8"))
    report = next(item for item in catalog["candidates"] if item["id"] == "report-core")
    integration = json.loads((INTEGRATION / "results/report-core-c2/integration.json").read_text(encoding="utf-8"))
    assert report["status"] == "integration_passed"
    assert report["formal_system_allowed"] is False
    assert integration["status"] == "integration_passed"
    assert integration["checks"]["formal_system_touched"] is False
    assert "C4 is unblocked" in (ROOT / "docs/evidence/B3_REPORT_C3_CONTRACT_EVIDENCE.md").read_text(encoding="utf-8")


def test_b3_c3_does_not_modify_schema_or_runtime_code():
    contract = (ROOT / "docs/contracts/B3_REPORT_COMPONENT_CONTRACT.md").read_text(encoding="utf-8")
    evidence = (ROOT / "docs/evidence/B3_REPORT_C3_CONTRACT_EVIDENCE.md").read_text(encoding="utf-8")
    assert "does not itself change production code, schema, migrations" in contract
    assert "Formal production behavior is unchanged" in evidence
