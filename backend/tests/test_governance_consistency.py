import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ARCHIVE = ROOT / ".archive"


def tracked_files(*parts: str) -> list[Path]:
    return [path for path in ROOT.joinpath(*parts).rglob("*") if path.is_file()]


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def read_archive(name: str) -> str:
    return (ARCHIVE / name).read_text(encoding="utf-8")


def test_authoritative_status_documents_agree_on_p6e_boundary():
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    status = read("[需求+所有角色看]STATUS.md")
    todo = read("[需求看]TODO.md")
    evidence = read_archive("evidence/P6E_ACCEPTANCE_EVIDENCE.md")

    assert "P6-E fake Provider" in roadmap
    assert "P6-E core workflow acceptance" in status
    assert "P6-E fake Provider 核心工作流整体验收" in todo
    assert "evidence/P6E_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "evidence/P6E_ACCEPTANCE_EVIDENCE.md" in status
    assert "Fake Provider complete workflow" in evidence
    assert "real network" in evidence
    assert "not global availability" in evidence


def test_governance_preserves_real_provider_and_runtime_boundaries():
    architecture = read("[架构师看]ARCHITECTURE.md")
    decisions = read("[架构+需求看]DECISIONS.md")
    progress = read("[需求+所有角色看]STATUS.md")
    provider_setup = read_archive("operations/AI_PROVIDER_SETUP.md")

    for document in (architecture, decisions, progress, provider_setup):
        assert "not_verified" in document
        assert "real-pass" in document

    assert "单进程" in architecture
    assert "synchronous Provider requests are not cancelled" in decisions
    assert "DeepSeek `deepseek-chat`" in progress
    assert "explicit opt-in" in provider_setup


def test_media_capability_selection_preserves_formal_boundaries():
    decision = read_archive("contracts/MEDIA_CAPABILITY_DECISION.md")
    roadmap = read("[需求+架构看]ROADMAP_CAPABILITIES.md")
    todo = read("[需求看]TODO.md")
    status = read("[需求+所有角色看]STATUS.md")
    architecture = read("[架构师看]ARCHITECTURE.md")
    frontend = read_archive("frontend/frontend-plan.md")
    phase_roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    progress = read("[需求+所有角色看]STATUS.md")

    for document in (decision, roadmap, todo, status, architecture, frontend, phase_roadmap, progress):
        assert "PaddleOCR" in document
        assert "RapidOCR" in document
    for document in (status, architecture, progress):
        assert "H:/Whisper" in document
    for document in (decision, roadmap, todo, architecture, phase_roadmap, progress):
        assert "edge-tts" in document
    assert "deterministic fake/loopback" in decision
    assert "C1" in decision
    assert "not_verified" in decision
    assert "不属于当前 Phase 9D 批准业务范围" in decision
    assert "C1" in roadmap and "smoke" in roadmap
    assert "Composer smoke -> Integration -> Formal" in todo


def test_phase8_closeout_is_consistent_and_temporary_prompts_are_removed():
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    status = read("[需求+所有角色看]STATUS.md")
    todo = read("[需求看]TODO.md")
    progress = read("[需求+所有角色看]STATUS.md")
    evidence = read_archive("evidence/PHASE8_ACCEPTANCE_EVIDENCE.md")

    for document in (roadmap, status, todo, progress):
        assert "PHASE8_ACCEPTANCE_EVIDENCE.md" in document
    assert "completed" in roadmap
    assert "deterministic `fake` LLM provider" in evidence
    assert "No real Provider Cards/Exercises generation evidence" in evidence
    assert "250 passed, 2 skipped" in evidence
    assert not (DOCS / "phase8").exists()


