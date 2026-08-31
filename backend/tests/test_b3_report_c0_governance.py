from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSER = Path("H:/studybuddy-composer")


def test_b3_report_c0_scope_is_frozen_without_promotion():
    evidence = (ROOT / "docs/evidence/B3_REPORT_C0_AUDIT_AND_SCOPE.md").read_text(encoding="utf-8")
    plan = (COMPOSER / "components/report-core/C0-DECISION-AND-C1-PLAN.md").read_text(encoding="utf-8")
    catalog = json.loads((COMPOSER / "manifests/b0-catalog.json").read_text(encoding="utf-8"))
    report = next(item for item in catalog["candidates"] if item["id"] == "report-core")

    assert report["status"] == "integration_passed"
    assert report["formal_system_allowed"] is False
    for marker in ("daily", "weekly", "monthly", "exam_alert", "JSON", "Markdown", "half-open"):
        assert marker in evidence and marker in plan
    for marker in ("PDF", "AI narrative", "delivery", "not_verified"):
        assert marker in evidence
    assert "must not create a second report domain" in evidence
    assert "B3 never authorizes B4 delivery" in plan


def test_b3_report_c0_documents_keep_c1_and_delivery_pending():
    status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    todo = (ROOT / "docs/TODO.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/ROADMAP_CAPABILITIES.md").read_text(encoding="utf-8")
    assert "B3 C0-C6 scoped closeout is complete only for local deterministic project-scoped JSON/Markdown reports" in status
    assert "B3 不授权 B4" in todo
    assert "C0-C3 状态" in roadmap or "C0 `audit-frozen`" in roadmap
    assert "不建立第二套 report domain" in roadmap
    assert "delivery=off" in todo
