from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["success", "empty", "rejected", "failed"]
SpanKind = Literal["document", "page", "slide"]
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024


class ParseOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_bytes: int = Field(default=DEFAULT_MAX_FILE_BYTES, ge=1)
    max_zip_members: int = Field(default=256, ge=1)
    max_uncompressed_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_compression_ratio: float = Field(default=1000.0, gt=0)


class TextSpan(BaseModel):
    ordinal: int = Field(ge=1)
    kind: SpanKind
    label: str
    text: str


class ParseResult(BaseModel):
    source_name: str
    source_suffix: str
    source_sha256: str
    parser_id: str
    parser_version: str
    status: Status
    text: str
    spans: list[TextSpan]
    warnings: list[str]
    error_code: str | None = None
    elapsed_ms: float
