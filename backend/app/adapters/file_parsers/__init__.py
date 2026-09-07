"""文件解析适配器模块。

本模块提供统一的文件解析接口，支持多种常见格式：
- PDF: 使用 PyPDF2 提取文本
- DOCX: 使用 python-docx 提取段落和表格
- TXT: 直接读取文本内容

主要组件：
- parse_file: 统一的文件解析函数
- ParseResult: 解析结果数据模型
- ParseOptions: 解析选项配置
- TextSpan: 文本片段定位信息
- PARSER_VERSION: 解析器版本号

使用示例：
    from app.adapters.file_parsers import parse_file
    result = parse_file("/path/to/file.pdf")
    print(result.text_content)
"""

from .adapter import PARSER_VERSION, parse_file
from .models import ParseOptions, ParseResult, TextSpan

__all__ = ["PARSER_VERSION", "ParseOptions", "ParseResult", "TextSpan", "parse_file"]
