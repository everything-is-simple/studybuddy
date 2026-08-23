from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.embedding import EmbeddingError
from app.providers import OpenAICompatibleEmbeddingProvider


class EmbeddingHandler(BaseHTTPRequestHandler):
    status = 200
    body: object = {"data": [{"index": 0, "embedding": [1.0, 0.0]}, {"index": 1, "embedding": [0.0, 1.0]}]}
    received: dict[str, object] = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.received = {
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(self.rfile.read(length)),
        }
        raw = json.dumps(self.body).encode("utf-8")
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), EmbeddingHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def provider(server, **kwargs):
    return OpenAICompatibleEmbeddingProvider(
        provider_id="embedding-test", model_id="embedding-model", model_revision="1",
        base_url=f"http://127.0.0.1:{server.server_port}", api_key="embedding-secret", **kwargs,
    )


def test_openai_compatible_embedding_request_and_dimensions(server):
    result = provider(server).embed(["first", "second"])
    assert result == [[1.0, 0.0], [0.0, 1.0]]
    assert EmbeddingHandler.received["authorization"] == "Bearer embedding-secret"
    assert EmbeddingHandler.received["body"] == {"model": "embedding-model", "input": ["first", "second"]}


@pytest.mark.parametrize("status,code", [
    (401, "embedding_provider_auth_failed"),
    (403, "embedding_provider_forbidden"),
    (429, "embedding_provider_rate_limited"),
    (500, "embedding_provider_unavailable"),
])
def test_embedding_http_errors_are_stable(server, status, code):
    EmbeddingHandler.status = status
    try:
        with pytest.raises(EmbeddingError, match=code):
            provider(server).embed(["text"])
    finally:
        EmbeddingHandler.status = 200


def test_embedding_schema_and_dimension_errors_are_stable(server):
    EmbeddingHandler.body = {"data": [{"index": 0, "embedding": [1.0]}]}
    try:
        with pytest.raises(EmbeddingError, match="embedding_schema_mismatch"):
            provider(server).embed(["first", "second"])
        EmbeddingHandler.body = {"data": [{"index": 0, "embedding": [0.0, 0.0]}]}
        with pytest.raises(EmbeddingError, match="embedding_invalid_vector"):
            provider(server).embed(["text"])
    finally:
        EmbeddingHandler.body = {"data": [{"index": 0, "embedding": [1.0, 0.0]}, {"index": 1, "embedding": [0.0, 1.0]}]}


def test_embedding_response_limit_is_enforced(server):
    provider_instance = provider(server, max_response_bytes=8)
    with pytest.raises(EmbeddingError, match="embedding_provider_response_too_large"):
        provider_instance.embed(["text"])
