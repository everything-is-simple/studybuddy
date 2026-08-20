from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


def make_client(root: Path, limit: int = 1024) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=limit)))


def rows(root: Path, table: str) -> int:
    with connect(root / "studybuddy.sqlite3") as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def assert_no_upload_residue(root: Path) -> None:
    assert list(root.glob(".incoming-*") ) == []
    assert list(root.rglob(".upload-*")) == []


def test_temporary_write_failure_is_safe_and_followup_succeeds(tmp_path: Path, monkeypatch):
    from app import main
    original = main.tempfile.NamedTemporaryFile
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        if kwargs.get("prefix") == ".incoming-" and calls == 0:
            calls += 1
            raise OSError("private synthetic path")
        return original(*args, **kwargs)

    monkeypatch.setattr(main.tempfile, "NamedTemporaryFile", fail_once)
    with make_client(tmp_path) as client:
        failed = client.post("/api/materials", files={"file": ("broken.txt", b"broken", "text/plain")})
        assert failed.status_code == 500
        assert failed.json() == {"detail": "material_upload_failed"}
        assert client.get("/api/materials").json() == []
        assert client.get("/api/health").status_code == 200
        followup = client.post("/api/materials", files={"file": ("after.txt", b"after", "text/plain")})
        assert followup.status_code == 201
    assert rows(tmp_path, "materials") == 1
    assert rows(tmp_path, "extractions") == 1
    assert_no_upload_residue(tmp_path)


def test_batch_temporary_write_failure_keeps_partial_success(tmp_path: Path, monkeypatch):
    from app import main
    original = main.tempfile.NamedTemporaryFile
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        if kwargs.get("prefix") == ".incoming-" and calls == 0:
            calls += 1
            raise OSError("private synthetic path")
        return original(*args, **kwargs)

    monkeypatch.setattr(main.tempfile, "NamedTemporaryFile", fail_once)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("broken.txt", b"broken", "text/plain")),
            ("files", ("good.txt", b"good", "text/plain")),
        ])
        assert response.status_code == 201
        payload = response.json()
        by_name = {item["original_name"]: item for item in payload["items"]}
        assert by_name["broken.txt"]["status"] == "failed"
        assert by_name["broken.txt"]["error_code"] == "material_upload_failed"
        assert by_name["broken.txt"]["material_id"] is None
        assert by_name["good.txt"]["status"] == "success"
        assert payload["success"] == 1 and payload["failed"] == 1
    assert_no_upload_residue(tmp_path)


def test_original_store_failure_is_safe_single_and_batch(tmp_path: Path, monkeypatch):
    from app import main
    original = main.store_original
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        if calls == 0:
            calls += 1
            raise OSError("private synthetic store path")
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "store_original", fail_once)
    with make_client(tmp_path) as client:
        single = client.post("/api/materials", files={"file": ("one.txt", b"one", "text/plain")})
        assert single.status_code == 500
        assert single.json() == {"detail": "material_upload_failed"}
        calls = 0
        batch = client.post("/api/materials/batch", files=[
            ("files", ("two.txt", b"two", "text/plain")),
            ("files", ("three.txt", b"three", "text/plain")),
        ])
        assert batch.status_code == 201
        by_name = {item["original_name"]: item for item in batch.json()["items"]}
        assert by_name["two.txt"]["error_code"] == "original_store_failed"
        assert by_name["three.txt"]["status"] == "success"
    assert rows(tmp_path, "materials") == 1
    assert_no_upload_residue(tmp_path)


def test_sqlite_failure_cleans_new_original(tmp_path: Path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "save_material_with_extraction", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private db")))
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("db.txt", b"db", "text/plain")})
        assert response.status_code == 500
        assert response.json() == {"detail": "material_persist_failed"}
    assert rows(tmp_path, "materials") == 0
    assert list(tmp_path.rglob("original")) == []
    assert_no_upload_residue(tmp_path)


def test_sqlite_failure_preserves_preexisting_shared_original(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        first = client.post("/api/materials", files={"file": ("first.txt", b"shared", "text/plain")}).json()
        original_path = next((tmp_path / "originals").rglob("original"))
        monkeypatch.setattr(main, "save_material_with_extraction", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private db")))
        failed = client.post("/api/materials", files={"file": ("second.txt", b"shared", "text/plain")})
        assert failed.status_code == 500
        assert failed.json() == {"detail": "material_persist_failed"}
        assert original_path.exists()
        assert client.get(f"/api/materials/{first['material_id']}").status_code == 200
        assert client.get(f"/api/materials/{first['material_id']}/original").status_code == 200
        assert client.get(f"/api/materials/{first['material_id']}/text").status_code == 200
    assert_no_upload_residue(tmp_path)
    assert rows(tmp_path, "materials") == 1


def test_failure_responses_do_not_expose_internal_details(tmp_path: Path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "store_original", lambda *a, **k: (_ for _ in ()).throw(OSError("C:/secret/private bytes")))
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("safe.txt", b"safe", "text/plain")})
        body = response.text
        assert response.status_code == 500
        assert "C:/secret" not in body
        assert "private bytes" not in body
        assert "Traceback" not in body
        assert "stored_path" not in body
