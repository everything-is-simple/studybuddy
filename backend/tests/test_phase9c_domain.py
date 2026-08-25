from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repository import (
    add_mistake_feedback,
    archive_mistake_case,
    archive_practice_session,
    connect,
    create_cram_goal,
    create_cram_session,
    create_exercise,
    create_exercise_set,
    create_practice_session,
    finish_practice_session,
    get_practice_result,
    get_practice_session,
    index_material_revision,
    list_practice_sessions,
    get_mistake_case,
    list_cram_goals,
    list_mistake_cases,
    list_weak_points,
    mark_mistake_from_attempt,
    redo_mistake_case,
    review_exercise_attempt,
    soft_delete_material,
    start_practice_session,
    submit_practice_session_item,
    transition_cram_goal,
    purge_material,
    get_cram_result,
)


def _seed_project(connection: sqlite3.Connection, project_id: str = "project_9c") -> None:
    connection.execute("INSERT INTO projects (id,name,created_at) VALUES (?,?,?)", (project_id, "Phase 9C", "now"))


def _exercise(connection: sqlite3.Connection, *, project_id: str = "project_9c", kind: str = "true_false") -> dict[str, object]:
    exercise_set = create_exercise_set(connection, project_id=project_id, title="Practice")
    payload = {"prompt": "Is this true?", "options": [], "answer_key": True, "explanation": "Explanation"}
    if kind == "multiple_choice":
        payload = {"prompt": "Choose", "options": ["no", "yes"], "answer_key": 1}
    if kind == "short_answer":
        payload = {"prompt": "Explain", "options": [], "answer_key": "because"}
    exercise = create_exercise(connection, project_id=project_id, set_id=str(exercise_set["id"]), exercise_type=kind, payload=payload)
    from app.repository import confirm_exercise
    return confirm_exercise(connection, project_id=project_id, exercise_id=str(exercise["id"]))


def _active_session(connection: sqlite3.Connection, exercise_id: str) -> dict[str, object]:
    session = create_practice_session(connection, project_id="project_9c", title="Timed", exercise_ids=[exercise_id], duration_seconds=60)
    return start_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))


def _cited_exercise(connection: sqlite3.Connection) -> tuple[dict[str, object], str]:
    material_id, extraction_id = "material_9c_source", "extraction_9c_source"
    connection.execute(
        "INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,NULL)",
        (material_id, "project_9c", "source.txt", "b" * 64, "originals/b", "text/plain", "now", "now"),
    )
    connection.execute(
        "INSERT INTO extractions VALUES (?,?,?,?,?,?,?,?,NULL)",
        (extraction_id, material_id, "txt", "1", "success", "A source for a practice snapshot.", "[]", "now"),
    )
    connection.execute("INSERT INTO text_spans VALUES (?,?,?,?,?,?)", ("span_9c", extraction_id, 0, "document", "source", "A source for a practice snapshot."))
    revision = index_material_revision(connection, material_id, extraction_id)
    chunk_id = connection.execute("SELECT id FROM chunks WHERE revision_id=?", (revision["id"],)).fetchone()[0]
    from app.repository import assemble_context, confirm_exercise
    key = assemble_context(connection, project_id="project_9c", hits=[{"chunk_id": chunk_id, "rank": 1}])["context_blocks"][0]["citation_key"]
    exercise_set = create_exercise_set(connection, project_id="project_9c", title="Cited")
    exercise = create_exercise(connection, project_id="project_9c", set_id=str(exercise_set["id"]), exercise_type="true_false",
                               source_revision=str(revision["id"]), payload={"prompt": "True?", "options": [], "answer_key": True,
                               "citations": [{"citation_key": key, "chunk_id": chunk_id, "quote": "A source for a practice snapshot."}]})
    return confirm_exercise(connection, project_id="project_9c", exercise_id=str(exercise["id"])), material_id