def test_phase9a_contract_migration_and_status_are_consistent():
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    status = read("[需求+所有角色看]STATUS.md")
    todo = read("[需求看]TODO.md")
    progress = read("[需求+所有角色看]STATUS.md")
    architecture = read("[架构师看]AI_LEARNING_ARCHITECTURE.md")
    decisions = read("[架构+需求看]DECISIONS.md")
    migration_doc = read("[架构师+运维看]MIGRATIONS.md")
    contract = read_archive("contracts/PHASE9A_DOMAIN_CONTRACT.md")
    acceptance = read_archive("evidence/PHASE9A_ACCEPTANCE_EVIDENCE.md")
    runner = (ROOT / "backend" / "app" / "migrations" / "runner.py").read_text(encoding="utf-8")

    for document in (roadmap, status, todo, progress, architecture):
        assert "v9" in document
    for document in (roadmap, todo, contract):
        assert "9A-2" in document
    assert "Phase 9A" in status
    assert "v9" in status
    assert "contracts/PHASE9A_DOMAIN_CONTRACT.md" in status
    assert "Current schema version: **15**." in migration_doc
    assert "9 | phase9a_learning_plan_schema" in migration_doc
    assert "10 | phase9b_material_learning_schema" in migration_doc
    assert "11 | phase9c_exercise_feedback_schema" in migration_doc
    assert "CURRENT_SCHEMA_VERSION = 15" in runner
    assert '(9, "phase9a_learning_plan_schema", v09.migrate)' in runner
    assert '(10, "phase9b_material_learning_schema", v10.migrate)' in runner
    assert '(11, "phase9c_exercise_feedback_schema", v11.migrate)' in runner
    assert "12 | phase9d_extended_learning_schema" in migration_doc
    assert '(12, "phase9d_extended_learning_schema", v12.migrate)' in runner
    assert "13 | phase10_operation_task_schema" in migration_doc
    assert '(13, "phase10_operation_task_schema", v13.migrate)' in runner
    assert "implemented/backend-pass" in contract
    assert "repository/domain transaction" in contract
    assert "API/UI" in contract
    assert "source lifecycle refresh" in contract
    assert "9A-4 implemented/backend-pass" in contract
    assert (ROOT / "backend" / "tests" / "test_phase9a_api.py").is_file()
    assert "9A-5 browser-pass" in contract
    assert "9A-6 `scoped-gates-pass`" in contract
    assert "9A-7 `restore-gates-pass`" in contract
    assert "9A-8 `completed`" in contract
    assert "272 passed, 2 skipped" in status
    assert "272 passed, 2 skipped" in progress
    assert "3 passed" in status
    assert "3 passed" in progress
    assert "PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md" in status
    assert "PHASE9A_BACKUP_RESTORE_EVIDENCE.md" in status
    for document in (roadmap, status, todo, progress, architecture, decisions, contract):
        assert "PHASE9A_ACCEPTANCE_EVIDENCE.md" in document
    assert "Phase 9A completed" in acceptance
    assert "272 passed, 2 skipped" in acceptance
    assert "3 passed" in acceptance
    assert "Phase 9B–9D" in acceptance
    assert "focused backend `16 passed`" in contract
    assert "full backend `272 passed, 2 skipped`" in contract
    assert "Phase 9A Chromium `3 passed`" in contract
    assert "Phase 9A completed" in contract
    assert (ROOT / "backend" / "tests" / "browser_phase9a.spec.js").is_file()
    assert "Phase 9A" in roadmap and "browser-pass" in roadmap
    assert not (DOCS / "PHASE9A_DOMAIN_CONTRACT.md").exists()


