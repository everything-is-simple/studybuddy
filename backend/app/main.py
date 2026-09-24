"""Backward-compatible FastAPI application entrypoint."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from . import app_factory
from .api.registration import ROUTE_MODULES


# Load the legacy page from bounded, ordered fragments. The assembled bytes stay
# identical to the former monolithic template for the compatibility route.
_template_dir = Path(__file__).parent / "templates"
_template_parts = [
    _template_dir / "index_head.html",
    *_template_dir.glob("index_script_*.js"),
    _template_dir / "index_tail.html",
]
_template_parts[1:-1] = sorted(_template_parts[1:-1], key=lambda path: path.name)
INDEX_HTML = "".join(path.read_text(encoding="utf-8") for path in _template_parts)


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
