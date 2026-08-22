from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.embedding import (FakeEmbeddingProvider, EmbeddingError, decode_vector, encode_vector,
                           cosine_similarity, FAKE_EMBEDDING_ALGORITHM_VERSION)
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


def test_codec_rejects_corrupt_and_nonfinite_vectors():
    with pytest.raises(EmbeddingError, match="embedding_payload_length_mismatch"):
        decode_vector(b"bad", 2)
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([0.0, 0.0])
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([float("nan")])
