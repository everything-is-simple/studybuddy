"""Domain repository exports."""

from . import _legacy

save_extraction = getattr(_legacy, 'save_extraction')
save_material_with_extraction = getattr(_legacy, 'save_material_with_extraction')
list_materials = getattr(_legacy, 'list_materials')
list_deleted_materials = getattr(_legacy, 'list_deleted_materials')
list_materials_page = getattr(_legacy, 'list_materials_page')
list_deleted_materials_page = getattr(_legacy, 'list_deleted_materials_page')
restore_material = getattr(_legacy, 'restore_material')
material_state = getattr(_legacy, 'material_state')
get_material = getattr(_legacy, 'get_material')
get_spans = getattr(_legacy, 'get_spans')
rename_material = getattr(_legacy, 'rename_material')
purge_material = getattr(_legacy, 'purge_material')
soft_delete_material = getattr(_legacy, 'soft_delete_material')

__all__ = ['save_extraction', 'save_material_with_extraction', 'list_materials', 'list_deleted_materials', 'list_materials_page', 'list_deleted_materials_page', 'restore_material', 'material_state', 'get_material', 'get_spans', 'rename_material', 'purge_material', 'soft_delete_material']
