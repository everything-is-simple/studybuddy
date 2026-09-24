"""Enforce the StudyBuddy source-file size policy for changed files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
from pathlib import Path

MAX_BYTES = 32 * 1024
LEGACY_MAIN = Path("backend/app/main.py")
# Documentation files (.md) are exempt; every managed source file is bounded.
SOURCE_SUFFIXES = {".py", ".js", ".css", ".html", ".ps1", ".json"}


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
    names += _git(root, "diff", "--cached", "--name-only", "--diff-filter=AM").splitlines()
    names += _git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({Path(name) for name in names})


def _main_html_sha256(path: Path) -> str | None:
    template_dir = path.parent / "templates"
    parts = [template_dir / "index_head.html"]
    parts.extend(sorted(template_dir.glob("index_script_*.js"), key=lambda item: item.name))
    parts.append(template_dir / "index_tail.html")
    if not all(part.exists() for part in parts):
        return None
    content = "".join(part.read_text(encoding="utf-8") for part in parts)
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
        if size > MAX_BYTES:
            failures.append(f"{relative}: file is {size} bytes; maximum is {MAX_BYTES}")
    main_path = root / LEGACY_MAIN
    if args.main_html_sha256 and main_path.exists():
        digest = _main_html_sha256(main_path)
        if digest != args.main_html_sha256:
            failures.append("backend/app/main.py: legacy INDEX_HTML payload hash changed")
    if failures:
        print("source-size check failed:")
        print("\n".join(failures))
        return 1
    print(f"source-size check passed: managed source files respect the {MAX_BYTES}-byte policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
