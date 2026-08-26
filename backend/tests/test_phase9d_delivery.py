from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig, config_from_environment
from app.delivery import DeliveryAdapterError, DeliveryOutcome, execute_report_delivery
from app.repository import (
    connect,
    create_report_snapshot,
    list_report_delivery_attempts,
)
from test_phase9d_domain import PROJECT_ID, _seed_project, _seed_report_facts


class RawFailureAdapter:
    channel = "smtp"

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        raise RuntimeError("private remote response: webhook-secret-private")


class CountingAdapter:
    channel = "smtp"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.payloads: list[dict[str, object]] = []

    def deliver(self, *, target_label: str, safe_payload: dict[str, object],
                markdown_content: str) -> DeliveryOutcome:
        self.calls += 1
        self.payloads.append(safe_payload)
        if self.fail:
            raise DeliveryAdapterError("delivery_failed")
        return DeliveryOutcome(status="dry_run")


def _report(connection: sqlite3.Connection) -> dict[str, object]:
    return create_report_snapshot(
        connection,
        project_id=PROJECT_ID,
        report_kind="daily",
        timezone_name="UTC",
        period_start="2026-01-15",
        period_end="2026-01-16",
    )


def _config(tmp_path: Path, *, mode: str = "dry_run", enabled: bool = False,
            authorized: bool = False, targets: tuple[str, ...] = ("guardian-primary",)) -> AppConfig:
    return AppConfig(
        data_root=tmp_path / "runtime",
        report_delivery_mode=mode,
        report_delivery_enabled=enabled,
        report_delivery_authorized=authorized,
        report_delivery_targets=targets,
        report_delivery_smtp_password="smtp-password-private",
        report_delivery_feishu_secret="webhook-secret-private",
    )


def test_delivery_configuration_defaults_to_off_and_validates_allowlist(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "STUDYBUDDY_REPORT_DELIVERY_MODE", "STUDYBUDDY_REPORT_DELIVERY_ENABLED",
        "STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED", "STUDYBUDDY_REPORT_DELIVERY_TARGETS",
        "STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD", "STUDYBUDDY_REPORT_DELIVERY_FEISHU_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    assert config_from_environment().report_delivery_mode == "off"

    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_MODE", "dry_run")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_TARGETS", "guardian-primary,guardian-backup")
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD", "smtp-password-private")
    configured = config_from_environment()
    assert configured.report_delivery_targets == ("guardian-primary", "guardian-backup")
    assert "smtp-password-private" not in repr(configured)

    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_TARGETS", "not an opaque label")
    with pytest.raises(ValueError, match="invalid_report_delivery_targets"):
        config_from_environment()


