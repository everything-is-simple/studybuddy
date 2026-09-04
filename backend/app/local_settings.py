"""Persisted local settings stored outside SQLite and outside backups.

Third defect addressed: enabling an installed local capability required
hand-copied environment variables, and the configuration page could test but not
save. Settings written here survive a restart and are re-read per request, so no
restart is needed.

Boundaries:
- File lives at `<data_root>/config/settings.json`, never inside SQLite, never
  inside `originals/`, and never inside a backup set (backup copies only the
  database and `originals/`).
- Secret values are accepted and stored for local single-user operation, but are
  never returned by any read projection and never logged.
- Writes are atomic (temporary file plus replace) and bounded in size.
- A malformed or unreadable file degrades to "no stored settings" instead of
  breaking startup.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

SETTINGS_DIRECTORY = "config"
SETTINGS_FILENAME = "settings.json"
MAX_SETTINGS_BYTES = 64 * 1024
_FORMAT = "studybuddy-local-settings"
_FORMAT_VERSION = 1

# Only these keys are accepted. Delivery credentials are deliberately excluded:
# outbound delivery stays runtime-only, default-off and per-use authorized.
_TEXT_KEYS = frozenset({
    "ai_provider_id", "ai_model_id", "ai_base_url",
    "embedding_provider_id", "embedding_model_id", "embedding_base_url",
    "ocr_provider_id", "ocr_model_id", "ocr_model_root",
    "asr_provider_id", "asr_model_id", "asr_runtime_path", "asr_model_path",
    "report_delivery_smtp_host", "report_delivery_smtp_username", "report_delivery_smtp_targets",
    "report_delivery_feishu_webhook",
})
_SECRET_KEYS = frozenset({"ai_api_key", "embedding_api_key", "report_delivery_smtp_password"})
_BOOL_KEYS = frozenset({"ocr_enabled", "asr_enabled", "report_delivery_smtp_secure"})
_INT_KEYS = frozenset({"report_delivery_smtp_port"})
ALLOWED_KEYS = _TEXT_KEYS | _SECRET_KEYS | _BOOL_KEYS | _INT_KEYS

_MAX_VALUE_CHARS = 1000
_PROVIDER_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


class SettingsError(Exception):
    """Stable, safe settings failure. Carries a code, never a path or payload."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def settings_path(data_root: Path | str) -> Path:
    return Path(data_root) / SETTINGS_DIRECTORY / SETTINGS_FILENAME


def _validated_text(key: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SettingsError("settings_invalid_value")
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > _MAX_VALUE_CHARS or "\x00" in trimmed:
        raise SettingsError("settings_invalid_value")
    if key.endswith("_provider_id") or key.endswith("_model_id"):
        if any(char not in _PROVIDER_ID_CHARS and not char.isalnum() for char in trimmed):
            raise SettingsError("settings_invalid_value")
    if key.endswith("_base_url"):
        parsed = urlparse(trimmed)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise SettingsError("settings_invalid_value")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise SettingsError("settings_invalid_value")
        try:
            parsed.port
        except ValueError:
            raise SettingsError("settings_invalid_value") from None
        return trimmed.rstrip("/")
    if key == "report_delivery_smtp_targets":
        # Format: label1=email1@example.com,label2=email2@example.com
        seen_labels: set[str] = set()
        for item in trimmed.split(","):
            item = item.strip()
            if not item:
                continue
            if item.count("=") != 1:
                raise SettingsError("settings_invalid_value")
            label, target = (part.strip() for part in item.split("=", 1))
            if (not label or not target or len(label) > 100 or len(target) > 500
                    or any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in label)):
                raise SettingsError("settings_invalid_value")
            if label in seen_labels:
                raise SettingsError("settings_invalid_value")
            seen_labels.add(label)
        return trimmed
    return trimmed


def _validated_secret(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SettingsError("settings_invalid_value")
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > _MAX_VALUE_CHARS or any(char.isspace() for char in trimmed):
        raise SettingsError("settings_invalid_value")
    return trimmed


def _validated_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise SettingsError("settings_invalid_value")


def _validated_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise SettingsError("settings_invalid_value")


def normalize_settings(payload: dict[str, object]) -> dict[str, object]:
    """Validate a settings payload, dropping empty values. Raises on bad input."""
    if not isinstance(payload, dict):
        raise SettingsError("settings_invalid_payload")
    unknown = set(payload) - ALLOWED_KEYS
    if unknown:
        raise SettingsError("settings_unknown_key")
    normalized: dict[str, object] = {}
    for key, value in payload.items():
        if key in _SECRET_KEYS:
            resolved: object | None = _validated_secret(value)
        elif key in _BOOL_KEYS:
            resolved = _validated_bool(value)
        elif key in _INT_KEYS:
            resolved = _validated_int(value)
        else:
            resolved = _validated_text(key, value)
        if resolved is not None:
            normalized[key] = resolved
    return normalized


def load_settings(data_root: Path | str) -> dict[str, object]:
    """Read stored settings. Returns an empty mapping when absent or unusable."""
    path = settings_path(data_root)
    try:
        if not path.is_file() or path.stat().st_size > MAX_SETTINGS_BYTES:
            return {}
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(document, dict) or document.get("format") != _FORMAT:
        return {}
    values = document.get("settings")
    if not isinstance(values, dict):
        return {}
    accepted: dict[str, object] = {}
    for key, value in values.items():
        if key not in ALLOWED_KEYS:
            continue
        try:
            if key in _SECRET_KEYS:
                resolved: object | None = _validated_secret(value)
            elif key in _BOOL_KEYS:
                resolved = _validated_bool(value)
            elif key in _INT_KEYS:
                resolved = _validated_int(value)
            else:
                resolved = _validated_text(key, value)
        except SettingsError:
            continue
        if resolved is not None:
            accepted[key] = resolved
    return accepted


def save_settings(data_root: Path | str, payload: dict[str, object], *,
                  merge: bool = True) -> dict[str, object]:
    """Atomically persist settings and return the stored mapping."""
    normalized = normalize_settings(payload)
    stored = {**load_settings(data_root), **normalized} if merge else normalized
    document = {"format": _FORMAT, "format_version": _FORMAT_VERSION, "settings": stored}
    body = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    if len(body.encode("utf-8")) > MAX_SETTINGS_BYTES:
        raise SettingsError("settings_payload_too_large")
    path = settings_path(data_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".settings-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError:
        raise SettingsError("settings_write_failed") from None
    return stored


def clear_settings(data_root: Path | str, keys: list[str] | None = None) -> dict[str, object]:
    """Remove specific keys, or every stored key when `keys` is omitted."""
    if keys is None:
        path = settings_path(data_root)
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            raise SettingsError("settings_write_failed") from None
        return {}
    unknown = set(keys) - ALLOWED_KEYS
    if unknown:
        raise SettingsError("settings_unknown_key")
    remaining = {key: value for key, value in load_settings(data_root).items() if key not in set(keys)}
    return save_settings(data_root, remaining, merge=False)


def public_settings(stored: dict[str, object]) -> dict[str, object]:
    """Projection safe for API/UI: secrets become presence flags only."""
    result: dict[str, object] = {}
    for key, value in stored.items():
        if key in _SECRET_KEYS:
            continue
        if key.endswith("_root") or key.endswith("_path"):
            # Filesystem locations are configured state, not display state.
            result[f"{key}_set"] = True
            continue
        result[key] = value
    for key in sorted(_SECRET_KEYS):
        result[f"{key}_set"] = bool(stored.get(key))
    return result
