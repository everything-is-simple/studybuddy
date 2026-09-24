"""学习报告数据访问层。

报告常量由 part_05 拥有，报告投影与交付实现由 part_08 拥有。
这里保留稳定的域出口，避免兼容层成为实现注册中心。
"""

from . import _legacy_part_05 as _part_05
from . import _legacy_part_08 as _part_08

PHASE9D_REPORT_MAX_EXPORT_BYTES = _part_05.PHASE9D_REPORT_MAX_EXPORT_BYTES
build_report_projection = _part_08.build_report_projection
export_report_snapshot = _part_08.export_report_snapshot
create_report_snapshot = _part_08.create_report_snapshot
get_report_snapshot = _part_08.get_report_snapshot
list_report_snapshots = _part_08.list_report_snapshots
record_report_delivery_attempt = _part_08.record_report_delivery_attempt
find_report_delivery_replay = _part_08.find_report_delivery_replay
list_report_delivery_attempts = _part_08.list_report_delivery_attempts

__all__ = ['PHASE9D_REPORT_MAX_EXPORT_BYTES', 'build_report_projection', 'export_report_snapshot', 'create_report_snapshot', 'get_report_snapshot', 'list_report_snapshots', 'record_report_delivery_attempt', 'find_report_delivery_replay', 'list_report_delivery_attempts']
