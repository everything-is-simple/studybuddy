from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.embedding import FakeEmbeddingProvider, EmbeddingError, decode_vector, encode_vector, cosine_similarity

def test_fake_embedding_is_deterministic_and_codec_round_trips():
    provider = FakeEmbeddingProvider()
    first = provider.embed(["  hello   world "])[0]
    second = provider.embed(["hello world"])[0]
    assert first == second
    assert decode_vector(encode_vector(first), len(first)) == pytest.approx(first)
    assert cosine_similarity(first, first) == pytest.approx(1.0)

def test_codec_rejects_corrupt_and_nonfinite_vectors():
    with pytest.raises(EmbeddingError, match="embedding_payload_length_mismatch"):
        decode_vector(b"bad", 2)
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([0.0, 0.0])
    with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
        encode_vector([float("nan")])
