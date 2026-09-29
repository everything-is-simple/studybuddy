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
        self.inline = tag == "script" and not dict(attrs).get("src")

    def handle_endtag(self, tag):
        if tag == "script":
            self.inline = False

    def handle_data(self, data):
        if self.inline:
            self.scripts.append(data)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        ([2026, 8, 29], ["2026-09-29", "2026-09-23", "2026-09-01", "2026-09-30"]),
        ([2026, 0, 1], ["2026-01-01", "2025-12-26", "2026-01-01", "2026-01-02"]),
        ([2026, 11, 31], ["2026-12-31", "2026-12-25", "2026-12-01", "2027-01-01"]),
        ([2028, 1, 29], ["2028-02-29", "2028-02-23", "2028-02-01", "2028-03-01"]),
    ],
)
def test_quick_period_includes_today_with_exclusive_end(today, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for frontend date-logic regression")
    parser = InlineScripts()
    parser.feed(
        (Path(__file__).parents[1] / "app/static/reports.html").read_text(encoding="utf-8")
    )
    source = next(script for script in parser.scripts if "function setQuickPeriod(" in script)
    # Exercise the actual page functions without loading or writing formal data.
    functions = source[
        source.index("function formatDate("):source.index("function setInitialPeriod(")
    ]
    script = f"""
const vm = require('vm');
const today = {json.dumps(today)};
const RealDate = Date;
const context = {{
  Date: class extends RealDate {{
    constructor(...args) {{ super(...(args.length ? args : [...today, 12])); }}
  }},
  createStart: {{value: ''}}, createEnd: {{value: ''}}
}};
vm.createContext(context);
vm.runInContext({json.dumps(functions)}, context);
const result = ['today', 'week', 'month'].map(kind => {{
  context.setQuickPeriod(kind);
  return [context.createStart.value, context.createEnd.value];
}});
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, timeout=10
    )
    periods = json.loads(result.stdout)
    assert periods == [[start, expected[3]] for start in expected[:3]]
    assert all(start < end for start, end in periods)
