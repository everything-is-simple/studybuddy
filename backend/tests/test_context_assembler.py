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
from app.repository import connect, assemble_context, validate_citation_key


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


def retrieval(client: TestClient, query: str, material_ids: list[str] | None = None) -> dict:
    response = client.post("/api/retrieval", json={"query": query, "material_ids": material_ids or []})
    assert response.status_code == 200
    return response.json()


def test_assemble_context_success_and_persists_keys(tmp_path: Path):
    with make_client(tmp_path) as client:
        mat = upload(client, "notes.txt", "alpha beta gamma delta epsilon zeta eta theta iota kappa")
        index(client, mat["material_id"])
        hits = retrieval(client, "alpha gamma", [mat["material_id"]])
        assert hits["status"] == "succeeded"
        chunk_ids = [h["chunk_id"] for h in hits["hits"]]
        result = client.post("/api/context/assemble", json={"hit_ids": chunk_ids})
        assert result.status_code == 200
        payload = result.json()
        assert payload["policy_version"] == "context_assembler_v1"
        assert len(payload["context_blocks"]) == len(chunk_ids)
        assert payload["total_tokens_estimate"] > 0
        assert payload["truncated"] is False
        for block in payload["context_blocks"]:
            assert block["citation_key"].startswith("ctx-")
            assert len(block["citation_key"]) == 21  # ctx- + 8 + - + 8
            assert block["material_name"] == "notes.txt"
            assert "source_info" in block
            assert "span_ids" in block
            assert "stored_path" not in block
        # Validate each key
        for block in payload["context_blocks"]:
            v = client.post("/api/citation/validate", json={"key": block["citation_key"]})
            assert v.status_code == 200
            assert v.json()["status"] == "valid"


def test_assemble_context_empty_hits(tmp_path: Path):
    with make_client(tmp_path) as client:
        result = client.post("/api/context/assemble", json={"hit_ids": []})
    assert result.status_code == 200
    assert result.json()["context_blocks"] == []
    assert result.json()["total_tokens_estimate"] == 0
    assert result.json()["truncated"] is False


def test_assemble_context_token_budget_truncation(tmp_path: Path):
    with make_client(tmp_path) as client:
        # Create two materials to get multiple chunks within size limit
        mat1 = upload(client, "a.txt", "first alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau")
        mat2 = upload(client, "b.txt", "second alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau")
        index(client, mat1["material_id"])
        index(client, mat2["material_id"])
        hits = retrieval(client, "alpha beta", [mat1["material_id"], mat2["material_id"]])
        assert hits["status"] == "succeeded"
        all_ids = [h["chunk_id"] for h in hits["hits"]]
        # Very tight budget should truncate after first block
        result = client.post("/api/context/assemble", json={"hit_ids": all_ids, "max_tokens": 10})
        assert result.status_code == 200
        payload = result.json()
        assert payload["truncated"] is True
        assert payload["total_tokens_estimate"] <= 10


def test_assemble_context_dedup_and_order_preserved(tmp_path: Path):
    with make_client(tmp_path) as client:
        mat = upload(client, "dedup.txt", "dedup content here")
        index(client, mat["material_id"])
        hits = retrieval(client, "dedup", [mat["material_id"]])
        chunk_ids = [h["chunk_id"] for h in hits["hits"]]
        assert len(chunk_ids) >= 1
        # Duplicate chunk_id should not produce duplicate blocks
        result = client.post("/api/context/assemble", json={"hit_ids": [chunk_ids[0], chunk_ids[0]]})
        assert result.status_code == 200
        blocks = result.json()["context_blocks"]
        keys = [b["citation_key"] for b in blocks]
        assert len(keys) == len(set(keys))


def test_validate_citation_key_valid_deleted_and_invalid(tmp_path: Path):
    with make_client(tmp_path) as client:
        mat = upload(client, "validate.txt", "validation text")
        index(client, mat["material_id"])
        hits = retrieval(client, "validation", [mat["material_id"]])
        chunk_ids = [h["chunk_id"] for h in hits["hits"]]
        assert len(chunk_ids) >= 1
        # Get a valid key from context assemble
        ctx = client.post("/api/context/assemble", json={"hit_ids": [chunk_ids[0]]}).json()
        valid_key = ctx["context_blocks"][0]["citation_key"]
        assert client.post("/api/citation/validate", json={"key": valid_key}).json()["status"] == "valid"
        # Invalid format
        assert client.post("/api/citation/validate", json={"key": "bad-key"}).json()["status"] == "invalid_format"
        assert client.post("/api/citation/validate", json={"key": "ctx-tooshort"}).json()["status"] == "invalid_format"
        empty_key = client.post("/api/citation/validate", json={"key": ""})
        assert empty_key.status_code == 400
        # Valid format but source purged (nonexistent chunk UUID prefix)
        uuid_prefix = mat['material_id'].split('_', 1)[1][:8] if '_' in mat['material_id'] else mat['material_id'][:8]
        fake_key = f"ctx-{uuid_prefix}-00000000"
        result = client.post("/api/citation/validate", json={"key": fake_key}).json()
        assert result["status"] in {"source_purged", "source_deleted"}
        # Delete material and re-validate
        client.delete(f"/api/materials/{mat['material_id']}")
        assert client.post("/api/citation/validate", json={"key": valid_key}).json()["status"] == "source_deleted"


def test_context_api_privacy_and_boundaries(tmp_path: Path):
    with make_client(tmp_path) as client:
        upload(client, "privacy.txt", "privacy check")
        result = client.post("/api/context/assemble", json={"hit_ids": ["nonexistent-chunk-id-12345"]})
        assert result.status_code == 200
        payload = result.json()
        assert payload["context_blocks"] == []
        assert "sqlite" not in payload.get("detail", "").lower() if "detail" in payload else True
        # Invalid max_tokens
        bad = client.post("/api/context/assemble", json={"hit_ids": ["x"], "max_tokens": 0})
        assert bad.status_code == 400
        assert bad.json()["detail"] == "context_invalid_max_tokens"
        # Empty hit_ids — allowed, returns empty context
        empty = client.post("/api/context/assemble", json={"hit_ids": []})
        assert empty.status_code == 200
        assert empty.json()["context_blocks"] == []


def test_context_assembler_direct_function(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as db:
        result = assemble_context(db, project_id="test", hits=[])
        assert result["context_blocks"] == []
        assert result["total_tokens_estimate"] == 0
        with pytest.raises(ValueError, match="context_invalid_input"):
            assemble_context(db, project_id="test", hits="not a list")
        with pytest.raises(ValueError, match="context_invalid_input"):
            assemble_context(db, project_id="test", hits=[], max_tokens=-1)
