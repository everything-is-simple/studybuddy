"""异步任务数据访问层的稳定域出口。"""

from . import _legacy_part_00 as _part_00

TASK_TERMINAL_STATUSES = _part_00.TASK_TERMINAL_STATUSES
TASK_ACTIVE_STATUSES = _part_00.TASK_ACTIVE_STATUSES
TASK_STAGE_CODES = _part_00.TASK_STAGE_CODES
create_operation_task = _part_00.create_operation_task
get_operation_task = _part_00.get_operation_task
claim_operation_task = _part_00.claim_operation_task
update_operation_task_progress = _part_00.update_operation_task_progress
heartbeat_operation_task = _part_00.heartbeat_operation_task
request_operation_task_cancel = _part_00.request_operation_task_cancel
retry_operation_task = _part_00.retry_operation_task
finish_operation_task = _part_00.finish_operation_task
recover_active_operation_tasks = _part_00.recover_active_operation_tasks
reclaim_stale_operation_tasks = _part_00.reclaim_stale_operation_tasks

__all__ = ['TASK_TERMINAL_STATUSES', 'TASK_ACTIVE_STATUSES', 'TASK_STAGE_CODES', 'create_operation_task', 'get_operation_task', 'claim_operation_task', 'update_operation_task_progress', 'heartbeat_operation_task', 'request_operation_task_cancel', 'retry_operation_task', 'finish_operation_task', 'recover_active_operation_tasks', 'reclaim_stale_operation_tasks']
