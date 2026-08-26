from __future__ import annotations

import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    create_operation_task,
    get_operation_task,
    recover_active_operation_tasks,
    request_operation_task_cancel,
    retry_operation_task,
)
from app.repository import connect
from app.task_runner import TaskRunner, TaskRunnerError


PROJECT = "task_project"


def seed_task(database: Path, *, task_id: str = "task_1", operation_id: str = "operation_1",
              kind: str = "test", max_retries: int = 0) -> None:
    with connect(database) as connection:
        connection.execute("INSERT INTO projects VALUES (?,?,?)", (PROJECT, "Tasks", "now"))
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES (?,?, 'queued', ?, ?, 0, 'now')",
            (operation_id, kind, PROJECT, "fingerprint_1"),
        )
        create_operation_task(
            connection, task_id=task_id, project_id=PROJECT, operation_id=operation_id,
            task_kind=kind, input_fingerprint="fingerprint_1", max_retries=max_retries,
        )


def task(database: Path, task_id: str = "task_1") -> dict[str, object]:
    with connect(database) as connection:
        return get_operation_task(connection, task_id=task_id)


def attempt_rows(database: Path) -> list[tuple[object, ...]]:
    with connect(database) as connection:
        return [tuple(row) for row in connection.execute(
            "SELECT attempt_number,status,progress_percent,stage_code,error_code FROM operation_task_attempts "
            "ORDER BY attempt_number"
        ).fetchall()]


def test_runner_executes_one_registered_task_and_updates_operation(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    calls: list[tuple[str, str]] = []
    runner = TaskRunner(database, lease_seconds=10)

    def handler(context):
        calls.append((context.task_id, context.operation_id))
        context.progress(40, "indexing")
        context.heartbeat()
        context.progress(90, "persisting")

    runner.register("test", handler)
    assert runner.run_once() is True
    assert calls == [("task_1", "operation_1")]
    finished = task(database)
    assert finished["status"] == "succeeded"
    assert finished["progress_percent"] == 100
    assert finished["stage_code"] == "finalizing"
    assert attempt_rows(database) == [(1, "succeeded", 90, "persisting", None)]
    with connect(database) as connection:
        assert tuple(connection.execute("SELECT status,error_code FROM ai_operations WHERE id='operation_1'").fetchone()) == (
            "succeeded", None,
        )


def test_runner_rejects_missing_handler_without_exposing_exception(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database, kind="missing")
    assert TaskRunner(database).run_once() is True
    assert task(database)["status"] == "failed"
    assert attempt_rows(database) == [(1, "failed", 0, "reading_source", "task_handler_not_registered")]


def test_handler_failure_is_stable_and_retry_preserves_attempt_history(tmp_path: Path, caplog):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database, max_retries=1)
    runner = TaskRunner(database)

    def failing(_context):
        raise RuntimeError("secret source text and path")

    runner.register("test", failing, retryable_error_codes=frozenset({"task_handler_failed"}))
    assert runner.run_once() is True
    assert "secret source text and path" not in caplog.text
    assert task(database)["status"] == "failed"
    assert task(database)["error_code"] == "task_handler_failed"
    assert runner.retry("task_1")["status"] == "queued"
    assert runner.run_once() is True
    assert attempt_rows(database) == [
        (1, "failed", 0, "reading_source", "task_handler_failed"),
        (2, "failed", 0, "reading_source", "task_handler_failed"),
    ]
    with pytest.raises(TaskRunnerError, match="task_retry_limit_reached"):
        runner.retry("task_1")


def test_retry_requires_registered_explicit_policy(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database, max_retries=1)
    runner = TaskRunner(database)
    runner.register("test", lambda _context: None)
    with connect(database) as connection:
        connection.execute("UPDATE operation_tasks SET status='failed',error_code='task_handler_failed' WHERE id='task_1'")
    with pytest.raises(TaskRunnerError, match="task_retry_not_allowed"):
        runner.retry("task_1")


