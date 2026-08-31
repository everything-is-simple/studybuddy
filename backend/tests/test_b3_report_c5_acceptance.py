from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect

PROJECT_ID = "project_b3_c5"
OTHER_PROJECT_ID = "project_b3_c5_other"


def _client(root: Path, project_id: str = PROJECT_ID) -> TestClient:
    root.mkdir(parents=True, exist_ok=True)
    with connect(root / "studybuddy.sqlite3") as connection:
        connection.execute(
            "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
            (project_id, "B3 C5", "2026-01-15T08:00:00+00:00"),
        )
    return TestClient(create_app(AppConfig(data_root=root, project_id=project_id)))


def _request(kind: str = "daily") -> dict[str, str]:
    return {
        "report_kind": kind,
        "timezone": "UTC",
        "period_start": "2026-01-15",
        "period_end": "2026-01-16",
    }


def test_c5_api_accepts_safe_kinds_replays_and_rejects_invalid_inputs(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        reports = []
        for kind in ("daily", "weekly", "monthly", "exam_alert"):
            response = client.post("/api/study/reports", json=_request(kind))
            assert response.status_code == 201, response.text
            report = response.json()
            reports.append(report)
            assert report["safe_payload"]["period"]["report_kind"] == kind
            assert "safe_payload_json" not in response.text
            assert "stored_path" not in response.text

        replay = client.post("/api/study/reports", json=_request("daily"))
        assert replay.status_code == 201
        assert replay.json()["id"] == reports[0]["id"]
        assert replay.json()["replay"] is True

        exported = client.get(f"/api/study/reports/{reports[0]['id']}/export?format=json")
        assert exported.status_code == 200
        assert json.loads(exported.text)["period"]["report_kind"] == "daily"
        markdown = client.get(f"/api/study/reports/{reports[0]['id']}/export?format=markdown")
        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert "stored_path" not in markdown.text

        for body, code in (
            ({**_request(), "report_kind": "pdf"}, "report_invalid_kind"),
            ({**_request(), "timezone": "not/a-timezone"}, "report_invalid_period"),
            ({**_request(), "period_end": "2026-01-15"}, "report_invalid_period"),
        ):
            rejected = client.post("/api/study/reports", json=body)
            assert rejected.status_code == 400
            assert rejected.json()["detail"] == code
        invalid_export = client.get(f"/api/study/reports/{reports[0]['id']}/export?format=pdf")
        assert invalid_export.status_code == 400
        assert invalid_export.json()["detail"] == "report_redaction_violation"
        assert client.get("/api/study/reports?limit=0").json()["detail"] == "invalid_pagination"

    with _client(tmp_path / "other", OTHER_PROJECT_ID) as other:
        assert other.get(f"/api/study/reports/{reports[0]['id']}").status_code == 404


def test_c5_startup_and_ordinary_reads_do_not_create_report_or_delivery_facts(tmp_path: Path):
    root = tmp_path / "data"
    with _client(root) as client:
        assert client.get("/api/readiness").status_code == 200
        assert client.get("/api/study/reports").json()["items"] == []

    with sqlite3.connect(root / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM report_snapshots").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM report_delivery_attempts").fetchone()[0] == 0
