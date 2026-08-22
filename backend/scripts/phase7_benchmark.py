from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.embedding import FakeEmbeddingProvider
from app.main import create_app
from app.repository import connect, run_hybrid_retrieval, run_vector_retrieval, verify_embeddings


def timed(function):
    started = time.perf_counter()
    value = function()
    return value, round((time.perf_counter() - started) * 1000, 3)


def run_case(root: Path, material_count: int, text: str) -> dict[str, object]:
    config = AppConfig(
        data_root=root, max_upload_bytes=2_000_000, ai_provider_id="fake",
        embedding_provider_id="fake", embedding_model_id="fake-embedding-v1",
    )
    provider = FakeEmbeddingProvider()
    index_ms = 0.0
    with TestClient(create_app(config)) as client:
        for number in range(material_count):
            material = client.post(
                "/api/materials",
                files={"file": (f"benchmark-{number}.txt", (text + f" Material {number}.").encode(), "text/plain")},
            )
            if material.status_code != 201:
                raise RuntimeError(f"material_import_failed:{material.status_code}:{material.text}")
            material_id = material.json()["material_id"]
            started = time.perf_counter()
            indexed = client.post(f"/api/materials/{material_id}/ai-index")
            if indexed.status_code != 200:
                raise RuntimeError(f"ai_index_failed:{indexed.status_code}:{indexed.text}")
            index_ms += (time.perf_counter() - started) * 1000
        with connect(root / "studybuddy.sqlite3") as db:
            vector, vector_ms = timed(lambda: run_vector_retrieval(
                db, project_id="default", query="benchmark retrieval stable", provider=provider, top_k=10,
            ))
            hybrid, hybrid_ms = timed(lambda: run_hybrid_retrieval(
                db, project_id="default", query="benchmark retrieval stable", provider=provider, top_k=10,
                allow_fallback=False,
            ))
            verify, verify_ms = timed(lambda: verify_embeddings(db))
            chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embedding_count = db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]

    backup = root.parent / f"backup-{material_count}"
    restored = root.parent / f"restored-{material_count}"
    backup_result, backup_ms = timed(lambda: backup_data(root, backup))
    verify_backup_result, backup_verify_ms = timed(lambda: verify_backup(backup))
    restore_result, restore_ms = timed(lambda: restore_backup(restored, backup, confirm=True))
    return {
        "materials": material_count,
        "chunks": chunk_count,
        "embeddings": embedding_count,
        "index_and_embedding_ms": round(index_ms, 3),
        "vector_ms": vector_ms,
        "hybrid_ms": hybrid_ms,
        "verify_ms": verify_ms,
        "backup_ms": backup_ms,
        "backup_verify_ms": backup_verify_ms,
        "restore_ms": restore_ms,
        "vector_hits": len(vector["hits"]),
        "hybrid_hits": len(hybrid["hits"]),
        "verify_status": verify["status"],
        "backup_status": backup_result["status"],
        "backup_verify_status": verify_backup_result["status"],
        "restore_status": restore_result["status"],
        "environment": "synthetic/local/single-process/SQLite/fake-provider",
    }


def main() -> None:
    text = ("Benchmark retrieval stable content. " * 120).strip()
    with tempfile.TemporaryDirectory(prefix="studybuddy-phase7-benchmark-") as directory:
        root = Path(directory) / "data"
        # The current deterministic chunker yields six chunks per material for this text.
        # 17 and 167 materials therefore exercise at least 100 and 1,000 chunks.
        results = [run_case(root / str(size), size, text) for size in (17, 167)]
    print(json.dumps({"benchmark": "phase7_synthetic_v1", "results": results}, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