def test_idempotency_replay_and_mismatch_do_not_create_another_task(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    with connect(database) as connection:
        replay = create_operation_task(
            connection, task_id="different_task", project_id=PROJECT, operation_id="operation_1",
            task_kind="test", input_fingerprint="fingerprint_1",
        )
        assert replay["id"] == "task_1" and replay["replay"] is True
        with pytest.raises(ValueError, match="task_idempotency_key_mismatch"):
            create_operation_task(
                connection, task_id="different_task", project_id=PROJECT, operation_id="operation_1",
                task_kind="test", input_fingerprint="different",
            )
        assert connection.execute("SELECT COUNT(*) FROM operation_tasks").fetchone()[0] == 1


def test_progress_cannot_regress_and_lease_loss_blocks_completion(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    runner = TaskRunner(database, lease_seconds=1)

    def handler(context):
        context.progress(80, "indexing")
        with pytest.raises(TaskRunnerError, match="task_lease_lost"):
            context.progress(20, "persisting")
        # Deliberately expire the attempt; later finish must be stale, not success.
        with connect(database) as connection:
            connection.execute("UPDATE operation_task_attempts SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (context.attempt_id,))
        context.heartbeat()

    runner.register("test", handler)
    assert runner.run_once() is True
    assert task(database)["status"] == "stale"
    assert task(database)["error_code"] == "task_lease_lost"


def test_multiple_runner_instances_preserve_single_process_concurrency_limit(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    with connect(database) as connection:
        connection.execute(
            "INSERT INTO ai_operations (id,operation_type,status,project_id,input_fingerprint,retry_count,created_at) "
            "VALUES ('operation_2','test','queued',?,'fingerprint_2',0,'now')", (PROJECT,)
        )
        create_operation_task(
            connection, task_id="task_2", project_id=PROJECT, operation_id="operation_2",
            task_kind="test", input_fingerprint="fingerprint_2",
        )
    entered, release = threading.Event(), threading.Event()
    first = TaskRunner(database)
    second = TaskRunner(database)

    def handler(_context):
        entered.set()
        assert release.wait(3)

    first.register("test", handler)
    second.register("test", handler)
    thread = threading.Thread(target=first.run_once)
    thread.start()
    assert entered.wait(3)
    assert second.run_once() is False
    with connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM operation_tasks WHERE status='queued'").fetchone()[0] == 1
    release.set()
    thread.join(3)
    assert second.run_once() is True


def test_queued_and_running_cooperative_cancel(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    queued_runner = TaskRunner(database)
    assert queued_runner.cancel("task_1") == "cancelled"
    assert queued_runner.run_once() is False
    assert task(database)["status"] == "cancelled"

    database2 = tmp_path / "studybuddy2.sqlite3"
    seed_task(database2)
    entered, release = threading.Event(), threading.Event()
    runner = TaskRunner(database2, poll_interval_seconds=0.01)

    def handler(context):
        entered.set()
        assert release.wait(3)
        context.raise_if_cancel_requested()

    runner.register("test", handler)
    thread = threading.Thread(target=runner.run_once)
    thread.start()
    assert entered.wait(3)
    assert runner.cancel("task_1") == "cancel_requested"
    release.set()
    thread.join(3)
    assert task(database2)["status"] == "cancelled"
    assert attempt_rows(database2)[0][1] == "cancelled"


def test_expired_and_startup_interrupted_tasks_become_stale_not_queued(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    runner = TaskRunner(database, lease_seconds=1)
    entered, release = threading.Event(), threading.Event()

    def handler(_context):
        entered.set()
        assert release.wait(3)

    runner.register("test", handler)
    thread = threading.Thread(target=runner.run_once)
    thread.start()
    assert entered.wait(3)
    with connect(database) as connection:
        assert recover_active_operation_tasks(connection) == 1
    release.set()
    thread.join(3)
    assert task(database)["status"] == "stale"
    assert task(database)["error_code"] == "task_recovery_required"
    assert attempt_rows(database)[0][1] == "stale"


def test_startup_does_not_execute_queued_task(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    from app.config import AppConfig
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(AppConfig(data_root=tmp_path))):
        pass
    assert task(database)["status"] == "queued"
    assert attempt_rows(database) == []


def test_shutdown_marks_inflight_task_stale_and_does_not_auto_run_on_next_runner(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    seed_task(database)
    entered, release = threading.Event(), threading.Event()
    runner = TaskRunner(database, poll_interval_seconds=0.01)

    def handler(_context):
        entered.set()
        assert release.wait(3)

    runner.register("test", handler)
    runner.start()
    assert entered.wait(3)
    runner.shutdown(timeout_seconds=0)
    assert task(database)["status"] == "stale"
    assert task(database)["error_code"] == "task_runner_shutdown"
    with pytest.raises(TaskRunnerError, match="task_runner_already_started"):
        runner.start()
    release.set()
    time.sleep(0.05)
    assert TaskRunner(database).run_once() is False


def test_runner_configuration_and_single_thread_guard(tmp_path: Path):
    database = tmp_path / "studybuddy.sqlite3"
    with pytest.raises(TaskRunnerError, match="task_runner_invalid_config"):
        TaskRunner(database, max_concurrency=2)
    runner = TaskRunner(database)
    runner.start()
    with pytest.raises(TaskRunnerError, match="task_runner_already_started"):
        runner.start()
    runner.shutdown()
