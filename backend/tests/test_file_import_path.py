from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig, DEFAULT_MAX_UPLOAD_BYTES
from app.main import create_app
from app.repository import connect

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=DEFAULT_MAX_UPLOAD_BYTES)))


def test_upload_parse_persist_and_restart_readback(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/materials",
            files={"file": ("sample.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")},
        )
        assert response.status_code == 201
        created = response.json()
        assert created["status"] == "success"
        assert created["span_count"] == 1
        assert (tmp_path / "originals" / created["source_sha256"][:2] / created["source_sha256"][2:] / "original").exists()
        detail = client.get(f"/api/materials/{created['material_id']}")
        assert detail.status_code == 200
        assert "StudyBuddy synthetic TXT fixture." in detail.json()["text"]

    # A new application instance proves the result is read from SQLite, not process state.
    with make_client(tmp_path) as restarted:
        listing = restarted.get("/api/materials")
        assert listing.status_code == 200
        assert listing.json()[0]["id"] == created["material_id"]
        detail = restarted.get(f"/api/materials/{created['material_id']}").json()
        assert "StudyBuddy synthetic TXT fixture." in detail["text"]
        assert detail["spans"][0]["span_kind"] == "document"


def test_rejected_format_is_persisted_as_parser_result(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/materials",
            files={"file": ("sample.rtf", (FIXTURES / "sample.rtf").read_bytes(), "application/rtf")},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "rejected"
        material_id = response.json()["material_id"]
        detail = client.get(f"/api/materials/{material_id}").json()
        assert detail["status"] == "rejected"
        assert detail["text"] == ""
        assert detail["warnings"]


def test_duplicate_hash_reuses_original_path(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = client.post("/api/materials", files={"file": ("first.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        second = client.post("/api/materials", files={"file": ("second.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        assert first.status_code == second.status_code == 201
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            rows = connection.execute("SELECT source_sha256, stored_path FROM materials ORDER BY original_name").fetchall()
            assert len(rows) == 2
            assert rows[0][0] == rows[1][0]
            assert rows[0][1] == rows[1][1]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1


def test_default_upload_limit_is_50_mib():
    assert DEFAULT_MAX_UPLOAD_BYTES == 50 * 1024 * 1024


def test_upload_rejects_path_traversal_filename(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("../escape.txt", b"body", "text/plain")})
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_filename"
        assert client.get("/api/materials").json() == []


def test_upload_limit_boundary_is_strictly_greater_than_configured_limit(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=8)
    with TestClient(create_app(config)) as client:
        accepted = client.post("/api/materials", files={"file": ("exact.txt", b"12345678", "text/plain")})
        assert accepted.status_code == 201
        rejected = client.post("/api/materials", files={"file": ("over.txt", b"123456789", "text/plain")})
        assert rejected.status_code == 413


def test_upload_size_limit_does_not_create_material(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=4)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials", files={"file": ("sample.txt", b"too large", "text/plain")})
        assert response.status_code == 413
        assert client.get("/api/materials").json() == []
        assert list(tmp_path.glob(".incoming-*")) == []
        assert not (tmp_path / "originals").exists()
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0


def test_database_failure_cleans_new_original(tmp_path: Path, monkeypatch):
    from app import main
    original_save = main.save_material_with_extraction
    def fail_save(*args, **kwargs):
        raise RuntimeError("synthetic database failure")
    monkeypatch.setattr(main, "save_material_with_extraction", fail_save)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("sample.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        assert response.status_code == 500
        assert response.json()["detail"] == "material_persist_failed"
        assert list((tmp_path / "originals").rglob("original")) == []
        assert client.get("/api/materials").json() == []
    monkeypatch.setattr(main, "save_material_with_extraction", original_save)


def test_batch_imports_multiple_files_with_item_results_and_filters(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=8)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("small.txt", b"12345678", "text/plain")),
            ("files", ("empty.txt", b"", "text/plain")),
            ("files", ("large.txt", b"123456789", "text/plain")),
            ("files", ("sample.rtf", b"{\\rtf1}", "application/rtf")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert payload["total"] == 4
        assert (payload["success"], payload["empty"], payload["rejected"], payload["failed"]) == (1, 1, 2, 0)
        by_name = {item["original_name"]: item for item in payload["items"]}
        assert by_name["large.txt"]["error_code"] == "file_too_large"
        assert by_name["sample.rtf"]["error_code"] == "unsupported_rtf"
        assert client.get("/api/materials?status=success").json()[0]["original_name"] == "small.txt"
        assert client.get("/api/materials?status=empty").json()[0]["original_name"] == "empty.txt"
        assert client.get("/api/materials?status=rejected").json()[0]["original_name"] == "sample.rtf"
        assert client.get("/api/materials?status=failed").json() == []
        assert client.get("/api/materials?status=unknown").status_code == 400
        assert all("text" not in item for item in client.get("/api/materials").json())
        assert list(tmp_path.glob(".incoming-*")) == []
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 3


def test_batch_oversize_does_not_affect_other_files(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=4)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("over.txt", b"12345", "text/plain")),
            ("files", ("ok.txt", b"1234", "text/plain")),
        ])
        assert response.status_code == 201
        items = {item["original_name"]: item for item in response.json()["items"]}
        assert items["over.txt"]["status"] == "rejected"
        assert items["ok.txt"]["status"] == "success"
        assert items["over.txt"]["material_id"] is None
        assert items["over.txt"]["source_sha256"] == ""
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        assert list(tmp_path.glob(".incoming-*")) == []


def test_batch_duplicate_hash_reuses_original(tmp_path: Path):
    body = (FIXTURES / "sample.txt").read_bytes()
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("one.txt", body, "text/plain")),
            ("files", ("two.txt", body, "text/plain")),
        ])
        assert response.status_code == 201
        assert response.json()["success"] == 2
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            rows = connection.execute("SELECT source_sha256, stored_path FROM materials ORDER BY original_name").fetchall()
        assert len(rows) == 2 and rows[0][0] == rows[1][0] and rows[0][1] == rows[1][1]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1


def test_batch_database_failure_is_item_level_and_other_file_survives(tmp_path: Path, monkeypatch):
    from app import main
    original_save = main.save_material_with_extraction
    calls = 0
    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic database failure")
        return original_save(*args, **kwargs)
    monkeypatch.setattr(main, "save_material_with_extraction", fail_first)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("failed.txt", b"first", "text/plain")),
            ("files", ("saved.txt", b"second", "text/plain")),
        ])
        assert response.status_code == 201
        items = {item["original_name"]: item for item in response.json()["items"]}
        assert items["failed.txt"]["error_code"] == "material_persist_failed"
        assert items["saved.txt"]["status"] == "success"
        assert client.get("/api/materials").json()[0]["original_name"] == "saved.txt"
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        assert list(tmp_path.glob(".incoming-*")) == []


def test_page_is_real_multi_file_picker_and_shows_materials(tmp_path: Path):
    with make_client(tmp_path) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'type="file" multiple' in page.text
        assert "/api/materials/batch" in page.text
        assert "success','empty','rejected','failed" in page.text
