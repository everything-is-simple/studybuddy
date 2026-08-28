from __future__ import annotations


def register_routes(app, context: dict[str, object]) -> None:
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML
    return context
