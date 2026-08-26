from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .backup import BackupError, backup_data, restore_backup, verify_backup
from .config import config_from_environment
from .diagnostics import DiagnosticError, collect_diagnostics
from .observability import emit_event, increment
from .migrations.runner import MigrationError, assert_schema_version
from .restore_acceptance import verify_restored_data
from .repository import connect, recover_active_operation_tasks
from .task_handlers import build_task_runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="studybuddy")
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--data-root", required=True, type=Path)
    backup.add_argument("--output", required=True, type=Path)
    backup.add_argument("--project-id", default="default")
    verify = sub.add_parser("verify-backup")
    verify.add_argument("--backup", required=True, type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("--data-root", required=True, type=Path)
    restore.add_argument("--backup", required=True, type=Path)
    restore.add_argument("--confirm", action="store_true")
    version = sub.add_parser("schema-version")
    version.add_argument("--database", required=True, type=Path)
    acceptance = sub.add_parser("verify-restored-data")
    acceptance.add_argument("--data-root", required=True, type=Path)
    acceptance.add_argument("--base-url")
    tasks = sub.add_parser("run-tasks")
    tasks.add_argument("--data-root", required=True, type=Path)
    tasks.add_argument("--once", action="store_true")
    tasks.add_argument("--max-tasks", type=int, default=1)
    diagnostics = sub.add_parser("diagnostics")
    diagnostics.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            result = backup_data(args.data_root, args.output, args.project_id)
        elif args.command == "verify-backup":
            result = verify_backup(args.backup)
        elif args.command == "schema-version":
            import sqlite3
            connection = sqlite3.connect(args.database)
            try:
                result = {"schema_version": assert_schema_version(connection)}
            finally:
                connection.close()
        elif args.command == "verify-restored-data":
            result = verify_restored_data(args.data_root, args.base_url)
            if result.get("status") != "passed":
                print(json.dumps(result, ensure_ascii=False))
                return 1
        elif args.command == "diagnostics":
            result = collect_diagnostics(args.data_root)
            increment("diagnostics", str(result["status"]))
            emit_event("operator_diagnostics", component="operator", outcome=str(result["status"]))
            if result["status"] != "ok":
                print(json.dumps(result, ensure_ascii=False))
                return 1
        elif args.command == "run-tasks":
            if args.max_tasks < 1 or args.max_tasks > 1000:
                print(json.dumps({"status": "failed", "error_code": "invalid_max_tasks"}, ensure_ascii=False))
                return 1
            config = replace(config_from_environment(), data_root=args.data_root)
            # This explicit runner process must not inherit a prior process's
            # execution claim. Recovery marks it stale; it never auto-retries it.
            with connect(config.database_path) as connection:
                recover_active_operation_tasks(connection)
            runner = build_task_runner(config)
            completed = 0
            if args.once:
                completed = int(runner.run_once())
            else:
                while completed < args.max_tasks and runner.run_once():
                    completed += 1
            result = {"status": "completed", "tasks_run": completed}
        else:
            result = restore_backup(args.data_root, args.backup, args.confirm)
    except (BackupError, MigrationError, DiagnosticError) as error:
        if args.command == "diagnostics":
            increment("diagnostics", "failed")
            emit_event("operator_diagnostics_failed", level=40, error_code=error.code,
                       component="operator", outcome="failed")
        print(json.dumps({"status": "failed", "error_code": error.code}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
