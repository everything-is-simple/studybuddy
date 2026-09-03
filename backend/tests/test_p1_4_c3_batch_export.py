from pathlib import Path


STATIC = Path(__file__).parents[1] / "app" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_materials_page_exposes_scoped_batch_export_controls():
    page = read("materials.html")
    assert 'id="select-page"' in page
    assert 'id="selection-status"' in page
    assert 'id="export-originals"' in page
    assert 'id="export-texts"' in page
    assert 'id="export-all"' in page
    assert "visibleIds" in page
    assert "resetSelection();\nconst generation=++loadGeneration" in page
    assert "batchExport.hidden=currentView!=='active'||!rows.length" in page


def test_batch_export_reuses_existing_api_contract_for_all_modes():
    page = read("materials.html")
    assert "'/api/materials/export'" in page
    assert "material_ids:Array.from(selectedIds)" in page
    assert "include_original:includeOriginal" in page
    assert "include_text:includeText" in page
    assert "exportSelected(true,false)" in page
    assert "exportSelected(false,true)" in page
    assert "exportSelected(true,true)" in page


def test_batch_export_checks_zip_and_recovers_controls_after_failure():
    page = read("materials.html")
    api = read("js/api.js")
    assert "if(exportBusy||!selectedIds.size)return" in page
    assert "if(!blob.type.includes('zip')||blob.size<4)" in page
    assert "finally{\nexportBusy=false;updateSelection()" in page
    assert "material_export_failed:'" in api
    assert "invalid_export_request:'" in api
    assert "export_too_large:'" in api


def test_c3_page_does_not_render_private_export_fields():
    page = read("materials.html").lower()
    for value in ("stored_path", "source_sha256", "traceback", "api_key", "select *"):
        assert value not in page
