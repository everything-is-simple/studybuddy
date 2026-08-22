from __future__ import annotations

import hashlib
import math
import re
import struct
from dataclasses import dataclass
from typing import Mapping, Protocol

EMBEDDING_ENCODING = "f32le_v1"
FAKE_EMBEDDING_PROVIDER_ID = "fake"
FAKE_EMBEDDING_MODEL_ID = "fake-embedding-v1"
FAKE_EMBEDDING_MODEL_REVISION = "1"
FAKE_EMBEDDING_ALGORITHM_VERSION = "sha256_bucket_v1"
MAX_EMBEDDING_BATCH = 32
MAX_EMBEDDING_TEXT_CHARS = 12000
MAX_EMBEDDING_DIMENSIONS = 4096
MAX_EMBEDDING_PAYLOAD_BYTES = MAX_EMBEDDING_DIMENSIONS * 4
_ID_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,255}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class EmbeddingError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EmbeddingIdentity:
    chunk_id: str
    source_revision: str
    content_hash: str
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    vector_encoding: str = EMBEDDING_ENCODING

    def validate(self) -> "EmbeddingIdentity":
        for value in (self.chunk_id, self.source_revision, self.provider_id, self.model_id,
                      self.model_revision, self.vector_encoding):
            if not isinstance(value, str) or not _ID_RE.fullmatch(value):
                raise EmbeddingError("embedding_invalid_identity")
        if not isinstance(self.content_hash, str) or not _HASH_RE.fullmatch(self.content_hash):
            raise EmbeddingError("embedding_invalid_identity")
        validate_dimensions(self.dimensions)
        if self.vector_encoding != EMBEDDING_ENCODING:
            raise EmbeddingError("embedding_encoding_unsupported")
        return self


class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    encoding: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def capabilities(self) -> dict[str, object]: ...


def normalize_embedding_text(text: str) -> str:
    if not isinstance(text, str):
        raise EmbeddingError("embedding_invalid_request")
    return " ".join(text.split())


def embedding_content_hash(text: str) -> str:
    return hashlib.sha256(normalize_embedding_text(text).encode("utf-8")).hexdigest()


def validate_dimensions(dimensions: object) -> int:
    if isinstance(dimensions, bool) or not isinstance(dimensions, int) or not 1 <= dimensions <= MAX_EMBEDDING_DIMENSIONS:
        raise EmbeddingError("embedding_invalid_dimensions")
    return dimensions


def _validate_limits(batch: object, dimensions: object) -> None:
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1 or batch > MAX_EMBEDDING_BATCH:
        raise EmbeddingError("embedding_batch_too_large")
    validate_dimensions(dimensions)


def _validate_vectors(vectors: object, count: int, dimensions: int) -> list[list[float]]:
    validate_dimensions(dimensions)
    if not isinstance(vectors, list) or len(vectors) != count:
        raise EmbeddingError("embedding_invalid_response")
    result: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise EmbeddingError("embedding_dimension_mismatch")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in vector):
            raise EmbeddingError("embedding_invalid_vector")
        values = [float(value) for value in vector]
        if not any(value != 0.0 for value in values):
            raise EmbeddingError("embedding_invalid_vector")
        result.append(values)
    return result


def encode_vector(values: list[float] | tuple[float, ...], *, encoding: str = EMBEDDING_ENCODING) -> bytes:
    if encoding != EMBEDDING_ENCODING:
        raise EmbeddingError("embedding_encoding_unsupported")
    if not isinstance(values, (list, tuple)) or not values:
        raise EmbeddingError("embedding_invalid_vector")
    dimensions = validate_dimensions(len(values))
    checked = _validate_vectors([list(values)], 1, dimensions)[0]
    try:
        payload = struct.pack("<" + "f" * dimensions, *checked)
    except (OverflowError, struct.error):
        raise EmbeddingError("embedding_invalid_vector") from None
    if len(payload) > MAX_EMBEDDING_PAYLOAD_BYTES:
        raise EmbeddingError("embedding_payload_too_large")
    return payload


def decode_vector(payload: bytes, dimensions: int, *, encoding: str = EMBEDDING_ENCODING) -> list[float]:
    if encoding != EMBEDDING_ENCODING:
        raise EmbeddingError("embedding_encoding_unsupported")
    dimensions = validate_dimensions(dimensions)
    if not isinstance(payload, (bytes, bytearray)):
        raise EmbeddingError("embedding_payload_invalid")
    expected = dimensions * 4
    if len(payload) > MAX_EMBEDDING_PAYLOAD_BYTES:
        raise EmbeddingError("embedding_payload_too_large")
    if len(payload) != expected:
        raise EmbeddingError("embedding_payload_length_mismatch")
    try:
        values = list(struct.unpack("<" + "f" * dimensions, bytes(payload)))
    except struct.error:
        raise EmbeddingError("embedding_payload_invalid") from None
    return _validate_vectors([values], 1, dimensions)[0]


