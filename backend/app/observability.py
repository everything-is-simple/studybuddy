"""可观测性基础设施 - 指标、事件和关联 ID 管理。

本模块提供轻量级、进程内的可观测性支持：
- 关联 ID：request_id, operation_id, task_id, project_id
- 计数器：低基数标签计数
- 直方图：HTTP 路由和任务耗时
- 结构化事件日志：JSON 格式

关联 ID：
- request_id: HTTP 请求 ID（每个请求分配）
- operation_id: 操作 ID（与 AI 操作记录关联）
- task_id: 后台任务 ID
- project_id: 项目 ID

指标类型：
- 计数器：increment(metric, *labels)
  - 例：increment('http_requests', 'GET', 'materials_collection', '2xx')
- HTTP 耗时：observe_http(route, duration_ms)
- 任务耗时：observe_task(task_kind, outcome, duration_ms)

事件日志：
- emit_event(event, level=INFO, error_code=None, **fields)
- JSON 格式，包含时间戳和关联 ID
- 允许字段白名单：component, outcome, method, route, status_class 等
- 不包含敏感信息（路径、密钥、用户数据）

设计原则：
- 进程内：不跨进程聚合
- 不持久化：指标仅在内存中
- 低基数：标签必须是固定代码值，不允许动态 ID
- 非阻塞：可观测性从不阻塞业务请求
- 安全：异常被捕获，不泄露到日志

使用场景：
- HTTP 中间件：记录请求指标和耗时
- 任务运行器：记录任务执行指标
- 生命周期事件：startup_complete, shutdown_begin
- 错误跟踪：通过 request_id 关联日志

示例：
    # HTTP 请求
    request_id = new_id('req')
    operation_id = new_id('op')
    tokens = set_correlation(request_id, operation_id)
    try:
        # ... 处理 ...
        increment('http_requests', 'GET', 'materials', '2xx')
        observe_http('materials', 123.4)
        emit_event('http_request', method='GET', status_class='2xx')
    finally:
        reset_correlation(tokens)
    
    # 后台任务
    tokens = set_task_correlation(task_id, operation_id, project_id)
    try:
        # ... 执行 ...
        observe_task('embedding_index', 'succeeded', 5678.9)
    finally:
        reset_task_correlation(tokens)
"""
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
_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("task_id", default=None)
_project_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("project_id", default=None)
_lock = threading.Lock()
_counters: dict[tuple[str, ...], int] = defaultdict(int)
_durations: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
_task_durations: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_LABEL = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def new_id(prefix: str) -> str:
    """生成新的不透明 ID（前缀 + UUID）。
    
    Args:
        prefix: ID 前缀（如 'req', 'op', 'task'）
    
    Returns:
        形如 'req_abc123...' 的 ID
    """
    return f"{prefix}_{uuid.uuid4().hex}"


def valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID.fullmatch(value) and not any(ord(c) < 32 for c in value))


def set_correlation(request_id: str, operation_id: str) -> tuple[contextvars.Token, contextvars.Token]:
    return _request_id.set(request_id), _operation_id.set(operation_id)


def reset_correlation(tokens: tuple[contextvars.Token, contextvars.Token]) -> None:
    _request_id.reset(tokens[0])
    _operation_id.reset(tokens[1])


def set_task_correlation(task_id: str, operation_id: str, project_id: str,
                         request_id: str | None = None) -> tuple[contextvars.Token, ...]:
    """Associate runner events with persisted opaque correlation IDs for this thread only."""
    return (_task_id.set(task_id), _operation_id.set(operation_id),
            _project_id.set(project_id), _request_id.set(request_id))


def reset_task_correlation(tokens: tuple[contextvars.Token, ...]) -> None:
    _task_id.reset(tokens[0])
    _operation_id.reset(tokens[1])
    _project_id.reset(tokens[2])
    _request_id.reset(tokens[3])


def correlation() -> tuple[str | None, str | None]:
    return _request_id.get(), _operation_id.get()


def _safe_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    # Metrics are intentionally low-cardinality. Call sites must use fixed code
    # values, never identifiers, paths, source text, exception text, or secrets.
    if not all(isinstance(label, str) and _LABEL.fullmatch(label) for label in labels):
        return ("invalid_label",)
    return labels


def increment(metric: str, *labels: str) -> None:
    """增加计数器指标。
    
    Args:
        metric: 指标名（如 'http_requests'）
        labels: 标签值（必须是固定代码值，不允许动态 ID）
    
    注意:
        标签必须低基数，不允许使用文件名、路径、用户数据等
    """
    if not isinstance(metric, str) or not _LABEL.fullmatch(metric):
        return
    with _lock:
        _counters[(metric, *_safe_labels(labels))] += 1


def observe_http(route: str, duration_ms: float) -> None:
    if not _LABEL.fullmatch(route) or duration_ms < 0:
        return
    with _lock:
        bucket = _durations[route]
        bucket[0] += duration_ms
        bucket[1] += 1


def observe_task(task_kind: str, outcome: str, duration_ms: float) -> None:
    if not _LABEL.fullmatch(task_kind) or not _LABEL.fullmatch(outcome) or duration_ms < 0:
        return
    with _lock:
        bucket = _task_durations[(task_kind, outcome)]
        bucket[0] += duration_ms
        bucket[1] += 1


def metrics_snapshot() -> dict[str, Any]:
    """获取当前进程的指标快照。
    
    Returns:
        包含 counters, http_duration, task_duration 的字典
    
    注意:
        指标仅在内存中，不跨进程聚合
    """
    with _lock:
        counters = {".".join(key): value for key, value in sorted(_counters.items())}
        durations = {
            route: {"count": int(values[1]), "total_ms": round(values[0], 3)}
            for route, values in sorted(_durations.items())
        }
        task_durations = {
            ".".join(key): {"count": int(values[1]), "total_ms": round(values[0], 3)}
            for key, values in sorted(_task_durations.items())
        }
    return {
        "scope": "process",
        "persistent": False,
        "cross_process_aggregation": False,
        "counters": counters,
        "http_duration": durations,
        "task_duration": task_durations,
    }


def emit_event(event: str, *, level: int = logging.INFO, error_code: str | None = None,
               **fields: str | int | float | bool | None) -> None:
    """发送结构化事件日志（JSON 格式）。
    
    Args:
        event: 事件名（如 'http_request', 'task_finished'）
        level: 日志级别（默认 INFO）
        error_code: 错误码（可选）
        fields: 允许字段（component, outcome, method, route 等）
    
    注意:
        - 关联 ID 自动从上下文填充
        - 异常被捕获，不阻塞业务请求
        - 不包含敏感信息（路径、密钥、用户数据）
    """
    # Event fields are a small, reviewed allowlist. IDs arrive only from the
    # correlation context, never from arbitrary caller input.
    allowed = {"component", "outcome", "method", "route", "status_class", "duration_ms", "retry_count", "lease_state"}
    payload: dict[str, Any] = {
        "event": event if isinstance(event, str) and _LABEL.fullmatch(event) else "invalid_event",
        "level": logging.getLevelName(level),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    request_id, operation_id = correlation()
    if request_id:
        payload["request_id"] = request_id
    if operation_id:
        payload["operation_id"] = operation_id
    if _task_id.get():
        payload["task_id"] = _task_id.get()
    if _project_id.get():
        payload["project_id"] = _project_id.get()
    if error_code and isinstance(error_code, str) and _LABEL.fullmatch(error_code):
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
    if path.startswith("/api/tasks/"):
        return "task_item"
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
