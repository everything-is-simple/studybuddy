from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app


def client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root)))


def test_startup_removes_only_top_level_stale_temp(tmp_path: Path):
    stale = tmp_path / ".incoming-stale"
    stale.write_bytes(b"stale")
    untouched = tmp_path / "not-incoming"
    untouched.write_bytes(b"keep")
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_temp = nested / ".incoming-nested"
    nested_temp.write_bytes(b"keep")
    with client(tmp_path) as app:
        assert app.get("/api/health").json() == {"status": "ok"}
    assert not stale.exists()
    assert untouched.exists() and nested_temp.exists()


def test_valid_zero_reference_orphan_removed_and_mismatch_preserved(tmp_path: Path):
    body = b"orphan body"
    digest = hashlib.sha256(body).hexdigest()
    target_dir = tmp_path / "originals" / digest[:2] / digest[2:]
    target_dir.mkdir(parents=True)
    (target_dir / "original").write_bytes(body)
    mismatch = tmp_path / "originals" / ("0" * 2) / ("0" * 62)
    mismatch.mkdir(parents=True)
    (mismatch / "original").write_bytes(b"not the hash")
    with client(tmp_path):
        pass
    assert not (target_dir / "original").exists()
    assert (mismatch / "original").exists()


def test_deleted_reference_preserves_original(tmp_path: Path):
    with client(tmp_path) as app:
        created = app.post("/api/materials", files={"file": ("x.txt", b"keep", "text/plain")}).json()
        assert app.delete(f"/api/materials/{created['material_id']}").status_code == 204
    original = next((tmp_path / "originals").rglob("original"))
    with client(tmp_path):
        pass
    assert original.exists()
    with client(tmp_path) as app:
        assert app.get("/api/materials").json() == []
        assert app.get("/api/materials/deleted").json()[0]["id"] == created["material_id"]


def test_missing_original_does_not_delete_material(tmp_path: Path):
    with client(tmp_path) as app:
        created = app.post("/api/materials", files={"file": ("x.txt", b"keep", "text/plain")}).json()
        material_id = created["material_id"]
        original = next((tmp_path / "originals").rglob("original"))
        original.unlink()
    with client(tmp_path) as app:
        assert app.get(f"/api/materials/{material_id}").status_code == 200
        assert app.get(f"/api/materials/{material_id}/text").status_code == 200
        assert app.get(f"/api/materials/{material_id}/original").status_code == 500


def test_recovery_unlink_failure_does_not_block_startup(tmp_path: Path, monkeypatch):
    stale = tmp_path / ".incoming-failure"
    stale.write_bytes(b"stale")
    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", lambda self, **kwargs: (_ for _ in ()).throw(OSError("synthetic")) if self == stale else original_unlink(self, **kwargs))
    with client(tmp_path) as app:
        assert app.get("/api/health").status_code == 200
    assert stale.exists()
