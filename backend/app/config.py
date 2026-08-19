from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_root: Path
    max_upload_bytes: int = 10 * 1024 * 1024
    project_id: str = "default"

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
    return AppConfig(
        data_root=Path(configured_root).resolve(),
        max_upload_bytes=int(os.environ.get("STUDYBUDDY_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)),
        project_id=os.environ.get("STUDYBUDDY_PROJECT_ID", "default"),
    )
