# A2.3：收缩 `backend/app/migrations/runner.py`——迁移函数体分片

> 这是 A2.X 的第三个独立任务。A2.X 总任务见 [`A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md`](A2_X_BOUNDDED_CORE_SPLIT_PROMPT.md)，任务编号和路线位置见 [`../../ROADMAP_CAPABILITIES.md`](../../ROADMAP_CAPABILITIES.md)。

## 1. 执行位置、阶段与目标

请在 `H:\studybuddy` 执行任务 **A2.3**。

当前路线位置：

```text
A0 已完成
→ A1 已完成：repository.py 兼容 façade 与域出口
→ A2 已完成：main.py 后端应用结构拆分
→ A2.1 已完成：收缩 repositories/_legacy.py (379KB → 30KB)
→ A2.2 已完成：收缩 main.py (157KB → 969 bytes)
→ A2.3 当前任务：收缩 migrations/runner.py
→ A2.4：收缩 providers.py
→ A3：正式静态前端与多页原生应用壳
```

当前分支和基线：

- 正式仓库：`H:\studybuddy`
- 当前分支：`master`
- 当前 HEAD：`f1093ae` (refactor: extract INDEX_HTML from main.py to template file (A2.2))
- 远端：`origin/master` 已同步
- 当前正式 schema：**v13**
- 当前迁移历史：v1 至 v13，共 13 个连续版本

本任务只处理一个生产文件及其拆分产物：

```text
backend/app/migrations/runner.py
```

当前大小：

```text
68,846 bytes (1,285 lines)
```

最终目标：

- `runner.py` <= 32 KiB，仅保留迁移执行引擎、registry 和公共 helpers。
- 13 个迁移函数体（`_migration_v1` 至 `_migration_v13`）和相关 DDL helpers 拆分到独立模块。
- 保持 `_MIGRATIONS` registry 的顺序和完整性。
- 保持 `migrate()`, `schema_version()`, `assert_schema_version()` 等公共 API 不变。
- 所有新增或实质重写源码文件不超过 32 KiB，目标 20–30 KiB。

## 2. 已完成结构与当前事实

A2.3 已验证的基线：

- 完整 backend：`413 passed, 2 skipped`
- Schema version：v13
- 迁移历史：v1–v13 连续
- Migration registry：`_MIGRATIONS` 包含 13 个条目
- Public API：`migrate()`, `schema_version()`, `inspect_schema_version()`, `assert_schema_version()`

## 3. 必须保护的不变量

### 3.1 Migration Registry 和执行顺序

必须保持：

- `_MIGRATIONS` 的版本号、名称和顺序完全不变。
- 每个迁移的 DDL、INSERT、UPDATE、CREATE 语句逐字节不变（除非移动到其他模块）。
- `CURRENT_SCHEMA_VERSION = 13` 不变。
- `_check_history()` 的验证逻辑不变。
- v1–v13 的迁移可以在空数据库上从头执行，也可以从任意中间版本升级。

### 3.2 Public API

必须保持：

- `backend.app.migrations.runner.migrate(connection) -> MigrationResult`
- `backend.app.migrations.runner.schema_version(connection) -> int`
- `backend.app.migrations.runner.inspect_schema_version(connection) -> int`
- `backend.app.migrations.runner.assert_schema_version(connection) -> int`
- `backend.app.migrations.runner.MigrationError`
- `backend.app.migrations.runner.MigrationResult`
- `backend.app.migrations.runner.CURRENT_SCHEMA_VERSION`

既有测试、CLI、`app_factory.py`、`lifespan.py` 和 backup/restore 代码依赖这些 API。

### 3.3 Schema 和数据不变

不得：

- 修改任何 migration 的 DDL（CREATE TABLE、ALTER TABLE、CREATE INDEX 等）。
- 新增、删除或重新排序 migration 版本。
- 修改 `schema_migrations` 表结构或 `PRAGMA user_version` 行为。
- 改变 migration 失败时的错误码、rollback 行为或 `IMMEDIATE` 事务语义。
- 在 A2.3 中新增 v14 或修改现有数据库的 schema。

## 4. 当前 `runner.py` 结构分析

### 4.1 文件组成

```text
68,846 bytes, 1,285 lines

主要部分：
1. Imports/constants (lines 1-10): ~300 bytes
2. Classes/helpers (lines 12-286): ~8,000 bytes
   - MigrationError, MigrationResult
   - _now(), _objects(), _columns()
   - _create_history(), _baseline_complete(), _create_canonical_schema(), _create_ai_schema()
3. Migration functions (lines 287-1177): ~50,000 bytes
   - _migration_v1 (v1 = _create_ai_schema wrapper)
   - _migration_v2 through _migration_v13 (actual DDL)
4. Registry and execution (lines 1163-1285): ~10,000 bytes
   - _MIGRATIONS tuple
   - schema_version(), _check_history(), migrate()
   - inspect_schema_version(), assert_schema_version()
```

### 4.2 迁移函数分布

