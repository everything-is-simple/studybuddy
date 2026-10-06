import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def tracked_files(*parts: str) -> list[Path]:
    return [path for path in ROOT.joinpath(*parts).rglob("*") if path.is_file()]


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_repository_has_one_executable_test_contract():
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    governance = read("[架构师+测试看]CODE_TEST_GOVERNANCE.md")
    assert 'testpaths = ["backend/tests"]' in config
    assert "test-backend.ps1" in governance
    assert "test-browser.ps1" in governance
    backend_runner = ROOT / "backend/scripts/test-backend.ps1"
    browser_runner = ROOT / "backend/scripts/test-browser.ps1"
    cli_entry = ROOT / "backend/app/__main__.py"
    assert backend_runner.is_file()
    assert browser_runner.is_file()
    assert cli_entry.is_file()
    assert "from .cli import main" in cli_entry.read_text(encoding="utf-8")
    backend_runner_text = backend_runner.read_text(encoding="utf-8")
    assert "--basetemp=$baseTemp" in backend_runner_text
    assert "no:cacheprovider" in backend_runner_text
    assert "'--workers=1'" in browser_runner.read_text(encoding="utf-8")


def test_repository_facade_exports_all_current_public_contract_names():
    from app import repository

    for name in (
        "study_weekly_trend",
        "PHASE9D_REPORT_MAX_EXPORT_BYTES",
        "recommend_practice_exercises",
    ):
        assert hasattr(repository, name), name


def test_browser_runner_rejects_production_root_and_descendants():
    runner = (ROOT / "backend" / "scripts" / "test-browser.ps1").read_text(encoding="utf-8")
    assert "$productionRoot" in runner
    assert "OrdinalIgnoreCase" in runner
    assert "productionRoot + '\\'" in runner
    assert "browser_test_root_must_not_be_production_data_root" in runner
    assert "$testRootBase" in runner
    assert "browser_test_root_must_be_under_studybuddy_test" in runner
    assert "STUDYBUDDY_ASR_PROVIDER = 'fake'" in runner
    assert "STUDYBUDDY_ASR_RUNTIME,Env:STUDYBUDDY_ASR_MODEL_PATH" in runner


def test_service_e2e_runner_isolated_and_does_not_kill_existing_listeners():
    runner = (ROOT / "backend" / "scripts" / "run-e2e-with-service.ps1").read_text(encoding="utf-8")
    assert "e2e_data_root_must_not_be_production_data_root" in runner
    assert "e2e_data_root_must_be_under_studybuddy_test" in runner
    assert "STUDYBUDDY_AI_PROVIDER = 'fake'" in runner
    assert "Stop-ServiceOnPort" not in runner
    assert "Stop-Process" not in runner
    assert "STUDYBUDDY_BASE_URL" in runner


def test_browser_loader_default_paths_target_sibling_test_root():
    loader = (ROOT / "backend" / "scripts" / "browser-source-loader.js").read_text(encoding="utf-8")
    # The loader now rewrites legacy literals through injectable roots rather
    # than relying on a fragile relative path from an individual spec.
    assert 'STUDYBUDDY_TEST_ROOT || "H:/studybuddy-test"' in loader
    assert "STUDYBUDDY_FIXTURE_ROOT || process.env.STUDYBUDDY_TEST_ROOT" in loader
    assert "H:/studybuddy-test/fixtures" in loader
    assert "STUDYBUDDY_TEST_ROOT" in loader
    assert "STUDYBUDDY_BACKEND_ROOT" in loader
    assert "STUDYBUDDY_PYTHON" in loader


def test_reports_domain_binds_to_owning_parts_without_legacy_registry():
    reports_source = (ROOT / "backend" / "app" / "repositories" / "reports.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", reports_source)
    from app.repositories import reports
    from app.repositories import _legacy_part_05, _legacy_part_08

    assert not hasattr(reports, "_legacy")
    assert reports.PHASE9D_REPORT_MAX_EXPORT_BYTES is _legacy_part_05.PHASE9D_REPORT_MAX_EXPORT_BYTES
    assert reports.build_report_projection is _legacy_part_08.build_report_projection
    assert reports.export_report_snapshot is _legacy_part_08.export_report_snapshot


def test_plans_domain_binds_to_plan_parts_without_legacy_registry():
    plans_source = (ROOT / "backend" / "app" / "repositories" / "plans.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", plans_source)
    from app.repositories import _legacy_part_09, _legacy_part_10, _legacy_part_11
    from app.repositories import plans

    assert plans.create_study_plan is _legacy_part_09.create_study_plan
    assert plans.create_study_plan_item is _legacy_part_10.create_study_plan_item
    assert plans.study_weekly_trend is _legacy_part_11.study_weekly_trend


def test_materials_domain_binds_to_material_parts_without_legacy_registry():
    materials_source = (ROOT / "backend" / "app" / "repositories" / "materials.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", materials_source)
    from app.repositories import _legacy_part_01, _legacy_part_13, _legacy_part_14
    from app.repositories import materials

    assert materials.save_material_with_extraction is _legacy_part_01.save_material_with_extraction
    assert materials.list_materials is _legacy_part_01.list_materials
    assert materials.restore_material is _legacy_part_01.restore_material
    assert materials.material_state is _legacy_part_13.material_state
    assert materials.get_material is _legacy_part_13.get_material
    assert materials.rename_material is _legacy_part_13.rename_material
    assert materials.soft_delete_material is _legacy_part_14.soft_delete_material
    assert materials.purge_material is _legacy_part_14.purge_material


