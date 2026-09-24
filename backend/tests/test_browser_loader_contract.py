from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOADER = ROOT / "backend" / "scripts" / "browser-source-loader.js"


def test_browser_loader_resolves_legacy_literals_from_injected_environment() -> None:
    source = """
module.exports = {
  python: 'C:/miniconda/py310/python.exe',
  backend: 'H:/studybuddy/backend',
  base: 'http://localhost:8787',
  run: `H:/studybuddy-test/runs/browser-${Date.now()}`,
  fixture: 'H:/studybuddy-test/fixtures/kaobuddy-foundation/sample.txt',
  fixtureTemplate: `H:/studybuddy-test/fixtures/kaobuddy-foundation/${'sample.txt'}`,
};
"""
    node_script = r'''
const vm = require('vm');
const loader = require(process.argv[1]);
const source = JSON.parse(process.argv[2]);
const module = {exports: {}};
vm.runInNewContext(loader.rewrite(source), {
  module,
  process: {env: {
    STUDYBUDDY_PYTHON: 'D:/python/python.exe',
    STUDYBUDDY_BACKEND_ROOT: 'X:/repo/backend',
    STUDYBUDDY_BASE_URL: 'http://127.0.0.1:9123',
    STUDYBUDDY_TEST_ROOT: 'X:/tests/run-123',
    STUDYBUDDY_FIXTURE_ROOT: 'X:/tests',
  }},
  require,
  __dirname: 'X:/repo/backend/scripts',
  Date,
});
process.stdout.write(JSON.stringify(module.exports));
'''
    result = subprocess.run(
        ["node", "-e", node_script, str(LOADER), json.dumps(source)],
        cwd=ROOT,
        env={**os.environ, "NODE_PATH": str(ROOT / "node_modules")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert resolved["python"] == "D:/python/python.exe"
    assert resolved["backend"] == "X:/repo/backend"
    assert resolved["base"] == "http://127.0.0.1:9123"
    assert resolved["run"].startswith("X:/tests/run-123/runs/browser-")
    assert resolved["fixture"] == "X:/tests/fixtures/kaobuddy-foundation/sample.txt"
    assert resolved["fixtureTemplate"] == "X:/tests/fixtures/kaobuddy-foundation/sample.txt"