def test_phase9b_closeout_and_current_regression_are_consistent():
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    status = read("[需求+所有角色看]STATUS.md")
    todo = read("[需求看]TODO.md")
    progress = read("[需求+所有角色看]STATUS.md")
    architecture = read("[架构师看]ARCHITECTURE.md")
    contract = read_archive("contracts/PHASE9B_DOMAIN_CONTRACT.md")
    evidence = read_archive("evidence/PHASE9B_ACCEPTANCE_EVIDENCE.md")
    decisions = read("[架构+需求看]DECISIONS.md")
    governance = read("[架构师+测试看]CODE_TEST_GOVERNANCE.md")

    for document in (roadmap, status, todo, progress, architecture, contract, decisions):
        assert "PHASE9B_ACCEPTANCE_EVIDENCE.md" in document
    for document in (roadmap, status, todo, progress, contract, evidence):
        assert "299 passed, 2 skipped" in document
    for document in (status, todo, progress, evidence):
        assert "45 passed" in document
    assert "9B-9" in roadmap and "Gate A-I" in roadmap
    assert "9B-9" in todo and "completed" in todo
    assert "9B-9" in contract and "completed" in contract
    assert "Phase 9B 已在 deterministic fake-provider" in evidence
    assert "Phase 9C/9D" in evidence
    assert "real Provider generation" in evidence
    assert "scheduler/worker" in evidence
    assert "299 passed, 2 skipped" in governance
    assert "Phase 9B" in governance
    assert "真实 Provider" in governance


def test_roadmap_orders_deferred_learning_after_phase6():
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    assert roadmap.index("Phase 6：AI MVP 产品化与整体验收") < roadmap.index("### Phase 7：Embedding 与 Hybrid Retrieval")
    assert "Phase 7：embedding / hybrid retrieval（按需，下一产品阶段）" in roadmap
    assert "Phase 8：卡片与练习" in roadmap
    phase8 = roadmap.index("Phase 8：卡片与练习")
    for phase in (
        "Phase 9A：学习领域基础与计划核心",
        "Phase 9B：资料学习工作流（S1/S2）",
        "Phase 9C：练习与反馈工作流（S3/S4/S5）",
        "Phase 9D：扩展学习服务（S6/S7，条件性）",
    ):
        assert phase in roadmap
        assert phase8 < roadmap.index(phase)
        phase8 = roadmap.index(phase)


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


def test_current_regression_fact_source_matches_latest_backend_gate():
    status = read("[需求+所有角色看]STATUS.md")
    governance = read("[架构师+测试看]CODE_TEST_GOVERNANCE.md")
    todo = read("[需求看]TODO.md")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = read("[需求+架构看]ROADMAP_CAPABILITIES.md")

    for document in (todo, readme):
        assert "665 passed, 3 skipped" in document[:2500]
        assert "当前 backend 基线为 `665 passed, 3 skipped`" in governance
        assert "665 passed / 3 skipped" in status
        assert "当前 backend 基线为 `665 passed, 3 skipped`" in roadmap
    assert "Chromium" in status and "not_verified" in status
    assert "RapidOCR" in status and "严格 C2" in status
    assert "H:\\Whisper" in roadmap


def test_repository_boundaries_and_runtime_artifacts_are_explicit():
    assert all(path.is_relative_to(ROOT / "backend" / "app") for path in tracked_files("backend", "app"))
    assert all(path.is_relative_to(ROOT / "backend" / "tests") for path in tracked_files("backend", "tests"))
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("*.sqlite3", "*.db", "test-results/", "playwright-report/", ".env"):
        assert entry in gitignore
    # 检查 INDEX.md 包含关键文档的引用（使用新的文件名）
    index_content = read("INDEX.md")
    for keyword in ("STATUS", "TODO", "CODE_TEST_GOVERNANCE", "ARCHITECTURE"):
        assert keyword in index_content

    allowed_core_docs = {
        "[架构师看]ARCHITECTURE.md",
        "[运维看]BACKUP_RESTORE.md",
        "[维护者看]CLEAN_SYSTEM_PROMPT.md",
        "[维护者看]CODE_DOCUMENTATION_PROJECT.md",
        "[维护者看]PI_WORKFLOW.md",
        "[架构师+测试看]CODE_TEST_GOVERNANCE.md",
        "[架构+需求看]DECISIONS.md",
        "INDEX.md",
        "[UI设计+用户看]LOCAL_V1_USER_GUIDE.md",
        "[架构师+运维看]MIGRATIONS.md",
        "[需求+测试看]P1_7_REAL_USE_CHECKLIST.md",
        "[需求+架构看]ROADMAP_CAPABILITIES.md",
        "[需求+所有角色看]STATUS.md",
        "[需求看]TODO.md",
        "[架构师看]AI_LEARNING_ARCHITECTURE.md",
        "[架构师+运维看]WORKSPACE_DIRECTORIES.md",
    }
    assert allowed_core_docs.issubset({path.name for path in DOCS.glob("*.md")})
    # contracts, evidence, operations 已移至 .archive/
    assert (ROOT / ".archive" / "contracts").is_dir()
    assert (ROOT / ".archive" / "evidence").is_dir()
    assert (ROOT / ".archive" / "operations").is_dir()
    assert not any((DOCS / "prompts").rglob("*.md"))
    # 证据文件已移至 .archive/evidence/
    assert (ARCHIVE / "evidence" / "PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md").is_file()
    assert (ARCHIVE / "evidence" / "PHASE9A_BACKUP_RESTORE_EVIDENCE.md").is_file()