def embedding_staleness(row: Mapping[str, object], *, expected_identity: EmbeddingIdentity,
                        payload_valid: bool | None = None, source_state: str = "ready") -> str | None:
    """Return a stable reason when an embedding must not be used for retrieval."""
    expected_identity.validate()
    if source_state == "missing":
        return "embedding_chunk_missing"
    if source_state == "deleted":
        return "embedding_source_deleted"
    if source_state == "not_current":
        return "embedding_source_not_current"
    if source_state != "ready":
        return "embedding_chunk_not_ready"
    if row.get("status") != "ready":
        return "embedding_status_unavailable"
    fields = (
        ("content_hash", "embedding_content_hash_stale"),
        ("source_revision", "embedding_source_revision_stale"),
        ("provider_id", "embedding_provider_stale"),
        ("model_id", "embedding_model_stale"),
        ("model_revision", "embedding_model_revision_stale"),
        ("dimensions", "embedding_dimensions_stale"),
        ("vector_encoding", "embedding_encoding_stale"),
    )
    for field, reason in fields:
        if row.get(field) != getattr(expected_identity, field):
            return reason
    if payload_valid is False or row.get("vector_payload") is None:
        return "embedding_payload_invalid" if payload_valid is False else "embedding_payload_missing"
    return None


@dataclass(frozen=True)
class FakeEmbeddingProvider:
    provider_id: str = FAKE_EMBEDDING_PROVIDER_ID
    model_id: str = FAKE_EMBEDDING_MODEL_ID
    model_revision: str = FAKE_EMBEDDING_MODEL_REVISION
    dimensions: int = 32
    encoding: str = EMBEDDING_ENCODING
    max_batch_size: int = MAX_EMBEDDING_BATCH
    max_text_chars: int = MAX_EMBEDDING_TEXT_CHARS

    def capabilities(self) -> dict[str, object]:
        return {
            "status": "demo", "configured": True, "runtime_kind": "deterministic_demo",
            "verification_status": "not_applicable", "network_required": False,
            "provider_id": self.provider_id, "model_id": self.model_id,
            "model_revision": self.model_revision, "dimensions": self.dimensions,
            "encoding": self.encoding, "algorithm_version": FAKE_EMBEDDING_ALGORITHM_VERSION,
            "limits": {"max_batch_size": MAX_EMBEDDING_BATCH, "max_text_chars": MAX_EMBEDDING_TEXT_CHARS,
                       "max_dimensions": MAX_EMBEDDING_DIMENSIONS, "max_response_bytes": 0},
            "supports": {"embeddings": True, "batch": True},
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or not texts:
            raise EmbeddingError("embedding_invalid_request")
        if isinstance(self.max_batch_size, bool) or not isinstance(self.max_batch_size, int) or len(texts) > self.max_batch_size:
            raise EmbeddingError("embedding_batch_too_large")
        _validate_limits(len(texts), self.dimensions)
        normalized_texts: list[str] = []
        for text in texts:
            normalized = normalize_embedding_text(text)
            if not normalized:
                raise EmbeddingError("embedding_invalid_request")
            if len(normalized) > self.max_text_chars:
                raise EmbeddingError("embedding_text_too_long")
            normalized_texts.append(normalized)
        result: list[list[float]] = []
        for normalized in normalized_texts:
            values = []
            for index in range(self.dimensions):
                seed = f"{FAKE_EMBEDDING_ALGORITHM_VERSION}\x1f{self.provider_id}\x1f{self.model_id}\x1f{self.model_revision}\x1f{normalized}\x1f{index}".encode("utf-8")
                block = hashlib.sha256(seed).digest()
                raw = int.from_bytes(block[:8], "little", signed=False)
                values.append((raw / 9223372036854775807.5) - 1.0)
            norm = math.sqrt(sum(value * value for value in values))
            result.append([value / norm for value in values])
        return _validate_vectors(result, len(texts), self.dimensions)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left or not all(math.isfinite(x) for x in left + right):
        raise EmbeddingError("embedding_invalid_vector")
    denominator = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    if denominator == 0:
        raise EmbeddingError("embedding_invalid_vector")
    return sum(a*b for a, b in zip(left, right)) / denominator
