from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from .config import AppConfig
from .repository import find_report_delivery_replay, record_report_delivery_attempt


DELIVERY_CHANNELS = {"smtp", "feishu"}
DELIVERY_MODES = {"off", "dry_run", "live"}


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


class LiveDeliveryAdapter:
    """Explicit placeholder: 9D never sends to SMTP, Feishu, or any endpoint."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                 markdown_content: str) -> DeliveryOutcome:
        raise DeliveryAdapterError("delivery_live_not_approved")


def _target_allowed(config: AppConfig, target_label: str) -> bool:
    return target_label in set(config.report_delivery_targets)


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
