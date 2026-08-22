from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Protocol

EMBEDDING_ENCODING = "f32le_v1"
MAX_EMBEDDING_BATCH = 32
MAX_EMBEDDING_TEXT_CHARS = 12000
MAX_EMBEDDING_DIMENSIONS = 4096

class EmbeddingError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def normalize_embedding_text(text: str) -> str:
    return " ".join(text.split())


def embedding_content_hash(text: str) -> str:
    return hashlib.sha256(normalize_embedding_text(text).encode("utf-8")).hexdigest()


def encode_vector(values: list[float] | tuple[float, ...]) -> bytes:
    if not values or len(values) > MAX_EMBEDDING_DIMENSIONS:
        raise EmbeddingError("embedding_invalid_vector")
    checked = []
    for value in values:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise EmbeddingError("embedding_invalid_vector")
        checked.append(float(value))
    if not any(value != 0.0 for value in checked):
        raise EmbeddingError("embedding_invalid_vector")
    return struct.pack("<" + "f" * len(checked), *checked)


def decode_vector(payload: bytes, dimensions: int) -> list[float]:
    if not isinstance(dimensions, int) or dimensions <= 0 or dimensions > MAX_EMBEDDING_DIMENSIONS:
        raise EmbeddingError("embedding_invalid_dimensions")
    if not isinstance(payload, (bytes, bytearray)) or len(payload) != dimensions * 4:
        raise EmbeddingError("embedding_payload_length_mismatch")
    try:
        values = list(struct.unpack("<" + "f" * dimensions, bytes(payload)))
    except struct.error:
        raise EmbeddingError("embedding_payload_invalid") from None
    if not values or not all(math.isfinite(value) for value in values) or not any(value != 0.0 for value in values):
        raise EmbeddingError("embedding_invalid_vector")
    return values


@dataclass(frozen=True)
class FakeEmbeddingProvider:
    provider_id: str = "fake"
    model_id: str = "fake-embedding-v1"
    model_revision: str = "1"
    dimensions: int = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        if len(texts) > MAX_EMBEDDING_BATCH:
            raise EmbeddingError("embedding_batch_too_large")
        result = []
        for text in texts:
            normalized = normalize_embedding_text(text)
            if not normalized or len(normalized) > MAX_EMBEDDING_TEXT_CHARS:
                raise EmbeddingError("embedding_invalid_request")
            digest = hashlib.sha256(("studybuddy-fake-embedding-v1\x1f" + normalized).encode("utf-8")).digest()
            values = []
            for index in range(self.dimensions):
                block = hashlib.sha256(digest + index.to_bytes(2, "little")).digest()
                values.append((int.from_bytes(block[:4], "little") / 2147483647.5) - 1.0)
            result.append(values)
        return result


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left or not all(math.isfinite(x) for x in left + right):
        raise EmbeddingError("embedding_invalid_vector")
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    if denominator == 0:
        raise EmbeddingError("embedding_invalid_vector")
    return sum(a*b for a, b in zip(left, right)) / denominator
