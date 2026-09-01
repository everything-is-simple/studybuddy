from __future__ import annotations

import hashlib
import json
import smtplib
import socket
import sqlite3
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import AppConfig
from .repository import find_report_delivery_replay, record_report_delivery_attempt


DELIVERY_CHANNELS = {"smtp", "feishu"}
DELIVERY_MODES = {"off", "dry_run", "live"}
DELIVERY_TIMEOUT_SECONDS = 10.0
MAX_DELIVERY_CONTENT_BYTES = 1 << 20
FEISHU_WEBHOOK_PREFIX = "/open-apis/bot/v2/hook/"


class DeliveryAdapterError(Exception):
    """Safe, stable delivery failure; raw provider errors never cross this boundary."""

    def __init__(self, code: str = "delivery_failed") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DeliveryContentSummary:
    content_sha256: str
    content_chars: int
    format: str = "markdown"

    def public(self) -> dict[str, object]:
        return {
            "content_sha256": self.content_sha256,
            "content_chars": self.content_chars,
            "format": self.format,
        }


@dataclass(frozen=True)
class DeliveryOutcome:
    status: str
    error_code: str | None = None


class ReportDeliveryAdapter(Protocol):
    channel: str

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        ...


class DryRunDeliveryAdapter:
    """Constructs a delivery result without opening a socket or sending content."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        # Validate serialization before recording a successful dry-run. This keeps
        # the audit result deterministic while retaining no report body in the DB.
        json.dumps(safe_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        return DeliveryOutcome(status="dry_run")


class SmtpDeliveryAdapter:
    """Runtime-configured SMTP adapter; live execution remains gated below."""

    channel = "smtp"

    def __init__(self, *, host: str, port: int, username: str, auth_code: str,
                 targets: dict[str, str], secure: bool = True,
                 timeout_seconds: float = DELIVERY_TIMEOUT_SECONDS) -> None:
        self.host, self.port, self.username = host.strip(), port, username.strip()
        self.auth_code, self.targets = auth_code, dict(targets)
        self.secure, self.timeout_seconds = secure, timeout_seconds

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        recipient = self.targets.get(target_label)
        if self.host not in {"smtp.qq.com", "smtp.163.com"} or not recipient:
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not self.username or not self.auth_code or "@" not in self.username or "@" not in recipient:
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        if len(markdown_content.encode("utf-8")) > MAX_DELIVERY_CONTENT_BYTES:
            raise DeliveryAdapterError("payload_too_large")
        message = EmailMessage()
        message["From"], message["To"] = self.username, recipient
        message["Subject"] = "StudyBuddy report"
        message.set_content(markdown_content)
        try:
            if self.secure:
                client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds)
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds)
            with client:
                client.ehlo()
                if not self.secure:
                    client.starttls()
                    client.ehlo()
                client.login(self.username, self.auth_code)
                client.send_message(message)
        except smtplib.SMTPAuthenticationError:
            raise DeliveryAdapterError("delivery_failed") from None
        except (smtplib.SMTPException, OSError, socket.timeout):
            raise DeliveryAdapterError("delivery_failed") from None
        return DeliveryOutcome(status="sent")


class FeishuWebhookDeliveryAdapter:
    """Runtime-configured HTTPS Feishu text webhook adapter."""

    channel = "feishu"

    def __init__(self, *, targets: dict[str, str], timeout_seconds: float = DELIVERY_TIMEOUT_SECONDS) -> None:
        self.targets = dict(targets)
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _allowed_url(url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.netloc == "open.feishu.cn"
            and parsed.path.startswith(FEISHU_WEBHOOK_PREFIX)
            and len(parsed.path.rsplit("/", 1)[-1]) >= 20
            and not parsed.query and not parsed.fragment
        )

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        url = self.targets.get(target_label)
        if not url or not self._allowed_url(url):
            raise DeliveryAdapterError("delivery_configuration_invalid")
        if not isinstance(markdown_content, str) or not markdown_content:
            raise DeliveryAdapterError("delivery_failed")
        body = json.dumps(
            {"msg_type": "text", "content": {"text": markdown_content}},
            ensure_ascii=True, separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > MAX_DELIVERY_CONTENT_BYTES:
            raise DeliveryAdapterError("payload_too_large")
        request = Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "Idempotency-Key": target_label},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310: allowlist validated above
                if response.status < 200 or response.status >= 300:
                    raise DeliveryAdapterError("delivery_failed")
                response.read(128)
        except DeliveryAdapterError:
            raise
        except (HTTPError, URLError, OSError, socket.timeout):
            raise DeliveryAdapterError("delivery_failed") from None
        return DeliveryOutcome(status="sent")


class LiveDeliveryAdapter:
    """Explicit placeholder: B4-C3 keeps Formal live delivery closed."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        raise DeliveryAdapterError("delivery_live_not_approved")


def _target_allowed(config: AppConfig, target_label: str) -> bool:
    return target_label in set(config.report_delivery_targets)


