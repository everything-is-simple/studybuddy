from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect
from app.storage import store_original


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=1024)))


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def test_original_symlink_is_rejected_without_reading_target(tmp_path: Path):
    body = b"safe content"
    digest = sha(body)
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("safe.txt", body, "text/plain")}).json()
        original = tmp_path / "originals" / digest[:2] / digest[2:] / "original"
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"outside")
        original.unlink()
        try:
            original.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("symlink unavailable")
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 500
        assert client.get(f"/api/materials/{created['material_id']}/text").status_code == 200
        assert outside.read_bytes() == b"outside"
    assert original.is_symlink() and outside.exists()


def test_recovery_preserves_symlink_and_valid_orphan_is_removed(tmp_path: Path):
    body = b"orphan"
    digest = sha(body)
    valid = tmp_path / "originals" / digest[:2] / digest[2:] / "original"
    valid.parent.mkdir(parents=True)
    valid.write_bytes(body)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    linked_dir = tmp_path / "originals" / "aa" / ("b" * 62)
    linked_dir.parent.mkdir(parents=True)
    try:
        linked_dir.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with make_client(tmp_path) as client:
        assert client.get("/api/health").status_code == 200
    assert not valid.exists()
    assert linked_dir.is_symlink() and outside.exists()


def test_store_original_rejects_symlink_target_and_hash_mismatch(tmp_path: Path):
    body = b"body"
    digest = sha(body)
    source = tmp_path / "incoming"
    source.write_bytes(body)
    target_dir = tmp_path / "originals" / digest[:2] / digest[2:]
    target_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_bytes(b"untouched")
    target = target_dir / "original"
    try:
        target.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(OSError):
        store_original(source, "x.txt", digest, tmp_path / "originals")
    assert outside.read_bytes() == b"untouched"
    target.unlink()
    target.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="stored_hash_mismatch"):
        store_original(source, "x.txt", digest, tmp_path / "originals")
    assert target.read_bytes() == b"wrong"


def test_root_outside_stored_path_rejected_but_text_export_works(tmp_path: Path):
    body = b"text remains"
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("x.txt", body, "text/plain")}).json()
        outside = tmp_path.parent / "outside-original"
        outside.write_bytes(b"outside")
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            db.execute("UPDATE materials SET stored_path = ? WHERE id = ?", (str(outside), created["material_id"]))
            db.commit()
        response = client.get(f"/api/materials/{created['material_id']}/original")
        assert response.status_code == 500
        assert client.get(f"/api/materials/{created['material_id']}/text").status_code == 200
        listing = client.get("/api/materials").json()
        assert "stored_path" not in listing[0] and "text" not in listing[0]
