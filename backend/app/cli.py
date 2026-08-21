from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backup import BackupError, backup_data, restore_backup, verify_backup
from .migrations.runner import MigrationError, assert_schema_version
from .restore_acceptance import verify_restored_data


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
        else:
            result = restore_backup(args.data_root, args.backup, args.confirm)
    except (BackupError, MigrationError) as error:
        print(json.dumps({"status": "failed", "error_code": error.code}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
