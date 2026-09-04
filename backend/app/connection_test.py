"""Provider and delivery connection-test adapters.

This module implements explicit connection tests for Provider (AI LLM/Embedding)
and Email (SMTP/Feishu) configurations. Tests use fixed synthetic payloads,
bounded responses, and stable error code mapping.

Contract: P1-5-0 frozen, P1-5-2 implementation.
- Tests are explicitly triggered (never automatic)
- Tests do not change configuration state
- Tests use fixed synthetic payloads
- Responses are bounded (timeout, max bytes, no redirects)
- Errors map to stable codes
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
    """Connection test error with stable error code."""

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
    """Test LLM Provider connection with synthetic payload.

    Returns:
        {"status": "ok"} on success
        Raises ConnectionTestError with stable error code on failure

    Error codes:
        - provider_connection_failed: network error
        - provider_timeout: request timeout
        - provider_auth_failed: HTTP 401
        - provider_forbidden: HTTP 403
        - provider_rate_limited: HTTP 429
        - provider_unavailable: HTTP 5xx
        - provider_protocol_error: other HTTP error or malformed response
        - provider_response_too_large: response exceeds limit
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
    """Test Embedding Provider connection with synthetic payload.

    Returns:
        {"status": "ok"} on success
        Raises ConnectionTestError with stable error code on failure

    Error codes: same as test_provider_llm_connection
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
    """Test SMTP connection with synthetic email.

    Returns:
        {"status": "ok"} on success
        Raises ConnectionTestError with stable error code on failure

    Error codes:
        - delivery_configuration_invalid: missing required config
        - delivery_connection_failed: network error
        - delivery_timeout: request timeout
        - delivery_auth_failed: authentication error
        - delivery_failed: SMTP protocol error
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
    """Test Feishu webhook connection with synthetic message.

    Returns:
        {"status": "ok"} on success
        Raises ConnectionTestError with stable error code on failure

    Error codes:
        - delivery_configuration_invalid: invalid webhook URL
        - delivery_connection_failed: network error
        - delivery_timeout: request timeout
        - delivery_failed: HTTP error or malformed response
        - delivery_response_too_large: response exceeds limit
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