| Version | Function | Lines | Description |
|---------|----------|-------|-------------|
| v1 | `_migration_v1` | 287-289 | Wraps `_create_ai_schema` |
| v1 helper | `_create_ai_schema` | 291-449 | 159 lines DDL |
| v2 | `_migration_v2` | 452-454 | Small |
| v3 | `_migration_v3` | 456-464 | Small |
| v4 | `_migration_v4` | 466-476 | Small |
| v5 | `_migration_v5` | 478-511 | Medium |
| v6 | `_migration_v6` | 513-523 | Small |
| v7 | `_migration_v7` | 525-602 | 78 lines |
| v8 | `_migration_v8` | 605-612 | Small |
| v9 | `_migration_v9` | 614-747 | 134 lines |
| v10 | `_migration_v10` | 750-841 | 92 lines |
| v11 | `_migration_v11` | 1014-1160 | 147 lines |
| v12 | `_migration_v12` | 904-1011 | 108 lines |
| v13 | `_migration_v13` | 844-901 | 58 lines |

**总计**：约 ~890 lines of migration DDL

其他大型 helpers：
- `_baseline_complete`: 193 lines
- `_create_canonical_schema`: 43 lines

## 5. A2.3 工作方式：拆分迁移函数体到独立模块

### 5.1 推荐结构

```text
backend/app/migrations/
  __init__.py                      # 公共 API 导出
  runner.py                        # <= 32 KiB: registry + execution engine
  _helpers.py                      # 共享 helpers: _objects, _columns, _baseline_complete
  _canonical.py                    # _create_canonical_schema
  _v01_canonical_material.py       # _migration_v1 + _create_ai_schema
  _v02_ai_phase0.py                # _migration_v2
  _v03_phase5_provider.py          # _migration_v3
  _v04_qa_idempotency.py           # _migration_v4
  _v05_phase7_embedding.py         # _migration_v5
  _v06_search_index.py             # _migration_v6
  _v07_phase8_cards.py             # _migration_v7
  _v08_exercise_provenance.py      # _migration_v8
  _v09_phase9a_learning_plan.py    # _migration_v9
  _v10_phase9b_material_learning.py # _migration_v10
  _v11_phase9c_feedback.py         # _migration_v11
  _v12_phase9d_extended.py         # _migration_v12
  _v13_phase10_tasks.py            # _migration_v13
```

每个 `_vNN_*.py` 模块：
- 包含一个 `def migrate(connection: sqlite3.Connection) -> None:` 函数（实际 DDL）
- 如有 helper（如 `_create_ai_schema`），包含在同一模块
- <= 32 KiB
- 无需 `__all__`，runner 直接 import

`runner.py` 新结构：
- Import 所有 migration 模块
- 保留 `_MIGRATIONS` registry，指向各模块的 `migrate` 函数
- 保留 `migrate()`, `schema_version()`, `_check_history()` 等执行引擎
- 保留 `MigrationError`, `MigrationResult`, `CURRENT_SCHEMA_VERSION`
- Import helpers from `_helpers.py`

### 5.2 实施步骤

1. **创建 `_helpers.py`**：
   - 移动 `_now()`, `_objects()`, `_columns()`, `_create_history()`
   - 移动 `_baseline_complete()` (193 lines)
   - 每个函数保持原签名

2. **创建 `_canonical.py`**：
   - 移动 `_create_canonical_schema()` (43 lines)

3. **创建 `_v01_canonical_material.py`**：
   - 移动 `_create_ai_schema()` (159 lines)
   - 定义 `def migrate(connection: sqlite3.Connection) -> None:` 调用 `_create_ai_schema(connection)`

4. **创建 `_v02_ai_phase0.py` 至 `_v13_phase10_tasks.py`**：
   - 每个文件包含对应版本的 DDL
   - 每个文件定义 `def migrate(connection: sqlite3.Connection) -> None:`
   - 保持原 DDL 逐字节不变

5. **更新 `runner.py`**：
   - Import helpers: `from ._helpers import _now, _objects, _columns, _create_history, _baseline_complete`
   - Import canonical: `from ._canonical import _create_canonical_schema`
   - Import migrations: `from . import _v01_canonical_material as v01`, etc.
   - 更新 `_MIGRATIONS` registry:
     ```python
     _MIGRATIONS: tuple[tuple[int, str, Callable[[sqlite3.Connection], None]], ...] = (
         (1, "canonical_material_schema", v01.migrate),
         (2, "ai_phase0_schema", v02.migrate),
         # ...
         (13, "phase10_operation_task_schema", v13.migrate),
     )
     ```
   - 保留 `migrate()`, `schema_version()`, `_check_history()`, `inspect_schema_version()`, `assert_schema_version()`
   - 删除已移动的函数定义

6. **更新 `__init__.py`**（如需要）：
   - 确保公共 API 仍可从 `backend.app.migrations.runner` 访问

7. **验证**：
   - Compile check: `python -m compileall -q backend/app`
   - Import smoke: `from backend.app.migrations.runner import migrate, CURRENT_SCHEMA_VERSION`
   - Migration tests: `python -m pytest backend/tests/test_migrations.py -q`
   - Full backend: `python -m pytest backend/tests/ -q`
   - Source size: `python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`

### 5.3 命名约定

