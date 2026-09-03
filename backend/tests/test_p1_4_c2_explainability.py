"""Focused static contract checks for the P1-4 C2 usability slice."""

from pathlib import Path

ROOT = Path(__file__).parents[1]
STATIC = ROOT / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_source_status_mapping_never_defaults_missing_links_to_valid():
    state = read("js/state.js")
    plans = read("plans.html")
    today = read("today.html")
    assert "not_linked:'未关联来源'" in state
    assert "linksForItem(item,links)" in state
    assert "sourceForItem(item,plan.source_links)" in plans
    assert "sourceForItem(item,plan.source_links)" in today
    assert "||item.source_status||'valid'" not in today
    assert "source_link_status)}" not in plans


def test_today_only_enables_material_action_for_valid_link():
    today = read("today.html")
    assert "materialForItem(item,plan.source_links)" in today
    assert "sourceStatus!=='valid'" in today
    assert "aria-disabled" in today


def test_material_picker_matches_parser_contract_and_explains_rejections():
    materials = read("materials.html")
    detail = read("material-detail.html")
    assert 'accept=".pdf,.txt,.md,.docx,.pptx"' in materials
    assert "DOC、PPT、RTF" in materials
    assert "sbApi.safeError({code:item.error_code})" in materials
    assert "解析状态" in detail
    assert "解析器" in detail
    assert "解析提示" in detail
    assert "没有可提取的正文" in detail
    assert "请转换或修复文件后重新导入" in detail


def test_c2_static_surfaces_do_not_render_sensitive_backend_fields():
    for name in ("plans.html", "today.html", "materials.html", "material-detail.html", "js/state.js"):
        content = read(name)
        assert "stored_path" not in content
        assert "traceback" not in content.lower()
        assert "api_key" not in content.lower()
