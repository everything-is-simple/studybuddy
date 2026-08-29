from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect

PROJECT_ID = "project_9d_api"
OTHER_PROJECT_ID = "project_9d_other"
NOW = "2026-01-15T08:00:00+00:00"


def _seed_project(path: Path, project_id: str = PROJECT_ID) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with connect(path / "studybuddy.sqlite3") as connection:
        connection.execute(
            "INSERT INTO projects (id,name,created_at) VALUES (?,?,?)",
            (project_id, "API project", NOW),
        )


def _client(tmp_path: Path, *, project_id: str = PROJECT_ID,
            delivery_mode: str = "off",
            delivery_targets: tuple[str, ...] = ()) -> TestClient:
    root = tmp_path / "data"
    _seed_project(root, project_id)
    return TestClient(create_app(AppConfig(
        data_root=root,
        project_id=project_id,
        report_delivery_mode=delivery_mode,
        report_delivery_targets=delivery_targets,
    )))


def _wav_bytes() -> bytes:
    return b"RIFF" + (20).to_bytes(4, "little") + b"WAVE" + b"studybuddy-capture"


def _capture_ready(client: TestClient) -> tuple[str, dict[str, object]]:
    created = client.post(
        "/api/study/capture-sessions",
        json={
            "asset_kind": "audio",
            "original_name": "lesson.wav",
            "media_type": "audio/wav",
        },
    )
    assert created.status_code == 201, created.text
    capture_id = created.json()["id"]
    uploaded = client.post(
        f"/api/study/capture-sessions/{capture_id}/upload",
        files={"file": ("lesson.wav", _wav_bytes(), "audio/wav")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "uploaded"
    return capture_id, uploaded.json()


def test_s7_api_flow_scope_idempotency_and_privacy(tmp_path: Path):
    with _client(tmp_path) as client:
        capture_id, uploaded = _capture_ready(client)
        assert "stored_path" not in json.dumps(uploaded)
        assert "studybuddy-capture" not in json.dumps(uploaded)

        listed = client.get("/api/study/capture-sessions")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == capture_id

        transcribed = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcribe",
            headers={"Idempotency-Key": "capture-api-key"},
        )
        assert transcribed.status_code == 200, transcribed.text
        payload = transcribed.json()
        assert payload["draft"]["quality_status"] == "uncertain"
        assert payload["draft"]["segments"]
        assert "raw" not in transcribed.text.lower()
        assert "stored_path" not in transcribed.text

        replay = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcribe",
            headers={"Idempotency-Key": "capture-api-key"},
        )
        assert replay.status_code == 200
        assert replay.json()["replay"] is True
        assert replay.json()["draft"]["id"] == payload["draft"]["id"]

        edited = client.post(
            f"/api/study/capture-sessions/{capture_id}/transcript/edit",
            json={"draft_id": payload["draft"]["id"], "text": "User reviewed lesson text"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["edited_by_user"] is True

        confirmed = client.post(
            f"/api/study/capture-sessions/{capture_id}/confirm",
            json={"draft_id": payload["draft"]["id"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["capture"]["status"] == "confirmed"
        assert confirmed.json()["revision"]["citations"]
        assert "stored_path" not in confirmed.text

        detail = client.get(f"/api/study/capture-sessions/{capture_id}")
        assert detail.status_code == 200
        assert detail.json()["source_status"] == "valid"

    with _client(tmp_path / "other", project_id=OTHER_PROJECT_ID) as other:
        assert other.get(f"/api/study/capture-sessions/{capture_id}").status_code == 404
        assert other.post(
            f"/api/study/capture-sessions/{capture_id}/transcribe",
        ).status_code == 404


def test_capture_session_can_start_from_a_new_empty_data_root(tmp_path: Path):
    root = tmp_path / "empty-data"
    with TestClient(create_app(AppConfig(data_root=root, project_id=PROJECT_ID))) as client:
        created = client.post(
            "/api/study/capture-sessions",
            json={
                "asset_kind": "audio",
                "original_name": "first-lesson.mp3",
                "media_type": "audio/mpeg",
            },
        )

    assert created.status_code == 201, created.text
    assert created.json()["project_id"] == PROJECT_ID


def test_s7_api_reject_path_and_input_boundaries(tmp_path: Path):
    with _client(tmp_path) as client:
        capture_id, _ = _capture_ready(client)
        transcribed = client.post(f"/api/study/capture-sessions/{capture_id}/transcribe")
        draft_id = transcribed.json()["draft"]["id"]
        rejected = client.post(
            f"/api/study/capture-sessions/{capture_id}/reject",
            json={"draft_id": draft_id},
        )
        assert rejected.status_code == 200
        assert rejected.json()["capture"]["status"] == "rejected"
        assert client.post(
            f"/api/study/capture-sessions/{capture_id}/confirm",
            json={"draft_id": draft_id},
        ).status_code == 409

        invalid = client.post(
            "/api/study/capture-sessions",
            json={"asset_kind": "video", "original_name": "x.mp4", "media_type": "video/mp4"},
        )
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "capture_asset_type_not_supported"
        malformed = client.post(
            "/api/study/capture-sessions",
            json={"asset_kind": "audio"},
        )
        assert malformed.status_code == 422
        assert "traceback" not in malformed.text.lower()
        assert "stored_path" not in malformed.text
        assert client.get("/api/study/capture-sessions?limit=0").status_code == 400
        assert client.get("/api/study/capture-sessions/capture_missing").status_code == 404


def test_s6_api_report_export_redaction_scope_and_delivery(tmp_path: Path):
    with _client(tmp_path, delivery_mode="off") as client:
        report_response = client.post(
            "/api/study/reports",
            headers={"Idempotency-Key": "report-api-key"},
            json={
                "report_kind": "daily",
                "timezone": "UTC",
                "period_start": "2026-01-15",
                "period_end": "2026-01-16",
            },
        )
        assert report_response.status_code == 201, report_response.text
        report = report_response.json()
        report_id = report["id"]
        for forbidden in ("stored_path", "answer_key", "Private"):
            assert forbidden not in report_response.text

        replay = client.post(
            "/api/study/reports",
            headers={"Idempotency-Key": "report-api-key"},
            json={
                "report_kind": "daily",
                "timezone": "UTC",
                "period_start": "2026-01-15",
                "period_end": "2026-01-16",
            },
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == report_id
        assert replay.json()["replay"] is True

        assert client.get("/api/study/reports").json()["total"] == 1
        assert client.get(f"/api/study/reports/{report_id}").status_code == 200
        assert client.get(f"/api/study/reports/{report_id}/preview").status_code == 200
        exported = client.get(f"/api/study/reports/{report_id}/export?format=json")
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("application/json")
        assert "stored_path" not in exported.text
        markdown = client.get(f"/api/study/reports/{report_id}/export?format=markdown")
        assert markdown.status_code == 200
        assert "answer_key" not in markdown.text

        delivery = client.post(
            f"/api/study/reports/{report_id}/delivery",
            headers={"Idempotency-Key": "delivery-api-key"},
            json={"channel": "smtp", "target_label": "guardian-primary"},
        )
        assert delivery.status_code == 200
        assert delivery.json()["status"] == "blocked"
        assert delivery.json()["error_code"] == "delivery_disabled"
        assert delivery.json()["sent"] is False
        assert "stored_path" not in delivery.text
        attempts = client.get(f"/api/study/reports/{report_id}/delivery-attempts")
        assert attempts.status_code == 200
        assert len(attempts.json()["items"]) == 1

        invalid_period = client.post(
            "/api/study/reports",
            json={
                "report_kind": "daily", "timezone": "not/a/timezone",
                "period_start": "2026-01-15", "period_end": "2026-01-16",
            },
        )
        assert invalid_period.status_code == 400
        assert invalid_period.json()["detail"] == "report_invalid_period"

    with _client(tmp_path / "other", project_id=OTHER_PROJECT_ID) as other:
        assert other.get(f"/api/study/reports/{report_id}").status_code == 404
        assert other.post(
            f"/api/study/reports/{report_id}/delivery",
            json={"channel": "smtp", "target_label": "guardian-primary"},
        ).status_code == 404


def test_s6_api_explicit_dry_run_and_live_remains_blocked(tmp_path: Path):
    with _client(
        tmp_path, delivery_mode="dry_run", delivery_targets=("guardian-primary",)
    ) as client:
        report = client.post(
            "/api/study/reports",
            json={
                "report_kind": "weekly", "timezone": "UTC",
                "period_start": "2026-01-12", "period_end": "2026-01-19",
            },
        ).json()
        dry_run = client.post(
            f"/api/study/reports/{report['id']}/delivery",
            json={"channel": "smtp", "target_label": "guardian-primary"},
        )
        assert dry_run.status_code == 200
        assert dry_run.json()["status"] == "dry_run"
        assert dry_run.json()["sent"] is False
        assert dry_run.json()["content_summary"]["content_sha256"]

        rejected = client.post(
            f"/api/study/reports/{report['id']}/delivery",
            json={"channel": "smtp", "target_label": "not-allowed"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["error_code"] == "delivery_target_not_allowed"

        live_override = client.post(
            f"/api/study/reports/{report['id']}/delivery",
            json={"channel": "smtp", "target_label": "guardian-primary", "mode": "live"},
        )
        assert live_override.status_code == 400
        assert live_override.json()["detail"] == "delivery_disabled"
