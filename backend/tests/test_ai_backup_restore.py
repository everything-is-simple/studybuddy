from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def make_answer(root: Path) -> tuple[str, str]:
    with TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=4096, ai_provider_id="fake"))) as client:
        material = client.post("/api/materials", files={"file": ("backup.txt", b"A trusted citation supports backup restore.", "text/plain")}).json()
        assert client.post(f"/api/materials/{material['material_id']}/ai-index").status_code == 200
        answer = client.post("/api/qa/ask", json={"question": "trusted citation", "material_ids": [material["material_id"]]}).json()
        assert answer["status"] == "succeeded"
        return material["material_id"], answer["citations"][0]["citation_key"]


def test_backup_restore_preserves_qa_and_retrieval_records(tmp_path: Path):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    _material_id, citation_key = make_answer(source)
    with connect(source / "studybuddy.sqlite3") as db:
        expected = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            "ai_operations", "qa_threads", "qa_messages", "qa_answers", "qa_citations", "retrieval_runs", "retrieval_hits",
        )}
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with connect(restored / "studybuddy.sqlite3") as db:
        actual = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in expected}
        assert actual == expected
        assert db.execute("SELECT status FROM qa_citations WHERE citation_key = ?", (citation_key,)).fetchone()[0] == "valid"
    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as client:
        restored_detail = client.get(f"/api/qa/citations/{citation_key}")
        assert restored_detail.status_code == 200
        assert restored_detail.json()["status"] == "valid"


def test_backup_restore_preserves_purged_historical_citation(tmp_path: Path):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    material_id, citation_key = make_answer(source)
    with TestClient(create_app(AppConfig(data_root=source, ai_provider_id="fake"))) as client:
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 200
    assert backup_data(source, backup)["status"] == "complete"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    with connect(restored / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT status FROM qa_citations WHERE citation_key = ?", (citation_key,)).fetchone()[0] == "source_unavailable"
        assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 1
    with TestClient(create_app(AppConfig(data_root=restored, ai_provider_id="fake"))) as client:
        assert client.get(f"/api/qa/citations/{citation_key}").json()["status"] == "source_unavailable"
