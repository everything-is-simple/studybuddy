"""Compatibility exports for the reports repository domain."""

from . import _legacy

from ._legacy import (
    build_report_projection,
    export_report_snapshot,
    create_report_snapshot,
    get_report_snapshot,
    list_report_snapshots,
    record_report_delivery_attempt,
    find_report_delivery_replay,
    list_report_delivery_attempts,
)

__all__ = [
    'build_report_projection',
    'export_report_snapshot',
    'create_report_snapshot',
    'get_report_snapshot',
    'list_report_snapshots',
    'record_report_delivery_attempt',
    'find_report_delivery_replay',
    'list_report_delivery_attempts',
]
