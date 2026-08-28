from __future__ import annotations

from __future__ import annotations
import hashlib
import json
import sqlite3
import stat
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from ..adapters.file_parsers.models import ParseResult
from ..chunking import CHUNKING_STRATEGY, CHUNKING_VERSION, SourceSpan, chunk_text
from ..embedding import (EMBEDDING_ENCODING, MAX_EMBEDDING_PAYLOAD_BYTES, EmbeddingError,
                         EmbeddingIdentity, EmbeddingProvider, cosine_similarity, decode_vector,
                         embedding_content_hash, embedding_staleness, encode_vector)
from ..import_locks import acquire_hash_lock, release_hash_lock
from ..migrations.runner import MigrationError, assert_schema_version, migrate
from ..providers import (CaptureProviderError, CaptureTranscriptionProvider,
                        CaptureTranscriptionRequest, LLMProvider, ProviderError,
                        ProviderRequest)
from ..storage import sha256_file, store_original
