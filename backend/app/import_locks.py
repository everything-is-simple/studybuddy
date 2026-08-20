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
    """Acquire a per-SHA-256 lock for one application process only."""
    with _registry_guard:
        entry = _entries.get(digest)
        if entry is None:
            entry = _Entry(threading.Lock())
            _entries[digest] = entry
        entry.users += 1
    entry.lock.acquire()
    return entry.lock


def release_hash_lock(digest: str, lock: threading.Lock) -> None:
    lock.release()
    with _registry_guard:
        entry = _entries.get(digest)
        if entry is not None:
            entry.users -= 1
            if entry.users == 0 and not entry.lock.locked():
                _entries.pop(digest, None)


def registry_size() -> int:
    """Module-private test seam; not exposed through HTTP."""
    with _registry_guard:
        return len(_entries)
