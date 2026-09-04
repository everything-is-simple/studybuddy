"""Tests for connection-test adapters.

Contract: P1-5-0 frozen, P1-5-2 implementation.
"""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.connection_test import (  # noqa: E402
    ConnectionTestError,
    provider_llm_connection_test,
    provider_embedding_connection_test,
    smtp_connection_test,
    feishu_connection_test,
    LLM_TEST_PAYLOAD,
    EMBEDDING_TEST_PAYLOAD,
    FEISHU_TEST_PAYLOAD,
    MAX_TEST_RESPONSE_BYTES,
    MAX_EMBEDDING_TEST_RESPONSE_BYTES,
)


def test_connection_test_uses_fixed_synthetic_payloads() -> None:
    """验证 connection-test 使用固定的 synthetic payload。"""
    # LLM test payload
    assert LLM_TEST_PAYLOAD == {
        "model": "",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }

    # Embedding test payload
    assert EMBEDDING_TEST_PAYLOAD == {
        "model": "",
        "input": ["test"],
    }

    # Feishu test payload
    assert FEISHU_TEST_PAYLOAD == {
        "msg_type": "text",
        "content": {"text": "Configuration test"},
    }


def test_provider_llm_connection_test_success() -> None:
    """验证 LLM Provider connection-test 成功路径。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "Hi"}}]
    }).encode("utf-8")
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        result = provider_llm_connection_test(
            base_url="https://api.example.com",
            api_key="test-key",
            model_id="test-model",
        )

    assert result == {"status": "ok"}


def test_provider_llm_connection_test_invalid_config() -> None:
    """验证 LLM Provider connection-test 拒绝不完整配置。"""
    with pytest.raises(ConnectionTestError) as exc:
        provider_llm_connection_test(
            base_url="",
            api_key="test-key",
            model_id="test-model",
        )
    assert exc.value.code == "provider_invalid_config"

    with pytest.raises(ConnectionTestError) as exc:
        provider_llm_connection_test(
            base_url="https://api.example.com",
            api_key="",
            model_id="test-model",
        )
    assert exc.value.code == "provider_invalid_config"


def test_provider_llm_connection_test_timeout() -> None:
    """验证 LLM Provider connection-test 超时映射。"""
    with patch("app.connection_test.urlopen", side_effect=TimeoutError):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_timeout"


def test_provider_llm_connection_test_http_errors() -> None:
    """验证 LLM Provider connection-test HTTP 错误映射。"""
    from urllib.error import HTTPError

    # 401 → provider_auth_failed
    error_401 = HTTPError("url", 401, "Unauthorized", {}, None)
    with patch("app.connection_test.urlopen", side_effect=error_401):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_auth_failed"

    # 429 → provider_rate_limited
    error_429 = HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("app.connection_test.urlopen", side_effect=error_429):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_rate_limited"

    # 503 → provider_unavailable
    error_503 = HTTPError("url", 503, "Service Unavailable", {}, None)
    with patch("app.connection_test.urlopen", side_effect=error_503):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_unavailable"


def test_provider_llm_connection_test_response_too_large() -> None:
    """验证 LLM Provider connection-test 响应体大小限制。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = str(MAX_TEST_RESPONSE_BYTES + 1)
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_response_too_large"


def test_provider_llm_connection_test_malformed_response() -> None:
    """验证 LLM Provider connection-test 拒绝非 JSON 响应。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = b"not json"
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        with pytest.raises(ConnectionTestError) as exc:
            provider_llm_connection_test(
                base_url="https://api.example.com",
                api_key="test-key",
                model_id="test-model",
            )
    assert exc.value.code == "provider_protocol_error"


def test_provider_embedding_connection_test_success() -> None:
    """验证 Embedding Provider connection-test 成功路径。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = json.dumps({
        "data": [{"embedding": [0.1, 0.2, 0.3]}]
    }).encode("utf-8")
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        result = provider_embedding_connection_test(
            base_url="https://api.example.com",
            api_key="test-key",
            model_id="test-model",
        )

    assert result == {"status": "ok"}


def test_smtp_connection_test_success() -> None:
    """验证 SMTP connection-test 成功路径（mock）。"""
    mock_smtp = MagicMock()

    with patch("app.connection_test.smtplib.SMTP_SSL", return_value=mock_smtp):
        result = smtp_connection_test(
            host="smtp.example.com",
            port=465,
            secure=True,
            username="user@example.com",
            password="test-password",
            sender="sender@example.com",
            recipient="recipient@example.com",
        )

    assert result == {"status": "ok"}
    mock_smtp.login.assert_called_once_with("user@example.com", "test-password")
    mock_smtp.sendmail.assert_called_once()
    mock_smtp.quit.assert_called_once()


