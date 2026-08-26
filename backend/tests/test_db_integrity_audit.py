from __future__ import annotations

import logging
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


def test_normal_startup_audit_and_api_readback(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("audit.txt", b"audit term", "text/plain")}).json()
    with make_client(tmp_path) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get(f"/api/materials/{created['material_id']}").status_code == 200
        assert client.get("/api/materials?q=audit").json()[0]["id"] == created["material_id"]
        assert client.get(f"/api/materials/{created['material_id']}/text").status_code == 200
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 200


def test_integrity_and_foreign_key_diagnostic_failures_are_bounded(tmp_path: Path, monkeypatch, caplog):
    from app import db_audit
    original_run = db_audit._run

    def fake_run(connection, sql, event, **kwargs):
        if "integrity_check" in sql:
            return [("corrupt synthetic detail",)]
        if "foreign_key_check" in sql:
            return [("secret_table", 1, "secret", 1)]
        return original_run(connection, sql, event, **kwargs)

    monkeypatch.setattr(db_audit, "_run", fake_run)
    with caplog.at_level(logging.WARNING):
        with make_client(tmp_path) as client:
            assert client.get("/api/health").json() == {"detail": "service_degraded"}
            assert client.get("/api/readiness").json() == {
                "detail": {"status": "degraded", "reason": "database_integrity_check_failed"}
            }
    text = caplog.text
    assert "corrupt synthetic detail" not in text
    assert "secret_table" not in text
    assert "integrity_check_failed" in text
    assert "foreign_key_check_failed" in text


def test_orphan_search_is_removed_and_missing_search_is_rebuilt(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = client.post("/api/materials", files={"file": ("indexed.txt", b"unique audit", "text/plain")}).json()
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        db.execute("DELETE FROM material_search WHERE material_id = ?", (created["material_id"],))
        db.execute("INSERT INTO material_search VALUES (?, ?, ?)", ("ghost", "ghost", "ghost"))
        db.commit()
    with make_client(tmp_path) as client:
        assert client.get("/api/materials?q=unique").json()[0]["id"] == created["material_id"]
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM material_search WHERE material_id = ?", (created["material_id"],)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM material_search WHERE material_id = 'ghost'").fetchone()[0] == 0


def test_orphan_relations_are_diagnostic_only(tmp_path: Path, monkeypatch, caplog):
    from app import db_audit
    with make_client(tmp_path):
        pass
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("INSERT INTO materials VALUES ('broken', 'default', 'broken.txt', 'x', 'x', 'text/plain', 'now', 'now', NULL)")
        db.execute("INSERT INTO extractions VALUES ('orphan-extraction', 'missing-material', 'txt', '1', 'failed', '', '[]', 'now', NULL)")
        db.execute("INSERT INTO text_spans VALUES ('orphan-span', 'missing-extraction', 1, 'document', 'Document', '')")
        db.commit()
    with caplog.at_level(logging.WARNING):
        with make_client(tmp_path) as client:
            assert client.get("/api/health").json() == {"detail": "service_degraded"}
            assert client.get("/api/readiness").json() == {
                "detail": {"status": "degraded", "reason": "database_foreign_key_check_failed"}
            }
    assert "database_material_extraction_relation_failed" in caplog.text
    assert "orphan-extraction" not in caplog.text
    assert "missing-material" not in caplog.text
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM materials WHERE id='broken'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM extractions WHERE id='orphan-extraction'").fetchone()[0] == 1


def test_audit_query_exception_does_not_block_health(tmp_path: Path, monkeypatch):
    from app import db_audit
    monkeypatch.setattr(db_audit, "_relation_checks", lambda connection: (_ for _ in ()).throw(sqlite3.DatabaseError("private")))
    with make_client(tmp_path) as client:
        assert client.get("/api/health").json() == {"detail": "service_degraded"}
        assert client.get("/api/readiness").json() == {
            "detail": {"status": "degraded", "reason": "database_relation_check_error"}
        }
