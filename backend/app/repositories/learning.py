"""稳定的卡片、练习集和笔记仓储域出口。"""

from . import _legacy_part_01 as _part_01
from . import _legacy_part_02 as _part_02
from . import _legacy_part_03 as _part_03
from . import _legacy_part_11 as _part_11
from . import _legacy_part_12 as _part_12
from . import _legacy_part_13 as _part_13

MAX_CARD_TEXT_LENGTH = _part_01.MAX_CARD_TEXT_LENGTH
MAX_CARD_TAGS = _part_01.MAX_CARD_TAGS
MAX_CARD_CITATIONS = _part_01.MAX_CARD_CITATIONS
MAX_DECK_TITLE_LENGTH = _part_01.MAX_DECK_TITLE_LENGTH
MAX_EXERCISE_PROMPT_LENGTH = _part_01.MAX_EXERCISE_PROMPT_LENGTH
MAX_EXERCISE_OPTIONS = _part_01.MAX_EXERCISE_OPTIONS
create_deck = _part_01.create_deck
get_deck = _part_01.get_deck
list_decks = _part_01.list_decks
get_card = _part_01.get_card
list_cards = _part_01.list_cards
list_card_citations = _part_01.list_card_citations
create_card = _part_01.create_card
update_card = _part_01.update_card
confirm_card = _part_02.confirm_card
transition_card = _part_02.transition_card
review_card = _part_02.review_card
MAX_EXERCISE_EXPLANATION_LENGTH = _part_02.MAX_EXERCISE_EXPLANATION_LENGTH
MAX_EXERCISE_ANSWER_LENGTH = _part_02.MAX_EXERCISE_ANSWER_LENGTH
MAX_GENERATION_TOPIC_LENGTH = _part_02.MAX_GENERATION_TOPIC_LENGTH
MAX_GENERATION_COUNT = _part_02.MAX_GENERATION_COUNT
GENERATION_PROMPT_VERSION = _part_02.GENERATION_PROMPT_VERSION
list_exercise_sets = _part_02.list_exercise_sets
get_exercise_set = _part_02.get_exercise_set
create_exercise_set = _part_02.create_exercise_set
get_exercise = _part_03.get_exercise
create_generation_operation = _part_02.create_generation_operation
fail_generation_operation = _part_02.fail_generation_operation
persist_generated_draft = _part_03.persist_generated_draft
list_exercises = _part_03.list_exercises
create_exercise = _part_03.create_exercise
update_exercise = _part_03.update_exercise
confirm_exercise = _part_03.confirm_exercise
transition_exercise = _part_03.transition_exercise
list_exercise_attempts = _part_03.list_exercise_attempts
submit_exercise_attempt = _part_03.submit_exercise_attempt
create_note = _part_11.create_note
create_user_note = _part_11.create_user_note
list_notes = _part_12.list_notes
get_note = _part_12.get_note
update_note = _part_12.update_note
update_note_content = _part_12.update_note_content
update_note_blocks = _part_12.update_note_blocks
create_note_block = _part_12.create_note_block
update_note_block = _part_12.update_note_block
delete_note_block = _part_12.delete_note_block
link_note_module = _part_12.link_note_module
unlink_note_module = _part_12.unlink_note_module
create_note_source_link = _part_12.create_note_source_link
delete_note_source_link = _part_12.delete_note_source_link
confirm_note = _part_12.confirm_note
transition_note = _part_12.transition_note
refresh_note_source_links = _part_12.refresh_note_source_links
archive_note = _part_12.archive_note
create_note_generation_operation = _part_13.create_note_generation_operation
fail_note_generation_operation = _part_13.fail_note_generation_operation
persist_generated_note_draft = _part_13.persist_generated_note_draft
generate_note_draft = _part_13.generate_note_draft

__all__ = ['MAX_CARD_TEXT_LENGTH', 'MAX_CARD_TAGS', 'MAX_CARD_CITATIONS', 'MAX_DECK_TITLE_LENGTH', 'MAX_EXERCISE_PROMPT_LENGTH', 'MAX_EXERCISE_OPTIONS', 'create_deck', 'get_deck', 'list_decks', 'get_card', 'list_cards', 'list_card_citations', 'create_card', 'update_card', 'confirm_card', 'transition_card', 'review_card', 'MAX_EXERCISE_EXPLANATION_LENGTH', 'MAX_EXERCISE_ANSWER_LENGTH', 'MAX_GENERATION_TOPIC_LENGTH', 'MAX_GENERATION_COUNT', 'GENERATION_PROMPT_VERSION', 'list_exercise_sets', 'get_exercise_set', 'create_exercise_set', 'get_exercise', 'create_generation_operation', 'fail_generation_operation', 'persist_generated_draft', 'list_exercises', 'create_exercise', 'update_exercise', 'confirm_exercise', 'transition_exercise', 'list_exercise_attempts', 'submit_exercise_attempt', 'create_note', 'create_user_note', 'list_notes', 'get_note', 'update_note', 'update_note_content', 'update_note_blocks', 'create_note_block', 'update_note_block', 'delete_note_block', 'link_note_module', 'unlink_note_module', 'create_note_source_link', 'delete_note_source_link', 'confirm_note', 'transition_note', 'refresh_note_source_links', 'archive_note', 'create_note_generation_operation', 'fail_note_generation_operation', 'persist_generated_note_draft', 'generate_note_draft']
