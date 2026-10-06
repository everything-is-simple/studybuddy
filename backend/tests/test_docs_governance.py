"""文档治理的结构化校验。

只校验结构和不变量，不锁定文档原句：
- docs/capabilities.json 是唯一能力状态源：字段齐全、状态词合法、引用的代码/测试/文档存在。
- 当前有效文档（README、AGENTS、docs 下除 archive/legacy 外）中的相对链接全部可解析。
- docs/00-INDEX.md 列出每一份当前有效文档，不留孤儿。
- 网络边界：服务默认只监听回环地址，示例与脚本不出现 0.0.0.0。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
MANIFEST = DOCS / "capabilities.json"
HISTORICAL_DIRS = ("archive", "legacy-product-references")
REQUIRED_FIELDS = ("id", "name", "doc", "implementation", "verification", "code", "tests", "evidence", "gaps")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _current_docs() -> list[Path]:
    docs = [p for p in DOCS.rglob("*.md") if not any(part in HISTORICAL_DIRS for part in p.relative_to(DOCS).parts)]
    return [ROOT / "README.md", ROOT / "AGENTS.md", *docs]


def test_manifest_entries_have_required_fields_and_legal_status_words() -> None:
    data = _manifest()
    vocab = data["status_vocabulary"]
    ids = [c["id"] for c in data["capabilities"]]
    assert len(ids) == len(set(ids)), "capability id 重复"
    for cap in data["capabilities"]:
        missing = [f for f in REQUIRED_FIELDS if f not in cap]
        assert not missing, f"{cap.get('id')} 缺少字段 {missing}"
        assert cap["implementation"] in vocab["implementation"], cap["id"]
        assert cap["verification"] in vocab["verification"], cap["id"]
        # real-pass 必须有本次真实证据；partial/not_implemented 必须写明缺口
        if cap["verification"] == "real-pass":
            assert cap["evidence"], f"{cap['id']} 标 real-pass 但没有证据"
        if cap["implementation"] != "implemented":
            assert cap["gaps"], f"{cap['id']} 未完成但没有列出缺口"


def test_manifest_paths_exist() -> None:
    missing: list[str] = []
    for cap in _manifest()["capabilities"]:
        if not (DOCS / cap["doc"]).is_file():
            missing.append(f"{cap['id']}: doc {cap['doc']}")
        for rel in [*cap["code"], *cap["tests"]]:
            if not (ROOT / rel).is_file():
                missing.append(f"{cap['id']}: {rel}")
    assert not missing, "清单引用了不存在的文件:\n" + "\n".join(missing)


def test_current_docs_relative_links_resolve() -> None:
    broken: list[str] = []
    for doc in _current_docs():
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if re.match(r"^(https?:|mailto:|#|computer:|file:)", target):
                continue
            path = unquote(target.split("#", 1)[0])
            if path and not (doc.parent / path).exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not broken, "失效链接:\n" + "\n".join(broken)


def test_index_lists_every_current_doc() -> None:
    index = (DOCS / "00-INDEX.md").read_text(encoding="utf-8")
    linked = {unquote(t.split("#", 1)[0]) for t in LINK.findall(index)}
    orphans = []
    for doc in _current_docs():
        if doc.parent == ROOT or doc.name == "00-INDEX.md":
            continue
        rel = doc.relative_to(DOCS).as_posix()
        if rel not in linked:
            orphans.append(rel)
    assert not orphans, "00-INDEX.md 未收录:\n" + "\n".join(orphans)


def test_service_binds_loopback_only() -> None:
    config = (ROOT / "backend/app/config.py").read_text(encoding="utf-8")
    assert 'DEFAULT_HOST = "127.0.0.1"' in config
    offenders = []
    for path in [*(ROOT / "backend/app").rglob("*.py"), *(ROOT / "backend/scripts").rglob("*.ps1")]:
        if "0.0.0.0" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, "出现 0.0.0.0:\n" + "\n".join(offenders)
