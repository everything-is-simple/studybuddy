"""P1-6-0 expanded B1-B4 verification scope governance tests."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
APP = ROOT / "backend" / "app"


CONTRACT = DOCS / "contracts" / "P1_6_VERIFICATION_SCOPE_CONTRACT.md"
EVIDENCE = DOCS / "evidence" / "P1_6_0_AUDIT_EVIDENCE.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p1_6_contract_and_evidence_exist_with_frozen_state() -> None:
    assert CONTRACT.is_file()
    assert EVIDENCE.is_file()
    contract = read(CONTRACT)
    evidence = read(EVIDENCE)
    assert "P1-6-0" in contract and "contract-frozen" in contract
    assert "P1-6-0" in evidence and "audit-complete" in evidence
    assert "不代表" in contract and "real-pass" in contract
    assert "不代表" in evidence and "real-pass" in evidence


def test_p1_6_contract_covers_all_four_capabilities_and_sources() -> None:
    contract = read(CONTRACT)
    evidence = read(EVIDENCE)
    for capability in ("B1 ASR", "B2 OCR", "B3 reports", "B4 delivery"):
        assert capability in contract
        assert capability in evidence
    for source in (
        "FORMAL_ASR_ACCEPTANCE_EVIDENCE.md",
        "B2_IMAGE_OCR_PROVIDER_CONTRACT.md",
        "B3_REPORT_COMPONENT_CONTRACT.md",
        "B4_DELIVERY_COMPONENT_CONTRACT.md",
    ):
        assert source in contract
        assert source in evidence


def test_p1_6_contract_freezes_required_verification_dimensions() -> None:
    contract = read(CONTRACT)
    for dimension in ("输入集", "取消/中断", "并发", "失败恢复", "跨环境", "真实用户路径"):
        assert dimension in contract
    assert "not_verified" in contract
    assert "P1-6-1" in contract
    assert "P1-6-6" in contract


def test_p1_6_contract_preserves_delivery_and_deployment_boundaries() -> None:
    contract = read(CONTRACT)
    evidence = read(EVIDENCE)
    for text in (contract, evidence):
        assert "delivery=off" in text
        assert "single-process" in text or "单进程" in text
        assert "single-instance" in text or "单实例" in text
        assert "SQLite" in text
        assert "local-disk" in text or "local disk" in text
    assert "产品 API live closed" in evidence


def test_p1_6_contract_has_no_new_production_or_schema_scope() -> None:
    contract = read(CONTRACT)
    evidence = read(EVIDENCE)
    for text in (contract, evidence):
        assert "不修改 `backend/app/`" in text or "不新增 API/schema/migration" in text
        assert "不新增或修改 schema" in text or "不新增 API/schema/migration" in text
        assert "不新增或修改" in text or "不新增 API/schema/migration" in text
    assert not (APP / "p1_6.py").exists()
    assert not (APP / "api" / "p1_6.py").exists()


def test_p1_6_evidence_records_gap_ledger_and_next_slice() -> None:
    evidence = read(EVIDENCE)
    assert "Gap ledger" in evidence
    assert "P1-6 后续建议拆分" in evidence
    assert "P1-6-1 B1 输入集与可取消性" in evidence
    assert "P1-6-2 B2 输入集与失败恢复" in evidence
    assert "P1-6-3 B3 跨环境与恢复矩阵" in evidence
    assert "P1-6-4 B4 adapter isolation 与 no-send recovery" in evidence


def test_p1_6_real_execution_requires_explicit_gates() -> None:
    contract = read(CONTRACT)
    for phrase in (
        "显式设置唯一的 provider/model/runtime/gateway/target",
        "独立临时 `data_root`",
        "禁止保存 secret",
        "显式 opt-in",
        "不打开产品 live API",
    ):
        assert phrase in contract


def test_p1_6_current_status_is_not_completed() -> None:
    status = read(DOCS / "STATUS.md")
    todo = read(DOCS / "TODO.md")
    roadmap = read(DOCS / "ROADMAP_CAPABILITIES.md")
    assert "P1-6：扩大" in todo
    assert "- [ ] P1-6" in todo
    assert "P1-6" in status
    assert "P1-6" in roadmap
    assert "逐项立项和验收" in roadmap


def test_p1_6_does_not_add_schema_or_migration_artifacts() -> None:
    migrations = ROOT / "backend" / "app" / "migrations"
    migration_names = {path.name.lower() for path in migrations.glob("*")}
    assert not any("p1_6" in name or "verification_scope" in name for name in migration_names)
    assert "schema" in read(CONTRACT).lower()
    assert "migration" in read(CONTRACT).lower()


def test_p1_6_evidence_explicitly_keeps_unverified_boundaries() -> None:
    evidence = read(EVIDENCE)
    for boundary in (
        "任意语言/音频/图片质量",
        "并发/容量",
        "跨 OS/GPU",
        "自动调度",
        "真实断电",
        "global production `real-pass`",
    ):
        assert boundary in evidence


def test_p1_6_next_slice_is_b1_and_not_an_implicit_implementation() -> None:
    contract = read(CONTRACT)
    assert "推荐下一步为 P1-6-1" in contract
    assert "P1-6-0 只做审计与契约冻结" in contract
    assert "不调用真实 ASR/OCR/Provider/delivery runtime" in contract
