from __future__ import annotations

from pathlib import Path
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.delivery import DeliveryAdapterError, DeliveryOutcome  # noqa: E402
from scripts.run_b4_delivery_c5_smoke import SYNTHETIC_CONTENT, run  # noqa: E402


def _env(monkeypatch: pytest.MonkeyPatch, channel: str) -> None:
    monkeypatch.setenv("LIVE_SMOKE", "1")
    monkeypatch.setenv("LIVE_SMOKE_CONFIRM", "I_UNDERSTAND_SYNTHETIC_DELIVERY_SMOKE")
    monkeypatch.setenv("STUDYBUDDY_B4_C5_TARGET_LABEL", "operator-smoke")
    if channel == "smtp":
        monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST", "smtp.163.com")
        monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT", "465")
        monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME", "sender@example.invalid")
        monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD", "private-auth-code")
        monkeypatch.setenv("STUDYBUDDY_B4_C5_SMTP_RECIPIENT", "recipient@example.invalid")
    else:
        monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890")


def test_smoke_requires_explicit_environment_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_SMOKE", raising=False)
    monkeypatch.delenv("LIVE_SMOKE_CONFIRM", raising=False)
    with pytest.raises(DeliveryAdapterError, match="delivery_authorization_required"):
        run("smtp")


@pytest.mark.parametrize("channel", ["smtp", "feishu"])
def test_smoke_uses_only_synthetic_content(monkeypatch: pytest.MonkeyPatch, channel: str) -> None:
    _env(monkeypatch, channel)
    captured: dict[str, object] = {}

    def delivered(self: object, **kwargs: object) -> DeliveryOutcome:
        captured.update(kwargs)
        return DeliveryOutcome(status="sent")

    monkeypatch.setattr(
        "app.delivery.SmtpDeliveryAdapter.deliver" if channel == "smtp" else "app.delivery.FeishuWebhookDeliveryAdapter.deliver",
        delivered,
    )
    result = run(channel)
    assert result["status"] == "sent"
    assert result["channel"] == channel
    assert result["sent"] is True
    assert captured["markdown_content"] == SYNTHETIC_CONTENT
    assert captured["safe_payload"] == {}
    assert "private-auth-code" not in str(result)
    assert "12345678901234567890" not in str(result)


def test_smoke_rejects_multiple_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    _env(monkeypatch, "smtp")
    with pytest.raises(DeliveryAdapterError, match="delivery_target_not_allowed"):
        run("smtp,feishu")
