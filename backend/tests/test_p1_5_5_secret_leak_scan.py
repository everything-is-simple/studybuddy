"""P1-5-5 secret leak scan governance tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "backend" / "app"
SCRIPT = ROOT / "backend" / "scripts" / "scan-secret-leaks.py"

spec = importlib.util.spec_from_file_location("scan_secret_leaks", SCRIPT)
assert spec and spec.loader
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)

SENTINELS = scanner.DEFAULT_SENTINELS


def test_scanner_reports_redacted_findings_without_secret_values(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "runtime.log"
    artifact.write_text(f"request failed: {SENTINELS[0]} and {SENTINELS[0]}", encoding="utf-8")

    findings = scanner.scan_files([artifact])

    assert findings == [{"path": str(artifact), "match_count": 2, "sentinel_indexes": ["0"]}]
    assert all(value not in capsys.readouterr().out for value in SENTINELS)


def test_scanner_clean_for_synthetic_runtime_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "runtime.json"
    artifact.write_text('{"status":"ok","error_code":"provider_auth_failed"}', encoding="utf-8")
    assert scanner.scan_files([artifact]) == []


def test_scanner_does_not_follow_links_or_scan_known_test_caches(tmp_path: Path) -> None:
    cache = tmp_path / "test-results"
    cache.mkdir()
    (cache / "failure.txt").write_text(SENTINELS[1], encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text(SENTINELS[2], encoding="utf-8")
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        link = None

    findings = scanner.scan_files(scanner.iter_files([tmp_path]))

    assert all("test-results" not in item["path"] for item in findings)
    if link:
        assert all(item["path"] != str(link) for item in findings)
    assert any(item["path"] == str(target) for item in findings)


def test_production_observability_allowlist_excludes_secret_payloads() -> None:
    source = (APP_ROOT / "observability.py").read_text(encoding="utf-8")
    assert "allowed =" in source
    assert "request_body" not in source
    assert "logger.log(level, json.dumps(payload" in source
    assert "api_key" not in source
    assert "smtp_password" not in source
    assert "feishu_webhook" not in source


def test_production_connection_and_delivery_paths_do_not_log_secret_values() -> None:
    sources = [
        APP_ROOT / "connection_test.py",
        APP_ROOT / "delivery.py",
        APP_ROOT / "api" / "system.py",
    ]
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert "logger." not in source, f"{path} must not log connection credentials"
        assert "print(" not in source, f"{path} must not print connection credentials"


def test_scan_script_output_is_redacted_and_bounded() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "match_count" in source
    assert "sentinel_indexes" in source
    assert "MAX_SCAN_BYTES" in source
    assert "print(f\"- {finding['path']}: {finding['match_count']} match(es)\")" in source
    assert "read_bytes" in source
    assert "finding['sentinel_indexes']" not in source


def test_schema_and_persistence_boundaries_remain_unchanged() -> None:
    runner = (APP_ROOT / "migrations" / "runner.py").read_text(encoding="utf-8")
    assert "CURRENT_SCHEMA_VERSION = 14" in runner
    page = (APP_ROOT / "static" / "settings-provider.html").read_text(encoding="utf-8")
    for forbidden in ("localStorage", "sessionStorage", "indexedDB", "STUDYBUDDY_REPORT_DELIVERY_MODE=live"):
        assert forbidden not in page
