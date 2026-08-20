from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=8)))


def safe(response) -> None:
    text = response.text.lower()
    for bad in ("stored_path", "traceback", "sqlite3", "database is locked", "select ", "g:/", "h:/"):
        assert bad not in text


def counts(root: Path) -> dict[str, int]:
    with connect(root / "studybuddy.sqlite3") as db:
        return {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("materials", "extractions", "text_spans", "material_search")}


def test_missing_malformed_and_invalid_uploads_are_safe(tmp_path: Path):
    with make_client(tmp_path) as client:
        cases = [
            client.post("/api/materials"),
            client.post("/api/materials", files={"wrong": ("x.txt", b"x", "text/plain")}),
            client.post("/api/materials", files={"file": ("../escape.txt", b"x", "text/plain")}),
            client.post("/api/materials", files={"file": ("folder/escape.txt", b"x", "text/plain")}),
            client.post("/api/materials", files={"file": (".", b"x", "text/plain")}),
            client.post("/api/materials", files={"file": ("x" * 256, b"x", "text/plain")}),
            client.post("/api/materials", data="not multipart", headers={"content-type": "text/plain"}),
        ]
        for response in cases:
            assert response.status_code in (400, 201, 422)
            safe(response)
        too_large = client.post("/api/materials", files={"file": ("large.txt", b"123456789", "text/plain")})
        assert too_large.status_code == 413 and too_large.json()["detail"] == "file_too_large"
        safe(too_large)
        assert client.get("/api/health").status_code == 200
        ok = client.post("/api/materials", files={"file": ("ok.txt", b"12345678", "text/plain")})
        assert ok.status_code == 201
    assert counts(tmp_path)["materials"] == 2
    assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []


def test_batch_invalid_and_oversize_items_are_isolated(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("../bad.txt", b"bad", "text/plain")),
            ("files", ("large.txt", b"123456789", "text/plain")),
            ("files", ("good.txt", b"good", "text/plain")),
            ("files", ("reject.rtf", b"{\\rtf1}", "application/rtf")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert payload["total"] == 4 and payload["success"] == 1 and payload["rejected"] == 3 and payload["failed"] == 0
        by_name = {item["original_name"]: item for item in payload["items"]}
        assert next(item for item in payload["items"] if item["status"] == "rejected")["error_code"] == "invalid_filename"
        assert by_name["large.txt"]["error_code"] == "file_too_large"
        assert by_name["good.txt"]["status"] == "success"
        assert client.get("/api/health").status_code == 200
    assert counts(tmp_path)["materials"] == 2
    assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []


@pytest.mark.parametrize("query", ["status=unknown", "limit=0", "limit=101", "limit=abc", "offset=-1", "offset=abc", "limit=1.5"])
def test_list_parameter_boundaries(tmp_path: Path, query: str):
    with make_client(tmp_path) as client:
        response = client.get("/api/materials?" + query)
        assert response.status_code == 400
        safe(response)
        assert client.get("/api/health").status_code == 200


def test_list_search_and_legacy_shapes(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("search.txt", b"search", "text/plain")}).json()
        legacy = client.get("/api/materials")
        assert isinstance(legacy.json(), list)
        paged = client.get("/api/materials?limit=1&offset=0").json()
        assert set(("items", "total", "limit", "offset", "has_more")) <= paged.keys()
        result = client.get("/api/materials?q=%00special").json()
        assert isinstance(result, list)
        assert all("text" not in item and "search_text" not in item and "stored_path" not in item for item in result)
        for invalid in ("missing", "../escape", "/absolute", "material_%00", "x" * 400):
            for suffix in ("", "/text", "/original"):
                response = client.get(f"/api/materials/{invalid}{suffix}")
                assert response.status_code in (404, 422, 500)
                safe(response)
        assert client.get(f"/api/materials/{created['material_id']}").status_code == 200


def test_rename_export_and_method_content_type_boundaries(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("name.txt", b"name", "text/plain")}).json()
        material_id = created["material_id"]
        for body in ({}, {"original_name": None}, {"original_name": 123}, {"original_name": "../x"}, {"original_name": "x" * 256}):
            response = client.patch(f"/api/materials/{material_id}", json=body)
            assert response.status_code in (400, 422)
            safe(response)
        export_cases = [{}, {"material_ids": []}, {"material_ids": "not-list"}, {"material_ids": [123]}, {"material_ids": [material_id], "include_original": False, "include_text": False}, {"material_ids": [material_id, material_id]}]
        for body in export_cases:
            response = client.post("/api/materials/export", json=body)
            assert response.status_code in (400, 404, 422)
            safe(response)
        for method, url in (("get", "/api/materials"), ("post", "/api/health"), ("get", f"/api/materials/{material_id}/restore")):
            response = getattr(client, method)(url)
            assert response.status_code in (200, 404, 405)
            safe(response)
        assert client.get(f"/api/materials/{material_id}").status_code == 200


def test_lifecycle_invalid_states_and_failure_followup(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("life.txt", b"life", "text/plain")}).json()
        material_id = created["material_id"]
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 404
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 404
        assert client.delete("/api/materials/missing").status_code == 404
        assert client.patch("/api/materials/missing", json={"original_name": "x.txt"}).status_code == 404
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.delete(f"/api/materials/{material_id}").status_code == 404
        assert client.patch(f"/api/materials/{material_id}", json={"original_name": "x.txt"}).status_code == 404
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 200
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 200
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 404
        assert client.get("/api/health").status_code == 200