def test_session_snapshot_and_privacy_for_deterministic_submission(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="multiple_choice")
        session = _active_session(connection, str(exercise["id"]))
        item = session["items"][0]
        assert "answer_key_json" not in item
        result = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer=0)
        assert result["grading_status"] == "deterministic" and result["is_correct"] is False
        assert "answer_json" not in result and "answer_key" not in result
        replay = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer=1)
        assert replay["id"] == result["id"] and replay["replay"] is True
        keyed = _active_session(connection, str(exercise["id"]))
        keyed_item = keyed["items"][0]
        first_keyed = submit_practice_session_item(connection, project_id="project_9c", session_id=str(keyed["id"]), item_id=str(keyed_item["id"]), answer=0, submission_key="key-2")
        with pytest.raises(ValueError, match="practice_submission_idempotency_mismatch"):
            submit_practice_session_item(connection, project_id="project_9c", session_id=str(keyed["id"]), item_id=str(keyed_item["id"]), answer=1, submission_key="key-2")
        second_keyed = submit_practice_session_item(connection, project_id="project_9c", session_id=str(keyed["id"]), item_id=str(keyed_item["id"]), answer=0, submission_key="key-2")
        assert first_keyed["id"] == second_keyed["id"] and second_keyed["replay"] is True
        result_summary = get_practice_result(connection, project_id="project_9c", session_id=str(session["id"]))
        assert result_summary["summary"]["score_ratio"] == 0.0
        assert "answer_key_json" not in result_summary["session"]
        assert len(list_practice_sessions(connection, project_id="project_9c", status="active")) == 2
        assert len(list_mistake_cases(connection, project_id="project_9c")) == 1
        assert list_weak_points(connection, project_id="project_9c")[0]["occurrence_count"] == 2


def test_s3_all_question_types_finish_and_result_summary(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        multiple = _exercise(connection, kind="multiple_choice")
        session = _active_session(connection, str(multiple["id"]))
        item = session["items"][0]
        submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer=1)
        finished = finish_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))
        assert finished["status"] == "finished"
        with pytest.raises(ValueError, match="practice_session_invalid_state"):
            submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer=0)

        true_false = _exercise(connection, kind="true_false")
        tf_session = _active_session(connection, str(true_false["id"]))
        tf_item = tf_session["items"][0]
        tf_result = submit_practice_session_item(connection, project_id="project_9c", session_id=str(tf_session["id"]), item_id=str(tf_item["id"]), answer=True)
        assert tf_result["grading_status"] == "deterministic" and tf_result["is_correct"] is True

        short_answer = _exercise(connection, kind="short_answer")
        sa_session = _active_session(connection, str(short_answer["id"]))
        sa_item = sa_session["items"][0]
        sa_result = submit_practice_session_item(connection, project_id="project_9c", session_id=str(sa_session["id"]), item_id=str(sa_item["id"]), answer="response")
        assert sa_result["grading_status"] == "pending_review" and sa_result["score"] is None
        summary = get_practice_result(connection, project_id="project_9c", session_id=str(sa_session["id"]))
        assert summary["summary"]["pending_review_count"] == 1
        assert summary["summary"]["scored_count"] == 0


def test_s4_uncertain_and_user_marked_are_distinct(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="short_answer")
        session = _active_session(connection, str(exercise["id"]))
        item = session["items"][0]
        attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer="uncertain")
        reviewed = review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(attempt["id"]), decision="uncertain", feedback="Needs human context")
        assert reviewed["decision"] == "uncertain"
        assert list_mistake_cases(connection, project_id="project_9c") == []
        marked = mark_mistake_from_attempt(connection, project_id="project_9c", attempt_id=str(attempt["id"]), feedback="User wants to revisit")
        assert marked["origin"] == "user_reported"
        assert marked["occurrences"][0]["reason_code"] == "user_marked"


def test_s4_short_answer_review_privacy_and_redeterministic_boundary(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        short = _exercise(connection, kind="short_answer")
        session = _active_session(connection, str(short["id"]))
        attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(session["items"][0]["id"]), answer="private submitted answer")
        review = review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(attempt["id"]), decision="correct", feedback="Accepted")
        assert review["decision"] == "correct"
        assert "answer_json" not in review and "answer_key_json" not in review
        assert list_mistake_cases(connection, project_id="project_9c") == []
        deterministic = _exercise(connection, kind="true_false")
        deterministic_session = _active_session(connection, str(deterministic["id"]))
        deterministic_attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(deterministic_session["id"]), item_id=str(deterministic_session["items"][0]["id"]), answer=False)
        with pytest.raises(ValueError, match="review_not_allowed"):
            review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(deterministic_attempt["id"]), decision="incorrect")


