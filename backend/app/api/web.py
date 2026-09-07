"""Web 路由模块。

提供前端页面路由和重定向，包括：
- 根路径重定向到新版静态前端
- Favicon 处理
- 遗留嵌入式 UI 兼容路由

这些路由不包含在 OpenAPI schema 中（前端资源，非 API）。
"""

from __future__ import annotations

from fastapi.responses import HTMLResponse, RedirectResponse, Response


def register_routes(app, context: dict[str, object]) -> None:
    """注册 Web 前端路由。
    
    Args:
        app: FastAPI 应用实例
        context: 路由上下文字典（包含共享的辅助函数和常量）
        
    Returns:
        更新后的上下文字典（本模块未添加新的上下文项）
    """
    globals().update({name: value for name, value in context.items() if not name.startswith("__")})
    
    @app.get("/", response_class=RedirectResponse, include_in_schema=False)
    def root_redirect():
        """将根路径重定向到新版静态前端首页。
        
        Returns:
            302 重定向到 /app/today.html
        """
        return RedirectResponse(url="/app/today.html", status_code=302)
    
    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        """处理 favicon 请求。
        
        Returns:
            204 No Content（StudyBuddy 不提供 favicon）
        """
        return Response(status_code=204)

    @app.get("/legacy", response_class=HTMLResponse, include_in_schema=False)
    def legacy_ui() -> str:
        """提供遗留嵌入式 UI（兼容性路由）。
        
        Returns:
            完整的 HTML 页面字符串（INDEX_HTML 常量）
            
        Note:
            此路由用于向后兼容，新开发应使用 /app/ 下的静态前端。
        """
        return INDEX_HTML
    
    return context
