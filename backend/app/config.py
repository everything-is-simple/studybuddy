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
DEFAULT_EMBEDDING_PROVIDER = None
DEFAULT_EMBEDDING_MODEL = None
DEFAULT_EMBEDDING_MODEL_REVISION = "1"
DEFAULT_EMBEDDING_TIMEOUT_SECONDS = 30.0
DEFAULT_EMBEDDING_MAX_BATCH_SIZE = 32
DEFAULT_EMBEDDING_MAX_TEXT_CHARS = 12000
DEFAULT_EMBEDDING_MAX_DIMENSIONS = 4096
DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_EMBEDDING_MAX_RETRIES = 0
DEFAULT_REPORT_DELIVERY_MODE = "off"
DEFAULT_REPORT_DELIVERY_ENABLED = False
DEFAULT_REPORT_DELIVERY_AUTHORIZED = False


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
    embedding_provider_id: str | None = DEFAULT_EMBEDDING_PROVIDER
    embedding_model_id: str | None = DEFAULT_EMBEDDING_MODEL
    embedding_base_url: str | None = None
    embedding_api_key: str | None = field(default=None, repr=False)
    embedding_model_revision: str = DEFAULT_EMBEDDING_MODEL_REVISION
    embedding_timeout_seconds: float = DEFAULT_EMBEDDING_TIMEOUT_SECONDS
    embedding_max_batch_size: int = DEFAULT_EMBEDDING_MAX_BATCH_SIZE
    embedding_max_text_chars: int = DEFAULT_EMBEDDING_MAX_TEXT_CHARS
    embedding_max_dimensions: int = DEFAULT_EMBEDDING_MAX_DIMENSIONS
    embedding_max_response_bytes: int = DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES
    embedding_max_retries: int = DEFAULT_EMBEDDING_MAX_RETRIES
    # Delivery is deliberately disabled for live use. Secrets are runtime-only
    # configuration and are excluded from reprs and persistence by design.
    report_delivery_mode: str = DEFAULT_REPORT_DELIVERY_MODE
    report_delivery_enabled: bool = DEFAULT_REPORT_DELIVERY_ENABLED
    report_delivery_authorized: bool = DEFAULT_REPORT_DELIVERY_AUTHORIZED
    report_delivery_targets: tuple[str, ...] = ()
    report_delivery_smtp_password: str | None = field(default=None, repr=False)
    report_delivery_feishu_secret: str | None = field(default=None, repr=False)

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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid_{name.lower()}")


def _env_delivery_mode() -> str:
    value = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_MODE", DEFAULT_REPORT_DELIVERY_MODE).strip().lower()
    if value not in {"off", "dry_run", "live"}:
        raise ValueError("invalid_report_delivery_mode")
    return value


def _env_delivery_targets() -> tuple[str, ...]:
    raw = os.environ.get("STUDYBUDDY_REPORT_DELIVERY_TARGETS", "")
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if len(values) > 100 or any(len(item) > 100 for item in values):
        raise ValueError("invalid_report_delivery_targets")
    for value in values:
        if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in value):
            raise ValueError("invalid_report_delivery_targets")
    return values


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
        embedding_provider_id=os.environ.get("STUDYBUDDY_EMBEDDING_PROVIDER") or None,
        embedding_model_id=os.environ.get("STUDYBUDDY_EMBEDDING_MODEL") or None,
        embedding_base_url=_valid_base_url(os.environ.get("STUDYBUDDY_EMBEDDING_BASE_URL")),
        embedding_api_key=os.environ.get("STUDYBUDDY_EMBEDDING_API_KEY") or None,
        embedding_model_revision=os.environ.get("STUDYBUDDY_EMBEDDING_MODEL_REVISION", DEFAULT_EMBEDDING_MODEL_REVISION),
        embedding_timeout_seconds=_env_float("STUDYBUDDY_EMBEDDING_TIMEOUT_SECONDS", DEFAULT_EMBEDDING_TIMEOUT_SECONDS, minimum=0.1, maximum=120.0),
        embedding_max_batch_size=_env_int("STUDYBUDDY_EMBEDDING_MAX_BATCH_SIZE", DEFAULT_EMBEDDING_MAX_BATCH_SIZE, minimum=1, maximum=32),
        embedding_max_text_chars=_env_int("STUDYBUDDY_EMBEDDING_MAX_TEXT_CHARS", DEFAULT_EMBEDDING_MAX_TEXT_CHARS, minimum=1, maximum=12000),
        embedding_max_dimensions=_env_int("STUDYBUDDY_EMBEDDING_MAX_DIMENSIONS", DEFAULT_EMBEDDING_MAX_DIMENSIONS, minimum=1, maximum=4096),
        embedding_max_response_bytes=_env_int("STUDYBUDDY_EMBEDDING_MAX_RESPONSE_BYTES", DEFAULT_EMBEDDING_MAX_RESPONSE_BYTES, minimum=1, maximum=16 * 1024 * 1024),
        embedding_max_retries=_env_int("STUDYBUDDY_EMBEDDING_MAX_RETRIES", DEFAULT_EMBEDDING_MAX_RETRIES, minimum=0, maximum=2),
        report_delivery_mode=_env_delivery_mode(),
        report_delivery_enabled=_env_bool("STUDYBUDDY_REPORT_DELIVERY_ENABLED", DEFAULT_REPORT_DELIVERY_ENABLED),
        report_delivery_authorized=_env_bool("STUDYBUDDY_REPORT_DELIVERY_AUTHORIZED", DEFAULT_REPORT_DELIVERY_AUTHORIZED),
        report_delivery_targets=_env_delivery_targets(),
        report_delivery_smtp_password=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD") or None,
        report_delivery_feishu_secret=os.environ.get("STUDYBUDDY_REPORT_DELIVERY_FEISHU_SECRET") or None,
    )
