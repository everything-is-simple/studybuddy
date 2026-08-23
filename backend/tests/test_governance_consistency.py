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
