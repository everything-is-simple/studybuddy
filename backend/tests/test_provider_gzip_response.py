"""Provider HTTP 客户端 gzip 响应透明解压测试。

部分 Provider（如火山引擎 plan API）无论 Accept-Encoding 如何都会返回
gzip 压缩的响应体。_request_json 与 _request_json_with_limit 必须对
gzip 魔数（1f 8b）响应透明解压后再解析 JSON，否则报 malformed_response。
"""
from __future__ import annotations

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.providers._helpers import _request_json, _request_json_with_limit


class _GzipHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({"data": [{"index": 0, "embedding": [0.1, 0.2]}], "ok": True}).encode("utf-8")
        compressed = gzip.compress(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.end_headers()
        self.wfile.write(compressed)

    def log_message(self, *args) -> None:  # 静默
        return None


@pytest.fixture()
def gzip_server():
    server = HTTPServer(("127.0.0.1", 0), _GzipHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    thread.join(timeout=5)


def test_request_json_accepts_gzip_response(gzip_server):
    payload = json.dumps({"model": "m", "input": ["x"]}).encode("utf-8")
    result = _request_json(gzip_server + "/chat/completions", payload,
                           {"Authorization": "Bearer k", "Content-Type": "application/json"}, 10)
    assert result["ok"] is True


def test_request_json_with_limit_accepts_gzip_response(gzip_server):
    payload = json.dumps({"model": "m", "input": ["x"]}).encode("utf-8")
    result = _request_json_with_limit(gzip_server + "/embeddings", payload,
                                      {"Authorization": "Bearer k", "Content-Type": "application/json"}, 10, 1 << 20)
    assert result["data"][0]["embedding"] == [0.1, 0.2]
