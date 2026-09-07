"""文件解析适配器模块。

本模块提供统一的文件解析接口，支持多种常见文档格式：
- 纯文本文件（.txt, .md, .markdown）
- PDF 文档（.pdf）
- Word 文档（.docx）
- PowerPoint 演示文稿（.pptx）

所有解析器都返回统一的 ParseResult 结构，包含：
- 文本内容和结构化 spans（页、段落、幻灯片等）
- 源文件 SHA-256 校验和
- 解析器版本和状态
- 警告和错误信息

Side Effects:
    - 读取文件内容并计算 SHA-256
    - 解压和验证 ZIP 容器（DOCX/PPTX）
    - 提取文本内容到内存
"""
from __future__ import annotations

import hashlib
import time
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from docx import Document
from pypdf import PdfReader

from .models import ParseOptions, ParseResult, Status, TextSpan

PARSER_VERSION = "1.0.0"
_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}


def _sha256(path: Path) -> str:
    """计算文件的 SHA-256 校验和。

    分块读取文件内容，避免大文件占用过多内存。

    Args:
        path: 文件路径

    Returns:
        十六进制格式的 SHA-256 校验和字符串
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _result(path: Path, digest: str, parser_id: str, started: float, **values: object) -> ParseResult:
    """构造标准解析结果对象。

    自动填充源文件元数据和计时信息。

    Args:
        path: 源文件路径
        digest: SHA-256 校验和
        parser_id: 解析器标识符（如 'formal-pdf'）
        started: 解析开始时间戳（perf_counter）
        **values: 其他 ParseResult 字段（status, text, spans 等）

    Returns:
        完整的 ParseResult 对象
    """
    return ParseResult(
        source_name=path.name,
        source_suffix=path.suffix.lower(),
        source_sha256=digest,
        parser_id=parser_id,
        parser_version=PARSER_VERSION,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        **values,
    )


def _failure(path: Path, digest: str, parser_id: str, started: float, code: str,
             warning: str = "", status: Status = "failed") -> ParseResult:
    """构造失败状态的解析结果。

    Args:
        path: 源文件路径
        digest: SHA-256 校验和（可能为空字符串）
        parser_id: 解析器标识符
        started: 解析开始时间戳
        code: 错误代码（如 'file_too_large', 'corrupt_pdf'）
        warning: 可选的警告消息（中文描述）
        status: 失败类型（'failed', 'rejected', 'empty'）

    Returns:
        包含错误信息的 ParseResult 对象
    """
    return _result(path, digest, parser_id, started, status=status, text="", spans=[],
                   warnings=[warning] if warning else [], error_code=code)


def _check_zip(path: Path, options: ParseOptions) -> None:
    """验证 ZIP 容器的安全性和资源限制。

    防御 ZIP 炸弹和过大文件攻击。检查项包括：
    - 成员数量限制
    - 解压后总大小限制
    - 单个成员大小限制
    - 压缩比限制（防止炸弹）
    - CRC 校验完整性

    Args:
        path: ZIP 文件路径
        options: 解析选项（包含各项限制阈值）

    Raises:
        ValueError: 当任一安全检查失败时，抛出包含错误代码的异常
    """
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > options.max_zip_members:
            raise ValueError("zip_member_limit")
        total = sum(member.file_size for member in members)
        if total > options.max_uncompressed_bytes:
            raise ValueError("zip_uncompressed_limit")
        for member in members:
            if member.file_size < 0 or member.compress_size < 0:
                raise ValueError("zip_invalid_size")
            if member.file_size > options.max_uncompressed_bytes:
                raise ValueError("zip_member_size_limit")
            if member.compress_size and member.file_size / member.compress_size > options.max_compression_ratio:
                raise ValueError("zip_compression_ratio_limit")
        if archive.testzip() is not None:
            raise ValueError("zip_crc_error")


def _parse_text(path: Path, digest: str, started: float) -> ParseResult:
    """解析纯文本文件。

    仅接受 UTF-8 编码的文本文件（.txt, .md, .markdown）。

    Args:
        path: 文件路径
        digest: SHA-256 校验和
        started: 解析开始时间戳

    Returns:
        ParseResult，包含完整文本内容和一个 document 类型的 span
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _failure(path, digest, "formal-text", started, "invalid_utf8", "仅接受 UTF-8 文本。")
    status: Status = "success" if text else "empty"
    spans = [] if not text else [TextSpan(ordinal=1, kind="document", label="document", text=text)]
    return _result(path, digest, "formal-text", started, status=status, text=text, spans=spans, warnings=[], error_code=None)


