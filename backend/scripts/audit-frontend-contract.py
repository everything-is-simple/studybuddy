"""Static frontend contract audit for StudyBuddy's native pages."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "backend" / "app" / "static"
API = ROOT / "backend" / "app" / "api"
ROUTE_RE = re.compile(r'@app\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)')
URL_RE = re.compile(r"(?P<caller>sbApi\.(?:json|upload)|fetch)\(\s*[`\"'](?P<url>[^`\"']+)")
IGNORE_LEGACY_FIELDS = {"capture_session_id"}
OLD_FIELDS = ("capture_session_id",)
OLD_STATES = ("asset_uploaded", "created")
REQUIRED_RESOURCES = {"capture", "plan", "note", "practice", "report", "task"}

def normalize(url: str) -> str:
    url = url.split("?", 1)[0]
    url = re.sub(r"\$\{[^}]+\}", "{param}", url)
    url = re.sub(r"\+[^;,)]+", "{param}", url)
    return url.rstrip("/") or "/"

def route_matches(candidate: str, route: str) -> bool:
    a, b = normalize(candidate), normalize(route)
    if a == b:
        return True
    ap, bp = a.split("/"), b.split("/")
    if len(ap) != len(bp):
        return False
    return all(x == y or x.startswith("{") or y.startswith("{") for x, y in zip(ap, bp))

def routes() -> list[dict[str, str]]:
    result = []
    for path in API.glob("*.py"):
        if path.name == "__init__.py":
            continue
        for method, url in ROUTE_RE.findall(path.read_text(encoding="utf-8")):
            result.append({"method": method.upper(), "path": url, "file": path.as_posix()})
    return result

def audit() -> dict[str, object]:
    known = routes()
    route_paths = [r["path"] for r in known]
    pages = []
    findings = []
    for path in sorted(STATIC.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        calls = []
        for match in URL_RE.finditer(text):
            raw = match.group("url")
            caller = match.group("caller")
            if not raw.startswith("/api/"):
                continue
            calls.append({"raw": raw, "path": normalize(raw), "direct_fetch": caller == "fetch"})
        missing = sorted({c["path"] for c in calls if not any(route_matches(c["path"], p) for p in route_paths)})
        direct_fetch = [c["raw"] for c in calls if c["direct_fetch"]]
        writes = bool(re.search(r"method\s*:\s*['\"](?:POST|PUT|PATCH|DELETE)|sbApi\.upload", text, re.I))
        has_retry = bool(re.search(r"retry|重试|refresh|刷新", text, re.I))
        json_without_header = bool(re.search(r"fetch\([\s\S]{0,500}?body\s*:\s*JSON\.stringify", text, re.I) and not re.search(r"Content-Type['\"]?\s*:\s*['\"]application/json", text, re.I))
        page = {"page": path.name, "api_calls": sorted({c["path"] for c in calls}), "missing_routes": missing,
                "direct_fetch": sorted(set(direct_fetch)), "writes": writes, "has_retry_signal": has_retry,
                "json_without_content_type": json_without_header,
                "old_fields": sorted(set(x for x in OLD_FIELDS if x in text)),
                "old_states": sorted(set(x for x in OLD_STATES if re.search(rf"['\"]{re.escape(x)}['\"]", text)))}
        pages.append(page)
        for route in missing:
            findings.append({"kind": "missing_route", "page": path.name, "value": route})
        for call in direct_fetch:
            findings.append({"kind": "direct_fetch", "page": path.name, "value": call})
        for key in page["old_fields"]:
            if key not in IGNORE_LEGACY_FIELDS:
                findings.append({"kind": "legacy_field", "page": path.name, "value": key})
        for key in page["old_states"]:
            findings.append({"kind": "legacy_state", "page": path.name, "value": key})
        if json_without_header:
            findings.append({"kind": "json_without_content_type", "page": path.name, "value": "JSON.stringify without explicit Content-Type"})
        if writes and not has_retry:
            findings.append({"kind": "write_without_retry_signal", "page": path.name, "value": "no retry/refresh signal"})
    fixture_path = ROOT / "docs" / "frontend-contract-fixtures.json"
    if not fixture_path.exists():
        findings.append({"kind": "missing_contract_fixture", "page": "shared", "value": fixture_path.name})
    else:
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        missing_resources = sorted(REQUIRED_RESOURCES - set(fixtures.get("resources", {})))
        for resource in missing_resources:
            findings.append({"kind": "missing_contract_fixture_resource", "page": "shared", "value": resource})
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    token_css = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8") if (STATIC / "css" / "tokens.css").exists() else ""
    all_css = "\n".join(p.read_text(encoding="utf-8") for p in STATIC.rglob("*") if p.suffix in {".css", ".html"})
    defined = set(re.findall(r"--([\w-]+)\s*:", css + token_css))
    used = set(re.findall(r"var\(--([\w-]+)\)", all_css))
    undefined = sorted(used - defined)
    for token in undefined:
        findings.append({"kind": "undefined_css_token", "page": "shared", "value": token})
    return {"routes": known, "pages": pages, "findings": findings,
            "summary": {"page_count": len(pages), "route_count": len(known), "finding_count": len(findings),
                        "undefined_css_tokens": undefined}}

def markdown(data: dict[str, object]) -> str:
    summary = data["summary"]
    lines = ["# 前端契约自动审计报告", "", "> 此报告由 `backend/scripts/audit-frontend-contract.py` 生成；发现项是待修复或待确认事项，不是完成声明。", "",
             f"- 页面：{summary['page_count']}", f"- 后端路由：{summary['route_count']}", f"- 发现项：{summary['finding_count']}", ""]
    lines += ["## 发现项", "", "| 类型 | 页面 | 值 |", "|---|---|---|"]
    for item in data["findings"]:
        lines.append(f"| `{item['kind']}` | `{item['page']}` | `{item['value']}` |")
    if not data["findings"]:
        lines.append("| — | — | 未发现问题 |")
    lines += ["", "## 页面扫描", "", "| 页面 | API 数 | 直接 fetch | 写操作 | retry 信号 |", "|---|---:|---|---|---|"]
    for page in data["pages"]:
        lines.append(f"| `{page['page']}` | {len(page['api_calls'])} | {'是' if page['direct_fetch'] else '否'} | {'是' if page['writes'] else '否'} | {'是' if page['has_retry_signal'] else '否'} |")
    return "\n".join(lines) + "\n"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--strict", action="store_true", help="发现项存在时返回 1")
    args = parser.parse_args()
    data = audit()
    if args.write_report:
        (ROOT / "docs" / "frontend-contract-audit-report.md").write_text(markdown(data), encoding="utf-8")
    output = json.dumps(data, ensure_ascii=False, indent=2) if args.json else markdown(data)
    sys.stdout.buffer.write((output + "\n").encode('utf-8'))
    return 1 if args.strict and data["findings"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
