from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("scenario", ["initial", "switch", "traversal", "repeat", "stale_load"])
def test_buddy_actual_script_keeps_route_and_frame_lifecycle_aligned(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for frontend routing regression")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const nodes = new Map();
let clones = 0;
function element(attrs = {}) {
  return {
    attrs: {...attrs}, dataset: {}, textContent: '', hidden: false, listeners: {},
    classList: {remove() {}, toggle() {return false;}},
    getAttribute(key) {return this.attrs[key] ?? null;},
    setAttribute(key, value) {this.attrs[key] = value;},
    addEventListener(type, handler) {this.listeners[type] = handler;},
    cloneNode() {clones++; return element(this.attrs);},
    replaceWith(next) {nodes.set('#buddy-frame', next);},
  };
}
for (const id of ['#buddy-frame', '#buddy-status', '#buddy-fallback-link',
                  '#buddy-navigation']) nodes.set(id, element());
const links = ['today', 'student', 'parent'].map(view => {
  const link = element();
  link.dataset.view = view;
  return link;
});
const switches = ['student', 'parent'].map(view => {
  const button = element();
  button.dataset.switchView = view;
  return button;
});
const document = {
  querySelector: id => nodes.get(id),
  querySelectorAll: selector => ({
    '[data-view]': links, '[data-switch-view]': switches,
    '[data-management-link]': [links[0]],
  })[selector] || [],
};
const entries = ['today'];
let cursor = 0;
const location = {search: '?view=today'};
const history = {
  replaceState(state) {entries[cursor] = state.view; location.search = '?view=' + state.view;},
  pushState(state) {
    entries.splice(cursor + 1);
    entries.push(state.view);
    cursor++;
    location.search = '?view=' + state.view;
  },
};
const storage = new Map();
const events = {};
const context = {
  document, location, history, URLSearchParams,
  localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)},
  window: {addEventListener: (type, handler) => {events[type] = handler;}},
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const frame = () => nodes.get('#buddy-frame');
const finish = () => frame().listeners.load({currentTarget: frame()});
const switchTo = view => switches.find(button => button.dataset.switchView === view).listeners.click();
function traverse(delta) {
  cursor += delta;
  location.search = '?view=' + entries[cursor];
  events.popstate();
}
function snapshot() {
  return {
    view: location.search, src: frame().getAttribute('src'),
    status: nodes.get('#buddy-status').textContent,
    label: nodes.get('#buddy-fallback-link').textContent,
    href: nodes.get('#buddy-fallback-link').href,
    pressed: switches.map(button => button.getAttribute('aria-pressed')),
    current: links.map(link => link.getAttribute('aria-current')),
  };
}
const snapshots = [];
finish();
if (process.argv[2] === 'initial') {
  snapshots.push(snapshot());
} else if (process.argv[2] === 'switch') {
  for (const view of ['student', 'parent']) {
    switchTo(view); finish(); snapshots.push(snapshot());
  }
} else if (process.argv[2] === 'traversal') {
  switchTo('student'); finish();
  switchTo('parent'); finish();
  for (const delta of [-1, -1, 1, 1]) {
    traverse(delta); finish(); snapshots.push(snapshot());
  }
} else if (process.argv[2] === 'repeat') {
  switchTo('student'); finish();
  const original = frame();
  switchTo('student');
  snapshots.push({...snapshot(), sameFrame: frame() === original, entries: entries.length});
} else {
  switchTo('student'); finish();
  const retired = frame();
  switchTo('parent');
  retired.listeners.load({currentTarget: retired});
  snapshots.push(snapshot());
  finish();
  snapshots.push(snapshot());
}
process.stdout.write(JSON.stringify({snapshots, clones}));
"""
    result = subprocess.run(
        [node, "-e", script,
         str(Path(__file__).parents[1] / "app/static/js/buddy-spa.js"), scenario],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=10,
    )
    result_data = json.loads(result.stdout)
    expected = {
        "initial": ["today"],
        "switch": ["student", "parent"],
        "traversal": ["student", "today", "student", "parent"],
        "repeat": ["student"],
        "stale_load": ["parent", "parent"],
    }[scenario]
    labels = {"today": "今天", "student": "学生", "parent": "家长"}
    for index, (snapshot, view) in enumerate(zip(result_data["snapshots"], expected, strict=True)):
        label = labels[view]
        assert snapshot["view"] == f"?view={view}"
        assert snapshot["src"] == snapshot["href"] == f"/app/{view}.html"
        assert snapshot["label"] == f"直接打开{label}页面"
        assert snapshot["pressed"] == [str(view == mode).lower() for mode in ("student", "parent")]
        assert snapshot["current"] == ["page" if view == mode else "false"
                                       for mode in ("today", "student", "parent")]
        expected_status = f"{label}页面已打开"
        if scenario == "stale_load" and index == 0:
            expected_status = f"正在打开{label}页面…"
        assert snapshot["status"] == expected_status
    if scenario == "repeat":
        assert result_data["snapshots"][0]["sameFrame"]
        assert result_data["snapshots"][0]["entries"] == 2
        assert result_data["clones"] == 2