def test_s4_review_feedback_and_attempt_facts_are_append_only_with_rollback(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="short_answer")
        session = _active_session(connection, str(exercise["id"]))
        attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(session["items"][0]["id"]), answer="original answer")
        connection.execute("CREATE TRIGGER fail_review BEFORE INSERT ON exercise_attempt_reviews BEGIN SELECT RAISE(ABORT, 'private'); END")
        with pytest.raises(sqlite3.IntegrityError):
            review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(attempt["id"]), decision="incorrect", feedback="feedback")
        connection.execute("DROP TRIGGER fail_review")
        assert connection.execute("SELECT COUNT(*) FROM exercise_attempt_reviews").fetchone()[0] == 0
        assert connection.execute("SELECT answer_json,grading_status FROM exercise_attempts WHERE id=?", (attempt["id"],)).fetchone()[1] == "pending_review"
        review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(attempt["id"]), decision="incorrect", feedback="feedback")
        case = list_mistake_cases(connection, project_id="project_9c")[0]
        connection.execute("CREATE TRIGGER fail_feedback BEFORE INSERT ON mistake_feedback_events BEGIN SELECT RAISE(ABORT, 'private'); END")
        with pytest.raises(sqlite3.IntegrityError):
            add_mistake_feedback(connection, project_id="project_9c", mistake_case_id=str(case["id"]), event_kind="user_correction", content="correction")
        connection.execute("DROP TRIGGER fail_feedback")
        assert connection.execute("SELECT COUNT(*) FROM mistake_feedback_events").fetchone()[0] == 0
        assert connection.execute("SELECT status FROM mistake_cases WHERE id=?", (case["id"],)).fetchone()[0] == "open"
        assert connection.execute("SELECT COUNT(*) FROM exercise_attempts WHERE id=?", (attempt["id"],)).fetchone()[0] == 1


def test_s4_redo_creates_new_session_and_preserves_attempt_history(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="multiple_choice")
        session = _active_session(connection, str(exercise["id"]))
        first = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(session["items"][0]["id"]), answer=0)
        case = list_mistake_cases(connection, project_id="project_9c")[0]
        redo = redo_mistake_case(connection, project_id="project_9c", mistake_case_id=str(case["id"]))
        assert redo["id"] != session["id"] and redo["items"][0]["exercise_id"] == exercise["id"]
        start_practice_session(connection, project_id="project_9c", session_id=str(redo["id"]))
        second = submit_practice_session_item(connection, project_id="project_9c", session_id=str(redo["id"]), item_id=str(redo["items"][0]["id"]), answer=1)
        assert second["id"] != first["id"]
        assert connection.execute("SELECT COUNT(*) FROM exercise_attempts WHERE exercise_id=?", (exercise["id"],)).fetchone()[0] == 2
        assert get_mistake_case(connection, project_id="project_9c", mistake_case_id=str(case["id"]))["occurrences"]


def test_short_answer_requires_explicit_review_and_feedback(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="short_answer")
        session = _active_session(connection, str(exercise["id"]))
        item = session["items"][0]
        result = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer="my answer")
        assert result["grading_status"] == "pending_review" and result["is_correct"] is None
        review = review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(result["id"]), decision="incorrect", feedback="Needs evidence")
        assert review["decision"] == "incorrect"
        with pytest.raises(ValueError, match="review_duplicate"):
            review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(result["id"]), decision="correct")
        assert len(list_mistake_cases(connection, project_id="project_9c")) == 1
        case_id = str(list_mistake_cases(connection, project_id="project_9c")[0]["id"])
        event = add_mistake_feedback(connection, project_id="project_9c", mistake_case_id=case_id, event_kind="user_correction", content="Corrected explanation")
        assert event["event_kind"] == "user_correction"
        assert list_mistake_cases(connection, project_id="project_9c")[0]["status"] == "fixed"
        retry = _active_session(connection, str(exercise["id"]))
        retry_attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(retry["id"]), item_id=str(retry["items"][0]["id"]), answer="still incomplete")
        review_exercise_attempt(connection, project_id="project_9c", attempt_id=str(retry_attempt["id"]), decision="incorrect")
        assert list_mistake_cases(connection, project_id="project_9c")[0]["status"] == "reopened"
        archived = archive_mistake_case(connection, project_id="project_9c", mistake_case_id=case_id)
        assert archived["status"] == "archived"
        assert list_weak_points(connection, project_id="project_9c") == []


