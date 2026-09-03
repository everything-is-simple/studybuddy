"""Migration v14: Fix revision_fingerprint to include material_id.

Resolves P14-P0-05: two materials with identical content now get distinct
revision fingerprints because material_id is included in the hash.

Strategy: in-place UPDATE of all revision_fingerprint values using the new
formula. No table rebuild, no CASCADE risk, fully rollbackable.
"""

from __future__ import annotations

import hashlib
import sqlite3


def _sha256_text(text: str) -> str:
    """Hash text content (same as runtime)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_fingerprint_new(material_id: str, source_sha256: str, text: str,
                               parser_id: str, parser_version: str) -> str:
    """New formula: includes material_id as first component.
    
    IMPORTANT: separator is the 4-character literal string backslash-x-1-f,
    not the actual ASCII control character 0x1F. This matches the runtime
    implementation in backend/app/repositories/_legacy_part_14.py exactly.
    """
    values = (str(material_id), str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    # Use raw string with escaped backslash to match runtime literal
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def _revision_fingerprint_old(source_sha256: str, text: str,
                               parser_id: str, parser_version: str) -> str:
    """Old formula: material_id NOT included (caused P14-P0-05 conflict)."""
    values = (str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def migrate(connection: sqlite3.Connection) -> None:
    """Recompute all revision_fingerprint values to include material_id."""
    # Fetch all revisions with their source data
    rows = connection.execute(
        """
        SELECT mr.id, mr.material_id, mr.source_sha256, e.text, mr.parser_id, mr.parser_version
        FROM material_revisions mr
        JOIN extractions e ON mr.extraction_id = e.id
        """
    ).fetchall()
    
    # Update each row with the new fingerprint
    for row in rows:
        revision_id, material_id, source_sha256, text, parser_id, parser_version = row
        new_fingerprint = _revision_fingerprint_new(
            material_id, source_sha256, text, parser_id, parser_version
        )
        connection.execute(
            "UPDATE material_revisions SET revision_fingerprint = ? WHERE id = ?",
            (new_fingerprint, revision_id)
        )
    
    # Verify no duplicates (should be impossible since old fingerprints were already unique)
    duplicate_check = connection.execute(
        "SELECT revision_fingerprint, COUNT(*) as cnt FROM material_revisions "
        "GROUP BY revision_fingerprint HAVING cnt > 1"
    ).fetchall()
    
    if duplicate_check:
        raise ValueError(f"Migration v14: duplicate fingerprints after update: {duplicate_check}")


def rollback(connection: sqlite3.Connection) -> None:
    """Rollback: recompute fingerprints using the old formula (without material_id)."""
    rows = connection.execute(
        """
        SELECT mr.id, mr.source_sha256, e.text, mr.parser_id, mr.parser_version
        FROM material_revisions mr
        JOIN extractions e ON mr.extraction_id = e.id
        """
    ).fetchall()
    
    for row in rows:
        revision_id, source_sha256, text, parser_id, parser_version = row
        old_fingerprint = _revision_fingerprint_old(
            source_sha256, text, parser_id, parser_version
        )
        connection.execute(
            "UPDATE material_revisions SET revision_fingerprint = ? WHERE id = ?",
            (old_fingerprint, revision_id)
        )
