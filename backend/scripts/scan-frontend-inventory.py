#!/usr/bin/env python3
"""Frontend inventory scanner.

Scans the formal static frontend and the browser test suite to produce a
fact-based inventory: which pages exist, what shared assets they load,
which API endpoints they call, and which browser specs exercise them.

Read-only. Writes two artifacts under docs/:
  - frontend-inventory-scan.md    (human report)
  - frontend-inventory-scan.json  (machine readable)
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "backend" / "app" / "static"
TESTS_DIR = ROOT / "backend" / "tests"
API_DIR = ROOT / "backend" / "app" / "api"
DOCS_DIR = ROOT / "docs"

CSS_REF = re.compile(r'<link[^>]+href=["\']([^"\']+\.css)["\']', re.I)
JS_REF = re.compile(r'<script[^>]+src=["\']([^"\']+\.js)["\']', re.I)
INLINE_STYLE = re.compile(r"<style[\s>]", re.I)
SCRIPT_BLOCK = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)

# A quoted "/api/..." literal, plus the machinery to follow `+ expr + '/more'` chains.
API_LITERAL = re.compile(r"""(['\"`])(/api/[^'\"`\s]*)\1""")
JS_EXPR = r"(?:[A-Za-z_$][\w$.]*\s*\([^()]*\)|[A-Za-z_$][\w$.]*)"
CONCAT_SEGMENT = re.compile(rf"""\s*\+\s*{JS_EXPR}\s*\+\s*(['\"`])([^'\"`]*)\1""")
CONCAT_TAIL = re.compile(rf"\s*\+\s*{JS_EXPR}")
DIRECT_FETCH = re.compile(r"\bfetch\s*\(")
# Backend route declarations live on the app object in backend/app/api/*.py.
BACKEND_ROUTE = re.compile(r"@app\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)")
# Page reference in specs: /app/<name>.html, or a bare '<name>.html' literal
PAGE_REF = re.compile(r"/app/([a-z0-9-]+\.html)")
BARE_PAGE_REF = re.compile(r"['\"`]([a-z0-9-]+\.html)['\"`?]")
LEGACY_REF = re.compile(r"\$\{BASE\}/legacy|['\"`]/legacy")
# Static outbound page links written in HTML (shell.js injects the shared nav separately).
PAGE_LINK = re.compile(r'href=["\']/app/([a-z0-9-]+\.html)')
BUTTON = re.compile(r"<button([^>]*)>(.*?)</button>", re.I | re.S)
FORM_CONTROL = re.compile(r"<(input|select|textarea|form)([^>]*)>", re.I)
ID_ATTR = re.compile(r'id=["\']([^"\']+)')
TAG_STRIP = re.compile(r"<[^>]+>")

# Trailing fragments produced by string concatenation, e.g. '/api/materials/' + id
TRAILING_JUNK = re.compile(r"[/&=]+$")
INTERPOLATION = re.compile(r"\$\{[^}]*\}")


def normalize_endpoint(raw: str) -> str:
    """Collapse interpolation and concatenation artifacts into a stable key."""
    endpoint = INTERPOLATION.sub("{id}", raw)
    endpoint, _, query = endpoint.partition("?")
    endpoint = re.sub(r"/+", "/", endpoint)
    endpoint = TRAILING_JUNK.sub("", endpoint)
    if query:
        endpoint += "?<query>"
    return endpoint or raw


def extract_endpoints(source: str) -> set[str]:
    """Collect endpoints, following `'/api/x/' + id + '/y'` concatenation chains."""
    endpoints: set[str] = set()
    for match in API_LITERAL.finditer(source):
        path = match.group(2)
        cursor = match.end()
        while True:
            segment = CONCAT_SEGMENT.match(source, cursor)
            if segment:
                path += "{id}" + segment.group(2)
                cursor = segment.end()
                continue
            tail = CONCAT_TAIL.match(source, cursor)
            if tail and path.endswith("/"):
                path += "{id}"
                cursor = tail.end()
            break
        endpoints.add(normalize_endpoint(path))
    return endpoints


def scan_controls(text: str) -> dict:
    """Collect the page's declared interactive surface: buttons and form controls."""
    buttons = []
    for attrs, label in BUTTON.findall(text):
        ident = ID_ATTR.search(attrs)
        clean = " ".join(TAG_STRIP.sub(" ", label).split())
        buttons.append({"id": ident.group(1) if ident else "", "label": clean})
    controls = defaultdict(list)
    for tag, attrs in FORM_CONTROL.findall(text):
        ident = ID_ATTR.search(attrs)
        if ident:
            controls[tag.lower()].append(ident.group(1))
    return {"buttons": buttons, "form_controls": {k: sorted(v) for k, v in controls.items()}}


def scan_pages() -> dict:
    pages = {}
    for html in sorted(STATIC_DIR.glob("*.html")):
        text = html.read_text(encoding="utf-8")
        inline_blocks = SCRIPT_BLOCK.findall(text)
        inline_source = "\n".join(inline_blocks)
        pages[html.name] = {
            "css": CSS_REF.findall(text),
            "js": JS_REF.findall(text),
            "inline_style": bool(INLINE_STYLE.search(text)),
            "inline_script_blocks": len(inline_blocks),
            "inline_script_bytes": len(inline_source.encode("utf-8")),
            "direct_fetch": len(DIRECT_FETCH.findall(inline_source)),
            "api_endpoints": sorted(extract_endpoints(inline_source)),
            "page_links": sorted({p for p in PAGE_LINK.findall(text) if p != html.name}),
            **scan_controls(text),
        }
    return pages


def scan_shared_modules() -> dict:
    modules = {}
    for asset in sorted(STATIC_DIR.glob("js/*.js")) + sorted(STATIC_DIR.glob("css/*.css")):
        text = asset.read_text(encoding="utf-8")
        rel = asset.relative_to(STATIC_DIR).as_posix()
        entry = {"bytes": len(text.encode("utf-8"))}
        if asset.suffix == ".js":
            entry["api_endpoints"] = sorted(extract_endpoints(text))
            entry["direct_fetch"] = len(DIRECT_FETCH.findall(text))
        modules[rel] = entry
    return modules


def route_key(url: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", url.split("?")[0]).rstrip("/") or "/"


def placeholder_match(called: str, route: str) -> bool:
    """Segment-wise match where either side may hold a `{id}` placeholder.

    A page that builds `'/api/study/plans/' + id + '/' + action` collapses the
    trailing action into a placeholder, so an exact key comparison would wrongly
    report `POST /api/study/plans/{id}/activate` as unreached.
    """
    left, right = called.split("/"), route.split("/")
    if len(left) != len(right):
        return False
    return all(a == b or a == "{id}" or b == "{id}" for a, b in zip(left, right))


def classify_routes(routes: list[dict], called: set[str]) -> dict[str, str]:
    """Label each route path `direct`, `dynamic` or `unreached`."""
    labels: dict[str, str] = {}
    for route in routes:
        key = route["key"]
        if key in labels and labels[key] == "direct":
            continue
        if key in called:
            labels[key] = "direct"
        elif any(placeholder_match(c, key) for c in called):
            labels[key] = "dynamic"
        else:
            labels[key] = "unreached"
    return labels


def scan_backend_routes() -> list[dict]:
    routes = []
    for module in sorted(API_DIR.glob("*.py")):
        if module.name == "__init__.py":
            continue
        for method, url in BACKEND_ROUTE.findall(module.read_text(encoding="utf-8")):
            if not url.startswith("/api/"):
                continue
            routes.append(
                {
                    "method": method.upper(),
                    "path": url,
                    "key": route_key(url),
                    "module": module.name,
                }
            )
    return routes


def scan_specs(known_pages: set[str]) -> dict:
    specs = {}
    for spec in sorted(TESTS_DIR.glob("browser*.spec.js")):
        text = spec.read_text(encoding="utf-8")
        pages = set(PAGE_REF.findall(text))
        # Specs that build URLs like `${BASE}/app/${name}` list page names separately.
        pages |= {p for p in BARE_PAGE_REF.findall(text) if p in known_pages}
        specs[spec.name] = {
            "pages": sorted(pages),
            "legacy_only": bool(LEGACY_REF.search(text)) and not pages,
            "bytes": len(text.encode("utf-8")),
        }
    return specs


def build_report(pages: dict, modules: dict, specs: dict, routes: list[dict]) -> str:
    page_to_specs: dict[str, list[str]] = defaultdict(list)
    for name, info in specs.items():
        for page in info["pages"]:
            page_to_specs[page].append(name)

    endpoint_to_callers: dict[str, set[str]] = defaultdict(set)
    for name, info in pages.items():
        for endpoint in info["api_endpoints"]:
            endpoint_to_callers[endpoint].add(name)
    for name, info in modules.items():
        for endpoint in info.get("api_endpoints", []):
            endpoint_to_callers[endpoint].add(name)

    lines: list[str] = []
    add = lines.append

    add("# 前端盘点自动扫描结果")
    add("")
    add("> 由 `backend/scripts/scan-frontend-inventory.py` 生成。只读扫描，反映当前代码事实。")
    add("")
    add(f"- 静态页面：{len(pages)}")
    add(f"- 共享资源：{len(modules)}")
    add(f"- 浏览器 spec：{len(specs)}")
    add(f"- 去重后前端调用的 API 端点：{len(endpoint_to_callers)}")
    add(f"- 后端 `/api/*` 路由声明：{len(routes)}（去重路径 {len({r['key'] for r in routes})}）")
    add("")

    add("## 1. 页面资源与内联脚本")
    add("")
    add("| 页面 | CSS | JS | 内联 style | 内联 script 块 | 内联脚本体积 | 直接 fetch | API 数 | 覆盖 spec 数 |")
    add("|---|---|---|---|---:|---:|---:|---:|---:|")
    for name, info in pages.items():
        css = ", ".join(Path(p).name for p in info["css"]) or "无"
        js = ", ".join(Path(p).name for p in info["js"]) or "无"
        inline_style = "⚠️ 是" if info["inline_style"] else "否"
        fetch_cell = "⚠️ " + str(info["direct_fetch"]) if info["direct_fetch"] else "0"
        add(
            f"| {name} | {css} | {js} | {inline_style} | {info['inline_script_blocks']} | "
            f"{info['inline_script_bytes'] / 1024:.1f} KiB | {fetch_cell} | "
            f"{len(info['api_endpoints'])} | {len(page_to_specs.get(name, []))} |"
        )
    add("")

    add("## 2. 共享资源")
    add("")
    add("| 资源 | 体积 | API 数 | 直接 fetch |")
    add("|---|---:|---:|---:|")
    for name, info in modules.items():
        api_count = len(info.get("api_endpoints", []))
        fetch_count = info.get("direct_fetch", 0)
        add(f"| `{name}` | {info['bytes'] / 1024:.1f} KiB | {api_count} | {fetch_count} |")
    add("")

    add("## 3. API 端点 → 调用方")
    add("")
    add("| API 端点 | 调用方 |")
    add("|---|---|")
    for endpoint in sorted(endpoint_to_callers):
        callers = ", ".join(sorted(endpoint_to_callers[endpoint]))
        add(f"| `{endpoint}` | {callers} |")
    add("")

    add("## 4. 页面入口与控件清单")
    add("")
    add("`静态出口` 只算 HTML 里写死的 `/app/*.html` 链接；`shell.js` 注入的共享导航不计入。")
    add("")
    add("| 页面 | 静态出口 | 按钮数 | 具名按钮 | 表单控件 |")
    add("|---|---|---:|---|---|")
    for name, info in pages.items():
        links = ", ".join(info["page_links"]) or "无"
        named = [b for b in info["buttons"] if b["id"]]
        named_cell = "<br>".join(f"`#{b['id']}` {b['label']}" for b in named) or "无"
        form_cell = (
            "<br>".join(
                f"{tag}: {', '.join('`#' + i + '`' for i in ids)}"
                for tag, ids in sorted(info["form_controls"].items())
            )
            or "无"
        )
        add(f"| {name} | {links} | {len(info['buttons'])} | {named_cell} | {form_cell} |")
    add("")

    add("## 5. 页面 → 覆盖 spec")
    add("")
    add("| 页面 | spec 数 | spec |")
    add("|---|---:|---|")
    for name in pages:
        specs_for_page = sorted(page_to_specs.get(name, []))
        cell = ", ".join(specs_for_page) if specs_for_page else "**无**"
        add(f"| {name} | {len(specs_for_page)} | {cell} |")
    add("")

    uncovered = [name for name in pages if not page_to_specs.get(name)]
    add("## 6. 未被任何 spec 引用的页面")
    add("")
    if uncovered:
        for name in uncovered:
            add(f"- {name}")
    else:
        add("无。所有页面至少被一个 spec 引用。")
    add("")

    orphan_specs = [name for name, info in specs.items() if not info["pages"]]
    add("## 7. 未引用 `/app/*.html` 的 spec")
    add("")
    add("这些 spec 只测 API、契约、治理规则或旧 `/legacy` 入口，不访问正式页面。")
    add("")
    if orphan_specs:
        add("| spec | 仅测 /legacy |")
        add("|---|---|")
        for name in orphan_specs:
            add(f"| {name} | {'是' if specs[name]['legacy_only'] else '否'} |")
    else:
        add("无。")
    add("")

    called = {key.split("?")[0] for key in endpoint_to_callers}
    labels = classify_routes(routes, called)
    by_module: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for route in routes:
        label = labels[route["key"]]
        if label != "direct":
            by_module[route["module"]][label].append(f"{route['method']} {route['path']}")
    counts = {
        label: len([k for k, v in labels.items() if v == label])
        for label in ("direct", "dynamic", "unreached")
    }

    add("## 8. 后端路由覆盖分类")
    add("")
    add(f"- 去重路由路径：{len(labels)}")
    add(f"- `direct`（页面/共享模块出现字面调用）：{counts['direct']}")
    add(f"- `dynamic`（页面用变量拼最后一段，静态扫描无法判定具体动作）：{counts['dynamic']}")
    add(f"- `unreached`（未找到任何前端引用）：{counts['unreached']}")
    add("")
    add(
        "`dynamic` 不是结论，只是静态扫描的不确定项；`unreached` 也不等于能力缺失，"
        "部分是 `/legacy` 专用、运维/探活端点或按安全边界有意不暂开。逐项定性属于第二阶段设计合同。"
    )
    add("")
    add("| 后端模块 | dynamic | unreached | 路由 |")
    add("|---|---:|---:|---|")
    for module in sorted(by_module):
        groups = by_module[module]
        rows = []
        for label in ("dynamic", "unreached"):
            for item in sorted(set(groups.get(label, []))):
                rows.append(f"`{item}` — {label}")
        add(
            f"| `{module}` | {len(set(groups.get('dynamic', [])))} | "
            f"{len(set(groups.get('unreached', [])))} | {'<br>'.join(rows)} |"
        )
    add("")

    return "\n".join(lines) + "\n"


def main() -> None:
    pages = scan_pages()
    modules = scan_shared_modules()
    specs = scan_specs(set(pages))
    routes = scan_backend_routes()

    report = build_report(pages, modules, specs, routes)
    (DOCS_DIR / "frontend-inventory-scan.md").write_text(report, encoding="utf-8")
    (DOCS_DIR / "frontend-inventory-scan.json").write_text(
        json.dumps(
            {
                "pages": pages,
                "shared_modules": modules,
                "specs": specs,
                "backend_routes": routes,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    covered = sum(1 for info in specs.values() if info["pages"])
    called = {e.split("?")[0] for p in pages.values() for e in p["api_endpoints"]}
    called |= {e.split("?")[0] for m in modules.values() for e in m.get("api_endpoints", [])}
    labels = classify_routes(routes, called)
    unreached = len([k for k, v in labels.items() if v == "unreached"])
    dynamic = len([k for k, v in labels.items() if v == "dynamic"])
    print(
        f"pages={len(pages)} shared={len(modules)} specs={len(specs)} "
        f"specs_with_pages={covered} routes={len(routes)} "
        f"dynamic_route_paths={dynamic} unreached_route_paths={unreached}"
    )
    print("wrote docs/frontend-inventory-scan.md")
    print("wrote docs/frontend-inventory-scan.json")


if __name__ == "__main__":
    main()
