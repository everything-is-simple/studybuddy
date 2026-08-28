"""Domain repository exports."""

from . import _legacy

TASK_TERMINAL_STATUSES = getattr(_legacy, 'TASK_TERMINAL_STATUSES')
TASK_ACTIVE_STATUSES = getattr(_legacy, 'TASK_ACTIVE_STATUSES')
TASK_STAGE_CODES = getattr(_legacy, 'TASK_STAGE_CODES')
create_operation_task = getattr(_legacy, 'create_operation_task')
get_operation_task = getattr(_legacy, 'get_operation_task')
claim_operation_task = getattr(_legacy, 'claim_operation_task')
update_operation_task_progress = getattr(_legacy, 'update_operation_task_progress')
heartbeat_operation_task = getattr(_legacy, 'heartbeat_operation_task')
request_operation_task_cancel = getattr(_legacy, 'request_operation_task_cancel')
retry_operation_task = getattr(_legacy, 'retry_operation_task')
finish_operation_task = getattr(_legacy, 'finish_operation_task')
recover_active_operation_tasks = getattr(_legacy, 'recover_active_operation_tasks')
reclaim_stale_operation_tasks = getattr(_legacy, 'reclaim_stale_operation_tasks')

__all__ = ['TASK_TERMINAL_STATUSES', 'TASK_ACTIVE_STATUSES', 'TASK_STAGE_CODES', 'create_operation_task', 'get_operation_task', 'claim_operation_task', 'update_operation_task_progress', 'heartbeat_operation_task', 'request_operation_task_cancel', 'retry_operation_task', 'finish_operation_task', 'recover_active_operation_tasks', 'reclaim_stale_operation_tasks']