def test_default_off_records_blocked_audit_without_adapter_or_secret_leak(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_report_facts(connection)
        report = _report(connection)
        adapter = CountingAdapter()
        result = execute_report_delivery(
            connection, config=AppConfig(data_root=tmp_path / "runtime"), project_id=PROJECT_ID,
            report_id=str(report["id"]), channel="smtp", target_label="guardian-primary", adapter=adapter,
        )
        assert result["status"] == "blocked"
        assert result["error_code"] == "delivery_disabled"
        assert result["sent"] is False
        assert adapter.calls == 0
        assert len(list_report_delivery_attempts(
            connection, project_id=PROJECT_ID, report_id=str(report["id"])
        )) == 1
        database_text = " ".join(
            str(value)
            for row in connection.execute("SELECT * FROM report_delivery_attempts").fetchall()
            for value in row if value is not None
        )
        returned = json.dumps(result)
        for forbidden in ("smtp-password-private", "webhook-secret-private", "Private plan title", "private answer key"):
            assert forbidden not in database_text
            assert forbidden not in returned
        assert "smtp-password-private" not in repr(_config(tmp_path))
        assert "webhook-secret-private" not in repr(_config(tmp_path))


def test_report_creation_and_read_do_not_trigger_delivery(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = _report(connection)
        assert list_report_delivery_attempts(
            connection, project_id=PROJECT_ID, report_id=str(report["id"])
        ) == []
        connection.execute("SELECT safe_payload_json FROM report_snapshots WHERE id=?", (report["id"],)).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM report_delivery_attempts").fetchone()[0] == 0


def test_dry_run_is_allowlisted_safe_and_does_not_send(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        _seed_report_facts(connection)
        report = _report(connection)
        adapter = CountingAdapter()
        result = execute_report_delivery(
            connection, config=_config(tmp_path), project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="guardian-primary", idempotency_key="dry-run-key", adapter=adapter,
        )
        assert result["status"] == "dry_run" and result["sent"] is False
        assert result["content_summary"]["content_chars"] > 0
        assert len(result["content_summary"]["content_sha256"]) == 64
        assert adapter.calls == 1
        delivered = json.dumps(adapter.payloads[0], ensure_ascii=False)
        for forbidden in ("Private plan title", "private answer key", "private submitted answer"):
            assert forbidden not in delivered

        rejected = execute_report_delivery(
            connection, config=_config(tmp_path), project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="not-allowlisted", adapter=adapter,
        )
        assert rejected["status"] == "blocked"
        assert rejected["error_code"] == "delivery_target_not_allowed"
        assert adapter.calls == 1


def test_live_requires_explicit_authorization_then_remains_not_approved(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = _report(connection)
        adapter = CountingAdapter()
        config = _config(tmp_path, mode="live", enabled=True, authorized=True)
        missing_confirmation = execute_report_delivery(
            connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="feishu", target_label="guardian-primary", adapter=adapter,
        )
        assert missing_confirmation["error_code"] == "delivery_authorization_required"
        approved_but_gated = execute_report_delivery(
            connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="feishu", target_label="guardian-primary", authorization_granted=True, adapter=adapter,
        )
        assert approved_but_gated["status"] == "blocked"
        assert approved_but_gated["error_code"] == "delivery_live_not_approved"
        assert adapter.calls == 0


def test_unexpected_adapter_failure_is_audited_with_stable_redacted_code(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = _report(connection)
        result = execute_report_delivery(
            connection, config=_config(tmp_path), project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="guardian-primary", adapter=RawFailureAdapter(),
        )
        assert result["status"] == "failed" and result["error_code"] == "delivery_failed"
        serialized = json.dumps(result)
        assert "webhook-secret-private" not in serialized
        stored = connection.execute(
            "SELECT error_code FROM report_delivery_attempts WHERE id=?", (result["id"],)
        ).fetchone()[0]
        assert stored == "delivery_failed"


def test_delivery_failure_retry_and_idempotency_do_not_repeat_implicit_work(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = _report(connection)
        failing = CountingAdapter(fail=True)
        config = _config(tmp_path)
        failed = execute_report_delivery(
            connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="guardian-primary", idempotency_key="failure-key", adapter=failing,
        )
        assert failed["status"] == "failed" and failed["error_code"] == "delivery_failed"
        assert failing.calls == 1

        replay = execute_report_delivery(
            connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="guardian-primary", idempotency_key="failure-key", adapter=failing,
        )
        assert replay["id"] == failed["id"] and replay["replay"] is True
        assert failing.calls == 1

        succeeding = CountingAdapter()
        retried = execute_report_delivery(
            connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
            channel="smtp", target_label="guardian-primary", idempotency_key="retry-key",
            retry_of=str(failed["id"]), adapter=succeeding,
        )
        assert retried["status"] == "dry_run" and retried["retry_of"] == failed["id"]
        assert succeeding.calls == 1
        attempts = list_report_delivery_attempts(connection, project_id=PROJECT_ID, report_id=str(report["id"]))
        assert [attempt["id"] for attempt in attempts] == [failed["id"], retried["id"]]
        with pytest.raises(ValueError, match="delivery_failed"):
            execute_report_delivery(
                connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
                channel="smtp", target_label="guardian-primary", idempotency_key="bad-retry-key",
                retry_of=str(retried["id"]), adapter=succeeding,
            )

        with pytest.raises(ValueError, match="delivery_idempotency_mismatch"):
            execute_report_delivery(
                connection, config=config, project_id=PROJECT_ID, report_id=str(report["id"]),
                channel="smtp", target_label="another-target", idempotency_key="retry-key", adapter=succeeding,
            )
