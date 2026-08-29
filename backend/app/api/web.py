from __future__ import annotations

from fastapi.responses import HTMLResponse, RedirectResponse


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    @app.get("/", response_class=RedirectResponse, include_in_schema=False)
    def root_redirect():
        """Redirect root to new static frontend."""
        return RedirectResponse(url="/app/today.html", status_code=302)
    
    @app.get("/legacy", response_class=HTMLResponse, include_in_schema=False)
    def legacy_ui() -> str:
        """Legacy embedded UI for compatibility."""
        return INDEX_HTML
    
    return context
