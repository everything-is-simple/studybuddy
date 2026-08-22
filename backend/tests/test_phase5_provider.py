from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig, config_from_environment
from app.providers import OpenAICompatibleLLMProvider, ProviderError, ProviderRequest


class Handler(BaseHTTPRequestHandler):
    response_status = 200
    response_body: object = {
        "id": "chatcmpl-test-1",
        "choices": [{"message": {"content": "Answer [ctx-12345678-abcdefgh]"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }
    response_raw: bytes | None = None
    received: dict[str, object] = {}
    request_count = 0

    def do_POST(self):
        self.__class__.request_count += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.received = {
            "authorization": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            "body": json.loads(self.rfile.read(length)),
        }
        body = self.response_raw if self.response_raw is not None else json.dumps(self.response_body).encode("utf-8")
        self.send_response(self.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def provider(server, **kwargs):
    return OpenAICompatibleLLMProvider(
        provider_id="deepseek", model_id="deepseek-chat",
        base_url=f"http://127.0.0.1:{server.server_port}", api_key="test-secret",
        **kwargs,
    )


def test_openai_compatible_request_and_metadata(server):
    result = provider(server).generate_answer(ProviderRequest(
        question="What?", context_blocks=[{"citation_key": "ctx-12345678-abcdefgh", "text": "Evidence."}],
    ))
    received = Handler.received
    assert received["authorization"] == "Bearer test-secret"
    assert received["body"]["model"] == "deepseek-chat"
    assert received["body"]["temperature"] == 0
    assert received["body"]["stream"] is False
    assert result.provider_request_id == "chatcmpl-test-1"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert result.total_tokens == 18
    assert result.latency_ms is not None
    assert result.citation_keys == ["ctx-12345678-abcdefgh"]


@pytest.mark.parametrize("status,code", [
    (401, "provider_auth_failed"), (403, "provider_forbidden"),
    (429, "provider_rate_limited"), (500, "provider_unavailable"),
])
def test_http_statuses_map_to_stable_errors(server, status, code):
    Handler.response_status = status
    try:
        with pytest.raises(ProviderError, match=code):
            provider(server).generate_answer(ProviderRequest("Question", []))
    finally:
        Handler.response_status = 200


def test_retry_only_retries_transient_provider_unavailable(server):
    Handler.response_status = 503
    Handler.request_count = 0
    try:
        with pytest.raises(ProviderError, match="provider_unavailable"):
            provider(server, max_retries=1).generate_answer(ProviderRequest("Question", []))
        assert Handler.request_count == 2
    finally:
        Handler.response_status = 200
        Handler.request_count = 0


def test_malformed_and_schema_mismatch_are_safe(server):
    Handler.response_body = {"unexpected": True}
    try:
        with pytest.raises(ProviderError, match="provider_schema_mismatch"):
            provider(server).generate_answer(ProviderRequest("Question", []))
    finally:
        Handler.response_body = {
            "id": "chatcmpl-test-1",
            "choices": [{"message": {"content": "Answer [ctx-12345678-abcdefgh]"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }


def test_output_limit_and_refusal(server):
    Handler.response_body = {"choices": [{"message": {"content": "too long"}, "finish_reason": "refusal"}]}
    try:
        with pytest.raises(ProviderError, match="provider_refusal"):
            provider(server).generate_answer(ProviderRequest("Question", [], max_answer_chars=100))
        Handler.response_body = {"choices": [{"message": {"content": "x" * 101}, "finish_reason": "stop"}]}
        with pytest.raises(ProviderError, match="provider_output_too_large"):
            provider(server).generate_answer(ProviderRequest("Question", [], max_answer_chars=100))
    finally:
        Handler.response_body = {
            "id": "chatcmpl-test-1",
            "choices": [{"message": {"content": "Answer [ctx-12345678-abcdefgh]"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }
        Handler.response_raw = None


def test_empty_content_and_malformed_json_are_rejected(server):
    Handler.response_body = {"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]}
    with pytest.raises(ProviderError, match="provider_malformed_response"):
        provider(server).generate_answer(ProviderRequest("Question", []))
    Handler.response_raw = b"not-json"
    try:
        with pytest.raises(ProviderError, match="provider_malformed_response"):
            provider(server).generate_answer(ProviderRequest("Question", []))
    finally:
        Handler.response_raw = None


def test_response_body_limit_is_enforced_during_read(server):
    Handler.response_raw = b"{" + b"x" * (2 * 1024 * 1024) + b"}"
    try:
        with pytest.raises(ProviderError, match="provider_output_too_large"):
            provider(server).generate_answer(ProviderRequest("Question", []))
    finally:
        Handler.response_raw = None


def test_config_secret_is_not_repr_or_capabilities(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STUDYBUDDY_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDYBUDDY_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("STUDYBUDDY_AI_MODEL", "deepseek-chat")
    monkeypatch.setenv("STUDYBUDDY_AI_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("STUDYBUDDY_AI_API_KEY", "super-secret-test-key")
    config = config_from_environment()
    assert "super-secret-test-key" not in repr(config)
    assert "super-secret-test-key" not in str(config)
    assert config.ai_base_url == "https://api.example.test"


@pytest.mark.parametrize("base_url", [
    "file:///private", "http://api.example.test", "https://user:pass@example.test", "https://example.test/path?key=value",
])
def test_invalid_provider_config_is_rejected(monkeypatch, base_url):
    monkeypatch.setenv("STUDYBUDDY_AI_BASE_URL", base_url)
    with pytest.raises(ValueError, match="invalid_ai_base_url"):
        config_from_environment()


def test_loopback_http_provider_config_is_allowed(monkeypatch):
    monkeypatch.setenv("STUDYBUDDY_AI_BASE_URL", "http://127.0.0.1:8080/")
    assert config_from_environment().ai_base_url == "http://127.0.0.1:8080"
