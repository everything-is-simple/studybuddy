from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.main import create_app
from app.restore_acceptance import verify_restored_data


def make_data(root: Path) -> dict[str, object]:
    with TestClient(create_app(AppConfig(data_root=root))) as client:
        created = client.post("/api/materials", files={"file": ("one.txt", b"restore text", "text/plain")})
        assert created.status_code == 201
        return created.json()


def test_offline_acceptance_checks_database_and_original(tmp_path: Path):
    root = tmp_path / "data"
    item = make_data(root)
    result = verify_restored_data(root)
    assert result["status"] == "passed"
    assert result["mode"] == "offline"
    assert result["checks"]["health"]["status"] == "skipped"
    assert result["checks"]["detail"]["material_id"] == item["material_id"]
    assert result["checks"]["original_download"]["status"] == "passed"
    assert result["checks"]["text_export"]["sha256"] == hashlib.sha256(b"restore text").hexdigest()


def test_online_acceptance_checks_http_contract(monkeypatch, tmp_path: Path):
    root = tmp_path / "data"
    item = make_data(root)
    material_id = str(item["material_id"])
    detail = {
        "id": material_id,
        "source_sha256": str(item["source_sha256"]),
        "original_name": "one.txt",
    }
    from app import restore_acceptance

    def fake_json(_base_url: str, path: str):
        if path == "/api/health":
            return 200, {"status": "ok"}
        if path == "/api/materials":
            return 200, [{"id": material_id}]
        if path == "/api/materials/deleted":
            return 200, []
        if path == "/api/materials/" + material_id:
            return 200, detail
        raise AssertionError(path)

    def fake_bytes(_base_url: str, path: str):
        if path.endswith("/original"):
            return 200, {"content-type": "text/plain"}, b"restore text"
        if path.endswith("/text"):
            return 200, {"content-type": "text/plain; charset=utf-8"}, b"restore text"
        raise AssertionError(path)

    monkeypatch.setattr(restore_acceptance, "_http_json", fake_json)
    monkeypatch.setattr(restore_acceptance, "_http_bytes", fake_bytes)
    result = verify_restored_data(root, "http://testserver")
    assert result["status"] == "passed"
    assert result["mode"] == "online"
    assert result["checks"]["health"]["status"] == "passed"
    assert result["checks"]["original_download"]["status"] == "passed"
    assert result["checks"]["text_export"]["status"] == "passed"


def test_empty_acceptance_skips_material_specific_checks(tmp_path: Path):
    root = tmp_path / "empty"
    with TestClient(create_app(AppConfig(data_root=root))):
        pass
    result = verify_restored_data(root)
    assert result["status"] == "passed"
    assert result["checks"]["detail"] == {"status": "skipped", "reason": "no_active_material"}
    assert result["checks"]["original_download"]["reason"] == "offline_mode"


def test_acceptance_does_not_expose_path_or_exception(tmp_path: Path):
    result = verify_restored_data(tmp_path / "missing")
    encoded = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "failed"
    assert result["error_code"] == "acceptance_database_missing"
    assert str(tmp_path) not in encoded
    assert "traceback" not in encoded.lower()