def test_tasks_domain_binds_to_task_part_without_legacy_registry():
    tasks_source = (ROOT / "backend" / "app" / "repositories" / "tasks.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", tasks_source)
    from app.repositories import _legacy_part_00
    from app.repositories import tasks

    assert tasks.TASK_TERMINAL_STATUSES is _legacy_part_00.TASK_TERMINAL_STATUSES
    assert tasks.TASK_ACTIVE_STATUSES is _legacy_part_00.TASK_ACTIVE_STATUSES
    assert tasks.TASK_STAGE_CODES is _legacy_part_00.TASK_STAGE_CODES
    for name in (
        "create_operation_task", "get_operation_task", "claim_operation_task",
        "update_operation_task_progress", "heartbeat_operation_task",
        "request_operation_task_cancel", "retry_operation_task",
        "finish_operation_task", "recover_active_operation_tasks",
        "reclaim_stale_operation_tasks",
    ):
        assert getattr(tasks, name) is getattr(_legacy_part_00, name)


def test_capture_domain_binds_to_capture_parts_without_legacy_registry():
    capture_source = (ROOT / "backend" / "app" / "repositories" / "capture.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", capture_source)
    from app.repositories import _legacy_part_05, _legacy_part_06, _legacy_part_07
    from app.repositories import capture

    assert not hasattr(capture, "_legacy")
    assert capture.PHASE9D_TRANSCRIPTION_OPERATION is _legacy_part_05.PHASE9D_TRANSCRIPTION_OPERATION
    assert capture.create_capture_session is _legacy_part_05.create_capture_session
    assert capture.upload_capture_asset is _legacy_part_06.upload_capture_asset
    assert capture.create_transcription_operation is _legacy_part_06.create_transcription_operation
    assert capture.complete_transcription_operation is _legacy_part_07.complete_transcription_operation
    assert capture.confirm_transcript_draft is _legacy_part_07.confirm_transcript_draft


def test_practice_domain_binds_to_practice_parts_without_legacy_registry():
    practice_source = (ROOT / "backend" / "app" / "repositories" / "practice.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", practice_source)
    from app.repositories import _legacy_part_03, _legacy_part_04, _legacy_part_05
    from app.repositories import practice

    assert not hasattr(practice, "_legacy")
    assert practice.PHASE9C_SESSION_TITLE_MAX is _legacy_part_03.PHASE9C_SESSION_TITLE_MAX
    assert practice.create_practice_session is _legacy_part_04.create_practice_session
    assert practice.finish_practice_session is _legacy_part_04.finish_practice_session
    assert practice.mark_mistake_from_attempt is _legacy_part_05.mark_mistake_from_attempt
    assert practice.recommend_practice_exercises is _legacy_part_05.recommend_practice_exercises


def test_learning_domain_binds_to_learning_parts_without_legacy_registry():
    learning_source = (ROOT / "backend" / "app" / "repositories" / "learning.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", learning_source)
    from app.repositories import _legacy_part_01, _legacy_part_02, _legacy_part_03
    from app.repositories import _legacy_part_11, _legacy_part_12, _legacy_part_13
    from app.repositories import learning

    assert not hasattr(learning, "_legacy")
    assert learning.create_card is _legacy_part_01.create_card
    assert learning.confirm_card is _legacy_part_02.confirm_card
    assert learning.create_exercise is _legacy_part_03.create_exercise
    assert learning.create_note is _legacy_part_11.create_note
    assert learning.list_notes is _legacy_part_12.list_notes
    assert learning.generate_note_draft is _legacy_part_13.generate_note_draft


def test_ai_domain_binds_to_ai_parts_without_legacy_registry():
    ai_source = (ROOT / "backend" / "app" / "repositories" / "ai.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", ai_source)
    from app.repositories import _legacy_part_00, _legacy_part_14, _legacy_part_15
    from app.repositories import _legacy_part_16, _legacy_part_17
    from app.repositories import ai

    assert not hasattr(ai, "_legacy")
    assert ai.RETRIEVAL_POLICY_VERSION is _legacy_part_00.RETRIEVAL_POLICY_VERSION
    assert ai.create_or_get_revision is _legacy_part_14.create_or_get_revision
    assert ai.create_embedding_index_operation is _legacy_part_15.create_embedding_index_operation
    assert ai.run_hybrid_retrieval is _legacy_part_16.run_hybrid_retrieval
    assert ai.create_qa_request is _legacy_part_17.create_qa_request
    assert ai.assemble_context is _legacy_part_17.assemble_context


def test_connection_domain_binds_to_runtime_and_task_part_without_legacy_registry():
    connection_source = (ROOT / "backend" / "app" / "repositories" / "connection.py").read_text(encoding="utf-8")
    assert not re.search(r"from \. import _legacy(?:\s|$)", connection_source)
    from app.repositories import _legacy_part_00, _legacy_runtime
    from app.repositories import connection

    assert not hasattr(connection, "_legacy")
    assert connection.connect is _legacy_part_00.connect
    assert connection.utc_now is _legacy_part_00.utc_now
    assert connection.VALID_STATUSES is _legacy_part_00.VALID_STATUSES
    assert connection.chunk_text is _legacy_runtime.chunk_text
    assert connection.store_original is _legacy_runtime.store_original
    assert connection.LLMProvider is _legacy_runtime.LLMProvider


