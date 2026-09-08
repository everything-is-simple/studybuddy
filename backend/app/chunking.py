"""文本分块 - 边界感知的滑动窗口分块策略。

本模块将长文本分割为重叠的分块，用于 Embedding 索引和检索。
分块策略优先在句子边界（\n, 空格）处切分，避免截断完整语义。

分块策略：
- boundary_window: 边界感知的滑动窗口
- 默认分块大小：800 token
- 默认重叠：80 token
- Token 计数：\w+ 正则匹配（粗略估计）

边界优先级：
1. \n（换行）
2. 空格
3. \t（制表符）
4. 强制截断（无边界时）

源范围跟踪：
- SourceSpan: 源文档中的语义单元（如段落、标题）
- 每个分块记录与其重叠的源范围
- 用于引用源和上下文追溯

分块结果（ChunkDraft）：
- chunk_index: 分块索引
- text: 原始文本
- normalized_text: 标准化文本（用于去重）
- start_offset, end_offset: 在原文中的位置
- token_count_estimate: Token 数估计
- overlap_before, overlap_after: 与前后分块的重叠
- span_overlaps: 与源范围的重叠

示例：
    text = "...长文本..."
    spans = [
        SourceSpan(id='p1', ordinal=0, kind='paragraph', label='段落1', text='...')
    ]
    chunks = chunk_text(text, spans, chunk_size=800, overlap=80)
    for chunk in chunks:
        print(f"分块 {chunk.chunk_index}: {len(chunk.text)} 字符")
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 80
CHUNKING_STRATEGY = "boundary_window"
CHUNKING_VERSION = "1.0.0"


@dataclass(frozen=True)
class SourceSpan:
    """源文档中的语义范围（如段落、标题、列表项）。
    
    Attributes:
        id: 范围 ID
        ordinal: 顺序号（用于排序）
        kind: 类型（如 'paragraph', 'heading'）
        label: 人类可读标签
        text: 范围文本内容
    """
    id: str
    ordinal: int
    kind: str
    label: str
    text: str


@dataclass(frozen=True)
class ChunkDraft:
    """分块草稿 - 包含文本、位置和源范围重叠信息。
    
    Attributes:
        chunk_index: 分块索引（从 0 开始）
        text: 原始分块文本
        normalized_text: 标准化文本（合并空白 + casefold）
        start_offset: 在原文中的起始位置
        end_offset: 在原文中的结束位置
        token_count_estimate: Token 数估计
        overlap_before: 与前一分块的重叠
        overlap_after: 与后一分块的重叠
        span_overlaps: 与源范围的重叠（span_id, start, end）
    """
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
    """粗略估计 Token 数（\w+ 正则匹配）。"""
    return len(re.findall(r"\w+|[^\W\d_]", text, flags=re.UNICODE))


def _normalized(text: str) -> str:
    """标准化文本（合并空白 + casefold）。"""
    return " ".join(text.split()).casefold()


def _boundary(text: str, start: int, end: int) -> int:
    """查找最佳分割边界（优先\n > 空格 > \t）。
    
    在 [minimum, end) 范围内反向搜索边界，确保至少切掉一半。
    
    Args:
        text: 原始文本
        start: 当前分块起始位置
        end: 请求的结束位置
    
    Returns:
        实际分割位置（在边界之后）
    """
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
    """将文本分割为重叠的分块（边界感知的滑动窗口）。
    
    Args:
        text: 原始文本
        spans: 源范围列表（可选）
        chunk_size: 分块大小（token 数，默认 800）
        overlap: 重叠大小（token 数，默认 80）
        strategy: 分块策略（默认 'boundary_window'）
        version: 分块版本（默认 '1.0.0'）
    
    Returns:
        分块草稿列表
    
    Raises:
        ValueError: 参数无效时（chunk_size < 1 或 overlap >= chunk_size）
    
    注意:
        - 空文本返回空列表
        - 分块优先在 \n, 空格, \t 处切分
        - 每个分块记录与源范围的重叠
    """
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
