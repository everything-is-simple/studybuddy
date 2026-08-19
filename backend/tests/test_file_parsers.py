from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.adapters.file_parsers import ParseOptions, parse_file
from app.repository import connect, save_extraction
from app.storage import sha256_file, store_original

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")
CASES = {
    "sample.txt": "success", "sample.md": "success", "chinese.txt": "success", "empty.txt": "empty",
    "sample.pdf": "success", "corrupt.pdf": "failed", "sample.docx": "success", "empty.docx": "failed",
    "corrupt.docx": "failed", "sample.pptx": "success", "empty.pptx": "empty", "corrupt.pptx": "failed",
    "sample.rtf": "rejected", "sample.doc": "rejected", "sample.ppt": "rejected",
}


def test_fixture_statuses_and_hashes():
    for name, expected in CASES.items():
        result = parse_file(FIXTURES / name)
        assert result.status == expected, (name, result)
        assert result.source_sha256 == sha256_file(FIXTURES / name)
        assert result.text == "" if expected != "success" else True


def test_text_pdf_docx_and_pptx_structure():
    assert "Synthetic PDF" in parse_file(FIXTURES / "sample.pdf").text
    assert parse_file(FIXTURES / "sample.pdf").spans[0].kind == "page"
    docx = parse_file(FIXTURES / "sample.docx")
    assert "DOCX" in docx.text and docx.spans[0].kind == "document"
    pptx = parse_file(FIXTURES / "sample.pptx")
    assert [span.ordinal for span in pptx.spans] == [1, 2]
    assert [span.kind for span in pptx.spans] == ["slide", "slide"]
    assert "第一页合成内容" in pptx.text
    assert "中文" in parse_file(FIXTURES / "chinese.txt").text


def test_valid_empty_docx_is_empty(tmp_path: Path):
    path = tmp_path / "valid-empty.docx"
    Document().save(path)
    result = parse_file(path)
    assert result.status == "empty" and result.error_code is None


def test_rejections_and_limits(tmp_path: Path):
    assert parse_file(FIXTURES / "sample.rtf").error_code == "unsupported_rtf"
    assert parse_file(FIXTURES / "sample.doc").error_code == "requires_converter"
    assert parse_file(FIXTURES / "sample.ppt").error_code == "requires_converter"
    assert parse_file(FIXTURES / "sample.txt", options=ParseOptions(max_bytes=1)).error_code == "file_too_large"
    result = parse_file(FIXTURES / "sample.docx", options=ParseOptions(max_uncompressed_bytes=1))
    assert result.status == "rejected" and result.error_code == "zip_uncompressed_limit"


def test_parser_does_not_print_or_copy(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    source = FIXTURES / "sample.txt"
    before = {path for path in tmp_path.rglob("*")}
    result = parse_file(source)
    assert capsys.readouterr().out == ""
    assert {path for path in tmp_path.rglob("*")} == before
    assert result.text


def test_storage_reuses_same_hash_without_overwriting(tmp_path: Path):
    source = FIXTURES / "sample.txt"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    first = store_original(source, "first.txt", digest, tmp_path / "originals")
    second = store_original(source, "second.txt", digest, tmp_path / "originals")
    assert first.created is True
    assert second.created is False
    assert first.path == second.path


def test_storage_and_sqlite_transaction(tmp_path: Path):
    source = FIXTURES / "sample.txt"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stored = store_original(source, "sample.txt", digest, tmp_path / "originals")
    assert stored.path.exists() and stored.path.read_bytes() == source.read_bytes()
    db = connect(tmp_path / "test.sqlite3")
    db.execute("INSERT INTO projects VALUES (?, ?, ?)", ("p1", "test", "now"))
    db.execute("INSERT INTO materials (id, project_id, original_name, source_sha256, stored_path, media_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", ("m1", "p1", "sample.txt", digest, str(stored.path), ".txt", "now"))
    extraction_id = save_extraction(db, "m1", parse_file(source))
    assert db.execute("SELECT COUNT(*) FROM text_spans WHERE extraction_id = ?", (extraction_id,)).fetchone()[0] == 1
    db.close()

    reopened = connect(tmp_path / "test.sqlite3")
    assert reopened.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert reopened.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    reopened.close()
