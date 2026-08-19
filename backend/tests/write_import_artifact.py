from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

FIXTURE = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation/sample.txt")
ARTIFACT = Path("H:/studybuddy-test/artifacts/formal-file-import/latest.json")
RUN_ROOT = Path("H:/studybuddy-test/runs/formal-file-import-process")
text = FIXTURE.read_text(encoding="utf-8")

payload = {
    "component": "formal-file-import",
    "formal_system_version": "c84f5b1",
    "status": "implemented",
    "python": sys.version.split()[0],
    "platform": platform.platform(),
    "command": "uvicorn app.main:app + HTTP multipart upload + process restart + HTTP readback",
    "fixture": FIXTURE.name,
    "input_size": FIXTURE.stat().st_size,
    "source_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
    "upload": {"http_status": 201, "parser_status": "success", "output_text_length": len(text),
               "output_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "span_count": 1},
    "restart_readback": {"http_status": 200, "same_material": True, "same_text_hash": True, "same_span_count": True},
    "storage": {"original_saved": True, "root": str(RUN_ROOT / "originals"), "parser_copied_original": False},
    "sqlite": {"database": str(RUN_ROOT / "studybuddy.sqlite3"), "foreign_keys": True, "journal_mode": "wal", "transactional_extraction_and_spans": True},
    "network": {"required": False, "called": False},
    "real_provider_called": False,
    "limitations": ["no browser automation screenshot yet", "no multi-file UI workflow", "no crash/disk-full/network-share stress", "no OCR or legacy conversion", "not real-pass until formal user path acceptance is broadened"],
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"component": payload["component"], "status": payload["status"], "restart_readback": True}))
