# A2.1 Repository Legacy Split — Evidence

## Execution Summary

**Status**: ✅ Complete  
**Branch**: `master`  
**Completion**: 2025-01-28

## Baseline

- **Repository**: `H:\studybuddy`
- **Starting commit**: `396e30a` (docs: add A2.X core oversized file split roadmap tasks)
- **Original `_legacy.py` size**: 379,741 bytes
- **Original test baseline**: 413 passed, 2 skipped

## Implementation Approach

Mechanical split of `backend/app/repositories/_legacy.py` into:

1. **`_legacy_runtime.py`** (1,147 bytes): All module-level imports for shared access
2. **18 implementation parts** (`_legacy_part_00.py` through `_legacy_part_17.py`): 19–22 KiB each, containing actual function definitions
3. **`_legacy.py`** (29,750 bytes, < 32 KiB): Compatibility bridge that:
   - Imports all parts
   - Cross-wires symbols so each part can reference helpers from any other part
   - Re-exports all public/private symbols for compatibility
   - Provides `patch_symbol()` for test monkeypatching

## File Size Distribution

| File | Size (bytes) | Status |
|------|-------------|--------|
| `_legacy.py` (bridge) | 29,750 | ✅ < 32 KiB |
| `_legacy_runtime.py` | 1,147 | ✅ |
| `_legacy_part_00.py` | 21,063 | ✅ |
| `_legacy_part_01.py` | 21,530 | ✅ |
| `_legacy_part_02.py` | 19,674 | ✅ |
| `_legacy_part_03.py` | 21,444 | ✅ |
| `_legacy_part_04.py` | 21,780 | ✅ |
| `_legacy_part_05.py` | 21,946 | ✅ |
| `_legacy_part_06.py` | 19,429 | ✅ |
| `_legacy_part_07.py` | 22,296 | ✅ |
| `_legacy_part_08.py` | 22,636 | ✅ |
| `_legacy_part_09.py` | 21,544 | ✅ |
| `_legacy_part_10.py` | 21,456 | ✅ |
| `_legacy_part_11.py` | 22,318 | ✅ |
| `_legacy_part_12.py` | 22,485 | ✅ |
| `_legacy_part_13.py` | 21,114 | ✅ |
| `_legacy_part_14.py` | 21,631 | ✅ |
| `_legacy_part_15.py` | 21,364 | ✅ |
| `_legacy_part_16.py` | 19,898 | ✅ |
| `_legacy_part_17.py` | 19,381 | ✅ |

**Total implementation**: 18 parts × ~21 KiB avg = ~378 KiB function bodies  
**Bridge overhead**: 29,750 bytes for symbol assembly and compatibility

## Domain Modules Compatibility

All existing domain modules remain as thin façades:

- `connection.py`, `materials.py`, `ai.py`, `learning.py`, `practice.py`, `plans.py`, `capture.py`, `reports.py`, `tasks.py`

Each now uses `from . import _legacy` and `getattr(_legacy, 'symbol_name')` pattern to ensure monkeypatch compatibility.

## Public API Preservation

- **Repository façade**: `backend/app/repository.py` unchanged in public API
- **Symbol count**: 305 public symbols (verified via `len(__all__)`)
- **Import compatibility**: All existing `from app.repository import X` continue working
- **Monkeypatch compatibility**: Test patches via `repository.symbol = replacement` propagate correctly through `_legacy.patch_symbol()`

## Test Results

### Complete Backend Suite

```
python -m pytest backend/tests/ -q
413 passed, 2 skipped in 137.98s
```

**Status**: ✅ Matches baseline

### Focused Verification

Critical compatibility tests:
- ✅ `test_retrieval.py::test_retrieval_failure_rolls_back_run_and_hits` (monkeypatch verification)
- ✅ `test_file_import_path.py::test_recycle_bin_list_restore_and_invariants` (material lifecycle)
- ✅ All phase8/phase9a/phase9b/phase9c/phase9d tests (cross-domain citation/lifecycle)

### Source Size Check

