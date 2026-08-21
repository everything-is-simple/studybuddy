from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import AppConfig, config_from_environment
from app.main import create_app
from app.providers import ProviderError, ProviderRequest, provider_registry


def test_capabilities_default_provider_not_configured(tmp_path: Path):
    with TestClient(create_app(AppConfig(data_root=tmp_path))) as client:
        response = client.get("/api/ai/capabilities")
        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "status": "not_configured",
            "configured": False,
            "provider_id": None,
            "model_id": None,
            "supports": {"qa": False},
            "error_code": "provider_not_configured",
        }
        text = response.text.lower()
        for bad in ("secret", "token", "key", "stored_path", "traceback", "sqlite", "h:/", "g:/"):
            assert bad not in text


def test_capabilities_fake_provider_available(tmp_path: Path):
    config = AppConfig(data_root=tmp_path, ai_provider_id="fake")
    with TestClient(create_app(config)) as client:
        response = client.get("/api/ai/capabilities")
        assert response.status_code == 200
        assert response.json() == {
            "status": "available",
            "configured": True,
            "provider_id": "fake",
            "model_id": "fake-studybuddy-v1",
            "supports": {"qa": True},
        }


def test_provider_environment_configuration(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STUDYBUDDY_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("STUDYBUDDY_AI_PROVIDER", "fake")
    monkeypatch.setenv("STUDYBUDDY_AI_MODEL", "fake-studybuddy-v1")
    config = config_from_environment()
    assert config.ai_provider_id == "fake"
    assert config.ai_model_id == "fake-studybuddy-v1"


def test_unknown_provider_uses_stable_not_configured_code():
    registry = provider_registry("unknown")
    try:
        registry.configured_provider()
    except ProviderError as error:
        assert error.code == "provider_not_configured"
    else:
        raise AssertionError("unknown provider should not be configured")
    assert registry.capabilities()["error_code"] == "provider_not_configured"


def test_fake_provider_is_deterministic_and_uses_context_citations():
    provider = provider_registry("fake").configured_provider()
    request = ProviderRequest(
        question="What matters?",
        context_blocks=[
            {"citation_key": "ctx-11111111-22222222", "text": "Alpha beta gamma."},
            {"citation_key": "ctx-33333333-44444444", "text": "Delta epsilon."},
        ],
    )
    first = provider.generate_answer(request)
    second = provider.generate_answer(request)
    assert first == second
    assert first.provider_id == "fake"
    assert first.model_id == "fake-studybuddy-v1"
    assert first.citation_keys == ["ctx-11111111-22222222", "ctx-33333333-44444444"]
    assert "ctx-11111111-22222222" in first.answer_text
    assert first.prompt_tokens > 0
    assert first.completion_tokens > 0


def test_fake_provider_rejects_empty_or_oversized_question():
    provider = provider_registry("fake").configured_provider()
    for question in ("", "x" * 8001):
        try:
            provider.generate_answer(ProviderRequest(question=question, context_blocks=[]))
        except ProviderError as error:
            assert error.code == "provider_invalid_request"
        else:
            raise AssertionError("invalid request should fail")
