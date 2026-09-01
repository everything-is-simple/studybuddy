from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import config_from_environment  # noqa: E402


def test_delivery_runtime_mapping_is_parsed_without_exposing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT", "465")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE", "true")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME", "sender@example.invalid")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD", "private-auth-code")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS", "guardian-primary=recipient@example.invalid")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_FEISHU_TARGET_LABEL", "guardian-primary")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890")

    config = config_from_environment()

    assert config.report_delivery_smtp_host == "smtp.163.com"
    assert config.report_delivery_smtp_targets == (("guardian-primary", "recipient@example.invalid"),)
    assert config.report_delivery_feishu_target_label == "guardian-primary"
    assert config.report_delivery_smtp_password_runtime == "private-auth-code"
    assert "private-auth-code" not in repr(config)
    assert "12345678901234567890" not in repr(config)


def test_delivery_runtime_mapping_rejects_duplicate_or_malformed_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS", "guardian-primary=a@example.invalid,guardian-primary=b@example.invalid")
    with pytest.raises(ValueError, match="invalid_studybuddy_report_delivery_smtp_targets"):
        config_from_environment()

    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS", "not allowed=a@example.invalid")
    with pytest.raises(ValueError, match="invalid_studybuddy_report_delivery_smtp_targets"):
        config_from_environment()


def test_delivery_runtime_mapping_defaults_remain_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "STUDYBUDDY_REPORT_DELIVERY_MODE",
        "STUDYBUDDY_REPORT_DELIVERY_ENABLED",
        "STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED",
        "STUDYBUDDY_REPORT_DELIVERY_TARGETS",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS",
        "STUDYBUDDY_REPORT_DELIVERY_FEISHU_TARGET_LABEL",
        "STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK",
    ):
        monkeypatch.delenv(name, raising=False)

    config = config_from_environment()

    assert config.report_delivery_mode == "off"
    assert config.report_delivery_enabled is False
    assert config.report_delivery_authorized is False
    assert config.report_delivery_smtp_targets == ()
    assert config.report_delivery_feishu_target_label is None
