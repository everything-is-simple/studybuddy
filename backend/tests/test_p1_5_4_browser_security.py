"""P1-5-4 browser evidence governance checks."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "backend/app/static/settings-provider.html"
EVIDENCE = ROOT / "docs/evidence/P1_5_4_BROWSER_SECURITY_EVIDENCE.md"


def test_p1_5_4_page_has_no_browser_persistence_or_config_save() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "/api/system/config", "provider-config-save", "email-config-save"):
        assert forbidden not in text
    assert "provider-connection-test" in text
    assert "email-connection-test" in text
    assert "navigator.clipboard.writeText" in text
    assert "STUDYBUDDY_REPORT_DELIVERY_ENABLED" not in text
    assert "STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED" not in text
    assert "STUDYBUDDY_REPORT_DELIVERY_MODE=live" not in text


def test_p1_5_4_secret_controls_are_password_inputs() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for field_id in ("provider-key", "smtp-password", "feishu-webhook"):
        match = re.search(rf'<input[^>]+id="{field_id}"[^>]*>', text)
        assert match, f"missing secret input {field_id}"
        tag = match.group(0)
        assert 'type="password"' in tag
        assert 'autocomplete="off"' in tag
        assert 'spellcheck="false"' in tag
    assert "clearSecretFields" in text
    assert "pagehide" in text
    assert "pageshow" in text


def test_p1_5_4_provider_export_uses_provider_id_and_email_export_is_complete() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "prefix+'_PROVIDER='+f.provider_id" in text
    for variable in (
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS",
        "STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK",
    ):
        assert variable in text
    assert 'id="email-copy"' in text


def test_p1_5_4_schema_remains_v14_and_evidence_exists() -> None:
    runner = (ROOT / "backend/app/migrations/runner.py").read_text(encoding="utf-8")
    assert re.search(r"CURRENT_SCHEMA_VERSION\s*=\s*14", runner)
    assert EVIDENCE.exists()
    evidence = EVIDENCE.read_text(encoding="utf-8")
    assert "browser-pass" in evidence
    assert "mock-tested" in evidence
    assert "real provider/email pass" in evidence
