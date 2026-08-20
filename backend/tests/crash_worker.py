from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig
from app.repository import connect
from app.storage import store_original


def token(value: str) -> None:
    print(value, flush=True)


def wait_command() -> None:
    sys.stdin.readline()


def main() -> None:
    root = Path(sys.argv[1])
    mode = sys.argv[2]
    body = b"crash recovery body"
    config = AppConfig(data_root=root, max_upload_bytes=1024)
    root.mkdir(parents=True, exist_ok=True)
    config.originals_root.mkdir(parents=True, exist_ok=True)
    if mode == "before_commit":
        with connect(config.database_path):
            pass
        token("READY")
        digest = hashlib.sha256(body).hexdigest()
        target = config.data_root / ".incoming-crashed"
        target.write_bytes(body)
        stored = store_original(target, "crashed.txt", digest, config.originals_root)
        token("ORIGINAL_STORED")
        with connect(config.database_path) as db:
            db.execute("BEGIN")
            db.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?)", ("default", "Default project", "now"))
            db.execute("INSERT INTO materials VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)", ("crashed", "default", "crashed.txt", digest, str(stored.path), "text/plain", "now", "now"))
            token("DB_TRANSACTION_OPEN")
            wait_command()
            os._exit(91)
    elif mode == "after_commit":
        with connect(config.database_path):
            pass
        token("READY")
        digest = hashlib.sha256(body).hexdigest()
        target = config.data_root / ".incoming-crashed"
        target.write_bytes(body)
        stored = store_original(target, "committed.txt", digest, config.originals_root)
        with connect(config.database_path) as db:
            with db:
                db.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?, ?)", ("unused", "unused", "now",)) if False else None
                db.execute("INSERT OR IGNORE INTO projects VALUES (?, ?, ?)", ("default", "Default project", "now"))
                db.execute("INSERT INTO materials VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)", ("committed", "default", "committed.txt", digest, str(stored.path), "text/plain", "now", "now"))
                extraction = "extraction_committed"
                db.execute("INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (extraction, "committed", "txt", "1", "success", body.decode(), "[]", "now", None))
                db.execute("INSERT INTO text_spans VALUES (?, ?, ?, ?, ?, ?)", ("span_committed", extraction, 1, "document", "Document", body.decode()))
                db.execute("INSERT INTO material_search VALUES (?, ?, ?)", ("committed", "committed.txt", body.decode()))
        token("DB_COMMITTED")
        wait_command()
        os._exit(93)


if __name__ == "__main__":
    main()
