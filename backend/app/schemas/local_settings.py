"""本地设置持久化的请求模式。

设置值存储在 `<data_root>/config/settings.json` 中，独立于 SQLite 数据库
和备份集之外。敏感字段仅用于本地单用户操作，不会在任何读取投影中回显。

交付凭据可存储，以便配置页面可以先测试再保存。交付开关故意缺失：
模式、启用状态和每次使用授权保持为运行时控制、默认关闭的安全控制，
因此存储 SMTP 密码永远不会自动开启出站交付。

Contract: P1-8 frozen.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# An explicit empty string is the clear instruction for every field, including
# the boolean and integer ones. Without this the form's "follow detection" and
# "leave blank" choices are rejected before any settings logic runs.
Clearable = Literal[""]


class LocalSettingsRequest(BaseModel):
    """部分设置更新请求。
    
    省略的字段保持不变。显式空字符串会清除该字段的存储值。
    
    字段说明：
        ai_provider_id: AI Provider ID（如 "openai"）
        ai_model_id: AI 模型 ID（如 "gpt-4o-mini"）
        ai_base_url: AI Provider 基础 URL
        ai_api_key: AI Provider API 密钥（敏感字段）
        ocr_provider_id: OCR Provider ID（如 "paddleocr"）
        ocr_enabled: OCR 是否启用
        asr_provider_id: ASR Provider ID
        asr_enabled: ASR 是否启用
        report_delivery_smtp_*: SMTP 邮件发送配置
        report_delivery_feishu_webhook: 飞书 Webhook URL
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
    ocr_enabled: bool | Clearable | None = None
    asr_provider_id: str | None = None
    asr_model_id: str | None = None
    asr_runtime_path: str | None = None
    asr_model_path: str | None = None
    asr_enabled: bool | Clearable | None = None
    report_delivery_smtp_host: str | None = None
    report_delivery_smtp_port: int | Clearable | None = None
    report_delivery_smtp_secure: bool | Clearable | None = None
    report_delivery_smtp_username: str | None = None
    report_delivery_smtp_password: str | None = None
    report_delivery_smtp_targets: str | None = None
    report_delivery_feishu_webhook: str | None = None


class LocalSettingsClearRequest(BaseModel):
    """显式移除存储的设置键。
    
    Args:
        keys: 要移除的键列表。如果为 None，则移除所有键。
    """

    keys: list[str] | None = None
