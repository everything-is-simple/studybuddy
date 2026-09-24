"""稳定的连接、共享运行时和存储工具仓储出口。"""

from . import _legacy_part_00 as _part_00
from ._legacy_runtime import (
    annotations, hashlib, json, sqlite3, stat, time, uuid, Callable,
    date, datetime, timedelta, timezone, Path, ZoneInfo,
    ZoneInfoNotFoundError, ParseResult, CHUNKING_STRATEGY, CHUNKING_VERSION,
    SourceSpan, chunk_text, EMBEDDING_ENCODING, MAX_EMBEDDING_PAYLOAD_BYTES,
    EmbeddingError, EmbeddingIdentity, EmbeddingProvider, cosine_similarity,
    decode_vector, embedding_content_hash, embedding_staleness, encode_vector,
    acquire_hash_lock, release_hash_lock, MigrationError, assert_schema_version,
    migrate, CaptureProviderError, CaptureTranscriptionProvider,
    CaptureTranscriptionRequest, LLMProvider, ProviderError, ProviderRequest,
    sha256_file, store_original,
)

VALID_STATUSES = _part_00.VALID_STATUSES
connect = _part_00.connect
utc_now = _part_00.utc_now

__all__ = ['annotations', 'hashlib', 'json', 'sqlite3', 'stat', 'time', 'uuid', 'Callable', 'date', 'datetime', 'timedelta', 'timezone', 'Path', 'ZoneInfo', 'ZoneInfoNotFoundError', 'ParseResult', 'CHUNKING_STRATEGY', 'CHUNKING_VERSION', 'SourceSpan', 'chunk_text', 'EMBEDDING_ENCODING', 'MAX_EMBEDDING_PAYLOAD_BYTES', 'EmbeddingError', 'EmbeddingIdentity', 'EmbeddingProvider', 'cosine_similarity', 'decode_vector', 'embedding_content_hash', 'embedding_staleness', 'encode_vector', 'acquire_hash_lock', 'release_hash_lock', 'MigrationError', 'assert_schema_version', 'migrate', 'CaptureProviderError', 'CaptureTranscriptionProvider', 'CaptureTranscriptionRequest', 'LLMProvider', 'ProviderError', 'ProviderRequest', 'sha256_file', 'store_original', 'VALID_STATUSES', 'connect', 'utc_now']
