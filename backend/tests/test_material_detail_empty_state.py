from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest


class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inline = False
        self.scripts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inline = not dict(attrs).get("src")

    def handle_endtag(self, tag):
        if tag == "script":
            self.inline = False

    def handle_data(self, data):
        if self.inline:
            self.scripts.append(data)


@pytest.mark.parametrize("search", ["", "?material=", "?citation=synthetic"])
def test_missing_material_id_finishes_empty_state_without_api_calls(search):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for frontend empty-state regression")
    parser = InlineScripts()
    parser.feed(
        (Path(__file__).parents[1] / "app/static/material-detail.html").read_text(
            encoding="utf-8"
        )
    )
    script = """
const vm = require('vm');
const nodes = new Map();
function element() {
  return {
    textContent: 'loading', hidden: true, disabled: false, children: [],
    href: '/app/qa.html',
    replaceChildren(...children) {
      this.children = children;
      this.textContent = children.map(child => child.textContent || '').join('');
    },
    append(...children) { this.children.push(...children); },
    removeAttribute(name) { delete this[name]; },
  };
}
const document = {
  querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, element());
    return nodes.get(selector);
  },
  createElement: element,
  addEventListener() {},
};
let apiCalls = 0;
const context = {
  document, URLSearchParams, location: {search: SEARCH},
  sbApi: {
    setPageScope() { return {signal: undefined}; },
    json() { apiCalls += 1; throw new Error('Unexpected request'); },
  },
};
vm.createContext(context);
for (const source of SCRIPTS) vm.runInContext(source, context);
const snapshot = Object.fromEntries(nodes);
process.stdout.write(JSON.stringify({apiCalls, snapshot}));
"""
    script = (
        "const SEARCH = " + json.dumps(search) + ";\n"
        "const SCRIPTS = " + json.dumps(parser.scripts) + ";\n" + script
    )
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True,
        encoding="utf-8", check=True, timeout=10
    )
    data = json.loads(result.stdout)
    nodes = data["snapshot"]
    assert data["apiCalls"] == 0
    assert nodes["#title"]["textContent"] == "缺少材料标识"
    assert nodes["#content"]["textContent"] == "请先从资料库选择一份材料。"
    assert nodes["#body"]["textContent"] == "需要先选择材料。"
    assert "href" not in nodes["#qa"]
    assert not nodes["#action-hint"]["hidden"]
    for selector in ("#index", "#queue-index", "#export-original", "#export-text",
                     "#refresh-page", "#refresh-candidates"):
        assert nodes[selector]["disabled"]
    for selector in ("#stage-import", "#stage-parse", "#stage-index",
                     "#candidate-status", "#link-status"):
        assert nodes[selector]["textContent"] == "需要先选择材料。"
