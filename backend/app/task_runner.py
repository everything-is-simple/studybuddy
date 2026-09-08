"""后台任务运行器 - 单进程任务调度和执行。

本模块提供单进程、单线程的后台任务调度器，用于执行长时间、可取消、
可重试的异步任务（如 Embedding 索引、AI 生成等）。

核心特性：
- 单工作线程：一次只执行一个任务
- 租约机制：任务执行前获取租约，失败后释放
- 心跳维持：处理器可定期延长租约
- 协作取消：处理器检查 cancel_requested 状态
- 失效回收：租约超时的任务自动回收
- 错误重试：支持按错误码白名单重试

任务生命周期：
1. queued: 创建后等待调度
2. running: 获取租约后开始执行
3. succeeded/failed/cancelled: 处理器完成
4. stale: 租约超时或进程退出

主要组件：
- TaskRunner: 任务调度器，管理生命周期和调度
- TaskContext: 任务上下文，提供取消、进度、心跳 API
- TaskHandler: 任务处理器函数类型
- TaskResult: 处理器返回结果
- TaskCancelled/TaskFailed/TaskRunnerError: 异常类型

处理器契约：
- 接受 TaskContext 参数
- 返回 TaskResult | None
- 定期调用 context.raise_if_cancel_requested()
- 定期调用 context.heartbeat() 延长租约
- 可通过 context.progress() 报告进度
- 抓住 TaskCancelled 或抛出 TaskFailed(错误码)

错误处理：
- TaskCancelled: 协作取消，任务标记为 cancelled
- TaskFailed(错误码): 业务错误，任务标记为 failed
- TaskRunnerError: 租约丢失，任务标记为 stale
- 其他异常: 任务标记为 failed，错误码为 'task_handler_failed'

并发控制：
- max_concurrency 固定为 1（单工作线程）
- 每个数据库一个调度锁（_dispatcher_lock）
- 同进程不允许启动多个调度器

示例：
    def my_handler(ctx: TaskContext) -> TaskResult | None:
        ctx.progress(0, 'starting')
        # ... 执行工作 ...
        ctx.raise_if_cancel_requested()
        ctx.heartbeat()
        ctx.progress(100, 'completed')
        return TaskResult(output_artifact_id='artifact_123')
    
    runner = TaskRunner(db_path, lease_seconds=30, max_concurrency=1)
    runner.register('embedding_index', my_handler,
                   retryable_error_codes=frozenset(['provider_timeout']))
    runner.start()
    # ... 应用运行 ...
    runner.shutdown(timeout_seconds=5.0)

注意：
- TaskRunner 从不自动启动，必须显式调用 start()
- shutdown() 不等待不配合的处理器，将其标记为 stale
- 失效任务可通过 retry() 重试（需配置 retryable_error_codes）
- 所有操作通过 SQLite 事务保证原子性
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .observability import (emit_event, increment, observe_task,
                             reset_task_correlation, set_task_correlation)
from .repository import (
    claim_operation_task,
    finish_operation_task,
    get_operation_task,
    heartbeat_operation_task,
    reclaim_stale_operation_tasks,
    request_operation_task_cancel,
    retry_operation_task,
    update_operation_task_progress,
)
from .repository import connect as connect_database

logger = logging.getLogger(__name__)
_runner_locks_guard = threading.Lock()
_runner_locks: dict[str, threading.Lock] = {}

@dataclass(frozen=True)
class TaskResult:
    """任务处理器返回结果。
    
    处理器只返回不透明的、已持久化的制品 ID。
    具体制品内容通过数据库或文件系统查询。
    
    Attributes:
        output_artifact_id: 输出制品 ID（如 embedding 索引版本 ID）
    """
    output_artifact_id: str | None = None


TaskHandler = Callable[["TaskContext"], TaskResult | None]


def _dispatcher_lock(database_path: Path) -> threading.Lock:
    key = str(database_path.resolve())
    with _runner_locks_guard:
        return _runner_locks.setdefault(key, threading.Lock())


@dataclass(frozen=True)
class TaskHandlerPolicy:
    handler: TaskHandler
    retryable_error_codes: frozenset[str]


class TaskRunnerError(ValueError):
    """任务运行器错误（配置错误、租约丢失等）。
    
    Args:
        code: 错误码（如 'task_lease_lost'）
    """
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TaskCancelled(Exception):
    """任务取消异常 - 处理器在协作取消安全点后抛出。
    
    处理器应定期调用 context.raise_if_cancel_requested() 检查取消。
    """


class TaskFailed(Exception):
    """任务失败异常 - 处理器抛出稳定的、非敏感业务错误码。
    
    Args:
        code: 业务错误码（如 'embedding_provider_unavailable'）
    
    注意:
        错误码不应包含敏感信息（密钥、路径、用户数据等）
    """
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TaskContext:
    """任务执行上下文 - 提供取消、进度、心跳 API。
    
    处理器通过这个上下文与调度器通信，报告进度和检查取消。
    
    Attributes:
        task_id: 任务 ID
        attempt_id: 尝试 ID（同一任务可有多次尝试）
        project_id: 项目 ID
        operation_id: 操作 ID（关联到 ai_operations）
        task_kind: 任务类型（如 'embedding_index'）
    
    方法：
        cancel_requested(): 检查是否有取消请求
        raise_if_cancel_requested(): 如有取消请求则抛出 TaskCancelled
        progress(percent, stage_code): 报告进度
        heartbeat(): 延长租约（长任务应定期调用）
    """
    task_id: str
    attempt_id: str
    project_id: str
    operation_id: str
    task_kind: str
    _database_path: Path
    _lease_seconds: int

    def _task_status(self) -> str:
        with connect_database(self._database_path) as connection:
            return str(get_operation_task(connection, task_id=self.task_id)["status"])

    def cancel_requested(self) -> bool:
        """检查是否有取消请求。
        
        Returns:
            True 表示有取消请求
        """
        return self._task_status() == "cancel_requested"

    def raise_if_cancel_requested(self) -> None:
        """如有取消请求则抛出 TaskCancelled 异常。
        
        处理器应在关键操作间定期调用此方法。
        
        Raises:
            TaskCancelled: 当任务被请求取消时
        """
        if self.cancel_requested():
            raise TaskCancelled()

    def progress(self, progress_percent: int | None, stage_code: str) -> None:
        """报告任务进度。
        
        Args:
            progress_percent: 进度百分比（0-100，或 None 表示不确定）
            stage_code: 阶段代码（如 'downloading', 'processing'）
        
        Raises:
            TaskRunnerError: 租约已丢失时
        """
        with connect_database(self._database_path) as connection:
            if not update_operation_task_progress(
                connection, task_id=self.task_id, attempt_id=self.attempt_id,
                progress_percent=progress_percent, stage_code=stage_code,
            ):
                raise TaskRunnerError("task_lease_lost")

    def heartbeat(self) -> None:
        """延长任务租约（心跳保活）。
        
        长时间运行的处理器应定期调用此方法，防止租约超时。
        
        Raises:
            TaskRunnerError: 租约已丢失时
        """
        with connect_database(self._database_path) as connection:
            if not heartbeat_operation_task(
                connection, task_id=self.task_id, attempt_id=self.attempt_id,
                lease_seconds=self._lease_seconds,
            ):
                raise TaskRunnerError("task_lease_lost")


class TaskRunner:
    """显式、单进程任务调度器 - 从不自动启动。
    
    单工作线程调度器，轮询数据库获取 queued 任务并执行。
    支持协作取消、租约维持、失效回收、错误重试。
    
    生命周期：
        1. 构造器：配置参数
        2. register(): 注册任务类型和处理器
        3. start(): 启动调度循环
        4. 运行中：cancel()/retry() 管理任务
        5. shutdown(): 停止调度器
    
    Args:
        database_path: SQLite 数据库路径
        lease_seconds: 租约时长（默认 30 秒）
        poll_interval_seconds: 轮询间隔（默认 0.1 秒）
        max_concurrency: 并发数（固定为 1）
    
    注意:
        - 必须显式调用 start()，不会自动启动
        - 同进程不允许多个调度器实例
        - shutdown() 不等待不配合的处理器
    """
    def __init__(self, database_path: Path, *, lease_seconds: int = 30,
                 poll_interval_seconds: float = 0.1, max_concurrency: int = 1):
        if lease_seconds < 1 or poll_interval_seconds <= 0 or max_concurrency != 1:
            raise TaskRunnerError("task_runner_invalid_config")
        self._database_path = Path(database_path)
        self._lease_seconds = lease_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._handlers: dict[str, TaskHandlerPolicy] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._dispatch_lock = _dispatcher_lock(self._database_path)
        self._active_task_id: str | None = None

    def register(self, task_kind: str, handler: TaskHandler, *,
                 retryable_error_codes: frozenset[str] = frozenset()) -> None:
        """注册任务类型和处理器。
        
        Args:
            task_kind: 任务类型（如 'embedding_index'）
            handler: 处理器函数，签名为 (TaskContext) -> TaskResult | None
            retryable_error_codes: 可重试错误码集合
        
        Raises:
            TaskRunnerError: 参数无效或重复注册时
        """
        if (not task_kind or not callable(handler) or
                any(not code or len(code) > 100 for code in retryable_error_codes)):
            raise TaskRunnerError("task_handler_invalid")
        if task_kind in self._handlers:
            raise TaskRunnerError("task_handler_already_registered")
        self._handlers[task_kind] = TaskHandlerPolicy(handler, retryable_error_codes)

    def cancel(self, task_id: str) -> str:
        """请求取消任务（协作取消）。
        
        将任务状态设为 'cancel_requested'，处理器应检查并响应。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            新状态（'cancel_requested'）
        """
        with connect_database(self._database_path) as connection:
            return request_operation_task_cancel(connection, task_id=task_id)

    def retry(self, task_id: str) -> dict[str, object]:
        """重试失败的任务（仅允许白名单错误码）。
        
        Args:
            task_id: 任务 ID
        
        Returns:
            更新后的任务状态
        
        Raises:
            TaskRunnerError: 任务不存在、未注册或错误码不可重试时
        """
        with connect_database(self._database_path) as connection:
            task = get_operation_task(connection, task_id=task_id)
            policy = self._handlers.get(str(task["task_kind"]))
            if policy is None:
                raise TaskRunnerError("task_retry_not_allowed")
            try:
                return retry_operation_task(
                    connection, task_id=task_id,
                    retryable_error_codes=set(policy.retryable_error_codes),
                )
            except ValueError as error:
                raise TaskRunnerError(str(error)) from None

    def start(self) -> None:
        """启动后台调度线程。
        
        创建守护线程，循环轮询和执行任务。
        
        Raises:
            TaskRunnerError: 调度器已启动时
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise TaskRunnerError("task_runner_already_started")
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="studybuddy-task-runner", daemon=True)
            self._thread.start()

    def shutdown(self, timeout_seconds: float = 5.0) -> None:
        """停止后台调度线程。
        
        等待当前任务完成，超时后强制退出。
        不配合的处理器被标记为 stale。
        
        Args:
            timeout_seconds: 等待超时（默认 5 秒）
        
        注意:
            不等待不配合的处理器，其尝试被标记为 stale
        """
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, timeout_seconds))
        # A handler that cannot stop remains outside the local runner's ownership.
        # Its attempt is deliberately marked stale, not falsely cancelled/succeeded.
        with connect_database(self._database_path) as connection:
            self._mark_active_stale(connection, "task_runner_shutdown")
        with self._lock:
            # An uncooperative handler may still be unwinding. Keep its thread
            # reference so a second dispatcher cannot be started in this process.
            if thread is None or not thread.is_alive():
                self._thread = None

    def run_once(self) -> bool:
        """执行一次调度循环（获取并执行一个任务）。
        
        Returns:
            True 表示执行了任务，False 表示无任务或获取锁失败
        """
        if self._stop.is_set() or not self._dispatch_lock.acquire(blocking=False):
            return False
        try:
            with connect_database(self._database_path) as connection:
                reclaim_stale_operation_tasks(connection)
                row = connection.execute(
                    "SELECT id FROM operation_tasks WHERE status='queued' ORDER BY created_at,id LIMIT 1"
                ).fetchone()
                if row is None:
                    return False
                task_id = str(row["id"])
                attempt_id = f"task_attempt_{uuid.uuid4().hex}"
                try:
                    claim = claim_operation_task(
                        connection, task_id=task_id, attempt_id=attempt_id,
                        lease_seconds=self._lease_seconds,
                    )
                except ValueError:
                    return False
                task = get_operation_task(connection, task_id=task_id)
                operation = connection.execute(
                    "SELECT request_id FROM ai_operations WHERE id=?", (task["operation_id"],)
                ).fetchone()
                task["request_id"] = operation["request_id"] if operation is not None else None
            with self._lock:
                self._active_task_id = task_id
            try:
                self._execute(task, str(claim["attempt_id"]))
            except Exception:
                self._finish(task_id, str(claim["attempt_id"]), "failed", "task_handler_failed")
            finally:
                with self._lock:
                    self._active_task_id = None
            return True
        finally:
            self._dispatch_lock.release()

    def _loop(self) -> None:
        increment("task_runner", "started")
        emit_event("task_runner_started", component="task_runner", outcome="started")
        try:
            while not self._stop.is_set():
                try:
                    worked = self.run_once()
                except Exception:
                    # A transient SQLite or runner failure must not silently kill
                    # the dispatcher. Task state remains durable for inspection or
                    # explicit retry; event payload intentionally omits exception text.
                    increment("task_runner", "poll_failed")
                    emit_event("task_runner_poll_failed", level=logging.WARNING,
                               error_code="task_handler_failed", component="task_runner", outcome="failed")
                    worked = False
                if not worked:
                    self._stop.wait(self._poll_interval_seconds)
        finally:
            increment("task_runner", "stopped")
            emit_event("task_runner_stopped", component="task_runner", outcome="stopped")

    def _execute(self, task: dict[str, object], attempt_id: str) -> None:
        task_id = str(task["id"])
        task_kind = str(task["task_kind"])
        context = TaskContext(
            task_id=task_id, attempt_id=attempt_id, project_id=str(task["project_id"]),
            operation_id=str(task["operation_id"]), task_kind=task_kind,
            _database_path=self._database_path, _lease_seconds=self._lease_seconds,
        )
        started = time.perf_counter()
        tokens = set_task_correlation(
            task_id, context.operation_id, context.project_id,
            str(task["request_id"]) if task.get("request_id") else None,
        )
        outcome = "failed"
        try:
            policy = self._handlers.get(task_kind)
            if policy is None:
                self._finish(task_id, attempt_id, "failed", "task_handler_not_registered")
                return
            try:
                context.raise_if_cancel_requested()
                result = policy.handler(context)
                if result is not None and not isinstance(result, TaskResult):
                    raise TaskFailed("task_handler_failed")
                # An already-completed irreversible handler may legitimately win a late cancel.
                outcome = "succeeded"
                self._finish(task_id, attempt_id, outcome, None,
                             output_artifact_id=result.output_artifact_id if result else None)
            except TaskCancelled:
                outcome = "cancelled"
                self._finish(task_id, attempt_id, outcome, None)
            except TaskFailed as error:
                outcome = "failed"
                self._finish(task_id, attempt_id, outcome, error.code)
            except TaskRunnerError as error:
                outcome = "stale"
                self._finish(task_id, attempt_id, outcome, error.code)
            except Exception:
                # Do not emit exception text, traceback, payload, source content, or provider data.
                outcome = "failed"
                self._finish(task_id, attempt_id, outcome, "task_handler_failed")
        finally:
            observe_task(task_kind, outcome, (time.perf_counter() - started) * 1000)
            reset_task_correlation(tokens)

    def _finish(self, task_id: str, attempt_id: str, status: str, error_code: str | None,
                *, output_artifact_id: str | None = None) -> None:
        try:
            with connect_database(self._database_path) as connection:
                if finish_operation_task(
                    connection, task_id=task_id, attempt_id=attempt_id,
                    status=status, error_code=error_code,
                    output_artifact_id=output_artifact_id,
                ):
                    increment("task_runs", str(status))
                    emit_event("task_finished", error_code=error_code, component="task_runner", outcome=status,
                               lease_state="closed")
        except Exception:
            increment("task_runs", "finish_failed")
            emit_event("task_finish_failed", level=logging.WARNING,
                       error_code="task_handler_failed", component="task_runner", outcome="failed")

    def _mark_active_stale(self, connection, error_code: str) -> None:
        with self._lock:
            task_id = self._active_task_id
        if task_id is None:
            return
        row = connection.execute(
            "SELECT id FROM operation_task_attempts WHERE task_id=? AND status='running' ORDER BY attempt_number DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is not None:
            finish_operation_task(connection, task_id=task_id, attempt_id=str(row["id"]),
                                  status="stale", error_code=error_code)
