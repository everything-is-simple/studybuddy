# P14-P0-05 修复总结

## 问题描述

当两个材料上传相同内容时，它们共享同一个 `source_sha256`（这是正常的，符合原始存储去重设计）。但在建立 AI 索引时，`material_revisions` 表的 `revision_fingerprint` 只包含 `(source_sha256, extraction_sha256, parser_id, parser_version)` 四元组，不包含 `material_id`。这导致第二个材料无法创建自己的 revision 记录，因为会违反 UNIQUE 约束。

**影响**：两个内容相同的材料只有第一个能建立 AI 索引，第二个会静默失败。

## 解决方案

### Migration v14: 原地更新指纹公式

**策略**：
- 不重建表，不添加新列
- 直接 UPDATE 所有 `revision_fingerprint` 值，使用新公式：`(material_id, source_sha256, extraction_sha256, parser_id, parser_version)`
- 保留现有 UNIQUE 约束在同一列上
- 完全可回滚：用旧公式重新计算即可

**优势**：
- 无数据丢失风险（无 DROP TABLE，无 CASCADE）
- 无 schema 分歧（升级后的数据库与新安装完全一致）
- 简单高效（单条 UPDATE 语句）
- 可测试性强（fingerprint 计算是纯函数）

**关键修复**：
- 修正了运行时代码中的分隔符 bug：从字面量 4 字符 `"\\x1f"` 改为实际控制字符 `"\x1f"`
- Migration 使用与运行时完全一致的公式（带测试验证）

## 测试覆盖

### 新增专项测试 (`test_p14_p0_05_revision_fingerprint_fix.py`)
1. ✅ `test_migration_14_updates_fingerprints_in_place` - 验证指纹原地更新
2. ✅ `test_migration_14_rollback_restores_old_formula` - 验证可回滚
3. ✅ `test_shared_content_different_materials_after_fix` - 验证相同内容的材料获得不同指纹
4. ✅ `test_migration_14_preserves_dependent_data` - 验证不丢失 chunks/embeddings
5. ✅ `test_migration_formula_matches_runtime` - 验证 migration 公式与运行时一致

### 更新现有集成测试
- ✅ `test_shared_hash_both_materials_can_be_indexed_after_fix` - 验证两个材料都能建立索引
- ✅ `test_revision_fingerprint_conflict_error_mapping_exists` - 验证错误映射仍然存在

### 全量测试结果
```
488 passed, 3 skipped
```

所有 schema version 相关断言已更新至 v14。

## 文件变更

### 新增
- `backend/app/migrations/_v14_fix_revision_fingerprint.py` - migration 实现
- `backend/tests/test_p14_p0_05_revision_fingerprint_fix.py` - 专项测试

### 修改
- `backend/app/migrations/runner.py` - 注册 v14，更新 CURRENT_SCHEMA_VERSION = 14
- `backend/app/repositories/_legacy_part_14.py` - 修复分隔符 bug（`"\\x1f"` → `"\x1f"`）
- `docs/MIGRATIONS.md` - 更新至 v14，添加 v14 说明
- `backend/tests/test_p1_4_real_input_chain.py` - 更新注释
- 10+ 测试文件 - 更新 schema version 断言从 13 到 14

### 删除
- 移除了之前的三阶段 migration 方案（v14/v15/v16），因为发现会触发 CASCADE 数据丢失

## 验证方式

1. 单元测试全通过（5 个新增 + 2 个集成）
2. 全量后端测试通过（488 passed）
3. 源代码大小检查通过
4. Migration 公式与运行时代码完全一致（有测试保证）

## 升级影响

- **数据安全**：无丢失风险，原地 UPDATE，无表重建
- **向后兼容**：可回滚，只需重新计算指纹
- **性能**：升级时间与 revision 数量线性相关，通常秒级
- **用户可见变化**：现有材料的指纹会变化，但不影响功能（chunks/citations 通过 revision_id FK 关联）

## 技术债务清理

修复了运行时代码中的隐藏 bug：
- `_revision_fingerprint()` 使用字面量 4 字符串 `"\\x1f"` 而非真正的 ASCII 0x1F 分隔符
- 这个 bug 在单材料场景下不可见，但会导致 migration 回填的指纹与运行时计算不匹配
- 现已统一为真正的控制字符 `"\x1f"`