def parse_file(source_path: Path, declared_media_type: str | None = None,
               options: ParseOptions | None = None) -> ParseResult:
    """统一文件解析入口。

    根据文件扩展名分发到对应的解析器：
    - .txt/.md/.markdown → 纯文本解析器
    - .pdf → PDF 解析器（pypdf）
    - .docx → Word 解析器（python-docx）
    - .pptx → PowerPoint 解析器（ZIP + XML）
    - .rtf/.doc/.ppt → 明确拒绝（暂不支持）
    - 其他 → 不支持的格式

    Args:
        source_path: 源文件路径
        declared_media_type: 声明的 MIME 类型（当前未使用，保留扩展名分发）
        options: 可选的解析选项（文件大小限制、ZIP 限制等）

    Returns:
        ParseResult 对象，包含解析状态、文本内容、结构化 spans 和元数据

    Side Effects:
        - 读取文件内容
        - 计算 SHA-256 校验和
        - 解压 ZIP 容器（DOCX/PPTX）
    """
    del declared_media_type  # Extension remains the conservative dispatch boundary.
    started = time.perf_counter()
    options = options or ParseOptions()
    path = Path(source_path)
    try:
        if not path.is_file():
            return _failure(path, "", "formal-file-parsers", started, "source_not_found")
        size = path.stat().st_size
        digest = _sha256(path)
        if size > options.max_bytes:
            return _failure(path, digest, "formal-file-parsers", started, "file_too_large", "超过单文件大小限制。", "rejected")
        suffix = path.suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            return _parse_text(path, digest, started)
        if suffix == ".pdf":
            try:
                reader = PdfReader(str(path), strict=True)
                spans = [TextSpan(ordinal=i, kind="page", label=f"page-{i}", text=page.extract_text() or "")
                         for i, page in enumerate(reader.pages, 1)]
            except Exception:
                return _failure(path, digest, "formal-pdf", started, "corrupt_pdf")
            text = "\n\n".join(span.text for span in spans)
            status: Status = "success" if text.strip() else "empty"
            warnings = [] if status == "success" else ["PDF 没有可提取的文字层；本阶段不执行 OCR。"]
            return _result(path, digest, "formal-pdf", started, status=status, text=text, spans=spans,
                           warnings=warnings, error_code=None)
        if suffix == ".docx":
            try:
                _check_zip(path, options)
                paragraphs = [paragraph.text for paragraph in Document(str(path)).paragraphs]
            except ValueError as exc:
                return _failure(path, digest, "formal-docx", started, str(exc), "DOCX 容器超过资源限制。", "rejected")
            except Exception:
                return _failure(path, digest, "formal-docx", started, "corrupt_docx")
            text = "\n".join(paragraphs)
            status = "success" if text.strip() else "empty"
            spans = [] if status == "empty" else [TextSpan(ordinal=1, kind="document", label="document", text=text)]
            return _result(path, digest, "formal-docx", started, status=status, text=text, spans=spans,
                           warnings=["仅提取段落正文，复杂样式、文本框和嵌入对象未纳入本阶段契约。"], error_code=None)
        if suffix == ".pptx":
            try:
                _check_zip(path, options)
                with zipfile.ZipFile(path) as archive:
                    names = sorted((name for name in archive.namelist()
                                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
                                   key=lambda name: int(Path(name).stem.removeprefix("slide")))
                    if not names:
                        return _failure(path, digest, "formal-pptx", started, "no_slides", "没有可读取的幻灯片。", "empty")
                    spans = []
                    for ordinal, name in enumerate(names, 1):
                        root = ET.fromstring(archive.read(name))
                        slide_text = " ".join(node.text.strip() for node in root.iter()
                                              if node.tag.endswith("}t") and node.text and node.text.strip())
                        spans.append(TextSpan(ordinal=ordinal, kind="slide", label=f"slide-{ordinal}", text=slide_text))
            except ValueError as exc:
                return _failure(path, digest, "formal-pptx", started, str(exc), "PPTX 容器超过资源限制。", "rejected")
            except Exception:
                return _failure(path, digest, "formal-pptx", started, "corrupt_pptx")
            text = "\n\n".join(span.text for span in spans)
            return _result(path, digest, "formal-pptx", started, status="success" if text.strip() else "empty",
                           text=text, spans=spans, warnings=[], error_code=None)
        if suffix == ".rtf":
            return _failure(path, digest, "formal-file-parsers", started, "unsupported_rtf", "RTF 暂无可靠解析器，本阶段拒绝。", "rejected")
        if suffix in {".doc", ".ppt"}:
            return _failure(path, digest, "formal-file-parsers", started, "requires_converter", "旧格式需要受控转换器，本阶段拒绝。", "rejected")
        return _failure(path, digest, "formal-file-parsers", started, "unsupported_format", "不支持的文件格式。", "rejected")
    except OSError:
        return _failure(path, "", "formal-file-parsers", started, "source_unreadable")
    except Exception:
        return _failure(path, "", "formal-file-parsers", started, "parser_exception")
