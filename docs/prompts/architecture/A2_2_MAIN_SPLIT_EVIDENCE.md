# A2.2 Main.py Split — Evidence

## Execution Summary

**Status**: ✅ Complete  
**Branch**: `master`  
**Completion**: 2025-01-28

## Baseline

- **Repository**: `H:\studybuddy`
- **Starting commit**: `2a3602a` (docs: add A2.2 main.py split prompt)
- **Original `main.py` size**: 156,889 bytes (233 lines)
- **Original test baseline**: 413 passed, 2 skipped

## Implementation Approach

Extracted the large INDEX_HTML constant (146,610 bytes) from `main.py` into a separate template file:

**Method**: Template File Extraction (Recommended Approach)

1. Created `backend/app/templates/` directory
2. Extracted INDEX_HTML content to `backend/app/templates/index.html`
3. Updated `main.py` to load INDEX_HTML from the template file at import time
4. Verified byte-for-byte content integrity via SHA-256

## File Changes

### Before

```
backend/app/main.py: 156,889 bytes (233 lines)
- Lines 1-10: imports and module setup
- Lines 11-213: INDEX_HTML constant (146,610 bytes)
- Lines 214-233: compatibility exports (~544 bytes)
```

### After

```
backend/app/main.py: 969 bytes (35 lines)
backend/app/templates/index.html: 156,067 bytes (146,557 bytes content)
```

**Reduction**: 156,889 → 969 bytes (155,920 bytes removed, 99.4% reduction)

## Content Verification

### INDEX_HTML SHA-256

**Expected**: `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`  
**Actual**: `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c`  
**Match**: ✅ Verified

The HTML content is byte-for-byte identical. All inline styles, scripts, ARIA attributes, and page behavior are preserved.

## Compatibility Preservation

### Python Module Exports

- ✅ `from app.main import INDEX_HTML` — works
- ✅ `from app.main import create_app` — works
- ✅ `from app.main import app` — works
- ✅ `app.routes` — 155 routes preserved

### CLI and Startup

```powershell
cd backend
python -m app --help
```

**Result**: ✅ CLI works correctly

### Import Smoke Test

```python
import sys
sys.path.insert(0, 'backend')
from app.main import INDEX_HTML, create_app, app
import hashlib

sha = hashlib.sha256(INDEX_HTML.encode('utf-8')).hexdigest()
# sha == '1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c'
# len(app.routes) == 155
```

**Result**: ✅ All imports work, SHA-256 matches, routes preserved

## Updated Files

```
backend/app/main.py                          # 156,889 → 969 bytes
backend/app/templates/index.html             # New: 156,067 bytes
backend/scripts/check-source-size.py         # Updated _main_html_sha256() logic
docs/prompts/architecture/A2_2_MAIN_SPLIT_PROMPT.md  # Fixed broken link
```

### main.py New Structure

```python
"""Backward-compatible FastAPI application entrypoint."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from . import app_factory
from .api.registration import ROUTE_MODULES


# Load INDEX_HTML from template file for backward compatibility
_template_path = Path(__file__).parent / "templates" / "index.html"
INDEX_HTML = _template_path.read_text(encoding="utf-8")


def create_app(config=None):
    return app_factory.create_app(config, index_html=INDEX_HTML)


# Preserve all existing app.main imports and monkeypatch targets.
for _name in dir(app_factory):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(app_factory, _name))


class _FacadeModule(types.ModuleType):
    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        app_factory.update_route_dependency(name, value)


sys.modules[__name__].__class__ = _FacadeModule
app = create_app()
```

### check-source-size.py Update

Updated `_main_html_sha256()` function to read from `templates/index.html` instead of parsing AST:

```python
def _main_html_sha256(path: Path) -> str | None:
    # INDEX_HTML is now loaded from templates/index.html
    template_path = path.parent / "templates" / "index.html"
    if not template_path.exists():
        return None
    content = template_path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

## Test Results

### Compilation

```
python -m compileall -q backend/app
```

**Result**: ✅ No syntax errors

### Source Size Check

```
python backend/scripts/check-source-size.py --main-html-sha256 1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c
```

**Result**: ✅ `source-size check passed: changed managed files respect the 32768-byte policy`

### Complete Backend Suite

```
python -m pytest backend/tests/ -q
```

**Result**: ✅ **413 passed, 2 skipped in 130.80s**

Matches baseline exactly.

### Focused Smoke Tests

- ✅ `test_file_import_path.py` — 28 passed
- ✅ `test_governance_consistency.py::test_markdown_relative_links_resolve_after_document_moves` — passed

## Schema and Infrastructure Stability

- ✅ Schema version: v13 (unchanged)
- ✅ Migration registry: No changes
- ✅ FastAPI routes: 155 total (unchanged)
- ✅ `INDEX_HTML` SHA-256: `1e111288010b473ae660c7446be6e1997659d49e0b705fea7ae98916621b728c` (unchanged)

## Constraints Respected

- ✅ No changes to migrations, schema, DDL, or database files
- ✅ No changes to API routes, request/response formats, or error codes
- ✅ No changes to HTML structure, CSS styles, or JavaScript logic
- ✅ No changes to ARIA attributes, accessibility semantics, or keyboard navigation
- ✅ All source files ≤ 32 KiB (`main.py` now 969 bytes)
- ✅ No frontend framework introduced (React/Vue/Vite)
- ✅ Backward compatibility preserved for all imports

## Benefits

1. **Size Compliance**: `main.py` reduced from 156,889 to 969 bytes, now compliant with 32 KiB policy
2. **Separation of Concerns**: HTML template separated from Python application code
3. **A3 Preparation**: Template file structure prepares for future static frontend migration
4. **Maintainability**: Easier to inspect and modify HTML without navigating Python code
5. **Testing**: Browser tests can reference HTML file directly if needed

## Unverified Boundaries

- Browser smoke tests: Not executed in this change (main.py is backend-only change)
- Real provider integration: Skipped (marked as opt-in smoke tests)
- Multi-worker deployment: Out of scope (single-process only)
- Production scale: Out of scope (local development only)

## Next Steps

A2.2 is complete. Remaining A2.X tasks:

- **A2.3**: Shrink `backend/app/migrations/runner.py` (68,846 bytes → ≤ 32 KiB)
- **A2.4**: Shrink `backend/app/providers.py` (33,593 bytes → ≤ 32 KiB)
- **A3**: Migrate inline UI to formal static frontend

## Technical Notes

### Template File vs. Constant Modules

We chose the template file approach (recommended in the prompt) over splitting into constant modules because:

1. Cleaner separation: HTML is naturally a template, not Python code
2. Tool compatibility: HTML files can be inspected with standard HTML tools
3. Future-proof: Easier to migrate to static frontend serving in A3
4. Size policy: `.html` files are not subject to Python source size checks

### Import-Time Loading

INDEX_HTML is loaded at module import time, not on each request. This means:

- The template is read once when `app.main` is first imported
- Runtime performance is identical to the previous inline constant
- Changes to `index.html` require process restart to take effect
- This is acceptable for the current single-process development deployment

### Path Resolution

The template path uses `Path(__file__).parent / "templates" / "index.html"`:

- Resolves correctly regardless of working directory
- No hardcoded absolute paths
- Works in development, testing, and packaged deployments

## Repository State

All changes committed and will be pushed:

```
M  backend/app/main.py
M  backend/scripts/check-source-size.py
M  docs/prompts/architecture/A2_2_MAIN_SPLIT_PROMPT.md
A  backend/app/templates/index.html
```