Migration 模块命名：
- `_vNN_` 前缀表示版本号（用两位数，如 `_v01_`, `_v02_`）
- 后缀使用 migration 名称的简短描述性词组
- 示例：
  - v1: `_v01_canonical_material.py`
  - v7: `_v07_phase8_cards.py`
  - v9: `_v09_phase9a_learning_plan.py`
  - v13: `_v13_phase10_tasks.py`

### 5.4 Import 策略

`runner.py` 中：
```python
from . import (
    _v01_canonical_material as v01,
    _v02_ai_phase0 as v02,
    _v03_phase5_provider as v03,
    # ...
    _v13_phase10_tasks as v13,
)
```

然后 `_MIGRATIONS` 使用 `v01.migrate`, `v02.migrate` 等。

## 6. 禁止事项

- 不修改任何 migration 的 DDL、INSERT、UPDATE 或 CREATE 语句。
- 不新增 v14 或删除现有版本。
- 不修改 `_MIGRATIONS` registry 的顺序、版本号或名称。
- 不修改 `CURRENT_SCHEMA_VERSION`（除非紧跟新 migration，但 A2.3 不做新 migration）。
- 不修改 `migrate()`, `schema_version()` 等公共 API 的签名或行为。
- 不修改 `_baseline_complete()` 的表/列检查逻辑（除非纯机械移动）。
- 不新增 rollback 逻辑（当前没有 rollback，A2.3 不新增）。
- 不在 A2.3 中修改数据库、运行 migration 或改变 `schema_migrations` 内容。

## 7. 测试和验收

### 7.1 每个变更后

```powershell
python -m compileall -q backend/app
PYTHONPATH=backend python -c "from app.migrations.runner import migrate, CURRENT_SCHEMA_VERSION; print('OK', CURRENT_SCHEMA_VERSION)"
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
git diff --check
```

### 7.2 Migration Tests

```powershell
python -m pytest backend/tests/test_migrations.py -xvs
```

必须通过：
- 从空数据库迁移到 v13
- 从 v1 升级到 v13
- 从 v9 升级到 v13
- Migration history 验证
- Rollback tests（如存在）

### 7.3 最终 A2.3 门禁

必须验证：

1. `runner.py` <= 32 KiB。
2. 所有新 migration 模块 (`_vNN_*.py`) <= 32 KiB。
3. `_helpers.py` <= 32 KiB。
4. `CURRENT_SCHEMA_VERSION == 13`。
5. `_MIGRATIONS` 包含 13 个条目，顺序和名称不变。
6. `migrate()`, `schema_version()`, `inspect_schema_version()`, `assert_schema_version()` 可用。
7. `python -m compileall -q backend/app` 通过。
8. Schema version 仍为 v13。
9. Migration registry 未改变。
10. 完整 backend regression 不低于当前基线：

```powershell
python -m pytest backend/tests/ -q
```

目标：`413 passed, 2 skipped`；若测试数量变化，必须解释变化。

11. Migration-specific tests：

```powershell
python -m pytest backend/tests/test_migrations.py -q
```

必须全部通过。

## 8. 文档、提交和回退

### 8.1 文档

完成后更新：

- `docs/prompts/architecture/A2_3_MIGRATIONS_SPLIT_EVIDENCE.md`
- `docs/ROADMAP_CAPABILITIES.md` 中 A2.3 状态

`docs/TODO.md` 和 `docs/STATUS.md` 是已冻结或超限文件，A2.3 状态记录在 ROADMAP 和 evidence 中。

文档必须明确：

- 最终 `runner.py` 大小和结构。
- 新增 migration 模块列表及各自大小。
- `_MIGRATIONS` registry 完整性验证。
- Compile、import、migration、backend 测试命令和结果。
- 未验证边界。

### 8.2 提交

推荐提交信息：

```text
refactor: split migrations/runner.py into versioned modules (A2.3)
```

提交必须可回退、可解释、通过所有必须门禁。

### 8.3 回退

失败时：

- 只回退当前代码提交；
- 不执行数据库 rollback；
- 不删除 data root、数据库、原件或 verified backup；
- 不手工修改 `schema_migrations` 或 `PRAGMA user_version`；
- 保留脱敏测试结果和 failure evidence；
- 先恢复上一个可运行提交，再分析问题。

## 9. 完成报告格式

最终报告必须包含：

1. A2.3 的实际实施方式。
2. `runner.py` 的初始/最终大小与最终结构。
3. 新增 migration 模块列表及各自大小。
4. `_MIGRATIONS` registry 完整性验证（13 个条目，顺序和名称）。
5. Public API 兼容性验证。
6. Compile、import smoke、源码大小检查结果。
7. Schema/migration/CURRENT_SCHEMA_VERSION 验证结果。
8. Backend/migration 测试的实际命令与结果。
9. Skip 项、未验证边界和残余风险。
10. Commit hash、推送分支和最终 `git status`。

只有在所有门禁真实通过后，才可以将 A2.3 标记为完成，并开始 A2.4。A2.3 完成不代表 A2.X 全部完成，也不代表有新的 schema 版本或 migration 被执行。
