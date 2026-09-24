"""稳定的练习会话、错题与冲刺目标仓储域出口。"""

from . import _legacy_part_03 as _part_03
from . import _legacy_part_04 as _part_04
from . import _legacy_part_05 as _part_05

PHASE9C_SESSION_TITLE_MAX = _part_03.PHASE9C_SESSION_TITLE_MAX
PHASE9C_SESSION_MAX_ITEMS = _part_03.PHASE9C_SESSION_MAX_ITEMS
PHASE9C_MIN_DURATION_SECONDS = _part_03.PHASE9C_MIN_DURATION_SECONDS
PHASE9C_MAX_DURATION_SECONDS = _part_03.PHASE9C_MAX_DURATION_SECONDS
PHASE9C_FEEDBACK_MAX = _part_03.PHASE9C_FEEDBACK_MAX
PHASE9C_CORRECTION_MAX = _part_03.PHASE9C_CORRECTION_MAX
PHASE9C_SESSION_STATUSES = _part_03.PHASE9C_SESSION_STATUSES
PHASE9C_MISTAKE_STATUSES = _part_03.PHASE9C_MISTAKE_STATUSES
PHASE9C_SOURCE_STATUSES = _part_03.PHASE9C_SOURCE_STATUSES
create_cram_goal = _part_04.create_cram_goal
get_cram_goal = _part_04.get_cram_goal
list_cram_goals = _part_04.list_cram_goals
transition_cram_goal = _part_04.transition_cram_goal
create_cram_session = _part_04.create_cram_session
get_cram_result = _part_04.get_cram_result
create_practice_session = _part_04.create_practice_session
get_practice_session = _part_04.get_practice_session
list_practice_sessions = _part_04.list_practice_sessions
get_practice_result = _part_04.get_practice_result
start_practice_session = _part_04.start_practice_session
archive_practice_session = _part_04.archive_practice_session
submit_practice_session_item = _part_04.submit_practice_session_item
finish_practice_session = _part_04.finish_practice_session
mark_mistake_from_attempt = _part_05.mark_mistake_from_attempt
review_exercise_attempt = _part_05.review_exercise_attempt
add_mistake_feedback = _part_05.add_mistake_feedback
archive_mistake_case = _part_05.archive_mistake_case
get_mistake_case = _part_05.get_mistake_case
list_mistake_cases = _part_05.list_mistake_cases
redo_mistake_case = _part_05.redo_mistake_case
list_weak_points = _part_05.list_weak_points
recommend_practice_exercises = _part_05.recommend_practice_exercises

__all__ = ['PHASE9C_SESSION_TITLE_MAX', 'PHASE9C_SESSION_MAX_ITEMS', 'PHASE9C_MIN_DURATION_SECONDS', 'PHASE9C_MAX_DURATION_SECONDS', 'PHASE9C_FEEDBACK_MAX', 'PHASE9C_CORRECTION_MAX', 'PHASE9C_SESSION_STATUSES', 'PHASE9C_MISTAKE_STATUSES', 'PHASE9C_SOURCE_STATUSES', 'create_cram_goal', 'get_cram_goal', 'list_cram_goals', 'transition_cram_goal', 'create_cram_session', 'get_cram_result', 'create_practice_session', 'get_practice_session', 'list_practice_sessions', 'get_practice_result', 'start_practice_session', 'archive_practice_session', 'submit_practice_session_item', 'finish_practice_session', 'mark_mistake_from_attempt', 'review_exercise_attempt', 'add_mistake_feedback', 'archive_mistake_case', 'get_mistake_case', 'list_mistake_cases', 'redo_mistake_case', 'list_weak_points', 'recommend_practice_exercises']
