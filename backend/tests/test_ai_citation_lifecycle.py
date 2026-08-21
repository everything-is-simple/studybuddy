from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def client_for(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=4096, ai_provider_id="fake")))


def create_answer(client: TestClient, name: str, text: str) -> tuple[dict, dict]:
    material = client.post("/api/materials", files={"file": (name, text.encode(), "text/plain")}).json()
    assert client.post(f"/api/materials/{material['material_id']}/ai-index").status_code == 200
    answer = client.post("/api/qa/ask", json={"question": "trusted citation", "material_ids": [material["material_id"]]}).json()
    assert answer["status"] == "succeeded"
    return material, answer


def test_citation_detail_deleted_then_purged_unavailable(tmp_path: Path):
    with client_for(tmp_path) as client:
        material, answer = create_answer(client, "citation.txt", "A trusted citation supports this answer.")
        key = answer["citations"][0]["citation_key"]
        valid = client.get(f"/api/qa/citations/{key}")
        assert valid.status_code == 200
        payload = valid.json()
        assert payload["status"] == "valid"
        assert payload["material_id"] == material["material_id"]
        assert len(payload["excerpt"]) <= 240
        assert "stored_path" not in payload
        assert client.delete(f"/api/materials/{material['material_id']}").status_code == 204
        assert client.get(f"/api/qa/citations/{key}").json()["status"] == "source_deleted"
        assert client.post(f"/api/materials/{material['material_id']}/purge").status_code == 200
        unavailable = client.get(f"/api/qa/citations/{key}").json()
        assert unavailable["status"] == "source_unavailable"
        assert "excerpt" not in unavailable
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT status FROM qa_citations WHERE citation_key = ?", (key,)).fetchone()[0] == "source_unavailable"
            assert db.execute("SELECT COUNT(*) FROM qa_answers").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM qa_messages WHERE role = 'assistant'").fetchone()[0] == 1


def test_purge_marks_only_target_valid_citations_and_rolls_back(tmp_path: Path):
    with client_for(tmp_path) as client:
        first, first_answer = create_answer(client, "first.txt", "A trusted citation supports the first answer.")
        second, second_answer = create_answer(client, "second.txt", "A trusted citation supports the second answer.")
        first_key = first_answer["citations"][0]["citation_key"]
        second_key = second_answer["citations"][0]["citation_key"]
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{first['material_id']}/purge").status_code == 200
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT status FROM qa_citations WHERE citation_key = ?", (first_key,)).fetchone()[0] == "source_unavailable"
            assert db.execute("SELECT status FROM qa_citations WHERE citation_key = ?", (second_key,)).fetchone()[0] == "valid"
