from __future__ import annotations

import hashlib
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


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=1024)))


def upload(client: TestClient, name: str, body: bytes, media: str = "text/plain") -> dict:
    response = client.post("/api/materials", files={"file": (name, body, media)})
    assert response.status_code == 201
    return response.json()


def assert_db_invariants(root: Path) -> None:
    with connect(root / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM materials WHERE id NOT IN (SELECT material_id FROM extractions)").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM extractions WHERE material_id NOT IN (SELECT id FROM materials)").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM text_spans WHERE extraction_id NOT IN (SELECT id FROM extractions)").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM material_search WHERE material_id NOT IN (SELECT id FROM materials)").fetchone()[0] == 0
        assert db.execute("SELECT material_id FROM material_search GROUP BY material_id HAVING COUNT(*) > 1").fetchall() == []


def assert_privacy(payload: object) -> None:
    text = str(payload).lower()
    for value in ("stored_path", "search_text", "traceback", "sqlite3", "database is locked"):
        assert value not in text


def assert_originals(root: Path, expected: int | None = None) -> None:
    originals = list((root / "originals").rglob("original")) if (root / "originals").exists() else []
    if expected is not None:
        assert len(originals) == expected
    for path in originals:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert path.parent.name == digest[2:] and path.parent.parent.name == digest[:2]


def test_single_material_full_lifecycle_and_restart(tmp_path: Path):
    body = b"lifecycle searchable content"
    with make_client(tmp_path) as client:
        created = upload(client, "old.txt", body)
        material_id = created["material_id"]
        assert client.get(f"/api/materials/{material_id}").status_code == 200
        assert client.get("/api/materials?q=searchable").json()[0]["id"] == material_id
        assert client.patch(f"/api/materials/{material_id}", json={"original_name": "new.txt"}).status_code == 200
        assert client.get("/api/materials?q=old.txt").json() == []
        assert client.get("/api/materials?q=new.txt").json()[0]["id"] == material_id
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.get(f"/api/materials/{material_id}").status_code == 404
        assert client.get("/api/materials?q=searchable").json() == []
        assert client.get("/api/materials/deleted").json()[0]["id"] == material_id
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 200
        assert client.get("/api/materials?q=searchable").json()[0]["id"] == material_id
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 200
        for endpoint in (f"/api/materials/{material_id}", f"/api/materials/{material_id}/text", f"/api/materials/{material_id}/original"):
            assert client.get(endpoint).status_code == 404
    assert_db_invariants(tmp_path)
    assert_originals(tmp_path, 0)
    with make_client(tmp_path) as client:
        assert client.get("/api/materials").json() == []
        assert client.get("/api/materials/deleted").json() == []


def test_shared_hash_three_material_sequence_preserves_original_until_last_purge(tmp_path: Path):
    body = b"shared lifecycle"
    with make_client(tmp_path) as client:
        items = [upload(client, f"{name}.txt", body) for name in ("a", "b", "c")]
        assert_originals(tmp_path, 1)
        assert client.delete(f"/api/materials/{items[0]['material_id']}").status_code == 204
        assert client.delete(f"/api/materials/{items[1]['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{items[0]['material_id']}/purge").status_code == 200
        assert_originals(tmp_path, 1)
        assert client.get(f"/api/materials/{items[2]['material_id']}/original").status_code == 200
        assert client.delete(f"/api/materials/{items[2]['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{items[2]['material_id']}/restore").status_code == 200
        assert client.delete(f"/api/materials/{items[2]['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{items[1]['material_id']}/purge").status_code == 200
        assert_originals(tmp_path, 1)
        assert client.post(f"/api/materials/{items[2]['material_id']}/purge").status_code == 200
    assert_db_invariants(tmp_path)
    assert_originals(tmp_path, 0)


@pytest.mark.parametrize("filename,body,media,expected_status", [
    ("success.txt", b"success", "text/plain", "success"),
    ("empty.txt", b"", "text/plain", "empty"),
    ("rejected.rtf", b"{\\rtf1}", "application/rtf", "rejected"),
])
def test_parser_status_lifecycle(tmp_path: Path, filename: str, body: bytes, media: str, expected_status: str):
    with make_client(tmp_path) as client:
        created = upload(client, filename, body, media)
        assert created["status"] == expected_status
        material_id = created["material_id"]
        before = client.get(f"/api/materials/{material_id}").json()
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 200
        after = client.get(f"/api/materials/{material_id}").json()
        assert after["status"] == before["status"]
        assert after["text"] == before["text"]
        assert after["warnings"] == before["warnings"]
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        assert client.post(f"/api/materials/{material_id}/purge").status_code == 200
    assert_db_invariants(tmp_path)


def test_search_pagination_and_failure_sequence(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        items = [upload(client, f"page-{i}.txt", f"term-{i}".encode()) for i in range(25)]
        page = client.get("/api/materials?limit=20&offset=0").json()
        assert page["total"] == 25 and page["has_more"] is True and len(page["items"]) == 20
        assert len({item["id"] for item in page["items"]}) == 20
        monkeypatch.setattr(main, "rename_material", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private")))
        failed = client.patch(f"/api/materials/{items[0]['material_id']}", json={"original_name": "changed.txt"})
        assert failed.status_code == 500 and failed.json() == {"detail": "material_update_failed"}
        assert_privacy(failed.json())
        monkeypatch.undo()
        assert client.get(f"/api/materials/{items[0]['material_id']}").json()["original_name"] == "page-0.txt"
        assert_db_invariants(tmp_path)
