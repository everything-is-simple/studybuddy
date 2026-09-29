from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "scenario",
    ["selection", "retry", "empty", "presets", "manual", "invalid", "review"],
)
def test_parent_actual_script_selection_and_minutes_controls(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for parent controls regression")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const nodes = new Map();
function element(attrs = {}) {
  const classes = new Set((attrs.class || '').split(' ').filter(Boolean));
  return {
    hidden: false, disabled: false, value: '', textContent: '', dataset: {},
    listeners: {}, attrs: {...attrs}, focused: false,
    classList: {
      toggle(name, enabled) {
        if (enabled) classes.add(name); else classes.delete(name);
        return enabled;
      },
      contains(name) {return classes.has(name);},
    },
    addEventListener(type, handler) {this.listeners[type] = handler;},
    setAttribute(name, value) {this.attrs[name] = value;},
    focus() {this.focused = true;},
  };
}
for (const id of ['home', 'wizard', 'success', 'status', 'material', 'minutes',
                 'review-material', 'review-minutes', 'create', 'step-material',
                 'step-time', 'step-review', 'start-planning', 'cancel',
                 'material-next', 'time-back', 'time-next', 'review-back',
                 'new-plan']) nodes.set('#parent-' + id, element());
for (const id of ['1', '2', '3']) nodes.set('#wizard-progress-' + id, element());
nodes.get('#parent-wizard').hidden = true;
nodes.get('#parent-success').hidden = true;
nodes.get('#parent-minutes').value = '20';
const buttons = ['15', '20', '30'].map(value => {
  const button = element({class: 'minute-option' + (value === '20' ? ' selected' : '')});
  button.dataset.minutes = value;
  return button;
});
class Option {
  constructor(label, value) {this.textContent = label; this.value = value; this.selected = false;}
}
const select = nodes.get('#parent-material');
select.children = [];
Object.defineProperty(select, 'firstChild', {get() {return this.children[0];}});
Object.defineProperty(select, 'value', {
  get() {return this.children.find(option => option.selected)?.value || '';},
  set(value) {this.children.forEach(option => {option.selected = option.value === value;});},
});
select.replaceChildren = function (...options) {
  this.children = options;
  if (options.length) options[0].selected = true;
};
select.append = function (option) {
  if (!this.children.length) option.selected = true;
  this.children.push(option);
};
select.insertBefore = function (option, before) {
  this.children.splice(this.children.indexOf(before), 0, option);
};
const calls = [];
let failLoad = process.argv[2] === 'retry';
const materials = process.argv[2] === 'empty'
  ? [{id: 'removed', original_name: 'Removed', deleted_at: 'synthetic'}]
  : [{id: 'synthetic-a', original_name: 'Synthetic A'},
     {id: 'synthetic-b', original_name: 'Synthetic B'}];
const context = {
  document: {
    querySelector: selector => nodes.get(selector),
    querySelectorAll: selector => selector === '.minute-option' ? buttons : [],
  },
  Option, Intl, Date,
  sbApi: {
    setPageScope() {return {signal: undefined};},
    async json(url, options = {}) {
      calls.push({url, method: options.method || 'GET'});
      if (options.method && options.method !== 'GET') throw Error('Unexpected write');
      if (failLoad) throw Error('Synthetic loading failure');
      return {items: materials};
    },
  },
  sbUi: {
    errorAction(node, reason, options) {
      node.textContent = 'Synthetic loading failure';
      node.retry = options.retry;
    },
  },
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const click = id => nodes.get('#parent-' + id).listeners.click();
const field = nodes.get('#parent-minutes');
function fill(value, event = 'input') {
  field.value = value;
  if (field.listeners[event]) field.listeners[event]();
}
function snapshot() {
  return {
    material: select.value, materialDisabled: select.disabled,
    status: nodes.get('#parent-status').textContent,
    steps: ['material', 'time', 'review'].map(step => !nodes.get('#parent-step-' + step).hidden),
    minutes: field.value,
    presets: buttons.map(button => ({
      value: button.dataset.minutes,
      selected: button.classList.contains('selected'),
      pressed: button.attrs['aria-pressed'],
    })),
    reviewMinutes: nodes.get('#parent-review-minutes').textContent,
    reviewMaterial: nodes.get('#parent-review-material').textContent,
    homeVisible: !nodes.get('#parent-home').hidden,
    wizardVisible: !nodes.get('#parent-wizard').hidden,
  };
}
(async () => {
  click('start-planning');
  await new Promise(resolve => setImmediate(resolve));
  const snapshots = [];
  if (process.argv[2] === 'retry') {
    snapshots.push(snapshot());
    failLoad = false;
    await nodes.get('#parent-status').retry();
    snapshots.push(snapshot());
    click('material-next');
    snapshots.push(snapshot());
  } else if (['selection', 'empty'].includes(process.argv[2])) {
    snapshots.push(snapshot());
    click('material-next');
    snapshots.push(snapshot());
  } else {
    select.value = 'synthetic-b';
    click('material-next');
    snapshots.push(snapshot());
    if (process.argv[2] === 'presets') {
      for (const button of buttons) {button.listeners.click(); snapshots.push(snapshot());}
    } else if (process.argv[2] === 'manual') {
      buttons[0].listeners.click();
      for (const value of ['30', '25', '20', '']) {
        fill(value); snapshots.push(snapshot());
      }
      fill('15', 'change'); snapshots.push(snapshot());
    } else if (process.argv[2] === 'invalid') {
      for (const value of ['4', '241', '5.5', '']) {
        fill(value); click('time-next'); snapshots.push(snapshot());
      }
    } else {
      for (const value of ['5', '240']) {
        fill(value); click('time-next'); snapshots.push(snapshot());
        click('review-back'); snapshots.push(snapshot());
      }
      click('time-back'); snapshots.push(snapshot());
      click('cancel'); snapshots.push(snapshot());
    }
  }
  process.stdout.write(JSON.stringify({snapshots, calls}));
})().catch(error => {console.error(error.message); process.exitCode = 1;});
"""
    result = subprocess.run(
        [
            node,
            "-e",
            script,
            str(Path(__file__).parents[1] / "app/static/js/parent.js"),
            scenario,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    )
    data = json.loads(result.stdout)
    snapshots = data["snapshots"]
    assert all(call["method"] == "GET" for call in data["calls"])
    assert len(data["calls"]) == (2 if scenario == "retry" else 1)
    if scenario in ("selection", "retry", "empty"):
        assert snapshots[-2]["material"] == ""
        assert snapshots[-1]["steps"] == [True, False, False]
        assert snapshots[-1]["status"] == "请先选择一份教材。"
        assert snapshots[-2]["materialDisabled"] == (scenario == "empty")
    else:
        assert snapshots[0]["steps"] == [False, True, False]
        assert snapshots[0]["material"] == "synthetic-b"
        if scenario in ("presets", "manual"):
            for snapshot in snapshots:
                expected = [
                    button["value"] for button in snapshot["presets"]
                    if button["value"] == snapshot["minutes"]
                ]
                actual = [
                    button["value"] for button in snapshot["presets"]
                    if button["selected"]
                ]
                assert actual == expected
            for snapshot in snapshots:
                assert all(
                    button["pressed"] == str(button["selected"]).lower()
                    for button in snapshot["presets"]
                )
        elif scenario == "invalid":
            assert len(snapshots) == 5
            for snapshot in snapshots[1:]:
                assert snapshot["steps"] == [False, True, False]
                assert snapshot["status"] == "请输入 5 到 240 之间的学习分钟数。"
        else:
            for index, value in ((1, "5"), (3, "240")):
                assert snapshots[index]["steps"] == [False, False, True]
                assert snapshots[index]["reviewMinutes"] == f"{value} 分钟"
                assert snapshots[index]["reviewMaterial"] == "Synthetic B"
                assert snapshots[index + 1]["steps"] == [False, True, False]
                assert snapshots[index + 1]["minutes"] == value
            assert snapshots[-2]["steps"] == [True, False, False]
            assert snapshots[-1]["homeVisible"]
            assert not snapshots[-1]["wizardVisible"]
