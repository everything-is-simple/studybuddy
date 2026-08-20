from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig, DEFAULT_MAX_UPLOAD_BYTES
from app.main import create_app
from app.repository import connect

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")


def make_client(root: Path) -> TestClient:
    return TestClient(create_app(AppConfig(data_root=root, max_upload_bytes=DEFAULT_MAX_UPLOAD_BYTES)))


def test_upload_parse_persist_and_restart_readback(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/materials",
            files={"file": ("sample.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")},
        )
        assert response.status_code == 201
        created = response.json()
        assert created["status"] == "success"
        assert created["span_count"] == 1
        assert (tmp_path / "originals" / created["source_sha256"][:2] / created["source_sha256"][2:] / "original").exists()
        detail = client.get(f"/api/materials/{created['material_id']}")
        assert detail.status_code == 200
        assert "StudyBuddy synthetic TXT fixture." in detail.json()["text"]

    # A new application instance proves the result is read from SQLite, not process state.
    with make_client(tmp_path) as restarted:
        listing = restarted.get("/api/materials")
        assert listing.status_code == 200
        assert listing.json()[0]["id"] == created["material_id"]
        detail = restarted.get(f"/api/materials/{created['material_id']}").json()
        assert "StudyBuddy synthetic TXT fixture." in detail["text"]
        assert detail["spans"][0]["span_kind"] == "document"


def test_rejected_format_is_persisted_as_parser_result(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/materials",
            files={"file": ("sample.rtf", (FIXTURES / "sample.rtf").read_bytes(), "application/rtf")},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "rejected"
        material_id = response.json()["material_id"]
        detail = client.get(f"/api/materials/{material_id}").json()
        assert detail["status"] == "rejected"
        assert detail["text"] == ""
        assert detail["warnings"]


def test_duplicate_hash_reuses_original_path(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = client.post("/api/materials", files={"file": ("first.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        second = client.post("/api/materials", files={"file": ("second.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        assert first.status_code == second.status_code == 201
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            rows = connection.execute("SELECT source_sha256, stored_path FROM materials ORDER BY original_name").fetchall()
            assert len(rows) == 2
            assert rows[0][0] == rows[1][0]
            assert rows[0][1] == rows[1][1]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1


def test_default_upload_limit_is_50_mib():
    assert DEFAULT_MAX_UPLOAD_BYTES == 50 * 1024 * 1024


def test_upload_rejects_path_traversal_filename(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("../escape.txt", b"body", "text/plain")})
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_filename"
        assert client.get("/api/materials").json() == []


def test_upload_limit_boundary_is_strictly_greater_than_configured_limit(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=8)
    with TestClient(create_app(config)) as client:
        accepted = client.post("/api/materials", files={"file": ("exact.txt", b"12345678", "text/plain")})
        assert accepted.status_code == 201
        rejected = client.post("/api/materials", files={"file": ("over.txt", b"123456789", "text/plain")})
        assert rejected.status_code == 413


def test_upload_size_limit_does_not_create_material(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=4)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials", files={"file": ("sample.txt", b"too large", "text/plain")})
        assert response.status_code == 413
        assert client.get("/api/materials").json() == []
        assert list(tmp_path.glob(".incoming-*")) == []
        assert not (tmp_path / "originals").exists()
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0


def test_database_failure_cleans_new_original(tmp_path: Path, monkeypatch):
    from app import main
    original_save = main.save_material_with_extraction
    def fail_save(*args, **kwargs):
        raise RuntimeError("synthetic database failure")
    monkeypatch.setattr(main, "save_material_with_extraction", fail_save)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials", files={"file": ("sample.txt", (FIXTURES / "sample.txt").read_bytes(), "text/plain")})
        assert response.status_code == 500
        assert response.json()["detail"] == "material_persist_failed"
        assert list((tmp_path / "originals").rglob("original")) == []
        assert client.get("/api/materials").json() == []
    monkeypatch.setattr(main, "save_material_with_extraction", original_save)


def test_batch_imports_multiple_files_with_item_results_and_filters(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=8)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("small.txt", b"12345678", "text/plain")),
            ("files", ("empty.txt", b"", "text/plain")),
            ("files", ("large.txt", b"123456789", "text/plain")),
            ("files", ("sample.rtf", b"{\\rtf1}", "application/rtf")),
        ])
        assert response.status_code == 201
        payload = response.json()
        assert payload["total"] == 4
        assert (payload["success"], payload["empty"], payload["rejected"], payload["failed"]) == (1, 1, 2, 0)
        by_name = {item["original_name"]: item for item in payload["items"]}
        assert by_name["large.txt"]["error_code"] == "file_too_large"
        assert by_name["sample.rtf"]["error_code"] == "unsupported_rtf"
        assert client.get("/api/materials?status=success").json()[0]["original_name"] == "small.txt"
        assert client.get("/api/materials?status=empty").json()[0]["original_name"] == "empty.txt"
        assert client.get("/api/materials?status=rejected").json()[0]["original_name"] == "sample.rtf"
        assert client.get("/api/materials?status=failed").json() == []
        assert client.get("/api/materials?status=unknown").status_code == 400
        assert all("text" not in item for item in client.get("/api/materials").json())
        assert list(tmp_path.glob(".incoming-*")) == []
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 3


def test_batch_oversize_does_not_affect_other_files(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, max_upload_bytes=4)
    with TestClient(create_app(config)) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("over.txt", b"12345", "text/plain")),
            ("files", ("ok.txt", b"1234", "text/plain")),
        ])
        assert response.status_code == 201
        items = {item["original_name"]: item for item in response.json()["items"]}
        assert items["over.txt"]["status"] == "rejected"
        assert items["ok.txt"]["status"] == "success"
        assert items["over.txt"]["material_id"] is None
        assert items["over.txt"]["source_sha256"] == ""
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        assert list(tmp_path.glob(".incoming-*")) == []


