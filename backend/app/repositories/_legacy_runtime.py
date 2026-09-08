"""Legacy 实现分片的共享运行时导入。

所有 _legacy_part_XX 分片通过 `from ._legacy_runtime import *`
获取它们所需的全部依赖，避免 18 个分片各自重复导入。

导入内容：
- 标准库: hashlib/json/sqlite3/stat/time/uuid/datetime/pathlib/zoneinfo
- 项目内: chunking/embedding/import_locks/migrations/providers/storage
- 适配器模型: ParseResult

注意：
- 本文件不含任何业务逻辑，仅是导入聚合
- 重构后此文件将随分片一起消亡
"""
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
