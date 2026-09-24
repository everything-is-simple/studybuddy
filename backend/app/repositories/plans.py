"""学习计划、源链接和节奏数据访问层的稳定域出口。"""

from . import _legacy_part_09 as _part_09
from . import _legacy_part_10 as _part_10
from . import _legacy_part_11 as _part_11
from . import _legacy_part_13 as _part_13

STUDY_TEXT_MAX = _part_09.STUDY_TEXT_MAX
STUDY_DESCRIPTION_MAX = _part_09.STUDY_DESCRIPTION_MAX
STUDY_METADATA_MAX = _part_09.STUDY_METADATA_MAX
STUDY_GOAL_PREFIX = _part_09.STUDY_GOAL_PREFIX
STUDY_MODULE_PREFIX = _part_09.STUDY_MODULE_PREFIX
STUDY_PLAN_PREFIX = _part_09.STUDY_PLAN_PREFIX
STUDY_ITEM_PREFIX = _part_09.STUDY_ITEM_PREFIX
STUDY_DEPENDENCY_PREFIX = _part_09.STUDY_DEPENDENCY_PREFIX
STUDY_PROGRESS_PREFIX = _part_09.STUDY_PROGRESS_PREFIX
STUDY_SOURCE_PREFIX = _part_09.STUDY_SOURCE_PREFIX
STUDY_PLAN_STATUSES = _part_09.STUDY_PLAN_STATUSES
STUDY_ITEM_STATUSES = _part_09.STUDY_ITEM_STATUSES
STUDY_PROGRESS_EVENTS = _part_09.STUDY_PROGRESS_EVENTS
STUDY_SOURCE_STATUSES = _part_09.STUDY_SOURCE_STATUSES
RHYTHM_CADENCES = _part_09.RHYTHM_CADENCES
RHYTHM_MAX_TARGET_MINUTES = _part_09.RHYTHM_MAX_TARGET_MINUTES
RHYTHM_MAX_ITEM_MINUTES = _part_09.RHYTHM_MAX_ITEM_MINUTES
RHYTHM_MAX_PERIOD_MINUTES = _part_09.RHYTHM_MAX_PERIOD_MINUTES
RHYTHM_MAX_ALLOCATION_MINUTES = _part_09.RHYTHM_MAX_ALLOCATION_MINUTES
NOTE_STATUSES = _part_09.NOTE_STATUSES
NOTE_PROVENANCES = _part_09.NOTE_PROVENANCES
NOTE_BLOCK_KINDS = _part_09.NOTE_BLOCK_KINDS
NOTE_MAX_TITLE = _part_09.NOTE_MAX_TITLE
NOTE_MAX_BLOCK_CONTENT = _part_09.NOTE_MAX_BLOCK_CONTENT
NOTE_MAX_CONTENT = _part_09.NOTE_MAX_CONTENT
NOTE_GENERATION_PROMPT_VERSION = _part_09.NOTE_GENERATION_PROMPT_VERSION

create_learning_goal = _part_09.create_learning_goal
list_learning_goals = _part_09.list_learning_goals
get_learning_goal = _part_09.get_learning_goal
archive_learning_goal = _part_09.archive_learning_goal
update_learning_goal = _part_09.update_learning_goal
create_knowledge_module = _part_09.create_knowledge_module
list_knowledge_modules = _part_09.list_knowledge_modules
get_knowledge_module = _part_09.get_knowledge_module
update_knowledge_module = _part_09.update_knowledge_module
archive_knowledge_module = _part_09.archive_knowledge_module
study_progress_summary = _part_09.study_progress_summary
create_study_plan = _part_09.create_study_plan
list_study_plans = _part_09.list_study_plans
get_study_plan = _part_09.get_study_plan
update_study_plan = _part_09.update_study_plan
transition_study_plan = _part_09.transition_study_plan
create_study_plan_item = _part_10.create_study_plan_item
update_study_plan_item = _part_10.update_study_plan_item
archive_study_plan_item = _part_10.archive_study_plan_item
add_study_plan_dependency = _part_10.add_study_plan_dependency
remove_study_plan_dependency = _part_10.remove_study_plan_dependency
append_study_progress_event = _part_10.append_study_progress_event
list_study_progress_events = _part_10.list_study_progress_events
create_module_source_link = _part_10.create_module_source_link
create_plan_item_source_link = _part_10.create_plan_item_source_link
delete_module_source_link = _part_10.delete_module_source_link
delete_plan_item_source_link = _part_10.delete_plan_item_source_link
refresh_study_source_links = _part_10.refresh_study_source_links
get_study_source_links = _part_11.get_study_source_links
list_study_source_candidates = _part_11.list_study_source_candidates
get_rhythm_settings = _part_11.get_rhythm_settings
save_rhythm_settings = _part_11.save_rhythm_settings
create_rhythm_settings = _part_11.create_rhythm_settings
update_rhythm_settings = _part_11.update_rhythm_settings
list_rhythm_allocations = _part_11.list_rhythm_allocations
create_rhythm_allocation = _part_11.create_rhythm_allocation
update_rhythm_allocation = _part_11.update_rhythm_allocation
delete_rhythm_allocation = _part_11.delete_rhythm_allocation
rhythm_summary = _part_11.rhythm_summary
study_weekly_trend = _part_11.study_weekly_trend

