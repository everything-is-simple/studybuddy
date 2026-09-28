"""Focused contracts for the Buddy P0 revision."""
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_source_display_contract_is_defined_and_three_state_only():
    state = (ROOT / "app" / "static" / "js" / "state.js").read_text(encoding="utf-8")
    assert "sourceDisplay(value){return this.displayLabel(value)}" in state
    assert "可用" in state and "处理中" in state and "有问题" in state


def test_error_info_contract_has_buddy_actions_and_safe_fallback():
    api = (ROOT / "app" / "static" / "js" / "api.js").read_text(encoding="utf-8")
    assert "window.sbApiErrorInfo=function(error)" in api
    assert "study_plan_dependency_cycle" in api and "plan-dependency-predecessor" in api
    assert "study_rhythm_allocation_duplicate" in api and "rhythm-date" in api
    assert "learning_goal_archived" in api and "plans-reload" in api
    assert "action:{type:'retry',control:'retry'}" in api
    assert "window.sbApi.errorInfo=window.sbApiErrorInfo" in api


def test_today_progress_is_inline_and_idempotent_guarded():
    today = (ROOT / "app" / "static" / "today.html").read_text(encoding="utf-8")
    assert "POST" in today or "method:'POST'" in today
    assert "/progress`" in today
    assert "sbSubmit.once(key" in today
    assert "continueButton.onclick" in today
    assert "continue-btn" in today and "type=" in today
