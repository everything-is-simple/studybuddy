from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.embedding import FakeEmbeddingProvider
from app.main import create_app
from app.repository import connect, index_embeddings_for_material, index_material_revision, run_hybrid_retrieval, run_vector_retrieval


def _client(root: Path, *, embedding: bool = True) -> TestClient:
    return TestClient(create_app(AppConfig(
        data_root=root,
        max_upload_bytes=200_000,
        ai_provider_id="fake",
        embedding_provider_id="fake" if embedding else None,
        embedding_model_id="fake-embedding-v1" if embedding else None,
    )))


def _prepare_material(client: TestClient, root: Path, text: str = "A stable acceptance source supports retrieval.") -> dict[str, str]:
    material = client.post("/api/materials", files={"file": ("acceptance.txt", text.encode(), "text/plain")}).json()
    assert client.post(f"/api/materials/{material['material_id']}/ai-index").status_code == 200
    with connect(root / "studybuddy.sqlite3") as db:
        extraction = db.execute(
            "SELECT id FROM extractions WHERE material_id = ? ORDER BY created_at DESC LIMIT 1",
            (material["material_id"],),
        ).fetchone()
        index_material_revision(db, material["material_id"], str(extraction["id"]))
        index_embeddings_for_material(db, material_id=material["material_id"], provider=FakeEmbeddingProvider())
    return material


def test_phase7_embedding_retrieval_backup_restore_preserves_metadata(tmp_path: Path):
    source, backup, restored = tmp_path / "source", tmp_path / "backup", tmp_path / "restored"
    with _client(source) as client:
        material = _prepare_material(client, source)
        answer = client.post("/api/qa/ask", json={
            "question": "stable acceptance source", "material_ids": [material["material_id"]],
            "retrieval_mode": "hybrid", "allow_retrieval_fallback": False,
        }).json()
        assert answer["status"] == "succeeded"
        with connect(source / "studybuddy.sqlite3") as db:
            provider = FakeEmbeddingProvider()
            vector = run_vector_retrieval(db, project_id="default", query="stable source", provider=provider)
            hybrid = run_hybrid_retrieval(db, project_id="default", query="stable source", provider=provider,
                                           allow_fallback=False)
            fallback = run_hybrid_retrieval(db, project_id="default", query="stable source", provider=None)
            assert vector["policy_version"] == "vector_cosine_v1"
            assert hybrid["policy_version"] == "hybrid_rrf_v1"
            assert fallback["policy_version"] == "fallback_lexical_v1"
            assert fallback["fallback"] is True
            before = {
                "schema": tuple(db.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()),
                "embedding": [tuple(row) for row in db.execute(
                    "SELECT chunk_id, provider_id, model_id, model_revision, dimensions, vector_encoding, status, "
                    "       hex(vector_payload) FROM embeddings ORDER BY id"
                ).fetchall()],
                "runs": [tuple(row) for row in db.execute(
                    "SELECT policy_version, embedding_provider_id, embedding_model_id, status, error_code "
                    "FROM retrieval_runs ORDER BY created_at, id"
                ).fetchall()],
                "hits": [tuple(row) for row in db.execute(
                    "SELECT rank, score, lexical_score, vector_score, citation_label FROM retrieval_hits ORDER BY run_id, rank"
                ).fetchall()],
                "qa": tuple(db.execute(
                    "SELECT status, retrieval_run_id, output_artifact_id FROM ai_operations WHERE id = ?",
                    (answer["operation_id"],),
                ).fetchone()),
            }
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert verify_backup(backup)["status"] == "valid"
    with connect(restored / "studybuddy.sqlite3") as db:
        after = {
            "schema": tuple(db.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()),
            "embedding": [tuple(row) for row in db.execute(
                "SELECT chunk_id, provider_id, model_id, model_revision, dimensions, vector_encoding, status, "
                "       hex(vector_payload) FROM embeddings ORDER BY id"
            ).fetchall()],
            "runs": [tuple(row) for row in db.execute(
                "SELECT policy_version, embedding_provider_id, embedding_model_id, status, error_code "
                "FROM retrieval_runs ORDER BY created_at, id"
            ).fetchall()],
            "hits": [tuple(row) for row in db.execute(
                "SELECT rank, score, lexical_score, vector_score, citation_label FROM retrieval_hits ORDER BY run_id, rank"
            ).fetchall()],
            "qa": tuple(db.execute(
                "SELECT status, retrieval_run_id, output_artifact_id FROM ai_operations WHERE id = ?",
                (answer["operation_id"],),
            ).fetchone()),
        }
    assert after == before


def test_phase7_corrupt_embedding_is_skipped_and_verify_is_read_only(tmp_path: Path):
    with _client(tmp_path) as client:
        material = _prepare_material(client, tmp_path, "Corruption boundary source text.")
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            row = db.execute("SELECT id, chunk_id, status FROM embeddings ORDER BY id LIMIT 1").fetchone()
            db.execute("UPDATE embeddings SET vector_payload = ? WHERE id = ?", (b"bad", row["id"]))
            db.commit()
            before = tuple(db.execute("SELECT status, error_code, hex(vector_payload) FROM embeddings WHERE id = ?", (row["id"],)).fetchone())
            vector = run_vector_retrieval(db, project_id="default", query="corruption boundary", provider=FakeEmbeddingProvider())
            assert all(hit["chunk_id"] != row["chunk_id"] for hit in vector["hits"])
            from app.repository import verify_embeddings
            report = verify_embeddings(db, material_id=material["material_id"])
            after = tuple(db.execute("SELECT status, error_code, hex(vector_payload) FROM embeddings WHERE id = ?", (row["id"],)).fetchone())
            assert report["policy_version"] == "embedding_verify_v1"
            assert after == before
