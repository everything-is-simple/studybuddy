"""Bounded local scale measurement for P1-4 C4-5.

This is a measurement tool, not a production benchmark endpoint. It creates a
throwaway SQLite database, inserts synthetic public task/material rows, and
reports timings only. No database or generated artifact is kept by the repo.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import shutil
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AppConfig
from app.main import create_app
from app.migrations.runner import migrate
from app.repository import connect
from fastapi.testclient import TestClient


def seed(database: Path, count: int) -> None:
    with connect(database) as db:
        config = AppConfig(data_root=database.parent)
        db.execute("INSERT INTO projects(id,name,created_at) VALUES (?,?,?)", (config.project_id, "Measurement", "2026-01-01T00:00:00+00:00"))
        for index in range(count):
            operation_id = f"measure_operation_{index}"
            task_id = f"measure_task_{index}"
            db.execute(
                "INSERT INTO ai_operations(id,operation_type,status,project_id,input_fingerprint,created_at) VALUES (?,?,?,?,?,?)",
                (operation_id, "embedding_index", "queued", config.project_id, f"operation_fingerprint_{index}", "2026-01-01T00:00:00+00:00"),
            )
            db.execute(
                "INSERT INTO operation_tasks(id,project_id,operation_id,task_kind,status,input_fingerprint,progress_percent,stage_code,retry_count,max_retries,created_at,updated_at) VALUES (?,?,?,?,?,?,0,'queued',0,0,?,?)",
                (task_id, config.project_id, operation_id, "embedding_index", "queued", f"task_fingerprint_{index}", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )
        db.commit()


def measure_task_list(count: int, limit: int) -> dict[str, object]:
    directory = tempfile.mkdtemp(prefix="studybuddy-c4-5-")
    root = Path(directory)
    database = root / "studybuddy.sqlite3"
    with connect(database) as db:
        migrate(db)
    seed(database, count)
    try:
        app = create_app(AppConfig(data_root=root))
        with TestClient(app) as client:
            started = time.perf_counter()
            response = client.get(f"/api/tasks?limit={limit}&offset=0")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            response.raise_for_status()
            body = response.json()
            return {"rows": count, "limit": limit, "elapsed_ms": elapsed_ms,
                    "returned": len(body["items"]), "total": body["total"]}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def measure_material_upload(count: int) -> dict[str, object]:
    directory = tempfile.mkdtemp(prefix="studybuddy-c4-5-materials-")
    root = Path(directory); config = AppConfig(data_root=root)
    try:
        app = create_app(config)
        with TestClient(app) as client:
            started = time.perf_counter()
            for index in range(count):
                response = client.post("/api/materials", files={"file": (f"measure-{index}.txt", f"bounded material {index}".encode(), "text/plain")})
                response.raise_for_status()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            listed = client.get("/api/materials?limit=100&offset=0")
            listed.raise_for_status()
            body = listed.json()
            return {"rows": count, "elapsed_ms": elapsed_ms, "listed_returned": len(body["items"]), "listed_total": body["total"]}
    finally:
        shutil.rmtree(root, ignore_errors=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Measure bounded C4-5 task-list scale")
    parser.add_argument("--sizes", default="10,100,500", help="comma-separated row counts, maximum 2000 each")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--include-material-upload", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    if not sizes or any(value < 1 or value > 2000 for value in sizes):
        parser.error("--sizes values must be between 1 and 2000")
    payload = {"measurement": "p1-4-c4-5", "task_list": [measure_task_list(size, args.limit) for size in sizes]}
    if args.include_material_upload:
        payload["material_upload"] = [measure_material_upload(size) for size in sizes if size <= 500]
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
