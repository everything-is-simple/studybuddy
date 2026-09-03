"""Request schemas for connection-test endpoints.

Contract: P1-5-0 frozen, P1-5-2 implementation.
"""

from __future__ import annotations

from pydantic import BaseModel


class ProviderConnectionTestRequest(BaseModel):
    """Request schema for Provider connection-test.

    provider_type: "llm" or "embedding"
    base_url: Provider API base URL (e.g., "https://api.deepseek.com")
    api_key: Provider API key (not persisted)
    model_id: Model identifier (e.g., "deepseek-chat")
    timeout_seconds: Optional timeout (default: 30.0)
    """

    provider_type: str  # "llm" or "embedding"
    base_url: str
    api_key: str
    model_id: str
    timeout_seconds: float | None = None


class EmailConnectionTestRequest(BaseModel):
    """Request schema for Email connection-test.

    channel: "smtp" or "feishu"

    SMTP fields (required when channel="smtp"):
    - smtp_host: SMTP server host
    - smtp_port: SMTP server port
    - smtp_secure: Use TLS (default: true)
    - smtp_username: Optional SMTP username
    - smtp_password: Optional SMTP password
    - smtp_sender: Sender email address
    - smtp_recipient: Recipient email address

    Feishu fields (required when channel="feishu"):
    - feishu_webhook: Feishu webhook URL

    timeout_seconds: Optional timeout (default: 10.0)
    """

    channel: str  # "smtp" or "feishu"

    # SMTP fields
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_secure: bool | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_recipient: str | None = None

    # Feishu fields
    feishu_webhook: str | None = None

    # Common
    timeout_seconds: float | None = None
