"""SSL 上下文配置与 Windows 证书存储修复。

本模块处理 SSL/TLS 证书验证的边缘情况，特别是 Windows 系统证书存储损坏的问题。

问题背景：
某些 Windows 环境下，系统证书存储包含损坏的证书条目，导致 Python 的
ssl.create_default_context() 初始化失败并抛出 SSLError: NOT_ENOUGH_DATA。
这会导致所有 HTTPS 请求（如 OpenAI API 调用）失败。

解决方案：
本模块在导入时自动执行一次探测：
1. 尝试创建默认 SSL context
2. 如果失败且 certifi 包可用，切换到 certifi 的证书包
3. 通过 urllib 的 opener 机制全局生效

安全性：
此修复不会降低安全性，仅将证书来源从系统存储切换到 certifi 包，
仍然执行标准的 TLS 证书验证。

关联模块：
- providers._openai_llm: OpenAI API 调用依赖 HTTPS
- providers._openai_embedding: OpenAI Embedding API 调用

Note:
    此模块在导入时自动执行 _ensure_ssl_context()，无需手动调用。
"""

from __future__ import annotations

import ssl
from urllib.request import HTTPSHandler, build_opener, install_opener


def _ensure_ssl_context() -> None:
    """Windows 证书存储损坏时，用 certifi 的证书包兜底。

    某些 Windows 环境下系统证书存储包含坏条目，导致 Python ssl 默认 context
    初始化失败（SSLError: NOT_ENOUGH_DATA）。这里做一次探测：如果默认 context
    不可用且安装了 certifi，就切换到 certifi 的证书包。

    这不会修改任何安全语义，只是把证书来源从"系统存储"换成"certifi 包"，
    仍然是标准的 TLS 验证。
    """
    try:
        ssl.create_default_context()
        return  # 默认正常，什么都不做
    except ssl.SSLError:
        pass
    try:
        import certifi  # type: ignore
        ctx = ssl.create_default_context(cafile=certifi.where())
        install_opener(build_opener(HTTPSHandler(context=ctx)))
    except Exception:
        pass  # 没有 certifi 或其它问题，保持原状


_ensure_ssl_context()
