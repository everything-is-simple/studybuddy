from __future__ import annotations

import concurrent.futures
import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.import_locks import registry_size
from app.main import create_app
from app.repository import connect


def post(client: TestClient, name: str, body: bytes):
    return client.post("/api/materials", files={"file": (name, body, "text/plain")})


def test_concurrent_same_hash_imports_share_one_original(tmp_path: Path):
    app = create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))
    body = b"concurrent shared content"
    with TestClient(app) as client, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda args: post(client, *args), [("one.txt", body), ("two.txt", body)]))
    assert first.status_code == second.status_code == 201
    one, two = first.json(), second.json()
    assert one["material_id"] != two["material_id"]
    assert one["source_sha256"] == two["source_sha256"] == hashlib.sha256(body).hexdigest()
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM material_search").fetchone()[0] == 2
    assert len(list((tmp_path / "originals").rglob("original"))) == 1
    assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []
    assert registry_size() == 0


def test_different_hashes_do_not_share_original(tmp_path: Path):
    app = create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))
    with TestClient(app) as client, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda args: post(client, *args), [("one.txt", b"one"), ("two.txt", b"two")]))
    assert [response.status_code for response in responses] == [201, 201]
    assert len(list((tmp_path / "originals").rglob("original"))) == 2
    assert registry_size() == 0


def test_batch_and_standalone_same_hash_share_one_original(tmp_path: Path):
    app = create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))
    body = b"batch shared body"
    with TestClient(app) as client, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        batch_future = pool.submit(lambda: client.post("/api/materials/batch", files=[("files", ("batch.txt", body, "text/plain"))]))
        single_future = pool.submit(lambda: client.post("/api/materials", files={"file": ("single.txt", body, "text/plain")}))
        batch, single = batch_future.result(), single_future.result()
        assert batch.status_code == 201 and single.status_code == 201
        assert batch.json()["success"] == 1
        assert client.get(f"/api/materials/{batch.json()['items'][0]['material_id']}/original").status_code == 200
        assert client.get(f"/api/materials/{single.json()['material_id']}/text").status_code == 200
    assert len(list((tmp_path / "originals").rglob("original"))) == 1
    assert registry_size() == 0


def test_parser_rejected_same_hash_keeps_one_referenced_original(tmp_path: Path):
    app = create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))
    body = b"{\\rtf1 synthetic}"
    with TestClient(app) as client, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda name: client.post("/api/materials", files={"file": (name, body, "application/rtf")}), ["a.rtf", "b.rtf"]))
        assert all(response.status_code == 201 for response in responses)
        assert all(response.json()["status"] == "rejected" for response in responses)
    assert len(list((tmp_path / "originals").rglob("original"))) == 1
    assert registry_size() == 0


def test_same_hash_persist_failure_then_success_preserves_original(tmp_path: Path, monkeypatch):
    from app import main
    original_save = main.save_material_with_extraction
    calls = 0

    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("private database failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(main, "save_material_with_extraction", fail_first)
    app = create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))
    body = b"shared failure body"
    with TestClient(app) as client, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda args: post(client, *args), [("bad.txt", body), ("good.txt", body)]))
    responses = [first, second]
    assert sorted(response.status_code for response in responses) == [201, 500]
    success = next(response.json() for response in responses if response.status_code == 201)
    with TestClient(app) as client:
        assert client.get(f"/api/materials/{success['material_id']}/original").status_code == 200
        assert client.get(f"/api/materials/{success['material_id']}/text").status_code == 200
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 1
    assert len(list((tmp_path / "originals").rglob("original"))) == 1
    assert list(tmp_path.glob(".incoming-*")) == [] and registry_size() == 0
