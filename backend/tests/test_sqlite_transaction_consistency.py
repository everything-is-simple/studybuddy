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


def counts(root: Path) -> dict[str, int]:
    with connect(root / "studybuddy.sqlite3") as db:
        return {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("projects", "materials", "extractions", "text_spans", "material_search")}


def upload(client: TestClient, name: str, body: bytes) -> dict[str, object]:
    response = client.post("/api/materials", files={"file": (name, body, "text/plain")})
    assert response.status_code == 201
    return response.json()


def test_material_transaction_rolls_back_when_search_insert_fails(tmp_path: Path, monkeypatch):
    from app import repository
    original_insert = repository._insert_search_row
    calls = 0

    def fail_first_search(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.DatabaseError("private SQL failure")
        return original_insert(*args, **kwargs)

    monkeypatch.setattr(repository, "_insert_search_row", fail_first_search)
    with make_client(tmp_path) as client:
        failed = client.post("/api/materials", files={"file": ("bad.txt", b"bad", "text/plain")})
        assert failed.status_code == 500
        assert failed.json() == {"detail": "material_persist_failed"}
        followup = upload(client, "good.txt", b"good searchable")
        assert client.get("/api/materials?q=searchable").json()[0]["id"] == followup["material_id"]
    assert counts(tmp_path) == {"projects": 1, "materials": 1, "extractions": 1, "text_spans": 1, "material_search": 1}
    assert len(list(tmp_path.rglob("original"))) == 1
    assert list(tmp_path.glob(".incoming-*")) == [] and list(tmp_path.rglob(".upload-*")) == []


def test_batch_transaction_failure_isolated(tmp_path: Path, monkeypatch):
    from app import main
    original = main.save_material_with_extraction
    calls = 0

    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.DatabaseError("private SQL failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "save_material_with_extraction", fail_first)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("bad.txt", b"bad", "text/plain")),
            ("files", ("two.txt", b"two indexed", "text/plain")),
            ("files", ("three.txt", b"three indexed", "text/plain")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert (payload["success"], payload["failed"]) == (2, 1)
        assert payload["items"][0]["error_code"] == "material_persist_failed"
        listed = client.get("/api/materials").json()
        assert {item["original_name"] for item in listed} == {"two.txt", "three.txt"}
        searched = client.get("/api/materials?q=indexed").json()
        assert {item["original_name"] for item in searched} == {"two.txt", "three.txt"}
    assert counts(tmp_path) == {"projects": 1, "materials": 2, "extractions": 2, "text_spans": 2, "material_search": 2}
    assert len(list(tmp_path.rglob("original"))) == 2


def test_connect_rebuilds_missing_and_removes_orphan_search_rows_idempotently(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload(client, "indexed.txt", b"unique index term")
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        db.execute("DELETE FROM material_search WHERE material_id = ?", (created["material_id"],))
        db.execute("INSERT INTO material_search (material_id, original_name, text) VALUES (?, ?, ?)", ("missing", "ghost", "ghost"))
        db.commit()
    with make_client(tmp_path) as client:
        result = client.get("/api/materials?q=unique").json()
        assert [item["id"] for item in result] == [created["material_id"]]
        assert "text" not in result[0] and "stored_path" not in result[0]
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM material_search WHERE material_id = ?", (created["material_id"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM material_search WHERE material_id = 'missing'").fetchone()[0] == 0
    with make_client(tmp_path):
        pass
    assert counts(tmp_path) == {"projects": 1, "materials": 1, "extractions": 1, "text_spans": 1, "material_search": 1}


def test_rename_failure_keeps_name_and_search_consistent(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        created = upload(client, "old.txt", b"rename text")
        monkeypatch.setattr(main, "rename_material", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private SQL failure")))
        failed = client.patch(f"/api/materials/{created['material_id']}", json={"original_name": "new.txt"})
        assert failed.status_code == 500 and failed.json() == {"detail": "material_update_failed"}
        monkeypatch.undo()
        assert client.get(f"/api/materials/{created['material_id']}").json()["original_name"] == "old.txt"
        assert client.get("/api/materials?q=old.txt").json()[0]["id"] == created["material_id"]
        assert client.patch(f"/api/materials/{created['material_id']}", json={"original_name": "new.txt"}).status_code == 200
        assert client.get("/api/materials?q=new.txt").json()[0]["id"] == created["material_id"]


def test_delete_restore_search_visibility_and_purge_failure_rollback(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        created = upload(client, "life.txt", b"visible term")
        assert client.get("/api/materials?q=visible").json()[0]["id"] == created["material_id"]
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 204
        assert client.get("/api/materials?q=visible").json() == []
        assert client.post(f"/api/materials/{created['material_id']}/restore").status_code == 200
        assert client.get("/api/materials?q=visible").json()[0]["id"] == created["material_id"]
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 204
        monkeypatch.setattr(main, "purge_material", lambda *a, **k: (_ for _ in ()).throw(sqlite3.DatabaseError("private SQL failure")))
        failed = client.post(f"/api/materials/{created['material_id']}/purge")
        assert failed.status_code == 500 and failed.json() == {"detail": "material_purge_failed"}
        monkeypatch.undo()
        assert client.get("/api/materials/deleted").json()[0]["id"] == created["material_id"]
        assert client.post(f"/api/materials/{created['material_id']}/purge").status_code == 200
    assert counts(tmp_path) == {"projects": 1, "materials": 0, "extractions": 0, "text_spans": 0, "material_search": 0}


def test_connection_pragmas_and_foreign_keys(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 2000
        assert str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        with __import__("pytest").raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", ("x", "missing", "p", "v", "success", "", "[]", "now", None))
