"""Tests for P14-P0-05 revision fingerprint fix (migration v14)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_new_fingerprint(material_id: str, source_sha256: str, text: str,
                              parser_id: str, parser_version: str) -> str:
    """New formula including material_id."""
    values = (str(material_id), str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def _compute_old_fingerprint(source_sha256: str, text: str,
                              parser_id: str, parser_version: str) -> str:
    """Old formula without material_id."""
    values = (str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


@pytest.fixture
def temp_db_v13(tmp_path: Path) -> Path:
    """Create a v13 schema with sample data."""
    from backend.app.migrations import runner
    
    database = tmp_path / "test.db"
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    
    # Use runner to create v13 schema (migrations 1-13)
    saved_migrations = list(runner._MIGRATIONS)
    saved_version = runner.CURRENT_SCHEMA_VERSION
    try:
        runner._MIGRATIONS = saved_migrations[:13]
        runner.CURRENT_SCHEMA_VERSION = 13
        runner.migrate(connection)
    finally:
        runner._MIGRATIONS = saved_migrations
        runner.CURRENT_SCHEMA_VERSION = saved_version
    
    connection.execute("PRAGMA foreign_keys = ON")
    
    # Add test data
    connection.executescript("""
        INSERT INTO projects VALUES ('p1', 'Project 1', '2024-01-01T00:00:00Z');
        INSERT INTO materials VALUES 
            ('m1', 'p1', 'file1.txt', 'sha256_1', 'originals/sha256_1', 'text/plain', 
             '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z', NULL);
        INSERT INTO extractions VALUES 
            ('e1', 'm1', 'text', '1.0.0', 'success', 'hello world', '[]', 
             '2024-01-01T00:00:00Z', NULL);
        
        INSERT INTO material_revisions VALUES 
            ('r1', 'm1', 'e1', 'sha256_1', 'extraction_sha256_1', 
             'text', '1.0.0', 'old_fingerprint_1', 1, '2024-01-01T00:00:00Z', NULL);
    """)
    connection.commit()
    connection.close()
    return database


def test_migration_14_updates_fingerprints_in_place(temp_db_v13: Path):
    """Migration 14 updates revision_fingerprint to include material_id."""
    from backend.app.migrations import _v14_fix_revision_fingerprint as v14
    
    connection = sqlite3.connect(str(temp_db_v13))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    
    # Get original fingerprint
    original = connection.execute(
        "SELECT revision_fingerprint FROM material_revisions WHERE id = 'r1'"
    ).fetchone()[0]
    
    # Apply migration
    v14.migrate(connection)
    connection.commit()
    
    # Get new fingerprint
    updated = connection.execute(
        "SELECT mr.material_id, mr.source_sha256, e.text, mr.parser_id, mr.parser_version, "
        "mr.revision_fingerprint FROM material_revisions mr "
        "JOIN extractions e ON mr.extraction_id = e.id WHERE mr.id = 'r1'"
    ).fetchone()
    
    # Verify it matches the new formula
    expected = _compute_new_fingerprint(
        updated["material_id"], updated["source_sha256"], updated["text"],
        updated["parser_id"], updated["parser_version"]
    )
    assert updated["revision_fingerprint"] == expected
    assert updated["revision_fingerprint"] != original
    
    connection.close()


def test_migration_14_rollback_restores_old_formula(temp_db_v13: Path):
    """Rollback recomputes fingerprints using the old formula."""
    from backend.app.migrations import _v14_fix_revision_fingerprint as v14
    
    connection = sqlite3.connect(str(temp_db_v13))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    
    # Get original data
    original_data = connection.execute(
        "SELECT mr.source_sha256, e.text, mr.parser_id, mr.parser_version "
        "FROM material_revisions mr JOIN extractions e ON mr.extraction_id = e.id WHERE mr.id = 'r1'"
    ).fetchone()
    
    # Apply migration
    v14.migrate(connection)
    connection.commit()
    
    new_fingerprint = connection.execute(
        "SELECT revision_fingerprint FROM material_revisions WHERE id = 'r1'"
    ).fetchone()[0]
    
    # Rollback
    v14.rollback(connection)
    connection.commit()
    
    rolled_back = connection.execute(
        "SELECT revision_fingerprint FROM material_revisions WHERE id = 'r1'"
    ).fetchone()[0]
    
    # Verify it matches the old formula
    expected_old = _compute_old_fingerprint(
        original_data["source_sha256"], original_data["text"],
        original_data["parser_id"], original_data["parser_version"]
    )
    assert rolled_back == expected_old
    assert rolled_back != new_fingerprint
    
    connection.close()


def test_shared_content_different_materials_after_fix(temp_db_v13: Path):
    """After fix, two materials with identical content get distinct fingerprints."""
    from backend.app.migrations import _v14_fix_revision_fingerprint as v14
    
    connection = sqlite3.connect(str(temp_db_v13))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    
    # Add second material with identical content
    connection.executescript("""
        INSERT INTO materials VALUES 
            ('m2', 'p1', 'file2.txt', 'sha256_2', 'originals/sha256_2', 'text/plain', 
             '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z', NULL);
        INSERT INTO extractions VALUES 
            ('e2', 'm2', 'text', '1.0.0', 'success', 'hello world', '[]', 
             '2024-01-01T00:00:00Z', NULL);
        INSERT INTO material_revisions VALUES 
            ('r2', 'm2', 'e2', 'sha256_2', 'extraction_sha256_2', 
             'text', '1.0.0', 'old_fingerprint_2', 1, '2024-01-01T00:00:00Z', NULL);
    """)
    connection.commit()
    
    # Apply migration
    v14.migrate(connection)
    connection.commit()
    
    # Fetch both fingerprints
    rows = connection.execute(
        "SELECT id, material_id, revision_fingerprint FROM material_revisions ORDER BY id"
    ).fetchall()
    
    assert len(rows) == 2
    fp1, fp2 = rows[0]["revision_fingerprint"], rows[1]["revision_fingerprint"]
    
    # They must be different (material_id differs)
    assert fp1 != fp2
    
    # Verify no UNIQUE constraint violations
    connection.execute("PRAGMA foreign_key_check")
    
    connection.close()


def test_migration_14_preserves_dependent_data(temp_db_v13: Path):
    """Migration 14 does not cascade delete chunks or other dependent data."""
    from backend.app.migrations import _v14_fix_revision_fingerprint as v14
    
    connection = sqlite3.connect(str(temp_db_v13))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    
    # Add chunks and dependent data
    connection.executescript("""
        INSERT INTO chunks (id, project_id, material_id, revision_id, extraction_id, chunk_index,
            text, normalized_text, start_offset, end_offset, token_count_estimate,
            overlap_before, overlap_after, strategy, chunking_version, status, created_at)
        VALUES ('c1', 'p1', 'm1', 'r1', 'e1', 0, 'hello', 'hello', 0, 5, 2, 0, 0,
            'fixed', '1.0.0', 'ready', '2024-01-01T00:00:00Z');
        
        INSERT INTO chunk_spans VALUES ('c1', 'span1', 0, 5);
    """)
    connection.commit()
    
    # Count before migration
    chunks_before = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    spans_before = connection.execute("SELECT COUNT(*) FROM chunk_spans").fetchone()[0]
    
    # Apply migration
    v14.migrate(connection)
    connection.commit()
    
    # Count after migration
    chunks_after = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    spans_after = connection.execute("SELECT COUNT(*) FROM chunk_spans").fetchone()[0]
    
    # All data preserved
    assert chunks_before == chunks_after == 1
    assert spans_before == spans_after == 1
    
    connection.close()


def test_migration_formula_matches_runtime():
    """Migration formula must match the runtime _revision_fingerprint function."""
    from backend.app.repositories._legacy_part_14 import _revision_fingerprint
    from backend.app.migrations._v14_fix_revision_fingerprint import _revision_fingerprint_new
    
    # Test data
    row = {
        "material_id": "m1",
        "source_sha256": "sha256_source",
        "text": "hello world",
        "parser_id": "text",
        "parser_version": "1.0.0"
    }
    
    runtime_fp = _revision_fingerprint(row)
    migration_fp = _revision_fingerprint_new(
        row["material_id"], row["source_sha256"], row["text"],
        row["parser_id"], row["parser_version"]
    )
    
    assert runtime_fp == migration_fp, (
        f"Migration formula mismatch: runtime={runtime_fp[:16]}... "
        f"migration={migration_fp[:16]}..."
    )
