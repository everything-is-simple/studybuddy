"""Compatibility exports for the materials repository domain."""

from . import _legacy

from ._legacy import (
    save_extraction,
    save_material_with_extraction,
    list_materials,
    list_deleted_materials,
    list_materials_page,
    list_deleted_materials_page,
    restore_material,
    material_state,
    get_material,
    get_spans,
    rename_material,
    purge_material,
    soft_delete_material,
)

__all__ = [
    'save_extraction',
    'save_material_with_extraction',
    'list_materials',
    'list_deleted_materials',
    'list_materials_page',
    'list_deleted_materials_page',
    'restore_material',
    'material_state',
    'get_material',
    'get_spans',
    'rename_material',
    'purge_material',
    'soft_delete_material',
]
