from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "晚上好！"),
        (4, "晚上好！"),
        (5, "早上好！"),
        (11, "早上好！"),
        (12, "下午好！"),
        (17, "下午好！"),
        (18, "晚上好！"),
        (23, "晚上好！"),
    ],
)
def test_student_actual_script_uses_local_time_for_greeting(hour, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for student greeting regression")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const nodes = new Map();
const calls = [];
const document = {
  querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, {
      hidden: false, textContent: selector === '#student-greeting' ? '\u65e9\u4e0a\u597d\uff01' : '',
      addEventListener() {},
    });
    return nodes.get(selector);
  },
};
document.querySelector('#student-greeting');
class LocalClock extends Date {
  constructor(...args) {
    if (args.length) super(...args);
    else super(2026, 8, 29, Number(process.argv[2]), 0, 0);
  }
}
const context = {
  document, Date: LocalClock, Intl,
  sbApi: {
    setPageScope() {return {signal: undefined};},
    async json(url, options = {}) {
      calls.push({url, method: options.method || 'GET'});
      return [];
    },
  },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
setImmediate(() => process.stdout.write(JSON.stringify({
  greeting: nodes.get('#student-greeting')?.textContent,
  date: nodes.get('#student-date').textContent,
  emptyVisible: !nodes.get('#student-empty').hidden,
  calls,
})));
"""
    result = subprocess.run(
        [
            node,
            "-e",
            script,
            str(Path(__file__).parents[1] / "app/static/js/student.js"),
            str(hour),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    )
    data = json.loads(result.stdout)
    assert data["greeting"] == expected
    assert data["date"] == "9月29日"
    assert data["emptyVisible"]
    assert data["calls"] == [{"url": "/api/study/plans", "method": "GET"}]
