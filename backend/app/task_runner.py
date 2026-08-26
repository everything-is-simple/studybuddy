from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .observability import emit_event, increment
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

TaskHandler = Callable[["TaskContext"], None]


def _dispatcher_lock(database_path: Path) -> threading.Lock:
    key = str(database_path.resolve())
    with _runner_locks_guard:
        return _runner_locks.setdefault(key, threading.Lock())


@dataclass(frozen=True)
class TaskHandlerPolicy:
    handler: TaskHandler
    retryable_error_codes: frozenset[str]


class TaskRunnerError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TaskCancelled(Exception):
    """A handler raises this only after a cooperative cancellation safe point."""


@dataclass(frozen=True)
class TaskContext:
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
        return self._task_status() == "cancel_requested"

    def raise_if_cancel_requested(self) -> None:
        if self.cancel_requested():
            raise TaskCancelled()

    def progress(self, progress_percent: int | None, stage_code: str) -> None:
        with connect_database(self._database_path) as connection:
            if not update_operation_task_progress(
                connection, task_id=self.task_id, attempt_id=self.attempt_id,
                progress_percent=progress_percent, stage_code=stage_code,
            ):
                raise TaskRunnerError("task_lease_lost")

    def heartbeat(self) -> None:
        with connect_database(self._database_path) as connection:
            if not heartbeat_operation_task(
                connection, task_id=self.task_id, attempt_id=self.attempt_id,
                lease_seconds=self._lease_seconds,
            ):
                raise TaskRunnerError("task_lease_lost")


class TaskRunner:
    """Explicit, single-process task dispatcher; it is never started by app startup."""

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
        if (not task_kind or not callable(handler) or
                any(not code or len(code) > 100 for code in retryable_error_codes)):
            raise TaskRunnerError("task_handler_invalid")
        if task_kind in self._handlers:
            raise TaskRunnerError("task_handler_already_registered")
        self._handlers[task_kind] = TaskHandlerPolicy(handler, retryable_error_codes)

    def cancel(self, task_id: str) -> str:
        with connect_database(self._database_path) as connection:
            return request_operation_task_cancel(connection, task_id=task_id)

    def retry(self, task_id: str) -> dict[str, object]:
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
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise TaskRunnerError("task_runner_already_started")
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="studybuddy-task-runner", daemon=True)
            self._thread.start()

    def shutdown(self, timeout_seconds: float = 5.0) -> None:
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
        policy = self._handlers.get(task_kind)
        if policy is None:
            self._finish(task_id, attempt_id, "failed", "task_handler_not_registered")
            return
        try:
            context.raise_if_cancel_requested()
            policy.handler(context)
            # An already-completed irreversible handler may legitimately win a late cancel.
            self._finish(task_id, attempt_id, "succeeded", None)
        except TaskCancelled:
            self._finish(task_id, attempt_id, "cancelled", None)
        except TaskRunnerError as error:
            self._finish(task_id, attempt_id, "stale", error.code)
        except Exception:
            # Do not emit exception text, traceback, payload, source content, or provider data.
            self._finish(task_id, attempt_id, "failed", "task_handler_failed")

    def _finish(self, task_id: str, attempt_id: str, status: str, error_code: str | None) -> None:
        try:
            with connect_database(self._database_path) as connection:
                if finish_operation_task(
                    connection, task_id=task_id, attempt_id=attempt_id,
                    status=status, error_code=error_code,
                ):
                    increment("task_runs", status)
                    emit_event("task_finished", error_code=error_code, component="task_runner", outcome=status)
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
