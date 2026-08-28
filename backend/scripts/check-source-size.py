"""Enforce the StudyBuddy source-file size policy for changed files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
from pathlib import Path

MAX_BYTES = 32 * 1024
LEGACY_MAIN = Path("backend/app/main.py")
SOURCE_SUFFIXES = {".py", ".js", ".css", ".html", ".ps1", ".json", ".md"}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8")


def _base_size(root: Path, base: str, path: Path) -> int | None:
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-s", f"{base}:{path.as_posix()}"],
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return int(result.stdout) if result.returncode == 0 else None


def _changed_paths(root: Path, base: str) -> list[Path]:
    names = _git(root, "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD").splitlines()
    names += _git(root, "diff", "--name-only", "--diff-filter=AM").splitlines()
    return sorted({Path(name) for name in names})


def _main_html_sha256(path: Path) -> str | None:
    # INDEX_HTML is now loaded from templates/index.html
    template_path = path.parent / "templates" / "index.html"
    if not template_path.exists():
        return None
    content = template_path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check changed managed source-file size limits")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="origin/master")
    parser.add_argument("--main-html-sha256", default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    failures: list[str] = []
    for relative in _changed_paths(root, args.base):
        if relative.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        path = root / relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        baseline = _base_size(root, args.base, relative)
        if relative == LEGACY_MAIN:
            if baseline is not None and size > baseline:
                failures.append(f"{relative}: legacy exception must not grow ({size} > {baseline} bytes)")
            continue
        if baseline is None and size > MAX_BYTES:
            failures.append(f"{relative}: new file is {size} bytes; maximum is {MAX_BYTES}")
        elif baseline is not None and baseline > MAX_BYTES and size > baseline:
            failures.append(f"{relative}: legacy oversized file must not grow ({size} > {baseline} bytes)")
        elif baseline is not None and baseline <= MAX_BYTES and size > MAX_BYTES:
            failures.append(f"{relative}: grew to {size} bytes; maximum is {MAX_BYTES}")
    main_path = root / LEGACY_MAIN
    if args.main_html_sha256 and main_path.exists():
        digest = _main_html_sha256(main_path)
        if digest != args.main_html_sha256:
            failures.append("backend/app/main.py: legacy INDEX_HTML payload hash changed")
    if failures:
        print("source-size check failed:")
        print("\n".join(failures))
        return 1
    print(f"source-size check passed: changed managed files respect the {MAX_BYTES}-byte policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