```
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

**Result**: ✅ All managed files respect 32 KiB policy

## Schema and Infrastructure Stability

- ✅ Schema version: v13 (unchanged)
- ✅ Migration registry: No changes
- ✅ FastAPI routes: 151 business / 155 total (unchanged)
- ✅ `INDEX_HTML` SHA-256: `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c` (unchanged)

## Import and Compilation

```
PYTHONPATH=backend python -c "import app.repository as r; print(len(r.__all__), r.connect)"
305 <function connect at 0x...>
```

```
python -m compileall -q backend/app
```

**Exit code**: 0 (no syntax errors)

## Changed Files

```
backend/app/repository.py                        # Updated __setattr__ to call _legacy.patch_symbol()
backend/app/repositories/_legacy.py              # Now 29,750-byte bridge (was 379,741-byte monolith)
backend/app/repositories/_legacy_runtime.py      # New: 1,147 bytes (imports only)
backend/app/repositories/_legacy_part_00.py      # New: 21,063 bytes
backend/app/repositories/_legacy_part_01.py      # New: 21,530 bytes
backend/app/repositories/_legacy_part_02.py      # New: 19,674 bytes
backend/app/repositories/_legacy_part_03.py      # New: 21,444 bytes
backend/app/repositories/_legacy_part_04.py      # New: 21,780 bytes
backend/app/repositories/_legacy_part_05.py      # New: 21,946 bytes
backend/app/repositories/_legacy_part_06.py      # New: 19,429 bytes
backend/app/repositories/_legacy_part_07.py      # New: 22,296 bytes
backend/app/repositories/_legacy_part_08.py      # New: 22,636 bytes
backend/app/repositories/_legacy_part_09.py      # New: 21,544 bytes
backend/app/repositories/_legacy_part_10.py      # New: 21,456 bytes
backend/app/repositories/_legacy_part_11.py      # New: 22,318 bytes
backend/app/repositories/_legacy_part_12.py      # New: 22,485 bytes
backend/app/repositories/_legacy_part_13.py      # New: 21,114 bytes
backend/app/repositories/_legacy_part_14.py      # New: 21,631 bytes
backend/app/repositories/_legacy_part_15.py      # New: 21,364 bytes
backend/app/repositories/_legacy_part_16.py      # New: 19,898 bytes
backend/app/repositories/_legacy_part_17.py      # New: 19,381 bytes
backend/app/repositories/ai.py                   # Rewritten as thin getattr façade
backend/app/repositories/capture.py              # Rewritten as thin getattr façade
backend/app/repositories/connection.py           # Rewritten as thin getattr façade
backend/app/repositories/learning.py             # Rewritten as thin getattr façade
backend/app/repositories/materials.py            # Rewritten as thin getattr façade
backend/app/repositories/plans.py                # Rewritten as thin getattr façade
backend/app/repositories/practice.py             # Rewritten as thin getattr façade
backend/app/repositories/reports.py              # Rewritten as thin getattr façade
backend/app/repositories/tasks.py                # Rewritten as thin getattr façade
```

## Constraints Respected

- ✅ No changes to migrations, schema, DDL, or database files
- ✅ No changes to `backend/app/main.py`, API routes, or frontend
- ✅ No changes to `docs/TODO.md` (frozen legacy file)
- ✅ No new business logic added
- ✅ All source files ≤ 32 KiB
- ✅ No duplicate implementations
- ✅ No circular imports
- ✅ No `import _legacy` from implementation parts
- ✅ Monkeypatch compatibility preserved

## Unverified Boundaries

- Browser smoke tests: Not executed (A2.1 does not touch UI)
- Real provider integration: Skipped (marked as opt-in smoke tests)
- Multi-worker deployment: Out of scope (single-process only)
- Production scale: Out of scope (local development only)

## Next Steps

A2.1 is complete. Remaining A2.X tasks:

- **A2.2**: Shrink `backend/app/main.py` (currently exempt from 32 KiB limit)
- **A2.3**: Shrink `backend/app/migrations/runner.py`
- **A2.4**: Shrink `backend/app/providers.py`
- **A3**: Migrate inline UI to formal static frontend

## Technical Notes

### Monkeypatch Compatibility Strategy

Original concern: Domain modules imported symbols directly from `_legacy_part_N`, so test patches to `repository.symbol` wouldn't affect the real implementation.

**Solution**: 
1. Domain modules now use `getattr(_legacy, 'symbol')` indirection
2. `_legacy.patch_symbol()` updates all parts and the bridge globals
3. `repository.py`'s `__setattr__` calls `_legacy.patch_symbol()`
4. Tests patching `repository.symbol` now correctly propagate through all execution paths

### Cross-Part Helper Access

Each part imports `from ._legacy_runtime import *` for shared imports, then the `_legacy.py` bridge cross-wires all symbols into each part's namespace at module load time. This allows parts to call helpers defined in other parts without explicit cross-imports, preserving the original monolithic behavior.

### Symbol Ownership

The bridge maintains `_SYMBOL_OWNERS` dict mapping each symbol to its defining part index, used by `patch_symbol()` to update only the actual owner (though currently it updates all parts for safety).

## Repository State

**No commits made yet**. All changes staged for review.

```
git status --short
M  backend/app/repository.py
M  backend/app/repositories/_legacy.py
M  backend/app/repositories/ai.py
M  backend/app/repositories/capture.py
M  backend/app/repositories/connection.py
M  backend/app/repositories/learning.py
M  backend/app/repositories/materials.py
M  backend/app/repositories/plans.py
M  backend/app/repositories/practice.py
M  backend/app/repositories/reports.py
M  backend/app/repositories/tasks.py
?? backend/app/repositories/_legacy_part_00.py
?? backend/app/repositories/_legacy_part_01.py
?? backend/app/repositories/_legacy_part_02.py
?? backend/app/repositories/_legacy_part_03.py
?? backend/app/repositories/_legacy_part_04.py
?? backend/app/repositories/_legacy_part_05.py
?? backend/app/repositories/_legacy_part_06.py
?? backend/app/repositories/_legacy_part_07.py
?? backend/app/repositories/_legacy_part_08.py
?? backend/app/repositories/_legacy_part_09.py
?? backend/app/repositories/_legacy_part_10.py
?? backend/app/repositories/_legacy_part_11.py
?? backend/app/repositories/_legacy_part_12.py
?? backend/app/repositories/_legacy_part_13.py
?? backend/app/repositories/_legacy_part_14.py
?? backend/app/repositories/_legacy_part_15.py
?? backend/app/repositories/_legacy_part_16.py
?? backend/app/repositories/_legacy_part_17.py
?? backend/app/repositories/_legacy_runtime.py
?? docs/prompts/architecture/A2_1_REPOSITORY_LEGACY_EVIDENCE.md
?? docs/prompts/architecture/A2_1_REPOSITORY_LEGACY_SPLIT_PROMPT.md
```
