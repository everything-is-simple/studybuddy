from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.embedding import (FakeEmbeddingProvider, EmbeddingError, decode_vector, encode_vector,
                           cosine_similarity, FAKE_EMBEDDING_ALGORITHM_VERSION, EmbeddingIdentity,
                           embedding_content_hash, embedding_staleness)
from app.providers import EmbeddingProviderRegistry

def test_fake_embedding_is_deterministic_and_codec_round_trips():
    provider = FakeEmbeddingProvider()
    first = provider.embed(["  hello   world "])[0]
    second = provider.embed(["hello world"])[0]
    assert first == second
    assert decode_vector(encode_vector(first), len(first)) == pytest.approx(first)
    assert cosine_similarity(first, first) == pytest.approx(1.0)

def test_fake_algorithm_is_versioned_and_cross_process_stable():
    provider = FakeEmbeddingProvider()
    assert FAKE_EMBEDDING_ALGORITHM_VERSION == "sha256_bucket_v1"
    assert provider.embed(["same text"])[0] == FakeEmbeddingProvider().embed(["same text"])[0]
    assert provider.embed(["same text"])[0] != FakeEmbeddingProvider(model_revision="2").embed(["same text"])[0]


def test_batch_and_response_validation_errors_are_stable():
    provider = FakeEmbeddingProvider()
    with pytest.raises(EmbeddingError, match="embedding_batch_too_large"):
        provider.embed(["x"] * 33)
    with pytest.raises(EmbeddingError, match="embedding_invalid_request"):
        provider.embed(["   "])
    with pytest.raises(EmbeddingError, match="embedding_text_too_long"):
        provider.embed(["x" * 12001])
    with pytest.raises(EmbeddingError, match="embedding_invalid_request"):
        provider.embed([1])  # type: ignore[list-item]


def test_embedding_registry_capability_is_safe_and_separate():
    payload = EmbeddingProviderRegistry("fake").capabilities()
    assert payload["runtime_kind"] == "deterministic_demo"
    assert payload["network_required"] is False
    assert payload["supports"] == {"embeddings": True, "batch": True}
    assert "key" not in str(payload).lower()
    assert EmbeddingProviderRegistry(None).capabilities()["error_code"] == "embedding_provider_not_configured"


def test_identity_and_stale_semantics_are_stable():
    identity = EmbeddingIdentity("chunk-1", "rev-1", embedding_content_hash("hello"),
                                 "fake", "fake-embedding-v1", "1", 2)
    row = {"status": "ready", "chunk_id": "chunk-1", "source_revision": "rev-1",
           "content_hash": identity.content_hash, "provider_id": "fake", "model_id": "fake-embedding-v1",
           "model_revision": "1", "dimensions": 2, "vector_encoding": "f32le_v1",
           "vector_payload": encode_vector([1.0, 0.0])}
    assert embedding_staleness(row, expected_identity=identity) is None
    assert embedding_staleness({**row, "model_revision": "2"}, expected_identity=identity) == "embedding_model_revision_stale"
    assert embedding_staleness(row, expected_identity=identity, payload_valid=False) == "embedding_payload_invalid"
    assert embedding_staleness(row, expected_identity=identity, source_state="deleted") == "embedding_source_deleted"


def test_codec_rejects_corrupt_and_nonfinite_vectors():
    with pytest.raises(EmbeddingError, match="embedding_payload_length_mismatch"):
        decode_vector(b"bad", 2)
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([0.0, 0.0])
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([float("nan")])
    with pytest.raises(EmbeddingError, match="embedding_encoding_unsupported"):
        encode_vector([1.0], encoding="unknown_v1")
    with pytest.raises(EmbeddingError, match="embedding_payload_length_mismatch"):
        decode_vector(encode_vector([1.0, 0.0]) + b"x", 2)
    with pytest.raises(EmbeddingError, match="embedding_encoding_unsupported"):
        decode_vector(encode_vector([1.0]), 1, encoding="unknown_v1")
