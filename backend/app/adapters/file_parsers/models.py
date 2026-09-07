"""文件解析结果数据模型。

本模块定义文件解析的输入选项和输出结果结构。

核心模型：
- ParseOptions: 解析选项配置（文件大小限制、压缩比等）
- ParseResult: 解析结果，包含文本、片段、警告和错误
- TextSpan: 文本片段（页面、幻灯片等）的位置和内容

状态类型：
- success: 解析成功
- empty: 文件为空或无文本内容
- rejected: 文件被拒绝（如格式不支持）
- failed: 解析失败
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["success", "empty", "rejected", "failed"]
SpanKind = Literal["document", "page", "slide"]
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024


class ParseOptions(BaseModel):
    """解析选项配置。
    
    Attributes:
        max_bytes: 文件最大字节数（默认 50 MiB）
        max_zip_members: ZIP 文件最大成员数（默认 256）
        max_uncompressed_bytes: 解压后最大字节数（默认 50 MiB）
        max_compression_ratio: 最大压缩比（默认 1000.0）
    
    Note:
        此模型为 frozen，创建后不可修改。
    """
    model_config = ConfigDict(frozen=True)
    max_bytes: int = Field(default=DEFAULT_MAX_FILE_BYTES, ge=1)
    max_zip_members: int = Field(default=256, ge=1)
    max_uncompressed_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_compression_ratio: float = Field(default=1000.0, gt=0)


class TextSpan(BaseModel):
    """文本片段定位信息。
    
    Attributes:
        ordinal: 片段序号（从 1 开始）
        kind: 片段类型（"document", "page", "slide"）
        label: 片段标签（如 "Page 1", "Slide 3"）
        text: 片段文本内容
    """
    ordinal: int = Field(ge=1)
    kind: SpanKind
    label: str
    text: str


class ParseResult(BaseModel):
    """文件解析结果。
    
    Attributes:
        source_name: 源文件名
        source_suffix: 源文件扩展名（如 ".pdf"）
        source_sha256: 源文件 SHA256 哈希
        parser_id: 解析器标识（如 "pypdf2", "docx"）
        parser_version: 解析器版本号
        status: 解析状态（"success", "empty", "rejected", "failed"）
        text: 提取的完整文本
        spans: 文本片段列表（按页面/幻灯片分割）
        warnings: 警告信息列表
        error_code: 错误代码（当 status="failed" 时）
        elapsed_ms: 解析耗时（毫秒）
    """
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