def test_markdown_relative_links_resolve_after_document_moves():
    markdown_files = [ROOT / "README.md", ROOT / "AGENTS.md", *DOCS.rglob("*.md")]
    link_pattern = re.compile(r"\[[^]]*\]\(([^)]+)\)")
    broken: list[str] = []

    for document in markdown_files:
        for target in link_pattern.findall(document.read_text(encoding="utf-8")):
            if not target or target.startswith(("http:", "https:", "mailto:", "#")):
                continue
            relative_target = unquote(target.split("#", 1)[0])
            if not (document.parent / relative_target).resolve().exists():
                broken.append(f"{document.relative_to(ROOT)} -> {target}")

    assert not broken, "Broken Markdown links:\n" + "\n".join(broken)


def test_core_design_tracks_current_phase_and_moved_document_links():
    architecture = read("[架构师看]ARCHITECTURE.md")
    ai_architecture = read("[架构师看]AI_LEARNING_ARCHITECTURE.md")
    backup = read("[运维看]BACKUP_RESTORE.md")
    migrations = read("[架构师+运维看]MIGRATIONS.md")
    roadmap = read_archive("historical-roadmaps/PHASE_ROADMAP.md")
    progress = read("[需求+所有角色看]STATUS.md")
    status = read("[需求+所有角色看]STATUS.md")
    phase9d = read_archive("evidence/PHASE9D_ACCEPTANCE_EVIDENCE.md")
    restore_acceptance = (ROOT / "backend" / "app" / "restore_acceptance.py").read_text(encoding="utf-8")

    for document in (architecture, ai_architecture, progress):
        assert "Phase 9C" in document
        assert "PHASE9C_ACCEPTANCE_EVIDENCE.md" in document
        assert "PHASE9D_ACCEPTANCE_EVIDENCE.md" in document
    for document in (architecture, ai_architecture, progress, status, phase9d):
        assert "v12" in document
        assert "Phase 9D" in document
    for document in (architecture, ai_architecture, progress, status):
        assert "v13" in document
    assert "operation_tasks" in restore_acceptance
    assert "not_run_by_restore_acceptance" in restore_acceptance
    assert "Phase 9D" in roadmap
    assert "PHASE9D_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "当前正式 schema 为 v11" not in architecture
    assert "API/UI、完整 source lifecycle/restore gates" not in ai_architecture
    assert "evidence/P6E_ACCEPTANCE_EVIDENCE.md" in architecture
    assert "operations/BACKUP_OPERATIONS.md" in backup
    assert "operations/RESTORE_DRILL.md" in backup
    assert "Phase 9D capture-session" in migrations
    assert "OCR/ASR" in backup and "report generation" in backup and "delivery" in backup
    assert "_phase9d_checks" in restore_acceptance
    assert "acceptance_phase9d_schema_missing" in restore_acceptance
    assert "evidence/PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "DECISIONS.md" in progress
