"""应用生命周期 - 启动预检到就绪的完整门控。

本模块实现 FastAPI lifespan，确保在持久存储可用之前
不暴露就绪的服务。

启动序列：
1. preflight(): 验证配置和存储拓扑
2. InstanceLock: 获取实例锁（防多进程共写 data_root）
3. 数据库连接验证（触发迁移引擎的版本检查）
4. run_audit(): 数据库健康审计（结果存入 app.state.audit_reasons）
5. reconcile(): 启动对账（清理残留、恢复中断任务）
6. ready = True，发出 startup_ready 事件
7. yield 服务请求
8. 关闭：释放实例锁，ready = False

失败处理：
- 任何一步失败都会阻止服务就绪（fail-fast）
- 预检/锁/数据库错误都转换为 StartupPreflightError
- 所有阶段记录指标和结构化事件

就绪状态：
- app.state.ready: 就绪标志（供健康检查读取）
- app.state.startup_state: starting/ready/stopped
- app.state.audit_reasons: 审计警告（degraded 时非空）

注意：
- 审计降级不阻止就绪（服务可用但有警告）
- 实例锁在 finally 中释放（异常路径也安全）
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import AppConfig
from .db_audit import run_audit
from .instance_lock import InstanceLock, InstanceLockError
from .migrations.runner import MigrationError
from .observability import emit_event, increment
from .recovery import reconcile
from .repository import connect
import sqlite3
from .startup_preflight import StartupPreflightError, preflight

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器（启动门控 + 关闭清理）。
    
    在持久存储可用之前不暴露就绪服务。执行预检、
    实例锁、数据库验证、审计和对账，全部通过后
    才设置 ready=True 并开始服务请求。
    
    Args:
        app: FastAPI 应用实例（state.config 必须已设置）
    
    Raises:
        StartupPreflightError: 预检失败、锁被占用
                              或数据库不可用时
    
    注意:
        - yield 前是启动阶段（失败则服务不启动）
        - yield 后是运行阶段
        - finally 中释放锁（关闭阶段）
    """
    config: AppConfig = app.state.config
    app.state.ready = False
    app.state.startup_state = "starting"
    instance_lock = None
    try:
        preflight(config)
        instance_lock = InstanceLock(config.data_root / ".studybuddy-instance.lock")
        instance_lock.acquire()
        app.state.instance_lock = instance_lock
        increment("startup", "instance_lock", "acquired")
        increment("startup", "preflight", "success")
    except StartupPreflightError as error:
        increment("startup", "preflight", "failed")
        emit_event("startup_preflight_failed", level=40, error_code=str(error))
        raise
    except InstanceLockError as error:
        increment("startup", "instance_lock", "failed")
        emit_event("startup_instance_lock_failed", level=40, error_code=str(error))
        raise StartupPreflightError(str(error)) from None
    try:
        try:
            with connect(config.database_path):
                pass
            increment("startup", "database", "success")
        except MigrationError as error:
            increment("startup", "database", "failed")
            emit_event("startup_database_failed", level=40, error_code=error.code)
            raise StartupPreflightError(error.code) from None
        except (OSError, sqlite3.Error, ValueError):
            increment("startup", "database", "failed")
            emit_event("startup_database_failed", level=40, error_code="database_startup_failed")
            raise StartupPreflightError("database_startup_failed") from None
        audit = run_audit(config.database_path) or {"status": "ok", "reasons": []}
        app.state.audit_reasons = tuple(audit.get("reasons", []))
        increment("startup", "audit", "completed" if audit.get("status") == "ok" else "degraded")
        reconcile(config)
        increment("startup", "recovery", "completed")
        app.state.ready = True
        app.state.startup_state = "ready"
        emit_event("startup_ready", component="startup", outcome="ready")
        yield
    finally:
        app.state.ready = False
        app.state.startup_state = "stopped"
        if instance_lock is not None:
            instance_lock.release()
            increment("startup", "instance_lock", "released")
