"""材料管理数据访问层代理。

本模块从 repositories._legacy 导出材料相关的数据库操作函数。
真正的实现在 _legacy 模块中，等待后续重构拆分。

主要导出函数：
- save_material_with_extraction: 创建材料并保存解析结果
- list_materials/list_deleted_materials: 查询材料列表（分页/全量）
- get_material/get_spans: 查询单个材料及其文本片段
- material_state: 获取材料状态摘要
- rename_material: 重命名材料
- soft_delete_material/purge_material: 删除材料（软删除/硬删除）
- restore_material: 恢复已删除材料

关联模块：
- api.materials_collection: HTTP API 层
- api.materials_detail: 材料详情 API
- repositories._legacy: 实际实现（待重构）

Note:
    此模块是临时代理层，待 _legacy 重构完成后将被拆分为
    独立的领域仓库模块。不建议在此文件中添加新功能。
"""

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
