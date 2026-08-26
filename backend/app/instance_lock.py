from __future__ import annotations

import os
import threading
from pathlib import Path


class InstanceLockError(RuntimeError):
    """The configured data root is already owned by another process."""


class InstanceLock:
    """Cross-platform advisory lock for one StudyBuddy process per data root."""

    _process_guard = threading.Lock()
    _process_paths: set[str] = set()

    def __init__(self, path: Path):
        self.path = Path(path)
        self._key = str(self.path.absolute())
        self._handle = None
        self._locked = False

    def acquire(self) -> None:
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
