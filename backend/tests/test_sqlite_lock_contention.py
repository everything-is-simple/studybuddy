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


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=1024)))


def holder(root: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(root / "studybuddy.sqlite3", timeout=0)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN IMMEDIATE")
    return connection


def upload(client: TestClient, name: str, body: bytes = b"content") -> dict[str, object]:
    response = client.post("/api/materials", files={"file": (name, body, "text/plain")})
    assert response.status_code == 201
    return response.json()


def assert_private(response) -> None:
    body = response.text.lower()
    for value in ("database is locked", "sqlite3", "traceback", "stored_path", "g:/", "h:/"):
        assert value not in body


def test_locked_single_import_cleans_new_original_and_recovers(tmp_path: Path):
    with make_client(tmp_path) as client:
        lock = holder(tmp_path)
        try:
            failed = client.post("/api/materials", files={"file": ("locked.txt", b"locked", "text/plain")})
            assert failed.status_code == 500 and failed.json() == {"detail": "material_persist_failed"}
            assert_private(failed)
        finally:
            lock.rollback()
            lock.close()
        assert list(tmp_path.rglob("original")) == []
        assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []
        created = upload(client, "after.txt", b"after lock")
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 200
        assert client.get("/api/materials?q=after").json()[0]["id"] == created["material_id"]


def test_locked_batch_failure_then_followup_batch_succeeds(tmp_path: Path):
    with make_client(tmp_path) as client:
        lock = holder(tmp_path)
        try:
            failed = client.post("/api/materials/batch", files=[("files", ("locked.txt", b"locked", "text/plain"))])
            assert failed.status_code == 201
            item = failed.json()["items"][0]
            assert item["status"] == "failed" and item["error_code"] == "material_persist_failed"
            assert_private(failed)
        finally:
            lock.rollback()
            lock.close()
        successful = client.post("/api/materials/batch", files=[
            ("files", ("one.txt", b"one", "text/plain")),
            ("files", ("two.txt", b"two", "text/plain")),
        ])
        assert successful.status_code == 201 and successful.json()["success"] == 2
        assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []


def test_locked_shared_hash_preserves_existing_original(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = upload(client, "first.txt", b"shared")
        original = next((tmp_path / "originals").rglob("original"))
        lock = holder(tmp_path)
        try:
            failed = client.post("/api/materials", files={"file": ("second.txt", b"shared", "text/plain")})
            assert failed.status_code == 500 and failed.json() == {"detail": "material_persist_failed"}
        finally:
            lock.rollback()
            lock.close()
        assert original.exists() and len(list((tmp_path / "originals").rglob("original"))) == 1
        assert client.get(f"/api/materials/{first['material_id']}/text").status_code == 200
        assert client.get(f"/api/materials/{first['material_id']}/original").status_code == 200
        second = upload(client, "third.txt", b"shared")
        assert second["source_sha256"] == first["source_sha256"]


def test_mutations_roll_back_on_lock_and_recover(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload(client, "old.txt", b"mutation term")
        material_id = created["material_id"]
        cases = [
            ("rename", lambda: client.patch(f"/api/materials/{material_id}", json={"original_name": "new.txt"}), "material_update_failed"),
            ("delete", lambda: client.delete(f"/api/materials/{material_id}"), "material_delete_failed"),
        ]
        for _, action, code in cases:
            lock = holder(tmp_path)
            try:
                response = action()
                assert response.status_code == 500 and response.json() == {"detail": code}
                assert_private(response)
            finally:
                lock.rollback(); lock.close()
        assert client.get(f"/api/materials/{material_id}").json()["original_name"] == "old.txt"
        assert client.get("/api/materials?q=old.txt").json()[0]["id"] == material_id
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        lock = holder(tmp_path)
        try:
            response = client.post(f"/api/materials/{material_id}/restore")
            assert response.status_code == 500 and response.json() == {"detail": "material_restore_failed"}
        finally:
            lock.rollback(); lock.close()
        assert client.get("/api/materials/deleted").json()[0]["id"] == material_id
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 200
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        original = next((tmp_path / "originals").rglob("original"))
        lock = holder(tmp_path)
        try:
            response = client.post(f"/api/materials/{material_id}/purge")
            assert response.status_code == 500 and response.json() == {"detail": "material_purge_failed"}
        finally:
            lock.rollback(); lock.close()
        assert original.exists() and client.get("/api/materials/deleted").json()[0]["id"] == material_id
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 200
