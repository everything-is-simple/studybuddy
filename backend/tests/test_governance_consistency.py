from pathlib import Path


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
    evidence = read("P6E_ACCEPTANCE_EVIDENCE.md")

    assert "P6-E fake Provider" in roadmap
    assert "P6-E core workflow acceptance" in status
    assert "P6-E fake Provider 核心工作流整体验收" in todo
    assert "P6E_ACCEPTANCE_EVIDENCE.md" in roadmap
    assert "P6E_ACCEPTANCE_EVIDENCE.md" in status
    assert "Fake Provider complete workflow" in evidence
    assert "real network" in evidence
    assert "not global availability" in evidence


def test_governance_preserves_real_provider_and_runtime_boundaries():
    architecture = read("ARCHITECTURE.md")
    decisions = read("DECISIONS.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    provider_setup = read("AI_PROVIDER_SETUP.md")

    for document in (architecture, decisions, progress, provider_setup):
        assert "not_verified" in document
        assert "real-pass" in document

    assert "单进程" in architecture
    assert "synchronous Provider requests are not cancelled" in decisions
    assert "DeepSeek `deepseek-chat`" in progress
    assert "explicit opt-in" in provider_setup


def test_phase8_closeout_is_consistent_and_temporary_prompts_are_removed():
    roadmap = read("PHASE_ROADMAP.md")
    status = read("STATUS.md")
    todo = read("TODO.md")
    progress = read("PROJECT_PROGRESS_REPORT.md")
    evidence = read("PHASE8_ACCEPTANCE_EVIDENCE.md")

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
    migration_doc = read("MIGRATIONS.md")
    contract = read("phase9a/PHASE9A_DOMAIN_CONTRACT.md")
    runner = (ROOT / "backend" / "app" / "migrations" / "runner.py").read_text(encoding="utf-8")

    for document in (roadmap, status, todo, progress, architecture):
        assert "9A-2" in document
        assert "v9" in document
    assert "phase9a/PHASE9A_DOMAIN_CONTRACT.md" in status
    assert "Current schema version: **9**." in migration_doc
    assert "9 | phase9a_learning_plan_schema" in migration_doc
    assert "CURRENT_SCHEMA_VERSION = 9" in runner
    assert '(9, "phase9a_learning_plan_schema", _migration_v9)' in runner
    assert "implemented/backend-pass" in contract
    assert "repository/domain transaction" in contract
    assert "API/UI" in contract
    assert "source lifecycle refresh" in contract
    assert "9A-4 implemented/backend-pass" in contract
    assert (ROOT / "backend" / "tests" / "test_phase9a_api.py").is_file()
    assert "9A-5 browser-pass" in contract
    assert "9A-6 source lifecycle" in contract
    assert "261 passed, 7 skipped" in status
    assert "261 passed, 7 skipped" in progress
    assert "2 passed" in status
    assert "2 passed" in progress
    assert (ROOT / "backend" / "tests" / "browser_phase9a.spec.js").is_file()
    assert "261 passed, 7 skipped" not in contract
    assert "Phase 9A" in roadmap and "browser-pass" in roadmap
    assert not (DOCS / "PHASE9A_DOMAIN_CONTRACT.md").exists()


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
    assert backend_runner.is_file()
    assert browser_runner.is_file()
    assert "'--workers=1'" in browser_runner.read_text(encoding="utf-8")


def test_repository_boundaries_and_runtime_artifacts_are_explicit():
    assert all(path.is_relative_to(ROOT / "backend" / "app") for path in tracked_files("backend", "app"))
    assert all(path.is_relative_to(ROOT / "backend" / "tests") for path in tracked_files("backend", "tests"))
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("*.sqlite3", "*.db", "test-results/", "playwright-report/", ".env"):
        assert entry in gitignore
    for name in ("STATUS.md", "TODO.md", "PHASE_ROADMAP.md", "CODE_TEST_GOVERNANCE.md"):
        assert name in read("INDEX.md")