def _configured_adapter(config: AppConfig, channel: str) -> ReportDeliveryAdapter:
    """Build a runtime adapter only for dry-run-compatible configuration."""
    if channel == "smtp":
        return SmtpDeliveryAdapter(
            host=config.report_delivery_smtp_host,
            port=config.report_delivery_smtp_port,
            username=config.report_delivery_smtp_username or "",
            auth_code=config.report_delivery_smtp_password_runtime or "",
            targets=dict(config.report_delivery_smtp_targets),
            secure=config.report_delivery_smtp_secure,
            timeout_seconds=config.report_delivery_timeout_seconds,
        )
    if channel == "feishu":
        return FeishuWebhookDeliveryAdapter(
            targets=dict(config.report_delivery_feishu_targets),
            timeout_seconds=config.report_delivery_timeout_seconds,
        )
    raise DeliveryAdapterError("delivery_target_not_allowed")


def _load_report_content(connection: sqlite3.Connection, *, project_id: str,
                         report_id: str) -> tuple[dict[str, object], str, str]:
    row = connection.execute(
        "SELECT status,content_version,safe_payload_json,markdown_content FROM report_snapshots "
        "WHERE id=? AND project_id=?",
        (report_id, project_id),
    ).fetchone()
    if row is None:
        raise ValueError("report_not_found")
    if row["status"] != "ready":
        raise ValueError("report_invalid_state")
    try:
        payload = json.loads(row["safe_payload_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DeliveryAdapterError("delivery_failed") from exc
    if not isinstance(payload, dict):
        raise DeliveryAdapterError("delivery_failed")
    return payload, str(row["markdown_content"]), str(row["content_version"])


def _content_summary(markdown_content: str) -> DeliveryContentSummary:
    encoded = markdown_content.encode("utf-8")
    return DeliveryContentSummary(
        content_sha256=hashlib.sha256(encoded).hexdigest(),
        content_chars=len(markdown_content),
    )


def execute_report_delivery(
    connection: sqlite3.Connection,
    *,
    config: AppConfig,
    project_id: str,
    report_id: str,
    channel: str,
    target_label: str,
    mode: str | None = None,
    authorization_granted: bool = False,
    idempotency_key: str | None = None,
    retry_of: str | None = None,
    adapter: ReportDeliveryAdapter | None = None,
) -> dict[str, object]:
    """Execute one explicit, project-scoped report delivery request.

    The only successful execution in 9D is local ``dry_run``. ``live`` is
    validated for authorization and allowlist policy, then rejected by the
    approved live gate. No adapter receives credentials and this function never
    performs implicit retry or background work.
    """
    if channel not in DELIVERY_CHANNELS:
        raise ValueError("delivery_target_not_allowed")
    selected_mode = config.report_delivery_mode
    if selected_mode not in DELIVERY_MODES:
        raise ValueError("delivery_failed")
    if mode is not None and mode != selected_mode:
        raise ValueError("delivery_disabled")
    if not isinstance(target_label, str) or not target_label:
        raise ValueError("delivery_target_not_allowed")

    payload, markdown_content, content_version = _load_report_content(
        connection, project_id=project_id, report_id=report_id
    )
    summary = _content_summary(markdown_content)
    safe_payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    content_fingerprint = hashlib.sha256(
        f"{content_version}\x1f{safe_payload_json}".encode("utf-8")
    ).hexdigest()
    replay = find_report_delivery_replay(
        connection, project_id=project_id, report_id=report_id, channel=channel,
        mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
        content_fingerprint=content_fingerprint,
    )
    if replay is not None:
        replay["sent"] = False
        replay["content_summary"] = summary.public()
        return replay
    allowed = _target_allowed(config, target_label)

    # Every policy decision is recorded as a bounded audit fact. The repository
    # stores only a content fingerprint, never the report payload or markdown.
    if selected_mode == "off":
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_disabled",
        )
    elif not allowed:
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_target_not_allowed",
        )
    elif selected_mode == "live" and (
        not config.report_delivery_enabled
        or not config.report_delivery_authorized
        or not authorization_granted
    ):
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_authorization_required",
        )
    elif selected_mode == "live":
        # This gate runs before adapter selection. A live sender cannot be
        # reached in 9D, even when a test or runtime injects one.
        result = record_report_delivery_attempt(
            connection, project_id=project_id, report_id=report_id, channel=channel,
            mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
            retry_of=retry_of, status_override="blocked", error_code_override="delivery_live_not_approved",
        )
    else:
        selected_adapter = adapter or DryRunDeliveryAdapter(channel)
        try:
            outcome = selected_adapter.deliver(
                target_label=target_label, safe_payload=payload, markdown_content=markdown_content
            )
        except DeliveryAdapterError as exc:
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override="failed", error_code_override=exc.code,
            )
        except Exception:
            # Adapters are an untrusted boundary: preserve only the stable code.
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override="failed", error_code_override="delivery_failed",
            )
        else:
            result = record_report_delivery_attempt(
                connection, project_id=project_id, report_id=report_id, channel=channel,
                mode=selected_mode, target_label=target_label, idempotency_key=idempotency_key,
                retry_of=retry_of, status_override=outcome.status,
                error_code_override=outcome.error_code,
            )

    result["sent"] = False
    result["content_summary"] = summary.public()
    return result
