from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


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
    assert "Phase 9：学习计划 / S1–S7" in roadmap
