"""Request schemas for local settings persistence.

Values are stored under `<data_root>/config/settings.json`, outside SQLite and
outside backup sets. Secret fields are accepted for local single-user operation
and are never echoed back by any read projection.

Outbound delivery credentials are deliberately absent: delivery stays
runtime-only, default-off and per-use authorized.
"""

from __future__ import annotations

from pydantic import BaseModel


class LocalSettingsRequest(BaseModel):
    """Partial settings update. Omitted fields are left unchanged.

    An explicit empty string clears the stored value for that field.
    """

    ai_provider_id: str | None = None
    ai_model_id: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    embedding_provider_id: str | None = None
    embedding_model_id: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    ocr_provider_id: str | None = None
    ocr_model_id: str | None = None
    ocr_model_root: str | None = None
    ocr_enabled: bool | None = None
    asr_provider_id: str | None = None
    asr_model_id: str | None = None
    asr_runtime_path: str | None = None
    asr_model_path: str | None = None
    asr_enabled: bool | None = None


class LocalSettingsClearRequest(BaseModel):
    """Explicit removal of stored settings keys, or of every key."""

    keys: list[str] | None = None
