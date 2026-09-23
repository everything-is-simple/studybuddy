from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "health-studybuddy.ps1"


class _HealthHandler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, str]] = {}
    delayed_path: str | None = None

    def do_GET(self) -> None:
        if self.path == self.delayed_path:
            time.sleep(2)
        status, body = self.responses.get(self.path, (200, '{"status":"ok"}'))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(body.encode("utf-8"))
        except OSError:
            pass

    def log_message(self, _format: str, *_args: object) -> None:
        pass


@pytest.mark.skipif(os.name != "nt", reason="health script is Windows PowerShell")
@pytest.mark.parametrize("scenario", ["healthy", "http_503", "timeout", "unavailable", "invalid_response"])
def test_health_script_reports_sanitized_probe_states(scenario: str) -> None:
    if scenario == "unavailable":
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        server = None
    else:
        _HealthHandler.responses = {
            "/api/liveness": (200, '{"status":"ok"}'),
            "/api/health": (200, '{"status":"ok"}'),
            "/api/readiness": (200, '{"status":"ready"}'),
        }
        _HealthHandler.delayed_path = None
        if scenario == "http_503":
            _HealthHandler.responses["/api/health"] = (503, '{"detail":"private response"}')
        elif scenario == "timeout":
            _HealthHandler.delayed_path = "/api/readiness"
        elif scenario == "invalid_response":
            _HealthHandler.responses["/api/readiness"] = (200, '{"status":"not_ready"}')
        server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
             "-BaseUrl", base_url, "-TimeoutSec", "1" if scenario == "timeout" else "4"],
            capture_output=True, text=True, timeout=25, check=False,
        )
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    payload = json.loads(result.stdout.strip())
    assert result.stderr == ""
    assert "private response" not in result.stdout
    if scenario == "healthy":
        assert result.returncode == 0
        assert payload == {
            "status": "healthy",
            "probes": {name: {"state": "ok", "http_status": 200}
                       for name in ("liveness", "health", "readiness")},
        }
    elif scenario == "http_503":
        assert result.returncode == 1
        assert payload["probes"]["health"] == {"state": "http_error", "http_status": 503}
    elif scenario == "timeout":
        assert result.returncode == 1
        assert payload["probes"]["readiness"] == {"state": "timeout", "http_status": None}
    elif scenario == "invalid_response":
        assert result.returncode == 1
        assert payload["probes"]["readiness"] == {"state": "invalid_response", "http_status": 200}
    else:
        assert result.returncode == 1
        assert payload["status"] == "unavailable"
        assert all(probe["state"] == "unavailable" for probe in payload["probes"].values())
