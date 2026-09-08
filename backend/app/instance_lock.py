"""实例锁 - 保证每个数据根目录只被一个进程占用。

本模块提供跨平台的咨询锁（advisory lock），防止多个
StudyBuddy 进程同时使用同一个 data_root。

锁机制：
- Windows: msvcrt.locking (LK_NBLCK 非阻塞锁)
- POSIX: fcntl.flock (LOCK_EX | LOCK_NB)
- 锁文件: data_root/.lock（内容为标识文本）

双层保护：
1. 进程内防重入：类级 _process_paths 集合跟踪已锁路径
2. 进程间互斥：操作系统文件锁

锁文件内容：
- 首次创建时写入 'studybuddy-instance-lock\n'
- 已有内容则不覆盖（保留诊断信息）

使用方式：
    lock = InstanceLock(data_root / '.lock')
    try:
        lock.acquire()
        # ... 应用运行 ...
    finally:
        lock.release()
    
    # 或使用上下文管理器
    with InstanceLock(data_root / '.lock'):
        # ... 应用运行 ...

异常：
- data_root_in_use: 已被其他进程（或本进程其他位置）占用
- data_root_lock_unavailable: 无法创建锁文件

注意：
- 支持上下文管理器协议（with 语句）
- 重复 acquire 是幂等的（已持锁则直接返回）
- release 后可重新 acquire
"""
from __future__ import annotations

import os
import threading
from pathlib import Path


class InstanceLockError(RuntimeError):
    """实例锁错误 - 数据根目录已被其他进程占用。"""


class InstanceLock:
    """跨平台咨询锁 - 保证每个数据根目录一个 StudyBuddy 进程。
    
    使用操作系统文件锁实现进程间互斥，配合进程内集合
    防止同进程重复加锁。
    
    Args:
        path: 锁文件路径（通常为 data_root/.lock）
    
    用法:
        with InstanceLock(path):
            ...  # 持锁运行
    """

    _process_guard = threading.Lock()
    _process_paths: set[str] = set()

    def __init__(self, path: Path):
        self.path = Path(path)
        self._key = str(self.path.absolute())
        self._handle = None
        self._locked = False

    def acquire(self) -> None:
        """获取实例锁（幂等）。
        
        执行流程：
        1. 进程内检查（防重入）
        2. 创建锁文件（a+b 模式，不截断）
        3. 首次写入标识文本
        4. 获取操作系统文件锁（非阻塞）
        
        Raises:
            InstanceLockError: 已被占用或锁文件不可用时
        """
        if self._handle is not None:
            return
        with self._process_guard:
            if self._key in self._process_paths:
                raise InstanceLockError("data_root_in_use")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle = self.path.open("a+b")
            except (OSError, IOError):
                raise InstanceLockError("data_root_lock_unavailable") from None
            try:
                handle.seek(0)
                if handle.tell() == 0:
                    handle.write(b"studybuddy-instance-lock\n")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                try:
                    handle.close()
                except OSError:
                    pass
                raise InstanceLockError("data_root_in_use") from None
            self._handle = handle
            self._locked = True
            self._process_paths.add(self._key)

    def release(self) -> None:
        """释放实例锁（幂等，未持锁时为空操作）。"""
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (OSError, IOError):
            pass
        finally:
            try:
                handle.close()
            except OSError:
                pass
            with self._process_guard:
                self._process_paths.discard(self._key)
            self._locked = False

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.release()
