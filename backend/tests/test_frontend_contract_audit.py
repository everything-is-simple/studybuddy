import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "audit-frontend-contract.py"
FIXTURES = ROOT / "docs" / "frontend-contract-fixtures.json"


def load_auditor():
    spec = importlib.util.spec_from_file_location("frontend_contract_auditor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_static_frontend_contract_has_no_mechanical_findings():
    data = load_auditor().audit()
    assert data["summary"]["finding_count"] == 0
    assert data["summary"]["undefined_css_tokens"] == []
    assert all(not page["direct_fetch"] for page in data["pages"])


def test_frontend_contract_fixtures_define_required_resource_states():
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    assert fixtures["version"] == 1
    assert fixtures["write_policy"]["idempotency_header"] == "Idempotency-Key"
    for name in ("capture", "plan", "note", "practice", "report", "task"):
        resource = fixtures["resources"][name]
        assert resource["endpoint"].startswith("/api/")
        assert resource["identity"] == "id"
        assert resource["states"]


def test_static_write_pages_use_shared_request_layer():
    findings = load_auditor().audit()["pages"]
    for page in findings:
        if page["writes"]:
            assert not page["direct_fetch"], page["page"]
