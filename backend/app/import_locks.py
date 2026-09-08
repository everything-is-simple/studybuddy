"""导入哈希锁 - 按内容哈希的进程内互斥。

本模块为材料导入提供按 SHA-256 哈希的互斥锁，防止同进程内
多个请求并发导入相同内容（避免重复解析和存储竞争）。

实现方式：
- 引用计数式注册表：digest → (锁, 使用者数)
- 使用者归零且未持锁时从注册表移除（防泄漏）
- 注册表由全局锁保护

作用范围：
- 仅进程内有效（不跨进程）
- 跨进程互斥由 instance_lock 保证（单实例部署）

使用方式：
    lock = acquire_hash_lock(content_hash)
    try:
        # ... 导入处理 ...
    finally:
        release_hash_lock(content_hash, lock)

注意：
- acquire 返回锁对象（调用者负责成对释放）
- registry_size() 仅供测试，不通过 HTTP 暴露
"""
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class _Entry:
    lock: threading.Lock
    users: int = 0


_entries: dict[str, _Entry] = {}
_registry_guard = threading.Lock()


def acquire_hash_lock(digest: str) -> threading.Lock:
    """获取按 SHA-256 哈希的进程内锁（引用计数）。
    
    Args:
        digest: 内容哈希（SHA-256 十六进制）
    
    Returns:
        对应的锁对象（调用者负责成对释放）
    """
    with _registry_guard:
        entry = _entries.get(digest)
        if entry is None:
            entry = _Entry(threading.Lock())
            _entries[digest] = entry
        entry.users += 1
    entry.lock.acquire()
    return entry.lock


def release_hash_lock(digest: str, lock: threading.Lock) -> None:
    """释放哈希锁（引用计数归零时清理注册表）。
    
    Args:
        digest: 内容哈希
        lock: acquire_hash_lock 返回的锁对象
    """
    lock.release()
    with _registry_guard:
        entry = _entries.get(digest)
        if entry is not None:
            entry.users -= 1
            if entry.users == 0 and not entry.lock.locked():
                _entries.pop(digest, None)


def registry_size() -> int:
    """返回注册表大小（模块私有测试接口，不通过 HTTP 暴露）。"""
    with _registry_guard:
        return len(_entries)
