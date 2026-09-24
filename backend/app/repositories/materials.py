"""材料管理数据访问层的稳定域出口。

材料入库/列表/恢复由 part 00/01 所有，材料详情/重命名由 part 13
所有，生命周期删除由 part 14 所有。这里仅保留稳定的导出面，避免
兼容层成为材料实现的注册中心。

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
- _legacy_part_*: 当前仍为有序实现分片，域出口不再依赖总表

Note:
    新实现应进入对应的材料域分片，并在此处显式导出。
"""

from . import _legacy_part_00 as _part_00
from . import _legacy_part_01 as _part_01
from . import _legacy_part_13 as _part_13
from . import _legacy_part_14 as _part_14

save_extraction = _part_00.save_extraction
save_material_with_extraction = _part_01.save_material_with_extraction
list_materials = _part_01.list_materials
list_deleted_materials = _part_01.list_deleted_materials
list_materials_page = _part_01.list_materials_page
list_deleted_materials_page = _part_01.list_deleted_materials_page
restore_material = _part_01.restore_material
material_state = _part_13.material_state
get_material = _part_13.get_material
get_spans = _part_13.get_spans
rename_material = _part_13.rename_material
purge_material = _part_14.purge_material
soft_delete_material = _part_14.soft_delete_material

__all__ = ['save_extraction', 'save_material_with_extraction', 'list_materials', 'list_deleted_materials', 'list_materials_page', 'list_deleted_materials_page', 'restore_material', 'material_state', 'get_material', 'get_spans', 'rename_material', 'purge_material', 'soft_delete_material']
