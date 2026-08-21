from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class AppConfig:
    data_root: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    project_id: str = "default"
    ai_provider_id: str | None = None
    ai_model_id: str | None = None

    @property
    def originals_root(self) -> Path:
        return self.data_root / "originals"

    @property
    def database_path(self) -> Path:
        return self.data_root / "studybuddy.sqlite3"


def config_from_environment() -> AppConfig:
    configured_root = os.environ.get("STUDYBUDDY_DATA_ROOT")
    if not configured_root:
        configured_root = str(Path.home() / ".studybuddy" / "data")
    raw_limit = os.environ.get("STUDYBUDDY_MAX_UPLOAD_BYTES")
    if raw_limit is None:
        max_upload_bytes = DEFAULT_MAX_UPLOAD_BYTES
    else:
        try:
            max_upload_bytes = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_max_upload_bytes") from exc
        if max_upload_bytes < 1:
            raise ValueError("invalid_max_upload_bytes")
    return AppConfig(
        data_root=Path(configured_root),
        max_upload_bytes=max_upload_bytes,
        project_id=os.environ.get("STUDYBUDDY_PROJECT_ID", "default"),
        ai_provider_id=os.environ.get("STUDYBUDDY_AI_PROVIDER") or None,
        ai_model_id=os.environ.get("STUDYBUDDY_AI_MODEL") or None,
    )
