"""迁移 v14: 修复修订指纹以包含 material_id。

解决 P14-P0-05: 两个材料内容相同时，旧指纹公式会冲突。
新公式将 material_id 作为第一个哈希分量。

策略：
- 就地 UPDATE 所有 revision_fingerprint 值
- 不重建表，无 CASCADE 风险，可完全回滚
- 更新后验证无重复指纹

本迁移提供 rollback() 函数（唯一一个），可用旧公式重算指纹。

分隔符注意：
运行时实现使用字面字符串 \\x1f（反斜杠+x+1+f 四字符），
而非 ASCII 控制字符 0x1F。本文件必须与
repositories/_legacy_part_14.py 完全一致。
"""
from __future__ import annotations

import hashlib
import sqlite3


def _sha256_text(text: str) -> str:
    """计算文本内容的 SHA256 哈希（与运行时实现一致）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_fingerprint_new(material_id: str, source_sha256: str, text: str,
                               parser_id: str, parser_version: str) -> str:
    """新指纹公式：material_id 作为第一个分量。
    
    重要：分隔符是四字符字面量（反斜杠-x-1-f），而非 ASCII 控制字符 0x1F。
    必须与 repositories/_legacy_part_14.py 的运行时实现完全一致。
    """
    values = (str(material_id), str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    # Use raw string with escaped backslash to match runtime literal
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def _revision_fingerprint_old(source_sha256: str, text: str,
                               parser_id: str, parser_version: str) -> str:
    """旧指纹公式：不含 material_id（P14-P0-05 冲突根因）。"""
    values = (str(source_sha256), _sha256_text(str(text)),
              str(parser_id), str(parser_version))
    return hashlib.sha256("\\x1f".join(values).encode("utf-8")).hexdigest()


def migrate(connection: sqlite3.Connection) -> None:
    """重算所有修订指纹以包含 material_id。
    
    执行流程：
    1. 联表查询所有修订及其源数据
    2. 用新公式逐行更新指纹
    3. 验证无重复指纹（有重复则抛出异常，事务回滚）
    
    Args:
        connection: SQLite 连接
    
    Raises:
        ValueError: 更新后仍有重复指纹时
    """
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
    """回滚：用旧公式（不含 material_id）重算指纹。
    
    Args:
        connection: SQLite 连接
    """
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
