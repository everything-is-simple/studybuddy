"""Provider 和交付连接测试适配器。

本模块实现 Provider（AI LLM/Embedding）和交付（SMTP/飞书）
配置的显式连接测试。测试使用固定合成载荷、有界响应和
稳定错误码映射。

契约：P1-5-0 冻结，P1-5-2 实现。
- 测试是显式触发的（绝不自动）
- 测试不改变配置状态
- 测试使用固定合成载荷
- 响应有界（超时、最大字节数、不跟随重定向）
- 错误映射为稳定错误码

四类测试：
1. provider_llm_connection_test: LLM 连通性（chat/completions）
2. provider_embedding_connection_test: Embedding 连通性（embeddings）
3. smtp_connection_test: SMTP 邮件发送
4. feishu_connection_test: 飞书 Webhook 推送

响应限制：
- LLM/飞书: 1 KB（合成载荷的响应很小）
- Embedding: 256 KB（向量响应可达 19 KB）

错误码体系：
- provider_*: Provider 连接/认证/协议错误
- delivery_*: 交付配置/连接/认证/协议错误

安全设计：
- 合成载荷不含任何学习材料
- 响应大小受限（防内存耗尽）
- 错误码稳定，不泄露原始异常
"""

from __future__ import annotations

import json
import smtplib
import socket
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Maximum response body size for connection tests (1 KB)
MAX_TEST_RESPONSE_BYTES = 1024
# Embedding responses carry a full vector, so a 1 KB cap can never be satisfied:
# a 1024-dimension `mistral-embed` reply measures about 19 KB. The read stays
# bounded, just at a size an embedding provider can actually return.
MAX_EMBEDDING_TEST_RESPONSE_BYTES = 256 * 1024

# Synthetic test payloads
LLM_TEST_PAYLOAD = {
    "model": "",  # Filled at runtime
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10,
}

EMBEDDING_TEST_PAYLOAD = {
    "model": "",  # Filled at runtime
    "input": ["test"],
}

SMTP_TEST_SUBJECT = "StudyBuddy Configuration Test"
SMTP_TEST_BODY = "No study material is included."

FEISHU_TEST_PAYLOAD = {
    "msg_type": "text",
    "content": {"text": "Configuration test"},
}


