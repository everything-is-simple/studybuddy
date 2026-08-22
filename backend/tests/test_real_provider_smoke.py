from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import config_from_environment
from app.main import create_app
from app.providers import ProviderRequest, provider_registry


def _targeted_real_provider_config():
    if os.environ.get("STUDYBUDDY_RUN_REAL_PROVIDER_SMOKE") != "1":
        pytest.skip("opt-in real provider smoke")
    target = os.environ.get("STUDYBUDDY_REAL_PROVIDER_TARGET")
    if not target:
        pytest.skip("real provider target is not set")
    config = config_from_environment()
    if (not config.ai_provider_id or config.ai_provider_id == "fake" or not config.ai_model_id
            or not config.ai_base_url or not config.ai_api_key):
        pytest.skip("real provider configuration is incomplete")
    if config.ai_provider_id != target:
        pytest.skip("real provider configuration does not match target")
    return config


def test_opt_in_real_provider_smoke_uses_synthetic_context():
    config = _targeted_real_provider_config()
    provider = provider_registry(
        config.ai_provider_id, config.ai_model_id,
        base_url=config.ai_base_url, api_key=config.ai_api_key,
        timeout_seconds=config.ai_timeout_seconds, max_retries=0,
    ).configured_provider()
    result = provider.generate_answer(ProviderRequest(
        question="What does the synthetic study note establish?",
        context_blocks=[{
            "citation_key": "ctx-12345678-abcdefgh",
            "text": "Synthetic study note: the controlled experiment establishes a stable result.",
        }],
        max_output_tokens=config.ai_max_output_tokens,
        max_prompt_chars=config.ai_max_prompt_chars,
        max_answer_chars=config.ai_max_answer_chars,
    ))
    assert result.answer_text
    assert result.provider_id == config.ai_provider_id
    assert result.model_id == config.ai_model_id
    assert result.latency_ms is not None
    assert result.prompt_tokens is not None
    assert result.completion_tokens is not None


def test_opt_in_real_provider_smoke_completes_qa_api_path(tmp_path: Path):
    config = _targeted_real_provider_config()
    app_config = replace(
        config,
        data_root=tmp_path,
        ai_max_output_tokens=min(config.ai_max_output_tokens, 256),
        ai_max_answer_chars=min(config.ai_max_answer_chars, 4000),
        ai_max_retries=0,
    )
    with TestClient(create_app(app_config)) as client:
        upload = client.post(
            "/api/materials",
            files={"file": ("synthetic-provider-smoke.txt", b"Synthetic study note: the controlled experiment establishes a stable result.", "text/plain")},
        )
        assert upload.status_code == 201
        material_id = upload.json()["material_id"]
        indexed = client.post(f"/api/materials/{material_id}/ai-index")
        assert indexed.status_code == 200
        response = client.post("/api/qa/ask", json={
            "question": "controlled experiment establishes",
            "material_ids": [material_id],
            "top_k": 3,
        })
        assert response.status_code == 200, response.json().get("detail", "real provider request failed")
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["answer_text"].strip()
        assert payload["provider_id"] == config.ai_provider_id
        assert payload["model_id"] == config.ai_model_id
        assert payload["citations"]
        with __import__("sqlite3").connect(tmp_path / "studybuddy.sqlite3") as db:
            operation = db.execute(
                "SELECT status, provider_id, model_id, provider_request_id, latency_ms "
                "FROM ai_operations WHERE id = ?", (payload["operation_id"],)
            ).fetchone()
            assert operation[0:3] == ("succeeded", config.ai_provider_id, config.ai_model_id)
            assert operation[3]
            assert operation[4] is not None
