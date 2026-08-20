from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.repository import connect

PYTHON = sys.executable
WORKER = Path(__file__).with_name("crash_worker.py")


def run_worker(root: Path, mode: str, exit_code: int) -> None:
    process = subprocess.Popen([PYTHON, str(WORKER), str(root), mode], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tokens = []
    while True:
        line = process.stdout.readline().strip()
        if not line:
            break
        tokens.append(line)
        if line in {"DB_TRANSACTION_OPEN", "DB_COMMITTED"}:
            process.stdin.write("continue\n")
            process.stdin.flush()
            break
    process.wait(timeout=15)
    assert process.returncode == exit_code
    assert set(tokens).issubset({"READY", "ORIGINAL_STORED", "DB_TRANSACTION_OPEN", "DB_COMMITTED", "CRASHED"})
    assert process.stderr.read() == ""


def integrity(root: Path) -> dict[str, int]:
    with connect(root / "studybuddy.sqlite3") as db:
        return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("materials", "extractions", "text_spans", "material_search")}


def test_before_commit_crash_rolls_back_and_restarts_cleanly(tmp_path: Path):
    run_worker(tmp_path, "before_commit", 91)
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/materials").json() == []
        assert client.get("/api/materials?q=crash").json() == []
        followup = client.post("/api/materials", files={"file": ("after.txt", b"after", "text/plain")})
        assert followup.status_code == 201
    assert integrity(tmp_path) == {"materials": 1, "extractions": 1, "text_spans": 1, "material_search": 1}
    assert not (tmp_path / ".incoming-crashed").exists()


def test_after_commit_crash_is_readable_after_restart(tmp_path: Path):
    run_worker(tmp_path, "after_commit", 93)
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))) as client:
        assert client.get("/api/health").status_code == 200
        listed = client.get("/api/materials").json()
        assert len(listed) == 1 and listed[0]["original_name"] == "committed.txt"
        material_id = listed[0]["id"]
        assert client.get(f"/api/materials/{material_id}").status_code == 200
        assert client.get("/api/materials?q=committed").json()[0]["id"] == material_id
        assert client.get(f"/api/materials/{material_id}/text").status_code == 200
        assert client.get(f"/api/materials/{material_id}/original").status_code == 200
        assert client.post("/api/materials/batch", files=[("files", ("next.txt", b"next", "text/plain"))]).status_code == 201
    assert integrity(tmp_path) == {"materials": 2, "extractions": 2, "text_spans": 2, "material_search": 2}


def test_preexisting_shared_original_survives_uncommitted_crash(tmp_path: Path):
    body = b"crash recovery body"
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))) as client:
        first = client.post("/api/materials", files={"file": ("existing.txt", body, "text/plain")}).json()
        original = next((tmp_path / "originals").rglob("original"))
    run_worker(tmp_path, "before_commit", 91)
    with TestClient(create_app(AppConfig(data_root=tmp_path, max_upload_bytes=1024))) as client:
        assert original.exists()
        assert client.get(f"/api/materials/{first['material_id']}").status_code == 200
        assert client.get(f"/api/materials/{first['material_id']}/original").status_code == 200
        assert client.get(f"/api/materials/{first['material_id']}/text").status_code == 200