def test_smtp_connection_test_invalid_config() -> None:
    """验证 SMTP connection-test 拒绝不完整配置。"""
    with pytest.raises(ConnectionTestError) as exc:
        smtp_connection_test(
            host="",
            port=465,
            secure=True,
            username=None,
            password=None,
            sender="sender@example.com",
            recipient="recipient@example.com",
        )
    assert exc.value.code == "delivery_configuration_invalid"


def test_smtp_connection_test_auth_failed() -> None:
    """验证 SMTP connection-test 认证失败映射。"""
    import smtplib

    mock_smtp = MagicMock()
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, "Authentication failed")

    with patch("app.connection_test.smtplib.SMTP_SSL", return_value=mock_smtp):
        with pytest.raises(ConnectionTestError) as exc:
            smtp_connection_test(
                host="smtp.example.com",
                port=465,
                secure=True,
                username="user@example.com",
                password="wrong-password",
                sender="sender@example.com",
                recipient="recipient@example.com",
            )
    assert exc.value.code == "delivery_auth_failed"


def test_smtp_connection_test_timeout() -> None:
    """验证 SMTP connection-test 超时映射。"""
    import socket

    with patch("app.connection_test.smtplib.SMTP_SSL", side_effect=socket.timeout):
        with pytest.raises(ConnectionTestError) as exc:
            smtp_connection_test(
                host="smtp.example.com",
                port=465,
                secure=True,
                username=None,
                password=None,
                sender="sender@example.com",
                recipient="recipient@example.com",
            )
    assert exc.value.code == "delivery_timeout"


def test_feishu_connection_test_success() -> None:
    """验证 Feishu webhook connection-test 成功路径。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = json.dumps({"code": 0}).encode("utf-8")
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        result = feishu_connection_test(
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
        )

    assert result == {"status": "ok"}


def test_feishu_connection_test_invalid_webhook() -> None:
    """验证 Feishu connection-test 拒绝无效 webhook URL。"""
    with pytest.raises(ConnectionTestError) as exc:
        feishu_connection_test(webhook_url="https://invalid.example.com/hook")
    assert exc.value.code == "delivery_configuration_invalid"

    with pytest.raises(ConnectionTestError) as exc:
        feishu_connection_test(webhook_url="")
    assert exc.value.code == "delivery_configuration_invalid"


def test_feishu_connection_test_failed_response() -> None:
    """验证 Feishu connection-test 拒绝非零错误码。"""
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = json.dumps({"code": 9499, "msg": "error"}).encode("utf-8")
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        with pytest.raises(ConnectionTestError) as exc:
            feishu_connection_test(
                webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-token",
            )
    assert exc.value.code == "delivery_failed"


def test_connection_test_error_has_stable_code() -> None:
    """验证 ConnectionTestError 包含稳定错误码。"""
    error = ConnectionTestError("provider_timeout")
    assert error.code == "provider_timeout"
    assert str(error) == "provider_timeout"


def test_embedding_connection_test_allows_a_real_vector_response() -> None:
    """P2-USE: a real embedding reply is far larger than the 1 KB LLM cap.

    Found while configuring a real provider: `mistral-embed` returns a
    1024-dimension vector, roughly 19 KB, so the shared 1 KB limit made every
    real embedding test fail with `provider_response_too_large` even though the
    provider answered correctly. The read stays bounded, just at a size an
    embedding provider can actually return.
    """
    vector = [0.0123456789] * 1024
    body = json.dumps({"data": [{"embedding": vector, "index": 0}],
                       "model": "mistral-embed"}).encode("utf-8")
    assert len(body) > MAX_TEST_RESPONSE_BYTES

    mock_response = MagicMock()
    mock_response.headers.get.return_value = str(len(body))
    mock_response.read.return_value = body
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        result = provider_embedding_connection_test(
            base_url="https://api.example.com/v1",
            api_key="test-key",
            model_id="mistral-embed",
        )
    assert result == {"status": "ok"}


def test_embedding_connection_test_still_bounds_an_oversized_response() -> None:
    oversized = b"x" * (MAX_EMBEDDING_TEST_RESPONSE_BYTES + 1)
    mock_response = MagicMock()
    mock_response.headers.get.return_value = None
    mock_response.read.return_value = oversized
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("app.connection_test.urlopen", return_value=mock_response):
        with pytest.raises(ConnectionTestError) as exc:
            provider_embedding_connection_test(
                base_url="https://api.example.com/v1",
                api_key="test-key",
                model_id="mistral-embed",
            )
    assert exc.value.code == "provider_response_too_large"
