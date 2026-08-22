from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_AI_TIMEOUT_SECONDS = 30.0
DEFAULT_AI_MAX_OUTPUT_TOKENS = 800
DEFAULT_AI_MAX_PROMPT_CHARS = 30000
DEFAULT_AI_MAX_ANSWER_CHARS = 12000
DEFAULT_AI_MAX_RETRIES = 0


@dataclass(frozen=True)
class AppConfig:
    data_root: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    project_id: str = "default"
    ai_provider_id: str | None = None
    ai_model_id: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = field(default=None, repr=False)
    ai_timeout_seconds: float = DEFAULT_AI_TIMEOUT_SECONDS
    ai_max_output_tokens: int = DEFAULT_AI_MAX_OUTPUT_TOKENS
    ai_max_prompt_chars: int = DEFAULT_AI_MAX_PROMPT_CHARS
    ai_max_answer_chars: int = DEFAULT_AI_MAX_ANSWER_CHARS
    ai_max_retries: int = DEFAULT_AI_MAX_RETRIES

    @property
    def originals_root(self) -> Path:
        return self.data_root / "originals"

    @property
    def database_path(self) -> Path:
        return self.data_root / "studybuddy.sqlite3"


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid_{name.lower()}") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid_{name.lower()}") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _valid_base_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("invalid_ai_base_url")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("invalid_ai_base_url")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid_ai_base_url") from exc
    return value.rstrip("/")


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
        ai_base_url=_valid_base_url(os.environ.get("STUDYBUDDY_AI_BASE_URL")),
        ai_api_key=os.environ.get("STUDYBUDDY_AI_API_KEY") or None,
        ai_timeout_seconds=_env_float("STUDYBUDDY_AI_TIMEOUT_SECONDS", DEFAULT_AI_TIMEOUT_SECONDS, minimum=0.1, maximum=120.0),
        ai_max_output_tokens=_env_int("STUDYBUDDY_AI_MAX_OUTPUT_TOKENS", DEFAULT_AI_MAX_OUTPUT_TOKENS, minimum=1, maximum=8192),
        ai_max_prompt_chars=_env_int("STUDYBUDDY_AI_MAX_PROMPT_CHARS", DEFAULT_AI_MAX_PROMPT_CHARS, minimum=100, maximum=200000),
        ai_max_answer_chars=_env_int("STUDYBUDDY_AI_MAX_ANSWER_CHARS", DEFAULT_AI_MAX_ANSWER_CHARS, minimum=100, maximum=100000),
        ai_max_retries=_env_int("STUDYBUDDY_AI_MAX_RETRIES", DEFAULT_AI_MAX_RETRIES, minimum=0, maximum=2),
    )