# Compatibility names used by older callers. Keep the aliases owned by the
# plans domain so the top-level facade no longer imports them directly from
# the legacy assembler.
get_study_rhythm = _part_13.get_study_rhythm
set_study_rhythm = _part_13.set_study_rhythm
get_rhythm_summary = _part_13.get_rhythm_summary
create_study_rhythm_allocation = _part_13.create_study_rhythm_allocation
update_study_rhythm_allocation = _part_13.update_study_rhythm_allocation
delete_study_rhythm_allocation = _part_13.delete_study_rhythm_allocation

__all__ = ['STUDY_TEXT_MAX', 'STUDY_DESCRIPTION_MAX', 'STUDY_METADATA_MAX', 'STUDY_GOAL_PREFIX', 'STUDY_MODULE_PREFIX', 'STUDY_PLAN_PREFIX', 'STUDY_ITEM_PREFIX', 'STUDY_DEPENDENCY_PREFIX', 'STUDY_PROGRESS_PREFIX', 'STUDY_SOURCE_PREFIX', 'STUDY_PLAN_STATUSES', 'STUDY_ITEM_STATUSES', 'STUDY_PROGRESS_EVENTS', 'STUDY_SOURCE_STATUSES', 'RHYTHM_CADENCES', 'RHYTHM_MAX_TARGET_MINUTES', 'RHYTHM_MAX_ITEM_MINUTES', 'RHYTHM_MAX_PERIOD_MINUTES', 'RHYTHM_MAX_ALLOCATION_MINUTES', 'NOTE_STATUSES', 'NOTE_PROVENANCES', 'NOTE_BLOCK_KINDS', 'NOTE_MAX_TITLE', 'NOTE_MAX_BLOCK_CONTENT', 'NOTE_MAX_CONTENT', 'NOTE_GENERATION_PROMPT_VERSION', 'create_learning_goal', 'list_learning_goals', 'get_learning_goal', 'archive_learning_goal', 'update_learning_goal', 'create_knowledge_module', 'list_knowledge_modules', 'get_knowledge_module', 'update_knowledge_module', 'archive_knowledge_module', 'study_progress_summary', 'create_study_plan', 'list_study_plans', 'get_study_plan', 'update_study_plan', 'transition_study_plan', 'create_study_plan_item', 'update_study_plan_item', 'archive_study_plan_item', 'add_study_plan_dependency', 'remove_study_plan_dependency', 'append_study_progress_event', 'list_study_progress_events', 'create_module_source_link', 'create_plan_item_source_link', 'delete_module_source_link', 'delete_plan_item_source_link', 'list_study_source_candidates', 'refresh_study_source_links', 'get_study_source_links', 'get_rhythm_settings', 'save_rhythm_settings', 'create_rhythm_settings', 'update_rhythm_settings', 'list_rhythm_allocations', 'create_rhythm_allocation', 'update_rhythm_allocation', 'delete_rhythm_allocation', 'rhythm_summary', 'study_weekly_trend', 'get_study_rhythm', 'set_study_rhythm', 'get_rhythm_summary', 'create_study_rhythm_allocation', 'update_study_rhythm_allocation', 'delete_study_rhythm_allocation']
