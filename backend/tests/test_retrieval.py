from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import AppConfig
from app.main import create_app
from app.embedding import FakeEmbeddingProvider
from app.repository import connect, index_embeddings_for_material, run_hybrid_retrieval


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=4096)))


def upload(client: TestClient, name: str, body: str) -> dict:
    response = client.post("/api/materials", files={"file": (name, body.encode("utf-8"), "text/plain")})
    assert response.status_code == 201
    return response.json()


def index(client: TestClient, material_id: str) -> dict:
    response = client.post(f"/api/materials/{material_id}/ai-index")
    assert response.status_code == 200
    return response.json()


def test_retrieval_requires_explicit_index_and_persists_failed_run(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "not-ready.txt", "not indexed yet")
        response = client.post("/api/retrieval", json={"query": "indexed"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "failed"
        assert payload["error_code"] == "retrieval_not_ready"
        assert payload["hits"] == []
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            row = db.execute("SELECT status, error_code FROM retrieval_runs WHERE id = ?", (payload["run_id"],)).fetchone()
            assert tuple(row) == ("failed", "retrieval_not_ready")
            assert db.execute("SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?", (payload["run_id"],)).fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM materials WHERE id = ?", (material["material_id"],)).fetchone()[0] == 1


def test_retrieval_success_is_stable_and_persists_hits(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = upload(client, "first.txt", "alpha studybuddy retrieval\ncommon")
        second = upload(client, "second.txt", "beta studybuddy retrieval\ncommon")
        index(client, first["material_id"])
        index(client, second["material_id"])
        response = client.post("/api/retrieval", json={"query": "studybuddy retrieval", "top_k": 5})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert [hit["rank"] for hit in payload["hits"]] == list(range(1, len(payload["hits"]) + 1))
        assert all(hit["text_preview"] and len(hit["text_preview"]) <= 240 for hit in payload["hits"])
        assert all("stored_path" not in hit for hit in payload["hits"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            rows = db.execute(
                "SELECT chunk_id, rank, vector_score, rerank_score, citation_label FROM retrieval_hits WHERE run_id = ? ORDER BY rank",
                (payload["run_id"],),
            ).fetchall()
            assert len(rows) == len(payload["hits"])
            assert all(row[2] is None and row[3] is None for row in rows)
            assert [row[1] for row in rows] == list(range(1, len(rows) + 1))
        again = client.post("/api/retrieval", json={"query": "studybuddy retrieval", "top_k": 5}).json()
        assert [(x["material_id"], x["start_offset"]) for x in again["hits"]] == [(x["material_id"], x["start_offset"]) for x in payload["hits"]]


def test_retrieval_unicode_fallback_empty_and_filters(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "中文.txt", "中文学习内容🙂")
        index(client, material["material_id"])
        hit = client.post("/api/retrieval", json={"query": "中文学习"})
        assert hit.status_code == 200
        assert hit.json()["status"] == "succeeded"
        empty = client.post("/api/retrieval", json={"query": "完全不存在"})
        assert empty.status_code == 200
        assert empty.json()["status"] == "empty"
        assert empty.json()["error_code"] == "retrieval_empty"
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?", (empty.json()["run_id"],)).fetchone()[0] == 0
        assert client.delete(f"/api/materials/{material['material_id']}").status_code == 204
        deleted = client.post("/api/retrieval", json={"query": "中文"})
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "failed"
        assert deleted.json()["error_code"] == "retrieval_not_ready"
        assert client.post(f"/api/materials/{material['material_id']}/restore").status_code == 200
        assert client.post("/api/retrieval", json={"query": "中文"}).json()["status"] == "succeeded"


def test_retrieval_input_boundaries_and_material_scope(tmp_path: Path):
    with make_client(tmp_path) as client:
        one = upload(client, "one.txt", "scope-one")
        two = upload(client, "two.txt", "scope-two")
        index(client, one["material_id"])
        index(client, two["material_id"])
        scoped = client.post("/api/retrieval", json={"query": "scope", "material_ids": [one["material_id"]]})
        assert scoped.status_code == 200
        assert {hit["material_id"] for hit in scoped.json()["hits"]} == {one["material_id"]}
        cases = [
            ({"query": ""}, "retrieval_invalid_query"),
            ({"query": "   "}, "retrieval_invalid_query"),
            ({"query": "scope", "top_k": 0}, "retrieval_invalid_top_k"),
            ({"query": "scope", "top_k": -1}, "retrieval_invalid_top_k"),
            ({"query": "scope", "top_k": 51}, "retrieval_invalid_top_k"),
            ({"query": 'scope OR *'}, None),
            ({"query": "scope", "material_ids": []}, "retrieval_invalid_materials"),
        ]
        for body, error in cases:
            response = client.post("/api/retrieval", json=body)
            if error is None:
                assert response.status_code in {200, 400}
                assert "sqlite" not in response.text.lower()
                assert "traceback" not in response.text.lower()
            else:
                assert response.status_code == 400
                assert response.json() == {"detail": error}


def test_retrieval_fts_rows_and_purge_cleanup(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "cleanup.txt", "cleanup searchable")
        indexed = index(client, material["material_id"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM chunks_search").fetchone()[0] == indexed["chunk_count"]
            db.execute("INSERT INTO chunks_search (id, text, normalized_text) VALUES ('orphan', 'cleanup', 'cleanup')")
        result = client.post("/api/retrieval", json={"query": "cleanup"})
        assert result.status_code == 200
        assert all(hit["chunk_id"] != "orphan" for hit in result.json()["hits"])
        assert client.delete(f"/api/materials/{material['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{material['material_id']}/purge").status_code == 200
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM chunks_search WHERE id = 'orphan'").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        # With no indexed material remaining, retrieval records a stable not-ready run.
        assert client.post("/api/retrieval", json={"query": "cleanup"}).json()["error_code"] == "retrieval_not_ready"


def test_hybrid_rrf_persists_scores_and_policy(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "hybrid.txt", "alpha semantic retrieval common")
        index(client, material["material_id"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            from app.repository import index_material_revision
            index_material_revision(db, material["material_id"], material["extraction_id"])
            index_embeddings_for_material(db, material_id=material["material_id"], provider=FakeEmbeddingProvider())
            result = run_hybrid_retrieval(db, project_id="default", query="alpha retrieval",
                                          provider=FakeEmbeddingProvider(), top_k=5)
            assert result["policy_version"] == "hybrid_rrf_v1"
            assert result["status"] in {"succeeded", "empty"}
            if result["hits"]:
                assert result["hits"][0]["score"] > 0
                row = db.execute("SELECT policy_version, lexical_score, vector_score, score FROM retrieval_runs rr JOIN retrieval_hits rh ON rh.run_id=rr.id WHERE rr.id=?", (result["run_id"],)).fetchone()
                assert row[0] == "hybrid_rrf_v1"
                assert row[3] == result["hits"][0]["score"]


def test_hybrid_fallback_is_explicit_and_vector_only_does_not_fallback(tmp_path: Path):
    with make_client(tmp_path) as client:
        material = upload(client, "fallback.txt", "fallback lexical content")
        index(client, material["material_id"])
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            class BrokenProvider(FakeEmbeddingProvider):
                def embed(self, texts):
                    from app.embedding import EmbeddingError
                    raise EmbeddingError("embedding_provider_unavailable")
            provider = BrokenProvider()
            result = run_hybrid_retrieval(db, project_id="default", query="fallback",
                                          provider=provider, allow_fallback=True)
            assert result["fallback"] is True
            assert result["policy_version"] == "fallback_lexical_v1"
            assert result["fallback_reason"] == "embedding_provider_unavailable"
            with pytest.raises(Exception):
                from app.repository import run_vector_retrieval
                run_vector_retrieval(db, project_id="default", query="fallback", provider=provider)


def test_retrieval_failure_rolls_back_run_and_hits(tmp_path: Path, monkeypatch):
    with make_client(tmp_path) as client:
        material = upload(client, "failure.txt", "failure searchable")
        index(client, material["material_id"])
        from app import repository
        original = repository._create_retrieval_run
        def fail_run(*args, **kwargs):
            raise sqlite3.OperationalError("private")
        monkeypatch.setattr(repository, "_create_retrieval_run", fail_run)
        response = client.post("/api/retrieval", json={"query": "failure"})
        assert response.status_code == 500
        assert response.json() == {"detail": "retrieval_failed"}
        monkeypatch.setattr(repository, "_create_retrieval_run", original)
        with connect(tmp_path / "studybuddy.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM retrieval_runs").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM retrieval_hits").fetchone()[0] == 0