def test_batch_duplicate_hash_reuses_original(tmp_path: Path):
    body = (FIXTURES / "sample.txt").read_bytes()
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("one.txt", body, "text/plain")),
            ("files", ("two.txt", body, "text/plain")),
        ])
        assert response.status_code == 201
        assert response.json()["success"] == 2
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            rows = connection.execute("SELECT source_sha256, stored_path FROM materials ORDER BY original_name").fetchall()
        assert len(rows) == 2 and rows[0][0] == rows[1][0] and rows[0][1] == rows[1][1]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1


def test_batch_database_failure_is_item_level_and_other_file_survives(tmp_path: Path, monkeypatch):
    from app import main
    original_save = main.save_material_with_extraction
    calls = 0
    def fail_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic database failure")
        return original_save(*args, **kwargs)
    monkeypatch.setattr(main, "save_material_with_extraction", fail_first)
    with make_client(tmp_path) as client:
        response = client.post("/api/materials/batch", files=[
            ("files", ("failed.txt", b"first", "text/plain")),
            ("files", ("saved.txt", b"second", "text/plain")),
        ])
        assert response.status_code == 201
        items = {item["original_name"]: item for item in response.json()["items"]}
        assert items["failed.txt"]["error_code"] == "material_persist_failed"
        assert items["saved.txt"]["status"] == "success"
        assert client.get("/api/materials").json()[0]["original_name"] == "saved.txt"
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        assert list(tmp_path.glob(".incoming-*")) == []


def upload_text(client: TestClient, name: str, body: bytes | None = None) -> dict[str, object]:
    content = (FIXTURES / "sample.txt").read_bytes() if body is None else body
    response = client.post("/api/materials", files={"file": (name, content, "text/plain")})
    assert response.status_code == 201
    return response.json()


