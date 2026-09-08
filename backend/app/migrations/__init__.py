"""数据库迁移包。

导出迁移系统的公共 API：
- CURRENT_SCHEMA_VERSION: 当前 Schema 版本（14）
- MigrationError: 迁移错误异常
- MigrationResult: 迁移执行结果
- migrate(): 执行迁移
- schema_version(): 读取已记录版本

版本迁移脚本在 _v01 到 _v14 模块中，由 runner.py 注册和调度。
"""
from .runner import (CURRENT_SCHEMA_VERSION, MigrationError, MigrationResult,
                     migrate, schema_version)

__all__ = ["CURRENT_SCHEMA_VERSION", "MigrationError", "MigrationResult", "migrate", "schema_version"]
