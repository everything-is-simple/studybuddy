"""原始文件存储 - 基于内容哈希的原子存储。

本模块将原始文件存储到哈希派生路径下，实现内容寻址存储（CAS）。
相同内容的文件只存储一次，多个材料可共享同一原始文件。

存储结构：
{root}/
  {hash[:2]}/          # 前缀目录（减少单目录文件数）
    {hash[2:]}/        # 哈希目录
      original         # 原始文件

例如：
  hash = "abc123..."
  路径 = root/ab/c123.../original

原子性保证：
- 使用临时文件 + os.replace() 原子替换
- 写入后 fsync 确保持久化
- 已存在文件的哈希验证

安全性：
- 禁止符号链接（storage root 和目录）
- 验证文件类型（必须是普通文件）
- 验证哈希一致性（避免哈希冲突）
- original_name 防注入检查

错误处理：
- FileNotFoundError: 源文件不存在
- ValueError: 参数无效（哈希格式、文件名、哈希不匹配）
- OSError: 存储目录无效或操作失败

使用场景：
- 材料导入：保存上传的原始文件
- 去重：相同内容的文件自动共享
- 内容寻址：通过哈希直接定位文件

示例：
    source = Path('/tmp/upload.pdf')
    content_hash = sha256_file(source)
    stored = store_original(
        source_path=source,
        original_name='document.pdf',
        content_hash=content_hash,
        root=Path('/data/originals')
    )
    print(f"Stored at: {stored.path}")
    print(f"Created: {stored.created}")  # False 表示已存在
"""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredFile:
    """存储结果 - 包含路径和是否新建。
    
    Attributes:
        original_name: 原始文件名（用户上传的文件名）
        content_hash: SHA256 内容哈希
        path: 存储路径（root/{hash[:2]}/{hash[2:]}/original）
        created: True 表示新建，False 表示已存在
    """
    original_name: str
    content_hash: str
    path: Path
    created: bool


def store_original(source_path: Path, original_name: str, content_hash: str, root: Path) -> StoredFile:
    """将原始文件存储到哈希派生路径（原子替换）。
    
    存储路径：root/{hash[:2]}/{hash[2:]}/original
    
    操作流程：
    1. 验证参数（源文件、文件名、哈希）
    2. 检查存储目录安全性（禁止符号链接）
    3. 如果目标已存在：
       - 验证哈希一致性
       - 返回 created=False
    4. 如果不存在：
       - 写入临时文件
       - fsync 确保持久化
       - os.replace() 原子替换
       - 返回 created=True
    
    Args:
        source_path: 源文件路径
        original_name: 原始文件名（必须是简单文件名，不包含路径）
        content_hash: SHA256 哈希（64 位小写十六进制）
        root: 存储根目录
    
    Returns:
        StoredFile 实例
    
    Raises:
        FileNotFoundError: 源文件不存在
        ValueError: 参数无效或哈希不匹配
        OSError: 存储目录无效或操作失败
    
    注意:
        - 使用 os.replace() 保证原子性
        - 失败时自动清理临时文件
        - 已存在文件必须哈希匹配，否则抛出 ValueError
    """
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if Path(original_name).name != original_name or original_name in {"", ".", ".."}:
        raise ValueError("invalid_original_name")
    if len(content_hash) != 64 or any(char not in "0123456789abcdef" for char in content_hash.lower()):
        raise ValueError("invalid_content_hash")
    storage_root = Path(root)
    if storage_root.is_symlink():
        raise OSError("invalid storage root")
    prefix_dir = storage_root / content_hash[:2]
    target_dir = prefix_dir / content_hash[2:]
    try:
        if storage_root.exists() and not stat.S_ISDIR(storage_root.lstat().st_mode):
            raise OSError("invalid storage root")
        storage_root.mkdir(parents=True, exist_ok=True)
        if storage_root.is_symlink():
            raise OSError("invalid storage root")
        for directory in (prefix_dir, target_dir):
            if directory.is_symlink():
                raise OSError("invalid storage directory")
            try:
                mode = directory.lstat().st_mode
            except FileNotFoundError:
                directory.mkdir()
                mode = directory.lstat().st_mode
            if not stat.S_ISDIR(mode) or directory.is_symlink():
                raise OSError("invalid storage directory")
    except OSError:
        raise
    target = target_dir / "original"
    if target.is_symlink():
        raise OSError("invalid existing original")
    try:
        target_mode = target.lstat().st_mode
    except FileNotFoundError:
        target_mode = None
    if target_mode is not None:
        if not stat.S_ISREG(target_mode):
            raise OSError("invalid existing original")
        if sha256_file(target) != content_hash:
            raise ValueError("stored_hash_mismatch")
        return StoredFile(original_name=original_name, content_hash=content_hash, path=target, created=False)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".upload-", delete=False) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as input_file:
                while block := input_file.read(1024 * 1024):
                    handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return StoredFile(original_name=original_name, content_hash=content_hash, path=target, created=True)


def sha256_file(path: Path) -> str:
    """计算文件的 SHA256 哈希值（分块读取，支持大文件）。
    
    Args:
        path: 文件路径
    
    Returns:
        小写十六进制 SHA256 哈希
    
    Raises:
        OSError: 文件读取失败时
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
