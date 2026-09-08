"""StudyBuddy 后端包。

FastAPI 应用包，主要分层：
- api/: REST API 路由层（15 个模块）
- services/: 业务服务层（导入等）
- repositories/: 数据访问层（代理模式，实现在 _legacy）
- providers/: AI Provider 适配层（LLM/Embedding/OCR/ASR）
- migrations/: SQLite Schema 迁移（当前版本 14）
- schemas/: Pydantic 请求/响应模型

核心模块：
- app_factory: FastAPI 应用工厂（create_app）
- lifespan: 启动/关闭生命周期
- config: 环境变量配置
- capabilities: 能力解析（环境 > 设置 > 检测）

入口：
- python -m app: CLI 操作员命令（见 __main__.py）
- uvicorn app.main:app: 启动 HTTP 服务
"""
