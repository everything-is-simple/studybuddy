"""HTTP 辅助函数 - 下载命名和原始文件安全校验。

本模块提供 HTTP 层使用的辅助函数：
- 下载文件名构造（防注入）
- 原始文件路径校验（路径逃逸防护 + 哈希验证）
- 重命名输入验证

安全设计：
- _download_name: 仅取文件名部分，双引号转单引号
- _checked_original_path:
  - 必须是绝对路径
  - 必须在 originals_root 内（逐级检查符号链接）
  - 必须是普通文件（非链接、非目录）
  - SHA-256 哈希必须匹配预期值
- _rename_name: 长度限制 + 文件名合法性验证

错误响应：
- 500 original_path_invalid: 路径不安全（服务端数据问题）
- 500 original_not_found: 文件缺失或类型不对
- 500 original_hash_mismatch: 内容被篡改或损坏

注意：
- 这些函数处理的是服务端存储的数据，500 而非 4xx
- 哈希验证每次下载都执行（防篡改）
"""
from __future__ import annotations

import stat
from pathlib import Path

from fastapi import HTTPException

from .storage import sha256_file
from .services.imports import _valid_filename

def _download_name(original_name: str, suffix: str = "") -> str:
    """构造安全的下载文件名（Content-Disposition 用）。
    
    Args:
        original_name: 原始文件名
        suffix: 可选后缀（如 '.txt'）
    
    Returns:
        安全的文件名（仅文件名部分，引号已转义）
    """
    safe_name = Path(original_name).name.replace('"', "'")
    return f"{safe_name}{suffix}"

def _checked_original_path(config: AppConfig, stored_path: str, expected_hash: str) -> Path:
    """校验并返回原始文件路径（路径安全 + 哈希验证）。
    
    校验项：
    - 绝对路径
    - 在 originals_root 内
    - 逐级目录无符号链接
    - 普通文件（非链接、非目录）
    - SHA-256 匹配预期值
    
    Args:
        config: 应用配置（提供 originals_root）
        stored_path: 数据库中存储的绝对路径
        expected_hash: 预期 SHA-256 哈希
    
    Returns:
        验证通过的文件路径
    
    Raises:
        HTTPException: 路径不安全、文件缺失或哈希不匹配时
    """
    root = config.originals_root
    target = Path(stored_path)
    if not target.is_absolute():
        raise HTTPException(status_code=500, detail="original_path_invalid")
    try:
        root_stat = root.lstat()
        if not root.is_dir() or root.is_symlink():
            raise HTTPException(status_code=500, detail="original_path_invalid")
        target.relative_to(root)
        current = root
        for part in target.relative_to(root).parts:
            current = current / part
            if current.is_symlink():
                raise HTTPException(status_code=500, detail="original_path_invalid")
            current.lstat()
    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="original_path_invalid") from exc
    try:
        mode = target.lstat().st_mode
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    import stat
    if not stat.S_ISREG(mode):
        raise HTTPException(status_code=500, detail="original_not_found")
    try:
        actual_hash = sha256_file(target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="original_not_found") from exc
    if actual_hash != expected_hash:
        raise HTTPException(status_code=500, detail="original_hash_mismatch")
    return target

def _rename_name(raw_name: str) -> str | None:
    """验证重命名输入（长度 + 文件名合法性）。
    
    Args:
        raw_name: 用户输入的新名称
    
    Returns:
        验证通过的名称，无效时返回 None
    """
    name = raw_name.strip()
    if len(name) > 255:
        return None
    return _valid_filename(name)
