from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path

from .backup import BackupError, backup_data, restore_backup, rotate_backups, upgrade_preflight, verify_backup
from .config import config_from_environment
from .diagnostics import APPLICATION_VERSION, DiagnosticError, collect_diagnostics
from .observability import emit_event, increment
from .migrations.runner import CURRENT_SCHEMA_VERSION, MigrationError, assert_schema_version
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
    serve = sub.add_parser("serve")
    serve.add_argument("--data-root", type=Path)
    sub.add_parser("version")
    rotation = sub.add_parser("rotate-backups")
    rotation.add_argument("--backup-root", required=True, type=Path)
    rotation.add_argument("--retain", required=True, type=int)
    rotation.add_argument("--confirm", action="store_true")
    upgrade = sub.add_parser("upgrade-preflight")
    upgrade.add_argument("--data-root", required=True, type=Path)
    upgrade.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn
            from .main import create_app
            config = config_from_environment()
            if args.data_root is not None:
                config = replace(config, data_root=args.data_root)
            logging.basicConfig(level=getattr(logging, config.log_level), format="%(message)s")
            app = create_app(config)
            uvicorn.run(app, host=config.host, port=config.port, workers=1, reload=False)
            return 0
        if args.command == "version":
            result = {"application_version": APPLICATION_VERSION, "schema_version": CURRENT_SCHEMA_VERSION}
        elif args.command == "backup":
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
        elif args.command == "rotate-backups":
            result = rotate_backups(args.backup_root, retain=args.retain, confirm=args.confirm)
        elif args.command == "upgrade-preflight":
            result = upgrade_preflight(args.data_root, args.backup)
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
    except (BackupError, MigrationError, DiagnosticError, ValueError) as error:
        code = getattr(error, "code", str(error) if str(error).startswith("invalid_") else "operator_command_failed")
        if args.command == "diagnostics":
            increment("diagnostics", "failed")
            emit_event("operator_diagnostics_failed", level=40, error_code=code,
                       component="operator", outcome="failed")
        print(json.dumps({"status": "failed", "error_code": code}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
