from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect


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


def test_startup_marks_interrupted_task_stale_without_starting_runner(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with connect(database) as connection:
        connection.execute("INSERT INTO projects VALUES ('task_recovery','Task recovery','now')")
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at,started_at) "
            "VALUES ('recovery_operation','embedding_index','running','task_recovery','input',0,'now','now')"
        )
        connection.execute(
            "INSERT INTO operation_tasks "
            "(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at,started_at) "
            "VALUES ('recovery_task','task_recovery','recovery_operation','test','running','input',40,'indexing',0,0,'now','now','now')"
        )
        connection.execute(
            "INSERT INTO operation_task_attempts "
            "(id,task_id,project_id,attempt_number,status,progress_percent,stage_code,lease_started_at,lease_expires_at,heartbeat_at,created_at,started_at) "
            "VALUES ('recovery_attempt','recovery_task','task_recovery',1,'running',40,'indexing','now','2999-01-01T00:00:00+00:00','now','now','now')"
        )
    with client(tmp_path) as app:
        assert app.get("/api/health").status_code == 200
    with connect(database) as connection:
        assert tuple(connection.execute(
            "SELECT status,error_code FROM operation_tasks WHERE id='recovery_task'"
        ).fetchone()) == ("stale", "task_recovery_required")
        assert tuple(connection.execute(
            "SELECT status,error_code FROM operation_task_attempts WHERE id='recovery_attempt'"
        ).fetchone()) == ("stale", "task_recovery_required")
        assert tuple(connection.execute(
            "SELECT status,error_code FROM ai_operations WHERE id='recovery_operation'"
        ).fetchone()) == ("stale", "task_recovery_required")


def test_recovery_unlink_failure_does_not_block_startup(tmp_path: Path, monkeypatch):
    stale = tmp_path / ".incoming-failure"
    stale.write_bytes(b"stale")
    original_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", lambda self, **kwargs: (_ for _ in ()).throw(OSError("synthetic")) if self == stale else original_unlink(self, **kwargs))
    with client(tmp_path) as app:
        assert app.get("/api/health").status_code == 200
    assert stale.exists()
