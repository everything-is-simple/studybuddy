from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.repository import (
    PHASE9D_REPORT_MAX_EXPORT_BYTES,
    connect,
    create_report_snapshot,
    export_report_snapshot,
)
from test_phase9d_domain import PROJECT_ID, _seed_project


def _report(connection):
    return create_report_snapshot(
        connection,
        project_id=PROJECT_ID,
        report_kind="daily",
        timezone_name="UTC",
        period_start="2026-01-15",
        period_end="2026-01-16",
    )


def test_report_export_limit_is_formal_and_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert PHASE9D_REPORT_MAX_EXPORT_BYTES == 1024 * 1024
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        report = _report(connection)
        json_text, json_type = export_report_snapshot(
            connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="json"
        )
        markdown_text, markdown_type = export_report_snapshot(
            connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="markdown"
        )
        assert json_type == "application/json"
        assert markdown_type == "text/markdown"
        assert json.loads(json_text)["period"]["report_kind"] == "daily"
        assert len(json_text.encode("utf-8")) <= PHASE9D_REPORT_MAX_EXPORT_BYTES
        assert len(markdown_text.encode("utf-8")) <= PHASE9D_REPORT_MAX_EXPORT_BYTES

        monkeypatch.setattr("app.repositories._legacy_part_08.PHASE9D_REPORT_MAX_EXPORT_BYTES", 1)
        with pytest.raises(ValueError, match="payload_too_large"):
            export_report_snapshot(
                connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="json"
            )
        with pytest.raises(ValueError, match="payload_too_large"):
            export_report_snapshot(
                connection, project_id=PROJECT_ID, report_id=str(report["id"]), format_name="markdown"
            )
