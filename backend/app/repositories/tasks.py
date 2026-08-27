"""Compatibility exports for the tasks repository domain."""

from . import _legacy

from ._legacy import (
    TASK_TERMINAL_STATUSES,
    TASK_ACTIVE_STATUSES,
    TASK_STAGE_CODES,
    create_operation_task,
    get_operation_task,
    claim_operation_task,
    update_operation_task_progress,
    heartbeat_operation_task,
    request_operation_task_cancel,
    retry_operation_task,
    finish_operation_task,
    recover_active_operation_tasks,
    reclaim_stale_operation_tasks,
)

__all__ = [
    'TASK_TERMINAL_STATUSES',
    'TASK_ACTIVE_STATUSES',
    'TASK_STAGE_CODES',
    'create_operation_task',
    'get_operation_task',
    'claim_operation_task',
    'update_operation_task_progress',
    'heartbeat_operation_task',
    'request_operation_task_cancel',
    'retry_operation_task',
    'finish_operation_task',
    'recover_active_operation_tasks',
    'reclaim_stale_operation_tasks',
]