def test_session_input_and_terminal_state_boundaries(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection)
        with pytest.raises(ValueError, match="practice_invalid_payload"):
            create_practice_session(connection, project_id="project_9c", title="Timed", exercise_ids=[str(exercise["id"])], timezone_name="GMT+8")
        with pytest.raises(ValueError, match="practice_invalid_payload"):
            create_practice_session(connection, project_id="project_9c", title="Timed", exercise_ids=[str(exercise["id"])], local_date="2026/01/01")
        with pytest.raises(ValueError, match="practice_invalid_selection"):
            create_practice_session(connection, project_id="project_9c", title="Timed", exercise_ids=[str(exercise["id"]), str(exercise["id"])])
        session = create_practice_session(connection, project_id="project_9c", title="Timed", exercise_ids=[str(exercise["id"])])
        archived = archive_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))
        assert archived["status"] == "archived"
        with pytest.raises(ValueError, match="practice_session_invalid_state"):
            start_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))


def test_s5_cram_goal_session_result_and_completion_boundary(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection, kind="multiple_choice")
        goal = create_cram_goal(connection, project_id="project_9c", title="Exam", target_date="2026-06-01", target_exercise_count=1)
        assert goal["status"] == "draft"
        with pytest.raises(ValueError, match="cram_goal_invalid_state"):
            create_cram_session(connection, project_id="project_9c", goal_id=str(goal["id"]), title="Cram", exercise_ids=[str(exercise["id"])])
        transition_cram_goal(connection, project_id="project_9c", goal_id=str(goal["id"]), target="active")
        cram = create_cram_session(connection, project_id="project_9c", goal_id=str(goal["id"]), title="Cram", exercise_ids=[str(exercise["id"])], duration_seconds=60)
        assert cram["session_kind"] == "cram" and cram["cram_goal_id"] == goal["id"]
        start_practice_session(connection, project_id="project_9c", session_id=str(cram["id"]))
        submit_practice_session_item(connection, project_id="project_9c", session_id=str(cram["id"]), item_id=str(cram["items"][0]["id"]), answer=0)
        finish_practice_session(connection, project_id="project_9c", session_id=str(cram["id"]))
        result = get_cram_result(connection, project_id="project_9c", goal_id=str(goal["id"]), session_id=str(cram["id"]))
        assert result["summary"]["scored_count"] == 1 and result["summary"]["mistake_count"] == 1
        assert "answer_key_json" not in result["session"]
        completed = transition_cram_goal(connection, project_id="project_9c", goal_id=str(goal["id"]), target="completed")
        assert completed["status"] == "completed"
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM rhythm_allocations").fetchone()[0] == 0
        assert len(list_cram_goals(connection, project_id="project_9c")) == 1


