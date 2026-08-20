from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredFile:
    original_name: str
    content_hash: str
    path: Path
    created: bool


def store_original(source_path: Path, original_name: str, content_hash: str, root: Path) -> StoredFile:
    """Retain one original under a hash-derived path using an atomic replace."""
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if Path(original_name).name != original_name or original_name in {"", ".", ".."}:
        raise ValueError("invalid_original_name")
    if len(content_hash) != 64 or any(char not in "0123456789abcdef" for char in content_hash.lower()):
        raise ValueError("invalid_content_hash")
    target_dir = Path(root) / content_hash[:2] / content_hash[2:]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "original"
    if target.exists():
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
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
