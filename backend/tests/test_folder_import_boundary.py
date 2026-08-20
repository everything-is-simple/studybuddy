from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app


def test_batch_same_basename_creates_distinct_materials_without_list_leaks(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("notes.txt", b"week one notes", "text/plain")),
            ("files", ("notes.txt", b"week two notes", "text/plain")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert payload["total"] == payload["success"] == 2
        first, second = payload["items"]
        assert first["original_name"] == second["original_name"] == "notes.txt"
        assert first["material_id"] != second["material_id"]
        assert first["source_sha256"] != second["source_sha256"]

        listed = client.get("/api/materials?limit=20").json()
        assert listed["total"] == 2
        for item in listed["items"]:
            assert "text" not in item
            assert "search_text" not in item
            assert "stored_path" not in item
        assert client.get(f"/api/materials/{first['material_id']}").json()["text"] == "week one notes"
        assert client.get(f"/api/materials/{second['material_id']}").json()["text"] == "week two notes"
        assert len(list((tmp_path / "originals").rglob("original"))) == 2


def test_batch_partial_success_and_size_rejection_remain_item_level(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=8))) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("ok.txt", b"12345678", "text/plain")),
            ("files", ("notes.md", b"# short", "text/markdown")),
            ("files", ("rejected.rtf", b"{\\rtf1}", "application/rtf")),
            ("files", ("too-large.txt", b"123456789", "text/plain")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert payload["total"] == 4
        assert payload["success"] == 2
        assert payload["rejected"] == 2
        by_name = {item["original_name"]: item for item in payload["items"]}
        assert by_name["rejected.rtf"]["error_code"] == "unsupported_rtf"
        assert by_name["too-large.txt"]["error_code"] == "file_too_large"
        assert by_name["too-large.txt"]["material_id"] is None
        assert len(client.get("/api/materials").json()) == 3
        assert list(tmp_path.glob(".incoming-*")) == []
