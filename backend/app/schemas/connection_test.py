"""连接测试端点的请求模式定义。

本模块定义用于测试外部服务连接的请求数据结构，包括：
- Provider 连接测试（LLM/Embedding）
- 邮件服务连接测试（SMTP/飞书）

合约版本: P1-5-0 冻结，P1-5-2 实现。
"""

from __future__ import annotations

from pydantic import BaseModel


class ProviderConnectionTestRequest(BaseModel):
    """Provider 连接测试请求模式。

    Attributes:
        provider_type: Provider 类型（"llm" 或 "embedding"）
        base_url: Provider API 基础 URL（如 "https://api.deepseek.com"）
        api_key: Provider API 密钥（仅用于测试，不持久化）
        model_id: 模型标识符（如 "deepseek-chat"）
        timeout_seconds: 可选的超时时间（默认 30.0 秒）
    """

    provider_type: str  # "llm" or "embedding"
    base_url: str
    api_key: str
    model_id: str
    timeout_seconds: float | None = None


class EmailConnectionTestRequest(BaseModel):
    """邮件服务连接测试请求模式。

    Attributes:
        channel: 渠道类型（"smtp" 或 "feishu"）
        
        SMTP 字段（当 channel="smtp" 时必需）:
            smtp_host: SMTP 服务器主机
            smtp_port: SMTP 服务器端口
            smtp_secure: 是否使用 TLS（默认 true）
            smtp_username: 可选的 SMTP 用户名
            smtp_password: 可选的 SMTP 密码
            smtp_sender: 发件人邮箱地址
            smtp_recipient: 收件人邮箱地址
        
        飞书字段（当 channel="feishu" 时必需）:
            feishu_webhook: 飞书 webhook URL
        
        通用字段:
            timeout_seconds: 可选的超时时间（默认 10.0 秒）
    """

    channel: str  # "smtp" or "feishu"

    # SMTP fields
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_secure: bool | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_recipient: str | None = None

    # Feishu fields
    feishu_webhook: str | None = None

    # Common
    timeout_seconds: float | None = None
