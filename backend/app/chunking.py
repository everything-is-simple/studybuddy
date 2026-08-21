from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 80
CHUNKING_STRATEGY = "boundary_window"
CHUNKING_VERSION = "1.0.0"


@dataclass(frozen=True)
class SourceSpan:
    id: str
    ordinal: int
    kind: str
    label: str
    text: str


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    text: str
    normalized_text: str
    start_offset: int
    end_offset: int
    token_count_estimate: int
    overlap_before: int
    overlap_after: int
    span_overlaps: tuple[tuple[str, int, int], ...]


def _token_count(text: str) -> int:
    return len(re.findall(r"\w+|[^\W\d_]", text, flags=re.UNICODE))


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _boundary(text: str, start: int, end: int) -> int:
    minimum = start + max(1, (end - start) // 2)
    candidates = [text.rfind(mark, minimum, end) for mark in ("\n", " ", "\t")]
    boundary = max(candidates)
    return boundary + 1 if boundary >= minimum else end


def _span_ranges(text: str, spans: list[SourceSpan]) -> list[tuple[SourceSpan, int, int]]:
    ranges: list[tuple[SourceSpan, int, int]] = []
    cursor = 0
    for span in sorted(spans, key=lambda item: (item.ordinal, item.id)):
        if not span.text:
            continue
        start = text.find(span.text, cursor)
        if start < 0:
            continue
        end = start + len(span.text)
        ranges.append((span, start, end))
        cursor = end
    return ranges


def chunk_text(text: str, spans: list[SourceSpan] | None = None, *,
               chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP,
               strategy: str = CHUNKING_STRATEGY,
               version: str = CHUNKING_VERSION) -> list[ChunkDraft]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("invalid_chunking_config")
    if not text:
        return []
    source_spans = _span_ranges(text, spans or [])
    drafts: list[ChunkDraft] = []
    start = 0
    index = 0
    while start < len(text):
        requested_end = min(len(text), start + chunk_size)
        end = requested_end if requested_end == len(text) else _boundary(text, start, requested_end)
        if end <= start:
            end = requested_end
        value = text[start:end]
        before = 0 if index == 0 else min(overlap, start)
        after = 0 if end == len(text) else min(overlap, len(text) - end)
        overlaps: list[tuple[str, int, int]] = []
        for span, span_start, span_end in source_spans:
            overlap_start = max(start, span_start)
            overlap_end = min(end, span_end)
            if overlap_start < overlap_end:
                overlaps.append((span.id, overlap_start, overlap_end))
        drafts.append(ChunkDraft(index, value, _normalized(value), start, end,
                                 _token_count(value), before, after, tuple(overlaps)))
        if end == len(text):
            break
        next_start = end - overlap
        start = next_start if next_start > start else start + 1
        index += 1
    return drafts
