"""Scan controlled runtime artifacts for known synthetic credential sentinels.

This scanner is intentionally scoped to operator-selected output roots. It never
reads or prints real credentials, and reports paths/counts only. Source files
containing test fixtures are handled by the separate governance tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

DEFAULT_SENTINELS = (
    "TEST_SECRET_DO_NOT_LEAK_7d0f",
    "TEST_SMTP_PASSWORD_DO_NOT_LEAK_29ce",
    "TEST_WEBHOOK_DO_NOT_LEAK_5a21",
)
MAX_SCAN_BYTES = 16 * 1024 * 1024
SKIP_NAMES = {".git", "__pycache__", "node_modules", "test-results", "playwright-report"}


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Yield regular files below roots without following links or known caches."""
    for root in roots:
        root = Path(root)
        if root.is_file() and not root.is_symlink():
            yield root
            continue
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            if any(part in SKIP_NAMES for part in path.parts):
                continue
            yield path


def scan_files(paths: Iterable[Path], sentinels: Iterable[str] = DEFAULT_SENTINELS) -> list[dict[str, object]]:
    """Return redacted findings for sentinel occurrences in bounded regular files."""
    needles = tuple(value for value in sentinels if isinstance(value, str) and value)
    findings: list[dict[str, object]] = []
    for path in paths:
        try:
            size = path.stat().st_size
            if size > MAX_SCAN_BYTES:
                continue
            data = path.read_bytes()
        except (OSError, ValueError):
            continue
        counts = {str(index): data.count(needle.encode("utf-8")) for index, needle in enumerate(needles)}
        total = sum(counts.values())
        if total:
            findings.append({"path": str(path), "match_count": total, "sentinel_indexes": [key for key, count in counts.items() if count]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan selected runtime artifacts for synthetic credential leaks.")
    parser.add_argument("roots", nargs="+", type=Path, help="runtime output roots or files to scan")
    parser.add_argument("--json", action="store_true", help="emit machine-readable redacted output")
    args = parser.parse_args()
    findings = scan_files(iter_files(args.roots))
    result = {"status": "leak_found" if findings else "clean", "files_scanned": "bounded", "findings": findings}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif findings:
        print("synthetic sentinel findings:")
        for finding in findings:
            print(f"- {finding['path']}: {finding['match_count']} match(es)")
    else:
        print("no synthetic sentinel findings")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
