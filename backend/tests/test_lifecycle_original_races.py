from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.import_locks import registry_size
from app.main import create_app
from app.repository import connect


def client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=1024)))


def upload(c: TestClient, name: str, body: bytes = b"shared") -> dict:
    r = c.post("/api/materials", files={"file": (name, body, "text/plain")})
    assert r.status_code == 201
    return r.json()


def test_purge_last_deleted_then_import_rebuilds_original(tmp_path: Path):
    body = b"race body"
    with client(tmp_path) as c:
        first = upload(c, "first.txt", body)
        assert c.delete(f"/api/materials/{first['material_id']}").status_code == 204
        assert c.post(f"/api/materials/{first['material_id']}/purge").status_code == 200
        second = upload(c, "second.txt", body)
        assert c.get(f"/api/materials/{second['material_id']}/original").status_code == 200
        assert c.get(f"/api/materials/{second['material_id']}/text").status_code == 200
    assert len(list((tmp_path / "originals").rglob("original"))) == 1
    assert registry_size() == 0


def test_active_shared_original_survives_deleted_purge(tmp_path: Path):
    with client(tmp_path) as c:
        active = upload(c, "active.txt", b"same")
        deleted = upload(c, "deleted.txt", b"same")
        original = next((tmp_path / "originals").rglob("original"))
        assert c.delete(f"/api/materials/{deleted['material_id']}").status_code == 204
        assert c.post(f"/api/materials/{deleted['material_id']}/purge").status_code == 200
        assert original.exists()
        assert c.get(f"/api/materials/{active['material_id']}").status_code == 200
        assert c.get(f"/api/materials/{active['material_id']}/original").status_code == 200
    assert registry_size() == 0


def test_purge_failure_and_unlink_failure_do_not_remove_original(tmp_path: Path, monkeypatch):
    from app import main
    with client(tmp_path) as c:
        created = upload(c, "gone.txt", b"gone")
        material_id = created["material_id"]
        original = next((tmp_path / "originals").rglob("original"))
        assert c.delete(f"/api/materials/{material_id}").status_code == 204
        monkeypatch.setattr(main, "purge_material", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private")))
        failed = c.post(f"/api/materials/{material_id}/purge")
        assert failed.status_code == 500 and failed.json() == {"detail": "material_purge_failed"}
        assert original.exists()
        monkeypatch.undo()
        original_unlink = Path.unlink
        monkeypatch.setattr(Path, "unlink", lambda self, **kwargs: (_ for _ in ()).throw(OSError("private")) if self == original else original_unlink(self, **kwargs))
        assert c.post(f"/api/materials/{material_id}/purge").status_code == 200
        assert original.exists()
    assert registry_size() == 0


def test_purge_preserves_mismatch_and_symlink_originals(tmp_path: Path):
    with client(tmp_path) as c:
        created = upload(c, "unsafe.txt", b"unsafe")
        material_id = created["material_id"]
        original = next((tmp_path / "originals").rglob("original"))
        assert c.delete(f"/api/materials/{material_id}").status_code == 204
        original.write_bytes(b"mismatch")
        assert c.post(f"/api/materials/{material_id}/purge").status_code == 200
        assert original.exists()
    assert registry_size() == 0
