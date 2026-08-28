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
    """Do not expose a ready service until persistent storage is usable."""
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
