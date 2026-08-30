import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


def tracked_files(*parts: str) -> list[Path]:
    return [path for path in ROOT.joinpath(*parts).rglob("*") if path.is_file()]


def read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_authoritative_status_documents_agree_on_p6e_boundary():
    roadmap = read("PHASE_ROADMAP.md")
    status = read("STATUS.md")
    todo = read("TODO.md")
    evidence = read("prompts/P6E_ACCEPTANCE_EVIDENCE.md")

    assert "P6-E fake Provider" in roadmap
    assert "P6-E core workflow acceptance" in status
    assert "P6-E fake Provider 核心工作流整体验收" in todo
    assert "prompts/P6E_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "prompts/P6E_ACCEPTANCE_EVIDENCE.md" in status
    assert "Fake Provider complete workflow" in evidence
    assert "real network" in evidence
    assert "not global availability" in evidence


def test_governance_preserves_real_provider_and_runtime_boundaries():
    architecture = read("ARCHITECTURE.md")
    decisions = read("prompts/DECISIONS.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    provider_setup = read("prompts/AI_PROVIDER_SETUP.md")

    for document in (architecture, decisions, progress, provider_setup):
        assert "not_verified" in document
        assert "real-pass" in document

    assert "单进程" in architecture
    assert "synchronous Provider requests are not cancelled" in decisions
    assert "DeepSeek `deepseek-chat`" in progress
    assert "explicit opt-in" in provider_setup


def test_media_capability_selection_preserves_formal_boundaries():
    decision = read("prompts/MEDIA_CAPABILITY_DECISION.md")
    roadmap = read("ROADMAP_CAPABILITIES.md")
    todo = read("TODO.md")
    status = read("STATUS.md")
    architecture = read("ARCHITECTURE.md")
    frontend = read("frontend-plan.md")
    phase_roadmap = read("PHASE_ROADMAP.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")

    for document in (decision, roadmap, todo, status, architecture, frontend, phase_roadmap, progress):
        assert "PaddleOCR" in document
        assert "RapidOCR" in document
    for document in (decision, status, architecture, phase_roadmap, progress):
        assert "H:/WhisperCli" in document
    for document in (decision, roadmap, todo, architecture, phase_roadmap, progress):
        assert "edge-tts" in document
    assert "deterministic fake/loopback" in decision
    assert "C1" in decision
    assert "not_verified" in decision
    assert "不属于当前 Phase 9D 批准业务范围" in decision
    assert "C1 smoke" in roadmap
    assert "Composer smoke -> Integration -> Formal" in todo


def test_phase8_closeout_is_consistent_and_temporary_prompts_are_removed():
    roadmap = read("PHASE_ROADMAP.md")
    status = read("STATUS.md")
    todo = read("TODO.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    evidence = read("prompts/PHASE8_ACCEPTANCE_EVIDENCE.md")

    for document in (roadmap, status, todo, progress):
        assert "PHASE8_ACCEPTANCE_EVIDENCE.md" in document
    assert "completed" in roadmap
    assert "deterministic `fake` LLM provider" in evidence
    assert "No real Provider Cards/Exercises generation evidence" in evidence
    assert "250 passed, 2 skipped" in evidence
    assert not (DOCS / "phase8").exists()


def test_phase9a_contract_migration_and_status_are_consistent():
    roadmap = read("PHASE_ROADMAP.md")
    status = read("STATUS.md")
    todo = read("TODO.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    architecture = read("ai-learning-architecture.md")
    decisions = read("prompts/DECISIONS.md")
    migration_doc = read("MIGRATIONS.md")
    contract = read("prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md")
    acceptance = read("prompts/PHASE9A_ACCEPTANCE_EVIDENCE.md")
    runner = (ROOT / "backend" / "app" / "migrations" / "runner.py").read_text(encoding="utf-8")

    for document in (roadmap, status, todo, progress, architecture):
        assert "v9" in document
    for document in (roadmap, todo, contract):
        assert "9A-2" in document
    assert "Phase 9A" in status
    assert "v9" in status
    assert "prompts/phase9a/PHASE9A_DOMAIN_CONTRACT.md" in status
    assert "Current schema version: **13**." in migration_doc
    assert "9 | phase9a_learning_plan_schema" in migration_doc
    assert "10 | phase9b_material_learning_schema" in migration_doc
    assert "11 | phase9c_exercise_feedback_schema" in migration_doc
    assert "CURRENT_SCHEMA_VERSION = 13" in runner
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
    roadmap = read("PHASE_ROADMAP.md")
    status = read("STATUS.md")
    todo = read("TODO.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    architecture = read("ARCHITECTURE.md")
    contract = read("prompts/phase9b/PHASE9B_DOMAIN_CONTRACT.md")
    evidence = read("prompts/PHASE9B_ACCEPTANCE_EVIDENCE.md")
    decisions = read("prompts/DECISIONS.md")
    governance = read("CODE_TEST_GOVERNANCE.md")

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
    roadmap = read("PHASE_ROADMAP.md")
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
    governance = read("CODE_TEST_GOVERNANCE.md")
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


def test_repository_boundaries_and_runtime_artifacts_are_explicit():
    assert all(path.is_relative_to(ROOT / "backend" / "app") for path in tracked_files("backend", "app"))
    assert all(path.is_relative_to(ROOT / "backend" / "tests") for path in tracked_files("backend", "tests"))
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("*.sqlite3", "*.db", "test-results/", "playwright-report/", ".env"):
        assert entry in gitignore
    for name in ("STATUS.md", "TODO.md", "PHASE_ROADMAP.md", "CODE_TEST_GOVERNANCE.md"):
        assert name in read("INDEX.md")

    allowed_core_docs = {
        "ARCHITECTURE.md",
        "A4_COMPLETION_REPORT.md",
        "A4_SUMMARY.md",
        "BACKUP_RESTORE.md",
        "CODE_TEST_GOVERNANCE.md",
        "INDEX.md",
        "MIGRATIONS.md",
        "frontend-plan.md",
        "frontend-contract-audit.md",
        "frontend-contract-audit-report.md",
        "frontend-implementation-diff-report.md",
        "frontend-static-capability-matrix.md",
        "frontend-static-failure-retry-matrix.md",
        "frontend-practice-workflow-contract.md",
        "component-adoption-audit-2026-08-27.md",
        "PHASE_ROADMAP.md",
        "PROJECT_PROGRESS_REPORT.md",
        "ROADMAP_CAPABILITIES.md",
        "STATUS.md",
        "TODO.md",
        "ai-learning-architecture.md",
        "LOCAL_V1_USER_GUIDE.md",
    }
    assert {path.name for path in DOCS.glob("*.md")} == allowed_core_docs
    assert (DOCS / "prompts" / "README.md").is_file()
    assert (DOCS / "prompts" / "evidence" / "PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md").is_file()
    assert (DOCS / "prompts" / "evidence" / "PHASE9A_BACKUP_RESTORE_EVIDENCE.md").is_file()
    assert not (DOCS / "PHASE9A_SOURCE_LIFECYCLE_EVIDENCE.md").exists()
    assert not (DOCS / "PHASE9A_BACKUP_RESTORE_EVIDENCE.md").exists()


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
    architecture = read("ARCHITECTURE.md")
    ai_architecture = read("ai-learning-architecture.md")
    backup = read("BACKUP_RESTORE.md")
    migrations = read("MIGRATIONS.md")
    roadmap = read("PHASE_ROADMAP.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    status = read("STATUS.md")
    phase9d = read("prompts/PHASE9D_ACCEPTANCE_EVIDENCE.md")
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
    assert "prompts/P6E_ACCEPTANCE_EVIDENCE.md" in architecture
    assert "prompts/BACKUP_OPERATIONS.md" in backup
    assert "prompts/RESTORE_DRILL.md" in backup
    assert "Phase 9D capture-session" in migrations
    assert "OCR/ASR" in backup and "report generation" in backup and "delivery" in backup
    assert "_phase9d_checks" in restore_acceptance
    assert "acceptance_phase9d_schema_missing" in restore_acceptance
    assert "prompts/PHASE7_EMBEDDING_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "prompts/DECISIONS.md" in progress
