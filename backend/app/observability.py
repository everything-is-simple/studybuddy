from __future__ import annotations

import contextvars
import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("studybuddy.observability")
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_operation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("operation_id", default=None)
_lock = threading.Lock()
_counters: dict[tuple[str, ...], int] = defaultdict(int)
_durations: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID.fullmatch(value) and not any(ord(c) < 32 for c in value))


def set_correlation(request_id: str, operation_id: str) -> tuple[contextvars.Token, contextvars.Token]:
    return _request_id.set(request_id), _operation_id.set(operation_id)


def reset_correlation(tokens: tuple[contextvars.Token, contextvars.Token]) -> None:
    _request_id.reset(tokens[0])
    _operation_id.reset(tokens[1])


def correlation() -> tuple[str | None, str | None]:
    return _request_id.get(), _operation_id.get()


def increment(metric: str, *labels: str) -> None:
    # Callers provide only fixed, low-cardinality labels. This module never accepts
    # paths, ids, query strings, filenames, or exception text as labels.
    with _lock:
        _counters[(metric, *labels)] += 1


def observe_http(route: str, duration_ms: float) -> None:
    with _lock:
        bucket = _durations[route]
        bucket[0] += duration_ms
        bucket[1] += 1


def metrics_snapshot() -> dict[str, Any]:
    with _lock:
        counters = {".".join(key): value for key, value in sorted(_counters.items())}
        durations = {
            route: {"count": int(values[1]), "total_ms": round(values[0], 3)}
            for route, values in sorted(_durations.items())
        }
    return {
        "scope": "process",
        "persistent": False,
        "counters": counters,
        "http_duration": durations,
    }


def emit_event(event: str, *, level: int = logging.INFO, error_code: str | None = None,
               **fields: str | int | float | bool | None) -> None:
    allowed = {"component", "outcome", "method", "route", "status_class", "duration_ms"}
    payload: dict[str, Any] = {
        "event": event,
        "level": logging.getLevelName(level),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    request_id, operation_id = correlation()
    if request_id:
        payload["request_id"] = request_id
    if operation_id:
        payload["operation_id"] = operation_id
    if error_code:
        payload["error_code"] = error_code
    for key, value in fields.items():
        if key in allowed and value is not None:
            payload[key] = value
    try:
        logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    except Exception:
        # Observability must never block startup or a business request.
        pass


def route_class(path: str) -> str:
    if path == "/api/health":
        return "health"
    if path == "/api/liveness":
        return "liveness"
    if path == "/api/metrics":
        return "metrics"
    if path == "/api/materials":
        return "materials_collection"
    if path == "/api/materials/batch":
        return "materials_batch"
    if path == "/api/materials/export":
        return "materials_export"
    if path.startswith("/api/materials/"):
        return "material_item"
    if path == "/":
        return "index"
    return "other"


def record_import(status: str) -> None:
    normalized = status if status in {"success", "empty", "rejected", "failed"} else "failed"
    increment("imports", normalized)