class ConnectionTestError(Exception):
    """连接测试错误（稳定错误码）。
    
    Args:
        code: 稳定错误码（如 'provider_auth_failed'）
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def provider_llm_connection_test(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    """用合成载荷测试 LLM Provider 连接。
    
    向 /chat/completions 端点发送固定的合成消息
    （"Hello"，max_tokens=10），验证响应结构。
    
    Args:
        base_url: OpenAI 兼容 API 基础 URL
        api_key: API 密钥
        model_id: 模型 ID
        timeout_seconds: 超时秒数
    
    Returns:
        {"status": "ok"}
    
    Raises:
        ConnectionTestError: 稳定错误码，包括：
            - provider_invalid_config: 配置缺失
            - provider_connection_failed: 网络错误
            - provider_timeout: 请求超时
            - provider_auth_failed: HTTP 401
            - provider_forbidden: HTTP 403
            - provider_rate_limited: HTTP 429
            - provider_unavailable: HTTP 5xx
            - provider_protocol_error: 其他 HTTP 错误或响应格式非法
            - provider_response_too_large: 响应超限
    """
    if not base_url or not api_key or not model_id:
        raise ConnectionTestError("provider_invalid_config")

    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = LLM_TEST_PAYLOAD.copy()
    payload["model"] = model_id
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        request = Request(endpoint, data=payload_bytes, headers=headers, method="POST")
        with urlopen(request, timeout=timeout_seconds) as response:
            # Check Content-Length header
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if int(length) > MAX_TEST_RESPONSE_BYTES:
                        raise ConnectionTestError("provider_response_too_large")
                except ValueError:
                    pass

            # Read response body with size limit
            body = response.read(MAX_TEST_RESPONSE_BYTES + 1)
            if len(body) > MAX_TEST_RESPONSE_BYTES:
                raise ConnectionTestError("provider_response_too_large")

            # Validate JSON response
            try:
                data = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ConnectionTestError("provider_protocol_error") from None

            if not isinstance(data, dict):
                raise ConnectionTestError("provider_protocol_error")

            # Minimal validation: expect OpenAI-compatible response structure
            if "choices" not in data and "error" not in data:
                raise ConnectionTestError("provider_protocol_error")

            return {"status": "ok"}

    except ConnectionTestError:
        raise
    except HTTPError as error:
        if error.code == 401:
            raise ConnectionTestError("provider_auth_failed") from None
        if error.code == 403:
            raise ConnectionTestError("provider_forbidden") from None
        if error.code == 429:
            raise ConnectionTestError("provider_rate_limited") from None
        if error.code in {500, 502, 503, 504}:
            raise ConnectionTestError("provider_unavailable") from None
        raise ConnectionTestError("provider_protocol_error") from None
    except TimeoutError:
        raise ConnectionTestError("provider_timeout") from None
    except URLError as error:
        if getattr(error, "reason", None).__class__.__name__ == "timeout":
            raise ConnectionTestError("provider_timeout") from None
        raise ConnectionTestError("provider_connection_failed") from None
    except OSError:
        raise ConnectionTestError("provider_connection_failed") from None


def provider_embedding_connection_test(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    """用合成载荷测试 Embedding Provider 连接。
    
    向 /embeddings 端点发送单条合成文本，验证响应结构。
    响应上限 256 KB（向量响应远大于 LLM）。
    
    Args:
        base_url: OpenAI 兼容 API 基础 URL
        api_key: API 密钥
        model_id: 模型 ID
        timeout_seconds: 超时秒数
    
    Returns:
        {"status": "ok"}
    
    Raises:
        ConnectionTestError: 错误码同 provider_llm_connection_test
    """
    if not base_url or not api_key or not model_id:
        raise ConnectionTestError("provider_invalid_config")

    endpoint = base_url.rstrip("/") + "/embeddings"
    payload = EMBEDDING_TEST_PAYLOAD.copy()
    payload["model"] = model_id
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        request = Request(endpoint, data=payload_bytes, headers=headers, method="POST")
        with urlopen(request, timeout=timeout_seconds) as response:
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if int(length) > MAX_EMBEDDING_TEST_RESPONSE_BYTES:
                        raise ConnectionTestError("provider_response_too_large")
                except ValueError:
                    pass

            body = response.read(MAX_EMBEDDING_TEST_RESPONSE_BYTES + 1)
            if len(body) > MAX_EMBEDDING_TEST_RESPONSE_BYTES:
                raise ConnectionTestError("provider_response_too_large")

            try:
                data = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ConnectionTestError("provider_protocol_error") from None

            if not isinstance(data, dict):
                raise ConnectionTestError("provider_protocol_error")

            # Minimal validation: expect OpenAI-compatible embedding response
            if "data" not in data and "error" not in data:
                raise ConnectionTestError("provider_protocol_error")

            return {"status": "ok"}

    except ConnectionTestError:
        raise
    except HTTPError as error:
        if error.code == 401:
            raise ConnectionTestError("provider_auth_failed") from None
        if error.code == 403:
            raise ConnectionTestError("provider_forbidden") from None
        if error.code == 429:
            raise ConnectionTestError("provider_rate_limited") from None
        if error.code in {500, 502, 503, 504}:
            raise ConnectionTestError("provider_unavailable") from None
        raise ConnectionTestError("provider_protocol_error") from None
    except TimeoutError:
        raise ConnectionTestError("provider_timeout") from None
    except URLError as error:
        if getattr(error, "reason", None).__class__.__name__ == "timeout":
            raise ConnectionTestError("provider_timeout") from None
        raise ConnectionTestError("provider_connection_failed") from None
    except OSError:
        raise ConnectionTestError("provider_connection_failed") from None


def smtp_connection_test(
    *,
    host: str,
    port: int,
    secure: bool,
    username: str | None,
    password: str | None,
    sender: str,
    recipient: str,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    """用合成邮件测试 SMTP 连接。
    
    发送固定主题/正文的测试邮件（不含任何学习材料），
    可选认证（提供凭据时登录）。
    
    Args:
        host: SMTP 主机
        port: 端口
        secure: 是否使用 SSL
        username: 可选用户名（提供时认证）
        password: 可选密码
        sender: 发件人
        recipient: 收件人
        timeout_seconds: 超时秒数
    
    Returns:
        {"status": "ok"}
    
    Raises:
        ConnectionTestError: 配置缺失、连接失败、超时、
                            认证失败或协议错误时
    """
    if not host or not port or not sender or not recipient:
        raise ConnectionTestError("delivery_configuration_invalid")

    try:
        # Create SMTP connection
        if secure:
            smtp = smtplib.SMTP_SSL(host, port, timeout=timeout_seconds)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout_seconds)

        try:
            # Authenticate if credentials provided
            if username and password:
                smtp.login(username, password)

            # Send test message
            message = f"Subject: {SMTP_TEST_SUBJECT}\n\n{SMTP_TEST_BODY}"
            smtp.sendmail(sender, [recipient], message)

            return {"status": "ok"}

        finally:
            smtp.quit()

    except smtplib.SMTPAuthenticationError:
        raise ConnectionTestError("delivery_auth_failed") from None
    except smtplib.SMTPException:
        raise ConnectionTestError("delivery_failed") from None
    except socket.timeout:
        raise ConnectionTestError("delivery_timeout") from None
    except OSError:
        raise ConnectionTestError("delivery_connection_failed") from None


def feishu_connection_test(
    *,
    webhook_url: str,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    """用合成消息测试飞书 Webhook 连接。
    
    向 Webhook 发送固定文本消息，验证 {"code": 0} 成功响应。
    URL 必须是 https://open.feishu.cn/ 开头。
    
    Args:
        webhook_url: 飞书机器人 Webhook URL
        timeout_seconds: 超时秒数
    
    Returns:
        {"status": "ok"}
    
    Raises:
        ConnectionTestError: URL 无效、连接失败、超时、
                            协议错误或响应超限时
    """
    if not webhook_url or not webhook_url.startswith("https://open.feishu.cn/"):
        raise ConnectionTestError("delivery_configuration_invalid")

    payload_bytes = json.dumps(FEISHU_TEST_PAYLOAD).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        request = Request(webhook_url, data=payload_bytes, headers=headers, method="POST")
        with urlopen(request, timeout=timeout_seconds) as response:
            # Check Content-Length header
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    if int(length) > MAX_TEST_RESPONSE_BYTES:
                        raise ConnectionTestError("delivery_response_too_large")
                except ValueError:
                    pass

            body = response.read(MAX_TEST_RESPONSE_BYTES + 1)
            if len(body) > MAX_TEST_RESPONSE_BYTES:
                raise ConnectionTestError("delivery_response_too_large")

            # Validate JSON response
            try:
                data = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ConnectionTestError("delivery_failed") from None

            if not isinstance(data, dict):
                raise ConnectionTestError("delivery_failed")

            # Feishu webhook returns {"code": 0} on success
            if data.get("code") != 0:
                raise ConnectionTestError("delivery_failed")

            return {"status": "ok"}

    except ConnectionTestError:
        raise
    except HTTPError:
        raise ConnectionTestError("delivery_failed") from None
    except TimeoutError:
        raise ConnectionTestError("delivery_timeout") from None
    except URLError as error:
        if getattr(error, "reason", None).__class__.__name__ == "timeout":
            raise ConnectionTestError("delivery_timeout") from None
        raise ConnectionTestError("delivery_connection_failed") from None
    except OSError:
        raise ConnectionTestError("delivery_connection_failed") from None
