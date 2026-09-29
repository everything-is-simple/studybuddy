from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backup import _copytree_path, backup_data, restore_backup, verify_backup
from app.config import AppConfig
from app.main import create_app


def test_copytree_path_preserves_non_windows_and_extends_windows(tmp_path: Path):
    expected = str(tmp_path)
    if os.name == "nt":
        expected = "\\\\?\\" + expected
    assert _copytree_path(tmp_path) == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows path syntax")
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (r"\\server\share\backup", r"\\?\UNC\server\share\backup"),
        (r"\\?\H:\backup", r"\\?\H:\backup"),
        (r"\\?\UNC\server\share\backup", r"\\?\UNC\server\share\backup"),
    ],
)
def test_windows_copytree_path_handles_unc_and_existing_prefix(value: str, expected: str):
    assert _copytree_path(Path(value)) == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows directory-length boundary")
def test_windows_restore_crosses_directory_limit(tmp_path: Path):
    body = b"Synthetic Windows restore path fixture."
    digest = hashlib.sha256(body).hexdigest()
    relative = Path("originals") / digest[:2] / digest[2:]
    padding = 250 - len(str(tmp_path / "restored.restore-staging" / relative)) - 1
    assert 0 < padding < 256
    parent = tmp_path / ("p" * padding)
    source, backup, restored = (parent / name for name in ("source", "backup", "restored"))
    staged_directory = parent / "restored.restore-staging" / relative
    assert len(str(staged_directory)) == 250
    assert len(str(restored / relative / "original")) < 260

    config = AppConfig(
        data_root=source,
        ai_provider_id="fake",
        embedding_provider_id="fake",
        embedding_model_id="fake-embedding-v1",
    )
    with TestClient(create_app(config)) as client:
        uploaded = client.post(
            "/api/materials",
            files={"file": ("path-fixture.txt", body, "text/plain")},
        )
        assert uploaded.status_code == 201
    assert backup_data(source, backup)["status"] == "complete"
    assert verify_backup(backup)["status"] == "valid"
    assert restore_backup(restored, backup, confirm=True)["status"] == "restored"
    assert (restored / relative / "original").read_bytes() == body
    assert not (parent / "restored.restore-staging").exists()
    assert verify_backup(backup)["status"] == "valid"