def test_rename_preserves_content_identity_and_survives_restart(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload_text(client, "original.txt")
        before = client.get(f"/api/materials/{created['material_id']}").json()
        renamed = client.patch(f"/api/materials/{created['material_id']}", json={"original_name": "  renamed.txt  "})
        assert renamed.status_code == 200
        payload = renamed.json()
        assert payload["original_name"] == "renamed.txt"
        assert payload["source_sha256"] == before["source_sha256"]
        assert payload["stored_path"] == before["stored_path"]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        assert list(tmp_path.glob(".incoming-*")) == []
        assert "text" not in payload
        assert client.get("/api/materials").json()[0]["original_name"] == "renamed.txt"

    with make_client(tmp_path) as restarted:
        detail = restarted.get(f"/api/materials/{created['material_id']}").json()
        assert detail["original_name"] == "renamed.txt"
        assert detail["source_sha256"] == before["source_sha256"]


def test_rename_validation_duplicates_and_deleted_material(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = upload_text(client, "one.txt")
        second = upload_text(client, "two.txt", b"different")
        assert client.patch(f"/api/materials/{second['material_id']}", json={"original_name": "one.txt"}).status_code == 200
        for bad_name in ["", "   ", ".", "..", "../escape.txt", "folder\\escape.txt", "x" * 256]:
            response = client.patch(f"/api/materials/{first['material_id']}", json={"original_name": bad_name})
            assert response.status_code == 400
            assert response.json()["detail"] == "invalid_filename"
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 204
        assert client.patch(f"/api/materials/{first['material_id']}", json={"original_name": "cannot.txt"}).status_code == 404
        assert client.patch("/api/materials/material_missing", json={"original_name": "missing.txt"}).status_code == 404


def test_logical_delete_preserves_data_hash_reuse_and_restart(tmp_path: Path):
    body = (FIXTURES / "sample.txt").read_bytes()
    with make_client(tmp_path) as client:
        first = upload_text(client, "one.txt", body)
        second = upload_text(client, "two.txt", body)
        first_detail = client.get(f"/api/materials/{first['material_id']}").json()
        original_path = Path(first_detail["stored_path"])
        assert original_path.exists()
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 204
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 404
        assert client.get(f"/api/materials/{first['material_id']}").status_code == 404
        assert all(item["id"] != first["material_id"] for item in client.get("/api/materials").json())
        for status in ("success", "empty", "rejected", "failed"):
            assert all(item["id"] != first["material_id"] for item in client.get(f"/api/materials?status={status}").json())
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            deleted_at = connection.execute("SELECT deleted_at FROM materials WHERE id = ?", (first["material_id"],)).fetchone()[0]
            assert deleted_at
            assert connection.execute("SELECT COUNT(*) FROM extractions WHERE material_id = ?", (first["material_id"],)).fetchone()[0] == 1
            extraction_id = connection.execute("SELECT id FROM extractions WHERE material_id = ?", (first["material_id"],)).fetchone()[0]
            assert connection.execute("SELECT COUNT(*) FROM text_spans WHERE extraction_id = ?", (extraction_id,)).fetchone()[0] == 1
        assert original_path.exists() and len(list((tmp_path / "originals").rglob("original"))) == 1
        survivor = client.get(f"/api/materials/{second['material_id']}")
        assert survivor.status_code == 200 and survivor.json()["text"]

    with make_client(tmp_path) as restarted:
        assert restarted.get(f"/api/materials/{first['material_id']}").status_code == 404
        assert restarted.get(f"/api/materials/{second['material_id']}").status_code == 200
        assert len(restarted.get("/api/materials").json()) == 1


def test_rename_and_delete_database_failures_leave_active_material_unchanged(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        created = upload_text(client, "before.txt")
        monkeypatch.setattr(main, "rename_material", lambda *args: (_ for _ in ()).throw(sqlite3.DatabaseError("rename failed")))
        assert client.patch(f"/api/materials/{created['material_id']}", json={"original_name": "after.txt"}).status_code == 500
        monkeypatch.undo()
        assert client.get(f"/api/materials/{created['material_id']}").json()["original_name"] == "before.txt"
        monkeypatch.setattr(main, "soft_delete_material", lambda *args: (_ for _ in ()).throw(sqlite3.DatabaseError("delete failed")))
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 500
        monkeypatch.undo()
        assert client.get(f"/api/materials/{created['material_id']}").status_code == 200


def test_material_schema_migrates_existing_database(tmp_path: Path):
    db = tmp_path / "studybuddy.sqlite3"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE materials (id TEXT PRIMARY KEY, project_id TEXT, original_name TEXT, source_sha256 TEXT, stored_path TEXT, media_type TEXT, created_at TEXT)")
    connection.execute("INSERT INTO materials VALUES ('m1', 'p1', 'old.txt', 'hash', 'path', 'text/plain', 'then')")
    connection.commit()
    connection.close()
    with connect(db) as migrated:
        row = migrated.execute("SELECT updated_at, deleted_at FROM materials WHERE id = 'm1'").fetchone()
        assert row[0] == "then" and row[1] is None


def test_recycle_bin_list_restore_and_invariants(tmp_path: Path):
    body = (FIXTURES / "sample.txt").read_bytes()
    with make_client(tmp_path) as client:
        first = upload_text(client, "same-one.txt", body)
        second = upload_text(client, "same-two.txt", body)
        before = client.get(f"/api/materials/{first['material_id']}").json()
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            extraction_before = connection.execute("SELECT COUNT(*) FROM extractions").fetchone()[0]
            spans_before = connection.execute("SELECT COUNT(*) FROM text_spans").fetchone()[0]
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 204
        deleted = client.get("/api/materials/deleted")
        assert deleted.status_code == 200
        deleted_item = deleted.json()[0]
        assert deleted_item["id"] == first["material_id"]
        assert deleted_item["deleted_at"]
        assert "text" not in deleted_item
        assert all(item["id"] != first["material_id"] for item in client.get("/api/materials").json())
        assert client.get(f"/api/materials/{first['material_id']}").status_code == 404
        restored = client.post(f"/api/materials/{first['material_id']}/restore")
        assert restored.status_code == 200
        restored_payload = restored.json()
        assert restored_payload["deleted_at"] is None
        assert restored_payload["source_sha256"] == before["source_sha256"]
        assert restored_payload["stored_path"] == before["stored_path"]
        assert "text" not in restored_payload
        assert client.get("/api/materials/deleted").json() == []
        assert client.get(f"/api/materials/{first['material_id']}").json()["text"]
        assert client.get(f"/api/materials/{second['material_id']}").json()["text"]
        assert len(list((tmp_path / "originals").rglob("original"))) == 1
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM extractions").fetchone()[0] == extraction_before
            assert connection.execute("SELECT COUNT(*) FROM text_spans").fetchone()[0] == spans_before
        assert list(tmp_path.glob(".incoming-*")) == []


def test_restore_error_cases_and_database_failure(tmp_path: Path, monkeypatch):
    from app import main
    with make_client(tmp_path) as client:
        created = upload_text(client, "restore.txt")
        assert client.post(f"/api/materials/{created['material_id']}/restore").status_code == 404
        assert client.post("/api/materials/missing/restore").status_code == 404
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 204
        monkeypatch.setattr(main, "restore_material", lambda *args: (_ for _ in ()).throw(sqlite3.DatabaseError("restore failed")))
        failed = client.post(f"/api/materials/{created['material_id']}/restore")
        assert failed.status_code == 500 and failed.json()["detail"] == "material_restore_failed"
        monkeypatch.undo()
        assert client.get(f"/api/materials/{created['material_id']}").status_code == 404
        assert client.get("/api/materials/deleted").json()[0]["id"] == created["material_id"]


def test_material_exports_and_lifecycle(tmp_path: Path):
    body = (FIXTURES / "sample.txt").read_bytes()
    with make_client(tmp_path) as client:
        created = upload_text(client, "sample.txt", body)
        detail = client.get(f"/api/materials/{created['material_id']}").json()
        original = client.get(f"/api/materials/{created['material_id']}/original")
        assert original.status_code == 200
        assert original.content == body
        assert original.headers["content-type"].startswith("text/plain")
        assert 'filename="sample.txt"' in original.headers["content-disposition"]
        text = client.get(f"/api/materials/{created['material_id']}/text")
        assert text.status_code == 200 and text.content.decode("utf-8") == detail["text"]
        assert 'filename="sample.txt.extracted.txt"' in text.headers["content-disposition"]
        renamed = client.patch(f"/api/materials/{created['material_id']}", json={"original_name": "renamed.txt"}).json()
        assert client.get(f"/api/materials/{created['material_id']}/original").headers["content-disposition"].find('filename="renamed.txt"') >= 0
        assert client.get(f"/api/materials/{created['material_id']}/original").content == body
        assert 'filename="renamed.txt.extracted.txt"' in client.get(f"/api/materials/{created['material_id']}/text").headers["content-disposition"]
        assert renamed["source_sha256"] == detail["source_sha256"]
        assert client.delete(f"/api/materials/{created['material_id']}").status_code == 204
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 404
        assert client.get(f"/api/materials/{created['material_id']}/text").status_code == 404
        assert client.post(f"/api/materials/{created['material_id']}/restore").status_code == 200
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 200
        assert client.get(f"/api/materials/{created['material_id']}/text").status_code == 200
        assert list(tmp_path.glob(".incoming-*")) == []
        assert len(list((tmp_path / "originals").rglob("original"))) == 1


def test_empty_and_rejected_text_exports(tmp_path: Path):
    with make_client(tmp_path) as client:
        empty = upload_text(client, "empty.txt", b"")
        rejected = client.post("/api/materials", files={"file": ("sample.rtf", (FIXTURES / "sample.rtf").read_bytes(), "application/rtf")}).json()
        for material in (empty, rejected):
            response = client.get(f"/api/materials/{material['material_id']}/text")
            assert response.status_code == 200 and response.content == b""
            assert response.headers["content-type"].startswith("text/plain")


def test_export_rejects_invalid_or_corrupt_original(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload_text(client, "sample.txt")
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            connection.execute("UPDATE materials SET stored_path = ? WHERE id = ?", (str(tmp_path / "outside"), created["material_id"]))
            connection.commit()
        assert client.get(f"/api/materials/{created['material_id']}/original").status_code == 500
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            connection.execute("UPDATE materials SET stored_path = ? WHERE id = ?", (str(tmp_path / "originals" / created["source_sha256"][:2] / created["source_sha256"][2:] / "original"), created["material_id"]))
            connection.commit()
        target = Path(created["source_sha256"][:2])
        original_path = tmp_path / "originals" / created["source_sha256"][:2] / created["source_sha256"][2:] / "original"
        original_path.write_bytes(b"tampered")
        response = client.get(f"/api/materials/{created['material_id']}/original")
        assert response.status_code == 500 and response.json()["detail"] == "original_hash_mismatch"


def test_material_search_query_lifecycle_and_index(tmp_path: Path):
    with make_client(tmp_path) as client:
        text = upload_text(client, "search-name.txt", b"StudyBuddy TXT searchable body")
        markdown = client.post("/api/materials", files={"file": ("notes.md", (FIXTURES / "sample.md").read_bytes(), "text/markdown")}).json()
        chinese = client.post("/api/materials", files={"file": ("chinese.txt", (FIXTURES / "chinese.txt").read_bytes(), "text/plain")}).json()
        rejected = client.post("/api/materials", files={"file": ("legacy.rtf", (FIXTURES / "sample.rtf").read_bytes(), "application/rtf")}).json()
        all_items = client.get("/api/materials").json()
        assert client.get("/api/materials?q=").json() == all_items
        result = client.get("/api/materials?q=studybuddy").json()
        assert {item["id"] for item in result} == {text["material_id"]}
        assert result[0]["match_fields"] == ["text"] and len(result[0]["snippet"]) <= 160
        assert all(len(item["snippet"]) <= 160 for item in result)
        name_result = client.get("/api/materials?q=search-name").json()[0]
        assert "original_name" in name_result["match_fields"]
        assert "text" not in name_result and "stored_path" not in name_result
        assert "text" not in result[0] and "stored_path" not in result[0]
        assert client.get("/api/materials?q=StudyBuddy%20TXT").json()[0]["id"] == text["material_id"]
        assert client.get("/api/materials?q=%20StudyBuddy%20").json()[0]["id"] == text["material_id"]
        assert client.get("/api/materials?q=Markdown&status=success").json()[0]["id"] == markdown["material_id"]
        assert client.get("/api/materials?q=%E4%B8%AD%E6%96%87").json()[0]["id"] == chinese["material_id"]
        assert client.get("/api/materials?q=not-present").json() == []
        assert client.get("/api/materials?q=legacy").json()[0]["id"] == rejected["material_id"]
        assert client.get("/api/materials?q=legacy&status=success").json() == []
        assert client.get("/api/materials?q=StudyBuddy&status=wrong").status_code == 400
        assert client.get("/api/materials?q=%3Cscript%3E").json() == []
        assert client.patch(f"/api/materials/{text['material_id']}", json={"original_name": "renamed-search.txt"}).status_code == 200
        assert client.get("/api/materials?q=renamed-search").json()[0]["id"] == text["material_id"]
        assert client.get("/api/materials?q=search-name").json() == []
        assert client.delete(f"/api/materials/{text['material_id']}").status_code == 204
        assert client.get("/api/materials?q=StudyBuddy").json() == []
        assert client.post(f"/api/materials/{text['material_id']}/restore").status_code == 200
        assert client.get("/api/materials?q=StudyBuddy").json()[0]["id"] == text["material_id"]
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM material_search WHERE material_id = ?", (text["material_id"],)).fetchone()[0] == 1

    with make_client(tmp_path) as restarted:
        assert restarted.get("/api/materials?q=StudyBuddy").json()[0]["id"] == text["material_id"]


def test_search_index_initializes_existing_material_without_duplicates(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload_text(client, "existing.txt", b"existing searchable text")
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        connection.execute("DELETE FROM material_search WHERE material_id = ?", (created["material_id"],))
        connection.commit()
    with make_client(tmp_path) as restarted:
        assert restarted.get("/api/materials?q=searchable").json()[0]["id"] == created["material_id"]
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM material_search WHERE material_id = ?", (created["material_id"],)).fetchone()[0] == 1


def test_purge_removes_deleted_rows_and_unshared_original(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload_text(client, "purge.txt")
        material_id = created["material_id"]
        stored_path = Path(client.get(f"/api/materials/{material_id}").json()["stored_path"])
        assert client.delete(f"/api/materials/{material_id}").status_code == 204
        response = client.post(f"/api/materials/{material_id}/purge")
        assert response.status_code == 200 and response.json() == {"status": "purged", "material_id": material_id}
        assert not stored_path.exists()
        with connect(tmp_path / "studybuddy.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM materials WHERE id = ?", (material_id,)).fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM extractions WHERE material_id = ?", (material_id,)).fetchone()[0] == 0
            assert connection.execute("SELECT COUNT(*) FROM material_search WHERE material_id = ?", (material_id,)).fetchone()[0] == 0
        assert client.post(f"/api/materials/{material_id}/restore").status_code == 404


def test_purge_shared_hash_preserves_then_removes_original(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = upload_text(client, "first.txt")
        second = upload_text(client, "second.txt")
        first_detail = client.get(f"/api/materials/{first['material_id']}").json()
        second_detail = client.get(f"/api/materials/{second['material_id']}").json()
        assert first_detail["source_sha256"] == second_detail["source_sha256"]
        original = Path(first_detail["stored_path"])
        assert original == Path(second_detail["stored_path"]) and original.exists()
        assert client.delete(f"/api/materials/{first['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{first['material_id']}/purge").status_code == 200
        assert original.exists() and client.get(f"/api/materials/{second['material_id']}").status_code == 200
        assert client.get(f"/api/materials/{second['material_id']}/original").status_code == 200
        assert client.delete(f"/api/materials/{second['material_id']}").status_code == 204
        assert client.post(f"/api/materials/{second['material_id']}/purge").status_code == 200
        assert not original.exists()


def test_purge_active_and_missing_return_404(tmp_path: Path):
    with make_client(tmp_path) as client:
        created = upload_text(client, "active.txt")
        assert client.post(f"/api/materials/{created['material_id']}/purge").status_code == 404
        assert client.get(f"/api/materials/{created['material_id']}").status_code == 200
        assert client.post("/api/materials/missing/purge").status_code == 404


def test_page_is_real_multi_file_picker_and_shows_materials(tmp_path: Path):
    with make_client(tmp_path) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'type="file" multiple' in page.text
        assert "/api/materials/batch" in page.text
        assert "success','empty','rejected','failed" in page.text
        assert 'id="rename"' in page.text and 'id="delete"' in page.text and 'id="purge"' in page.text