def test_s5_cram_selection_scope_and_rollback(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        other = "project_other"
        _seed_project(connection, other)
        exercise = _exercise(connection)
        goal = create_cram_goal(connection, project_id="project_9c", title="Exam", target_date="2026-06-01", target_exercise_count=1)
        transition_cram_goal(connection, project_id="project_9c", goal_id=str(goal["id"]), target="active")
        with pytest.raises(ValueError, match="cram_selection_invalid"):
            create_cram_session(connection, project_id="project_9c", goal_id=str(goal["id"]), title="Empty", exercise_ids=[])
        with pytest.raises(ValueError, match="cram_selection_invalid"):
            create_cram_session(connection, project_id="project_9c", goal_id=str(goal["id"]), title="Too many", exercise_ids=[str(exercise["id"]), str(exercise["id"])])
        with pytest.raises(ValueError, match="cram_goal_not_found"):
            create_cram_session(connection, project_id=other, goal_id=str(goal["id"]), title="Wrong", exercise_ids=[str(exercise["id"])])
        connection.execute("CREATE TRIGGER fail_cram_item BEFORE INSERT ON practice_session_items BEGIN SELECT RAISE(ABORT, 'private'); END")
        with pytest.raises(sqlite3.IntegrityError):
            create_cram_session(connection, project_id="project_9c", goal_id=str(goal["id"]), title="Rollback", exercise_ids=[str(exercise["id"])])
        connection.execute("DROP TRIGGER fail_cram_item")
        assert connection.execute("SELECT COUNT(*) FROM practice_sessions WHERE cram_goal_id=?", (goal["id"],)).fetchone()[0] == 0


def test_project_and_state_boundaries_and_cram_does_not_touch_plan(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        other = "project_other"
        _seed_project(connection, other)
        exercise = _exercise(connection)
        with pytest.raises(ValueError, match="exercise_not_ready"):
            create_practice_session(connection, project_id=other, title="No", exercise_ids=[str(exercise["id"])])
        goal = create_cram_goal(connection, project_id="project_9c", title="Exam", target_date="2026-06-01", target_exercise_count=1)
        with pytest.raises(ValueError, match="cram_goal_invalid_state"):
            transition_cram_goal(connection, project_id="project_9c", goal_id=str(goal["id"]), target="completed")
        transition_cram_goal(connection, project_id="project_9c", goal_id=str(goal["id"]), target="active")
        cram = create_practice_session(connection, project_id="project_9c", title="Cram", exercise_ids=[str(exercise["id"])], session_kind="cram", cram_goal_id=str(goal["id"]))
        assert cram["session_kind"] == "cram"
        assert connection.execute("SELECT COUNT(*) FROM study_progress_events").fetchone()[0] == 0


def test_expired_session_rejects_submit_and_read_reclaims_status(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection)
        session = _active_session(connection, str(exercise["id"]))
        connection.execute("UPDATE practice_sessions SET deadline_at='2000-01-01T00:00:00+00:00' WHERE id=?", (session["id"],))
        item = session["items"][0]
        with pytest.raises(ValueError, match="practice_session_expired"):
            submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(item["id"]), answer=True)
        assert get_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))["status"] == "expired"
        assert get_practice_result(connection, project_id="project_9c", session_id=str(session["id"]))["summary"]["unanswered_count"] == 1


def test_session_source_lifecycle_retains_history_without_source_text(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise, material_id = _cited_exercise(connection)
        session = _active_session(connection, str(exercise["id"]))
        assert session["items"][0]["citation_status"] == "valid"
        assert soft_delete_material(connection, material_id) is True
        deleted = get_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))
        assert deleted["items"][0]["citation_status"] == "source_deleted"
        purge_material(connection, material_id)
        unavailable = get_practice_session(connection, project_id="project_9c", session_id=str(session["id"]))
        assert unavailable["items"][0]["citation_status"] == "source_unavailable"
        assert "answer_key_json" not in unavailable["items"][0]


def test_s4_source_status_degrades_without_deleting_mistake_facts(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise, material_id = _cited_exercise(connection)
        session = _active_session(connection, str(exercise["id"]))
        attempt = submit_practice_session_item(connection, project_id="project_9c", session_id=str(session["id"]), item_id=str(session["items"][0]["id"]), answer=False)
        case = list_mistake_cases(connection, project_id="project_9c")[0]
        assert soft_delete_material(connection, material_id) is True
        deleted = get_mistake_case(connection, project_id="project_9c", mistake_case_id=str(case["id"]))
        assert deleted["occurrences"][0]["source_status"] == "source_deleted"
        purge_material(connection, material_id)
        unavailable = get_mistake_case(connection, project_id="project_9c", mistake_case_id=str(case["id"]))
        assert unavailable["occurrences"][0]["source_status"] == "source_unavailable"
        assert unavailable["occurrences"][0]["attempt_id"] == attempt["id"]


def test_transaction_rolls_back_partial_session_on_snapshot_failure(tmp_path: Path):
    with connect(tmp_path / "studybuddy.sqlite3") as connection:
        _seed_project(connection)
        exercise = _exercise(connection)
        connection.execute("CREATE TRIGGER fail_session_item BEFORE INSERT ON practice_session_items BEGIN SELECT RAISE(ABORT, 'private'); END")
        with pytest.raises(sqlite3.IntegrityError):
            create_practice_session(connection, project_id="project_9c", title="Rollback", exercise_ids=[str(exercise["id"])])
        connection.execute("DROP TRIGGER fail_session_item")
        assert connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM practice_session_items").fetchone()[0] == 0
