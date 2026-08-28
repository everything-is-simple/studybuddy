"""SSL context setup for Windows certificate store fallback."""

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
