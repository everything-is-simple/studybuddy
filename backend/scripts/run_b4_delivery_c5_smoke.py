"""Run one explicitly authorized, synthetic B4 C5 delivery smoke.

This is an operator-only verification script. It never changes the product
live gate, reads no Integration configuration, and emits no secret or target.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.delivery import DeliveryAdapterError, FeishuWebhookDeliveryAdapter, SmtpDeliveryAdapter

CONFIRMATION = "I_UNDERSTAND_SYNTHETIC_DELIVERY_SMOKE"
SYNTHETIC_CONTENT = "StudyBuddy B4 C5 synthetic delivery smoke. No study material is included."


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise DeliveryAdapterError("delivery_configuration_invalid")
    return value


def _result(*, channel: str, status: str, error_code: str | None = None) -> dict[str, object]:
    return {
        "gate": "B4-C5",
        "channel": channel,
        "status": status,
        "error_code": error_code,
        "sent": status == "sent",
        "synthetic_content_sha256": hashlib.sha256(SYNTHETIC_CONTENT.encode("utf-8")).hexdigest(),
        "synthetic_content_chars": len(SYNTHETIC_CONTENT),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def run(channel: str) -> dict[str, object]:
    if os.environ.get("LIVE_SMOKE") != "1" or os.environ.get("LIVE_SMOKE_CONFIRM") != CONFIRMATION:
        raise DeliveryAdapterError("delivery_authorization_required")
    label = _required("STUDYBUDDY_B4_C5_TARGET_LABEL")
    if channel == "smtp":
        adapter = SmtpDeliveryAdapter(
            host=_required("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST"),
            port=int(_required("STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT")),
            username=_required("STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME"),
            auth_code=_required("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD"),
            targets={label: _required("STUDYBUDDY_B4_C5_SMTP_RECIPIENT")},
            secure=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE", "true").lower() == "true",
        )
    elif channel == "feishu":
        adapter = FeishuWebhookDeliveryAdapter(
            targets={label: _required("STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK")},
        )
    else:
        raise DeliveryAdapterError("delivery_target_not_allowed")
    outcome = adapter.deliver(target_label=label, safe_payload={}, markdown_content=SYNTHETIC_CONTENT)
    return _result(channel=channel, status=outcome.status, error_code=outcome.error_code)


def main() -> int:
    channel = os.environ.get("STUDYBUDDY_B4_C5_SMOKE_CHANNEL", "").strip().lower()
    try:
        result = run(channel)
    except DeliveryAdapterError as error:
        result = _result(channel=channel if channel in {"smtp", "feishu"} else "invalid", status="failed",
                         error_code=error.code)
    except ValueError:
        result = _result(channel=channel if channel in {"smtp", "feishu"} else "invalid", status="failed",
                         error_code="delivery_configuration_invalid")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "sent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
