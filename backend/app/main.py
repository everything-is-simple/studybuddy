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
