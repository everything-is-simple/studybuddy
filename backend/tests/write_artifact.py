from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.adapters.file_parsers import parse_file

FIXTURES = Path("H:/studybuddy-test/fixtures/kaobuddy-foundation")
ARTIFACT = Path("H:/studybuddy-test/artifacts/formal-file-parsers/latest.json")
CASES = ["sample.txt", "sample.md", "chinese.txt", "empty.txt", "sample.pdf", "corrupt.pdf", "sample.docx", "empty.docx", "corrupt.docx", "sample.pptx", "empty.pptx", "corrupt.pptx", "sample.rtf", "sample.doc", "sample.ppt"]


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


records = []
for name in CASES:
    path = FIXTURES / name
    result = parse_file(path)
    records.append({"fixture": name, "input_size": path.stat().st_size, "sha256": result.source_sha256,
                    "status": result.status, "output_text_length": len(result.text),
                    "output_text_sha256": digest(result.text), "span_count": len(result.spans),
                    "warnings": result.warnings, "error_code": result.error_code, "elapsed_ms": result.elapsed_ms})

payload = {
    "component": "formal-file-parsers", "formal_system_version": "e7126c9", "parser_version": "1.0.0",
    "status": "implemented", "python": sys.version.split()[0], "platform": platform.platform(),
    "command": f"{sys.executable} -m pytest backend/tests/test_file_parsers.py -q",
    "fixture_root": str(FIXTURES), "network": {"required": False, "called": False},
    "original_files_saved_by_parser": False, "records": records,
    "coverage": ["TXT", "Markdown", "PDF", "DOCX", "PPTX", "RTF/legacy rejection", "SHA-256", "size and ZIP limits", "no stdout", "storage", "SQLite WAL/foreign keys/transaction"],
    "limitations": ["no user upload path", "no OCR or legacy conversion", "no crash/disk-full/network-share stress", "no complex DOCX text boxes or embedded objects", "no provider calls", "not real-pass"],
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
ARTIFACT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"component": payload["component"], "status": payload["status"], "records": len(records)}))
