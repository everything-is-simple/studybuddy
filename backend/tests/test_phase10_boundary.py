from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_phase10_boundary_runner_is_reproducible_and_redacted():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "phase10_boundary.py")],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["environment"] == "synthetic/local/single-process/single-instance/SQLite/fake-provider"
    assert payload["thresholds_are_local_timebox_only"] is True
    assert payload["backup_restore"] == {"verified": True, "restored_schema_preserved": True}
    assert payload["task_retry"] == {"verified": True, "attempt_count": 2, "progress_percent": 100}
    assert payload["lifecycle"]["cycles"] == 10
    assert all(check["status"] == "passed" for check in payload["checks"])
    forbidden = ("studybuddy-phase10-boundary-", "studybuddy.sqlite3", "stored_path", "Boundary evidence")
    assert not any(value in result.stdout for value in forbidden)


def test_phase10_boundary_runner_script_has_no_external_provider_or_repo_artifacts():
    script = (ROOT / "scripts" / "phase10_boundary.py").read_text(encoding="utf-8")
    assert "TestClient" in script
    assert "fake" in script
    assert "tempfile.mkdtemp" in script
    assert "requests" not in script
    assert "httpx.Client" not in script
    assert "H:\\studybuddy-test" not in script
