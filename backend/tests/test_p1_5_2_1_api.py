"""Tests for connection-test API endpoints.

Contract: P1-5-0 frozen, P1-5-2 implementation.
"""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.app_factory import create_app  # noqa: E402
from app.connection_test import ConnectionTestError  # noqa: E402


@pytest.fixture
def client():
    """Create test client."""
    app = create_app(index_html="<html></html>")
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_provider_connection_test_endpoint_llm_success(client) -> None:
    """验证 LLM Provider connection-test API 成功路径。"""
    with patch("app.api.system.provider_llm_connection_test") as mock_test:
        mock_test.return_value = {"status": "ok"}

        response = client.post(
            "/api/system/provider-connection-test",
            json={
                "provider_type": "llm",
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "model_id": "test-model",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_test.assert_called_once()


def test_provider_connection_test_endpoint_embedding_success(client) -> None:
    """验证 Embedding Provider connection-test API 成功路径。"""
    with patch("app.api.system.provider_embedding_connection_test") as mock_test:
        mock_test.return_value = {"status": "ok"}

        response = client.post(
            "/api/system/provider-connection-test",
            json={
                "provider_type": "embedding",
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "model_id": "test-model",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_test.assert_called_once()


def test_provider_connection_test_endpoint_invalid_type(client) -> None:
    """验证 Provider connection-test API 拒绝无效类型。"""
    response = client.post(
        "/api/system/provider-connection-test",
        json={
            "provider_type": "invalid",
            "base_url": "https://api.example.com",
            "api_key": "test-key",
            "model_id": "test-model",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_provider_type"


def test_provider_connection_test_endpoint_error_mapping(client) -> None:
    """验证 Provider connection-test API 错误码映射。"""
    with patch("app.api.system.provider_llm_connection_test") as mock_test:
        mock_test.side_effect = ConnectionTestError("provider_timeout")

        response = client.post(
            "/api/system/provider-connection-test",
            json={
                "provider_type": "llm",
                "base_url": "https://api.example.com",
                "api_key": "test-key",
                "model_id": "test-model",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "provider_timeout"


def test_email_connection_test_endpoint_smtp_success(client) -> None:
    """验证 SMTP connection-test API 成功路径。"""
    with patch("app.api.system.smtp_connection_test") as mock_test:
        mock_test.return_value = {"status": "ok"}

        response = client.post(
            "/api/system/email-connection-test",
            json={
                "channel": "smtp",
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "smtp_secure": True,
                "smtp_sender": "sender@example.com",
                "smtp_recipient": "recipient@example.com",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_test.assert_called_once()


def test_email_connection_test_endpoint_feishu_success(client) -> None:
    """验证 Feishu connection-test API 成功路径。"""
    with patch("app.api.system.feishu_connection_test") as mock_test:
        mock_test.return_value = {"status": "ok"}

        response = client.post(
            "/api/system/email-connection-test",
            json={
                "channel": "feishu",
                "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_test.assert_called_once()


def test_email_connection_test_endpoint_invalid_channel(client) -> None:
    """验证 Email connection-test API 拒绝无效 channel。"""
    response = client.post(
        "/api/system/email-connection-test",
        json={
            "channel": "invalid",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_channel"


def test_email_connection_test_endpoint_smtp_missing_fields(client) -> None:
    """验证 SMTP connection-test API 拒绝不完整配置。"""
    response = client.post(
        "/api/system/email-connection-test",
        json={
            "channel": "smtp",
            "smtp_host": "smtp.example.com",
            # Missing smtp_port, smtp_sender, smtp_recipient
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "delivery_configuration_invalid"


def test_email_connection_test_endpoint_feishu_missing_webhook(client) -> None:
    """验证 Feishu connection-test API 拒绝缺少 webhook。"""
    response = client.post(
        "/api/system/email-connection-test",
        json={
            "channel": "feishu",
            # Missing feishu_webhook
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "delivery_configuration_invalid"


def test_email_connection_test_endpoint_error_mapping(client) -> None:
    """验证 Email connection-test API 错误码映射。"""
    with patch("app.api.system.smtp_connection_test") as mock_test:
        mock_test.side_effect = ConnectionTestError("delivery_auth_failed")

        response = client.post(
            "/api/system/email-connection-test",
            json={
                "channel": "smtp",
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "smtp_secure": True,
                "smtp_sender": "sender@example.com",
                "smtp_recipient": "recipient@example.com",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "delivery_auth_failed"


def test_provider_connection_test_does_not_expose_secrets(client) -> None:
    """验证 Provider connection-test 错误响应不暴露 secret。"""
    with patch("app.api.system.provider_llm_connection_test") as mock_test:
        mock_test.side_effect = ConnectionTestError("provider_auth_failed")

        response = client.post(
            "/api/system/provider-connection-test",
            json={
                "provider_type": "llm",
                "base_url": "https://api.example.com",
                "api_key": "SECRET_API_KEY_12345",
                "model_id": "test-model",
            },
        )

    # 验证响应不包含 API key
    response_text = response.text
    assert "SECRET_API_KEY_12345" not in response_text
    assert "api_key" not in response.json().get("detail", "")


def test_email_connection_test_does_not_expose_secrets(client) -> None:
    """验证 Email connection-test 错误响应不暴露 secret。"""
    with patch("app.api.system.smtp_connection_test") as mock_test:
        mock_test.side_effect = ConnectionTestError("delivery_auth_failed")

        response = client.post(
            "/api/system/email-connection-test",
            json={
                "channel": "smtp",
                "smtp_host": "smtp.example.com",
                "smtp_port": 465,
                "smtp_username": "user@example.com",
                "smtp_password": "SECRET_PASSWORD_67890",
                "smtp_sender": "sender@example.com",
                "smtp_recipient": "recipient@example.com",
            },
        )

    # 验证响应不包含密码
    response_text = response.text
    assert "SECRET_PASSWORD_67890" not in response_text
    assert "smtp_password" not in response.json().get("detail", "")
