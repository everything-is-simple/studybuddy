from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.delivery import (
    DeliveryAdapterError,
    FeishuWebhookDeliveryAdapter,
    SmtpDeliveryAdapter,
)


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.logged_in: tuple[str, str] | None = None
        self.messages = []
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def login(self, username: str, auth_code: str) -> None:
        self.logged_in = (username, auth_code)

    def send_message(self, message: object) -> None:
        self.messages.append(message)


class FakeResponse:
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return b"ok"


def test_smtp_adapter_uses_configured_allowlisted_target(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSmtp.instances.clear()
    monkeypatch.setattr("app.delivery.smtplib.SMTP_SSL", FakeSmtp)
    adapter = SmtpDeliveryAdapter(
        host="smtp.163.com", port=465, username="sender@example.invalid",
        auth_code="private-auth-code", targets={"guardian-primary": "recipient@example.invalid"},
    )

    result = adapter.deliver(target_label="guardian-primary", safe_payload={}, markdown_content="# Safe report")

    assert result.status == "sent"
    assert len(FakeSmtp.instances) == 1
    assert FakeSmtp.instances[0].logged_in == ("sender@example.invalid", "private-auth-code")
    assert FakeSmtp.instances[0].messages[0]["To"] == "recipient@example.invalid"


@pytest.mark.parametrize("host,target", [
    ("smtp.evil.invalid", {"guardian-primary": "recipient@example.invalid"}),
    ("smtp.qq.com", {}),
])
def test_smtp_adapter_rejects_unapproved_host_or_target(host: str, target: dict[str, str]) -> None:
    adapter = SmtpDeliveryAdapter(
        host=host, port=465, username="sender@example.invalid", auth_code="private-auth-code", targets=target,
    )

    with pytest.raises(DeliveryAdapterError, match="delivery_configuration_invalid"):
        adapter.deliver(target_label="guardian-primary", safe_payload={}, markdown_content="safe")


def test_feishu_adapter_posts_only_allowlisted_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("app.delivery.urlopen", fake_urlopen)
    adapter = FeishuWebhookDeliveryAdapter(
        targets={"guardian-primary": "https://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890"},
    )

    assert adapter.deliver(target_label="guardian-primary", safe_payload={}, markdown_content="safe").status == "sent"
    assert len(calls) == 1
    assert b"safe" in calls[0][0].data


@pytest.mark.parametrize("url", [
    "http://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890",
    "https://evil.invalid/open-apis/bot/v2/hook/12345678901234567890",
    "https://open.feishu.cn/open-apis/bot/v2/hook/short",
    "https://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890?redirect=1",
])
def test_feishu_adapter_rejects_unapproved_url(url: str) -> None:
    adapter = FeishuWebhookDeliveryAdapter(targets={"guardian-primary": url})

    with pytest.raises(DeliveryAdapterError, match="delivery_configuration_invalid"):
        adapter.deliver(target_label="guardian-primary", safe_payload={}, markdown_content="safe")


def test_adapter_rejects_oversized_content_before_network() -> None:
    adapter = FeishuWebhookDeliveryAdapter(
        targets={"guardian-primary": "https://open.feishu.cn/open-apis/bot/v2/hook/12345678901234567890"},
    )

    with pytest.raises(DeliveryAdapterError, match="payload_too_large"):
        adapter.deliver(target_label="guardian-primary", safe_payload={}, markdown_content="x" * ((1 << 20) + 1))
