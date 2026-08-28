"""Domain repository exports."""

from . import _legacy

build_report_projection = getattr(_legacy, 'build_report_projection')
export_report_snapshot = getattr(_legacy, 'export_report_snapshot')
create_report_snapshot = getattr(_legacy, 'create_report_snapshot')
get_report_snapshot = getattr(_legacy, 'get_report_snapshot')
list_report_snapshots = getattr(_legacy, 'list_report_snapshots')
record_report_delivery_attempt = getattr(_legacy, 'record_report_delivery_attempt')
find_report_delivery_replay = getattr(_legacy, 'find_report_delivery_replay')
list_report_delivery_attempts = getattr(_legacy, 'list_report_delivery_attempts')

__all__ = ['build_report_projection', 'export_report_snapshot', 'create_report_snapshot', 'get_report_snapshot', 'list_report_snapshots', 'record_report_delivery_attempt', 'find_report_delivery_replay', 'list_report_delivery_attempts']
