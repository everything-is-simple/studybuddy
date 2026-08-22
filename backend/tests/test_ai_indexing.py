from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.chunking import SourceSpan, chunk_text
from app.config import AppConfig
from app.main import create_app
from app.embedding import FakeEmbeddingProvider, encode_vector
from app.repository import (connect, index_embeddings_for_material, index_material_revision,
                            rebuild_embeddings_for_material, verify_embeddings)


def client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=4096)))


def upload(c: TestClient, body: bytes = "第一段🙂内容。\n\n第二段 content。".encode()) -> dict:
    response = c.post("/api/materials", files={"file": ("source.txt", body, "text/plain")})
    assert response.status_code == 201
    return response.json()


def test_chunker_uses_unicode_offsets_and_source_slices():
    text = "甲🙂乙\n\n第二段 content"
    spans = [SourceSpan("s1", 1, "page", "page-1", "甲🙂乙"),
             SourceSpan("s2", 2, "page", "page-2", "第二段 content")]
    chunks = chunk_text(text, spans, chunk_size=6, overlap=1)
    assert chunks
    assert all(item.text == text[item.start_offset:item.end_offset] for item in chunks)
    assert chunks[0].start_offset == 0
    assert chunks[0].text.startswith("甲🙂乙")
    assert any(item[0] == "s1" for item in chunks[0].span_overlaps)
    assert any(any(item[0] == "s2" for item in chunk.span_overlaps) for chunk in chunks)
    assert chunk_text(text, spans, chunk_size=6, overlap=1) == chunks


def test_chunker_empty_and_invalid_boundaries():
    assert chunk_text("") == []
    with pytest.raises(ValueError, match="invalid_chunking_config"):
        chunk_text("text", chunk_size=2, overlap=2)
    malformed = [SourceSpan("missing", 1, "page", "page-1", "not in source")]
    assert chunk_text("source", malformed, chunk_size=20, overlap=0)[0].span_overlaps == ()


def test_empty_index_reports_empty_without_phantom_chunk(tmp_path: Path):
    with client(tmp_path) as c:
        created = upload(c, b"")
        response = c.post(f"/api/materials/{created['material_id']}/ai-index")
        assert response.status_code == 200
        assert response.json()["status"] == "empty"
        assert response.json()["chunk_count"] == 0
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0


def test_index_api_is_explicit_idempotent_and_lifecycle_safe(tmp_path: Path):
    with client(tmp_path) as c:
        created = upload(c)
        material_id = created["material_id"]
        status = c.get(f"/api/materials/{material_id}/ai-index")
        assert status.status_code == 200
        assert status.json()["status"] == "not_indexed"

        first = c.post(f"/api/materials/{material_id}/ai-index")
        assert first.status_code == 200
        assert first.json()["status"] == "ready"
        revision_id = first.json()["revision_id"]
        assert first.json()["chunk_count"] >= 1
        second = c.post(f"/api/materials/{material_id}/ai-index")
        assert second.status_code == 200
        assert second.json()["revision_id"] == revision_id
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM material_revisions").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == second.json()["chunk_count"]
            assert db.execute("SELECT COUNT(*) FROM chunk_spans").fetchone()[0] >= 1

        assert c.patch(f"/api/materials/{material_id}", json={"original_name": "renamed.txt"}).status_code == 200
        assert c.post(f"/api/materials/{material_id}/ai-index").json()["revision_id"] == revision_id
        assert c.delete(f"/api/materials/{material_id}").status_code == 204
        assert c.post(f"/api/materials/{material_id}/ai-index").status_code == 404
        assert c.post(f"/api/materials/{material_id}/restore").status_code == 200
        assert c.get(f"/api/materials/{material_id}/ai-index").json()["status"] == "ready"
        assert c.delete(f"/api/materials/{material_id}").status_code == 204
        assert c.post(f"/api/materials/{material_id}/purge").status_code == 200
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM material_revisions").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM chunk_spans").fetchone()[0] == 0


def test_index_rejects_missing_and_does_not_expose_private_details(tmp_path: Path):
    with client(tmp_path) as c:
        response = c.post("/api/materials/missing/ai-index")
        assert response.status_code == 404
        assert response.json() == {"detail": "material_not_found"}
        assert "sqlite" not in str(response.json()).lower()
        assert "traceback" not in str(response.json()).lower()


def test_embedding_index_is_idempotent_and_explicit_rebuild_retries(tmp_path: Path):
    with client(tmp_path) as c:
        created = upload(c)
        material_id = created["material_id"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            index_material_revision(db, material_id, created["extraction_id"])
            provider = FakeEmbeddingProvider()
            first = index_embeddings_for_material(db, material_id=material_id, provider=provider)
            second = index_embeddings_for_material(db, material_id=material_id, provider=provider)
            assert first["embedded_count"] >= 1
            assert second["embedded_count"] == 0
            assert second["skipped_count"] == first["embedded_count"]
            assert db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == first["embedded_count"]
            db.execute("UPDATE embeddings SET status='failed', error_code='test_failure'")
            db.commit()
            assert index_embeddings_for_material(db, material_id=material_id, provider=provider)["embedded_count"] == 0
            rebuilt = rebuild_embeddings_for_material(db, material_id=material_id, provider=provider)
            assert rebuilt["embedded_count"] == first["embedded_count"]
            assert db.execute("SELECT COUNT(*) FROM embeddings WHERE status='ready'").fetchone()[0] == first["embedded_count"]


def test_embedding_verify_is_read_only_and_reports_payload_issues(tmp_path: Path):
    with client(tmp_path) as c:
        created = upload(c)
        material_id = created["material_id"]
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            revision = index_material_revision(db, material_id, created["extraction_id"])
            provider = FakeEmbeddingProvider()
            index_embeddings_for_material(db, material_id=material_id, provider=provider)
            before = db.execute("SELECT status, vector_payload FROM embeddings ORDER BY id").fetchall()
            report = verify_embeddings(db, material_id=material_id)
            assert report["status"] == "valid"
            assert report["counts"]["ready_valid"] == len(before)
            db.execute("UPDATE embeddings SET vector_payload = substr(vector_payload, 1, 1)")
            db.commit()
            invalid = verify_embeddings(db, material_id=material_id)
            assert invalid["status"] == "invalid"
            assert any(item["code"] == "embedding_payload_length_mismatch" for item in invalid["issues"])
            after = db.execute("SELECT status, vector_payload FROM embeddings ORDER BY id").fetchall()
            assert [tuple(row) for row in after] != []
            assert after[0][0] == "ready"
            assert revision["id"]


def test_embedding_verify_rejects_ambiguous_scope(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        with pytest.raises(ValueError, match="embedding_verify_ambiguous_scope"):
            verify_embeddings(db, project_id="p", material_id="m")


def test_index_transaction_rolls_back_on_chunk_write_failure(tmp_path: Path, monkeypatch):
    with client(tmp_path) as c:
        created = upload(c)
        material_id = created["material_id"]
        from app import repository
        monkeypatch.setattr(repository, "chunk_text", lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("private")))
        response = c.post(f"/api/materials/{material_id}/ai-index")
        assert response.status_code == 500
        assert response.json() == {"detail": "ai_index_failed"}
        monkeypatch.undo()
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM material_revisions").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        assert c.post(f"/api/materials/{material_id}/ai-index").status_code == 200
