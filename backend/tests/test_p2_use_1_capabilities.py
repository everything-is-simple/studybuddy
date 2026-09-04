"""P2-USE-1 out-of-box capability enablement.

Covers the three defects this slice closes:
1. installed local components no longer default to disabled,
2. configuration persists through the UI instead of hand-copied env vars,
3. capability status is observable per capability with honest degradation labels.

Detection is stubbed so the suite stays deterministic on any host.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import capability_detect as detect
from app.capabilities import capability_snapshot, resolve_config
from app.capability_detect import (STATUS_AVAILABLE, STATUS_NOT_CONFIGURED, STATUS_NOT_INSTALLED,
                                   DetectedComponent, DetectionResult)
from app.config import AppConfig
from app.local_settings import (MAX_SETTINGS_BYTES, SettingsError, clear_settings, load_settings,
                                public_settings, save_settings, settings_path)
from app.main import create_app

_ENV_KEYS = (
    "STUDYBUDDY_OCR_PROVIDER", "STUDYBUDDY_OCR_ENABLED", "STUDYBUDDY_OCR_MODEL_ROOT",
    "STUDYBUDDY_ASR_PROVIDER", "STUDYBUDDY_ASR_RUNTIME", "STUDYBUDDY_ASR_MODEL_PATH",
    "STUDYBUDDY_AI_PROVIDER", "STUDYBUDDY_AI_MODEL", "STUDYBUDDY_AI_BASE_URL",
    "STUDYBUDDY_AI_API_KEY", "STUDYBUDDY_EMBEDDING_PROVIDER", "STUDYBUDDY_EMBEDDING_MODEL",
    "STUDYBUDDY_EMBEDDING_BASE_URL", "STUDYBUDDY_EMBEDDING_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _detection(*, ocr: bool = True, asr: bool = True, fallback: bool = True,
               ocr_root: Path | None = None, runtime: Path | None = None,
               model: Path | None = None) -> DetectionResult:
    paddle = (DetectedComponent(STATUS_AVAILABLE, None, ocr_root or Path("/models"),
                                identity="PP-OCRv5_server_det+PP-OCRv5_server_rec")
              if ocr else DetectedComponent(STATUS_NOT_INSTALLED, "paddleocr_package_missing"))
    whisper = (DetectedComponent(STATUS_AVAILABLE, None, runtime or Path("/whisper/main.exe"),
                                 model or Path("/whisper/ggml-large-v3-turbo.bin"),
                                 identity="ggml-large-v3-turbo")
               if asr else DetectedComponent(STATUS_NOT_CONFIGURED, "asr_runtime_not_found"))
    rapid = (DetectedComponent(STATUS_AVAILABLE, None, Path("/rapid"), identity="ch_PP-OCRv4")
             if fallback else DetectedComponent(STATUS_NOT_INSTALLED, "rapidocr_package_missing"))
    return DetectionResult(paddle_ocr=paddle, rapid_ocr=rapid, whisper_asr=whisper)


def _config(tmp_path: Path, **overrides: object) -> AppConfig:
    return AppConfig(data_root=tmp_path / "data", auto_detect_enabled=True, **overrides)


# --- defect 1: out-of-box lockdown ------------------------------------------

def test_detected_local_ocr_enables_capability_without_environment(tmp_path: Path) -> None:
    base = _config(tmp_path)
    assert base.ocr_enabled is False and base.ocr_provider_id is None

    resolved = resolve_config(base, settings={}, detection=_detection())

    assert resolved.ocr_enabled is True
    assert resolved.ocr_provider_id == "paddleocr"
    assert resolved.ocr_source == "detected"
    assert resolved.asr_provider_id == "whisper-cpp"
    assert resolved.asr_runtime_path is not None and resolved.asr_model_path is not None
    assert resolved.asr_source == "detected"


def test_missing_component_stays_off_and_is_reported_not_silently_disabled(tmp_path: Path) -> None:
    resolved = resolve_config(_config(tmp_path), settings={},
                              detection=_detection(ocr=False, asr=False, fallback=False))
    snapshot = capability_snapshot(resolved, _detection(ocr=False, asr=False, fallback=False))

    assert resolved.ocr_enabled is False
    assert snapshot["capabilities"]["ocr"]["status"] == STATUS_NOT_INSTALLED
    assert snapshot["capabilities"]["ocr"]["reason"] == "paddleocr_package_missing"
    assert snapshot["capabilities"]["asr"]["status"] == STATUS_NOT_CONFIGURED
    assert snapshot["ocr_fallback_installed"] is False


def test_explicit_environment_off_beats_detection(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDYBUDDY_OCR_ENABLED", "false")
    resolved = resolve_config(_config(tmp_path, ocr_enabled=False), settings={},
                              detection=_detection())

    assert resolved.ocr_enabled is False
    state = capability_snapshot(resolved, _detection())["capabilities"]["ocr"]
    assert state["status"] == "disabled"
    assert state["reason"] == "ocr_disabled_by_configuration"


def test_explicit_environment_provider_wins_over_detection(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDYBUDDY_OCR_PROVIDER", "operator-choice")
    resolved = resolve_config(_config(tmp_path, ocr_provider_id="operator-choice"),
                              settings={"ocr_provider_id": "stored-choice"},
                              detection=_detection())

    assert resolved.ocr_provider_id == "operator-choice"
    assert resolved.ocr_source == "environment"


def test_stored_settings_beat_detection_but_lose_to_environment(tmp_path: Path) -> None:
    resolved = resolve_config(_config(tmp_path),
                              settings={"ocr_provider_id": "stored-ocr", "ocr_enabled": False},
                              detection=_detection())

    assert resolved.ocr_provider_id == "stored-ocr"
    assert resolved.ocr_source == "settings"
    assert resolved.ocr_enabled is False


def test_detection_is_skipped_when_autodetect_is_disabled(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(**_kwargs: object) -> DetectionResult:
        raise AssertionError("detection must not run when auto-detect is disabled")

    monkeypatch.setattr(detect, "detect_all", _fail)
    base = AppConfig(data_root=tmp_path / "data", auto_detect_enabled=False)
    resolved = resolve_config(base, settings={})
    assert resolved == base
    assert resolved.ocr_enabled is False and resolved.ocr_provider_id is None


# --- detection probe behavior ------------------------------------------------

def test_paddle_probe_rejects_incomplete_model_root(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detect, "_module_installed", lambda _name: True)
    root = tmp_path / "models"
    (root / detect.PADDLE_DET_DIR).mkdir(parents=True)
    assert detect.detect_paddle_ocr(root).status == STATUS_NOT_CONFIGURED

    (root / detect.PADDLE_REC_DIR).mkdir()
    assert detect.detect_paddle_ocr(root).reason == "ocr_model_root_invalid"

    for name in (detect.PADDLE_DET_DIR, detect.PADDLE_REC_DIR):
        (root / name / "inference.pdiparams").write_bytes(b"stub")
    probe = detect.detect_paddle_ocr(root)
    assert probe.available and probe.path == root


def test_whisper_probe_requires_runtime_and_model(tmp_path: Path) -> None:
    runtime = tmp_path / "main.exe"
    runtime.write_bytes(b"stub")
    assert detect.detect_whisper_asr(runtime).reason == "asr_model_not_found"

    models = tmp_path / "Models"
    models.mkdir()
    (models / "ggml-large-v3-turbo.bin").write_bytes(b"stub")
    probe = detect.detect_whisper_asr(runtime)
    assert probe.available and probe.identity == "ggml-large-v3-turbo"
    assert detect.detect_whisper_asr(tmp_path / "absent.exe").reason == "asr_runtime_invalid"


def test_detection_never_leaks_paths_through_public_projection() -> None:
    component = DetectedComponent(STATUS_AVAILABLE, None, Path("/secret/place/models"),
                                  identity="model-x")
    projected = detect.public_component(component)
    assert "/secret/place" not in json.dumps(projected)
    assert projected["status"] == STATUS_AVAILABLE and projected["model_id"] == "model-x"
    assert detect.public_component(component, enabled=False)["status"] == "disabled"


# --- defect 2: configuration persistence ------------------------------------

def test_settings_round_trip_and_merge(tmp_path: Path) -> None:
    root = tmp_path / "data"
    assert load_settings(root) == {}

    save_settings(root, {"ai_provider_id": "deepseek", "ai_api_key": "sk-secret"})
    save_settings(root, {"ai_model_id": "deepseek-chat"})
    stored = load_settings(root)

    assert stored == {"ai_provider_id": "deepseek", "ai_api_key": "sk-secret",
                      "ai_model_id": "deepseek-chat"}
    assert settings_path(root).is_file()


def test_settings_live_outside_sqlite_and_originals(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_provider_id": "deepseek"})
    location = settings_path(root)

    assert location.parent.name == "config"
    assert location.suffix == ".json"
    assert not (root / "originals" / "config").exists()
    assert "originals" not in location.parts


def test_public_projection_hides_secrets_and_paths(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_api_key": "sk-secret", "ai_provider_id": "deepseek",
                         "ocr_model_root": "/opt/models", "asr_runtime_path": "/opt/whisper.exe"})
    projected = json.dumps(public_settings(load_settings(root)))

    assert "sk-secret" not in projected
    assert "/opt/models" not in projected and "/opt/whisper.exe" not in projected
    assert '"ai_api_key_set": true' in projected
    assert '"ocr_model_root_set": true' in projected


def test_settings_reject_unknown_keys_and_bad_values(tmp_path: Path) -> None:
    root = tmp_path / "data"
    # Delivery credentials are storable, but the delivery switches are not: mode,
    # enablement and per-use authorization stay runtime-only security controls.
    for guarded in ("report_delivery_mode", "report_delivery_enabled",
                    "report_delivery_authorized"):
        with pytest.raises(SettingsError) as unknown:
            save_settings(root, {guarded: "on"})
        assert unknown.value.code == "settings_unknown_key"

    with pytest.raises(SettingsError) as bad_target:
        save_settings(root, {"report_delivery_smtp_targets": "missing-separator"})
    assert bad_target.value.code == "settings_invalid_value"

    for payload in ({"ai_base_url": "ftp://example.com"},
                    {"ai_base_url": "http://evil.example.com"},
                    {"ai_base_url": "https://user:pw@example.com"},
                    {"ai_api_key": "has space"},
                    {"ocr_enabled": "maybe"},
                    {"ai_provider_id": "x" * 1001}):
        with pytest.raises(SettingsError) as error:
            save_settings(root, payload)
        assert error.value.code == "settings_invalid_value"

    assert load_settings(root) == {}


def test_settings_accept_loopback_http_and_normalize_url(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_base_url": "http://127.0.0.1:11434/"})
    assert load_settings(root)["ai_base_url"] == "http://127.0.0.1:11434"


def test_corrupt_settings_file_degrades_to_empty(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_provider_id": "deepseek"})
    settings_path(root).write_text("{not json", encoding="utf-8")
    assert load_settings(root) == {}

    settings_path(root).write_text(json.dumps({"format": "other", "settings": {}}), encoding="utf-8")
    assert load_settings(root) == {}


def test_oversized_settings_file_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_provider_id": "deepseek"})
    settings_path(root).write_text(" " * (MAX_SETTINGS_BYTES + 1), encoding="utf-8")
    assert load_settings(root) == {}


def test_clear_removes_selected_keys_or_everything(tmp_path: Path) -> None:
    root = tmp_path / "data"
    save_settings(root, {"ai_provider_id": "deepseek", "ai_api_key": "sk-secret",
                         "embedding_provider_id": "openai"})

    remaining = clear_settings(root, ["ai_api_key"])
    assert "ai_api_key" not in remaining and remaining["ai_provider_id"] == "deepseek"

    assert clear_settings(root) == {}
    assert not settings_path(root).exists()
    assert load_settings(root) == {}


# --- defect 3: observable capability status ---------------------------------

def test_snapshot_reports_seven_capabilities_with_honest_degradation(tmp_path: Path) -> None:
    resolved = resolve_config(_config(tmp_path), settings={}, detection=_detection())
    snapshot = capability_snapshot(resolved, _detection())
    capabilities = snapshot["capabilities"]

    assert set(capabilities) == {"import_parse", "ocr", "asr", "index", "qa", "generation", "report"}
    assert capabilities["import_parse"]["status"] == STATUS_AVAILABLE
    assert capabilities["ocr"]["status"] == STATUS_AVAILABLE
    assert capabilities["asr"]["status"] == STATUS_AVAILABLE
    assert capabilities["report"]["status"] == STATUS_AVAILABLE
    # No provider key yet: index degrades honestly, Q&A and generation stay unconfigured.
    assert capabilities["index"]["status"] == "degraded"
    assert capabilities["index"]["reason"] == "embedding_provider_not_configured"
    assert capabilities["qa"]["status"] == STATUS_NOT_CONFIGURED
    assert capabilities["generation"]["status"] == STATUS_NOT_CONFIGURED
    assert snapshot["ready_count"] == 4 and snapshot["total_count"] == 7
    assert snapshot["delivery_mode"] == "off"


def test_provider_credentials_complete_the_snapshot(tmp_path: Path) -> None:
    stored = {"ai_provider_id": "deepseek", "ai_model_id": "deepseek-chat",
              "ai_base_url": "https://api.deepseek.com", "ai_api_key": "sk-secret",
              "embedding_provider_id": "openai", "embedding_model_id": "text-embedding-3-small",
              "embedding_base_url": "https://api.openai.com/v1", "embedding_api_key": "sk-secret"}
    resolved = resolve_config(_config(tmp_path), settings=stored, detection=_detection())
    snapshot = capability_snapshot(resolved, _detection())

    assert snapshot["ready_count"] == 7
    assert snapshot["degraded_count"] == 0
    assert "sk-secret" not in json.dumps(snapshot)


def test_partial_credentials_are_not_reported_available(tmp_path: Path) -> None:
    resolved = resolve_config(_config(tmp_path),
                              settings={"ai_provider_id": "deepseek",
                                        "ai_base_url": "https://api.deepseek.com"},
                              detection=_detection())
    state = capability_snapshot(resolved, _detection())["capabilities"]["qa"]
    assert state["status"] == STATUS_NOT_CONFIGURED
    assert state["reason"] == "provider_credentials_missing"


# --- API surface -------------------------------------------------------------

@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(detect, "detect_all",
                        lambda **_kwargs: _detection(ocr_root=tmp_path / "models"))
    root = tmp_path / "data"
    root.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app(_config(tmp_path))) as test_client:
        yield test_client


def test_capabilities_endpoint_returns_dashboard_payload(client: TestClient) -> None:
    response = client.get("/api/system/capabilities")
    assert response.status_code == 200
    payload = response.json()

    assert payload["capabilities"]["ocr"]["status"] == STATUS_AVAILABLE
    assert payload["capabilities"]["ocr"]["source"] == "detected"
    assert payload["auto_detect_enabled"] is True
    assert payload["delivery_mode"] == "off"
    assert "/models" not in json.dumps(payload).replace("PP-OCRv5", "")


def test_self_check_endpoint_reprobes(client: TestClient) -> None:
    response = client.post("/api/system/capabilities/self-check")
    assert response.status_code == 200
    assert response.json()["checked"] is True


def test_settings_endpoint_persists_and_applies_without_restart(client: TestClient) -> None:
    written = client.put("/api/system/settings", json={
        "ai_provider_id": "deepseek", "ai_model_id": "deepseek-chat",
        "ai_base_url": "https://api.deepseek.com", "ai_api_key": "sk-secret",
    })
    assert written.status_code == 200
    payload = written.json()

    # Applied in the same process, no restart involved.
    assert payload["capabilities"]["qa"]["status"] == STATUS_AVAILABLE
    assert payload["capabilities"]["generation"]["status"] == STATUS_AVAILABLE
    assert payload["settings"]["ai_api_key_set"] is True
    assert "sk-secret" not in written.text

    reread = client.get("/api/system/settings").json()["settings"]
    assert reread["ai_provider_id"] == "deepseek"
    assert "ai_api_key" not in reread

    after = client.get("/api/system/capabilities").json()
    assert after["capabilities"]["qa"]["status"] == STATUS_AVAILABLE


def test_settings_endpoint_clears_with_empty_string(client: TestClient) -> None:
    client.put("/api/system/settings", json={"ai_provider_id": "deepseek",
                                            "ai_api_key": "sk-secret"})
    cleared = client.put("/api/system/settings", json={"ai_provider_id": ""})
    assert cleared.status_code == 200
    assert "ai_provider_id" not in cleared.json()["settings"]


def test_settings_endpoint_rejects_bad_input_safely(client: TestClient) -> None:
    empty = client.put("/api/system/settings", json={})
    assert empty.status_code == 400 and empty.json()["detail"] == "settings_empty_payload"

    bad = client.put("/api/system/settings", json={"ai_base_url": "ftp://example.com"})
    assert bad.status_code == 400 and bad.json()["detail"] == "settings_invalid_value"

    unknown = client.post("/api/system/settings/clear", json={"keys": ["not_a_key"]})
    assert unknown.status_code == 400 and unknown.json()["detail"] == "settings_unknown_key"


def test_settings_clear_endpoint_resets_capabilities(client: TestClient) -> None:
    client.put("/api/system/settings", json={
        "ai_provider_id": "deepseek", "ai_model_id": "deepseek-chat",
        "ai_base_url": "https://api.deepseek.com", "ai_api_key": "sk-secret",
    })
    cleared = client.post("/api/system/settings/clear", json={})
    assert cleared.status_code == 200
    assert cleared.json()["capabilities"]["qa"]["status"] == STATUS_NOT_CONFIGURED
    assert cleared.json()["settings"]["ai_api_key_set"] is False


def test_stored_delivery_credentials_reach_the_resolved_config(tmp_path: Path) -> None:
    """Email credentials persist, but the delivery switch stays a security control."""
    root = tmp_path / "data"
    save_settings(root, {
        "report_delivery_smtp_host": "smtp.example.com",
        "report_delivery_smtp_port": 465,
        "report_delivery_smtp_secure": True,
        "report_delivery_smtp_username": "sender@example.com",
        "report_delivery_smtp_password": "app-specific-code",
        "report_delivery_smtp_targets": "parent=guardian@example.com",
    })
    base = AppConfig(data_root=root)
    resolved = resolve_config(base, settings=load_settings(root), detection=None)

    assert resolved.report_delivery_smtp_host == "smtp.example.com"
    assert resolved.report_delivery_smtp_port == 465
    assert resolved.report_delivery_smtp_secure is True
    assert resolved.report_delivery_smtp_username == "sender@example.com"
    assert resolved.report_delivery_smtp_password_runtime == "app-specific-code"
    assert resolved.report_delivery_smtp_targets == (("parent", "guardian@example.com"),)
    # Outbound delivery is not switched on by storing credentials.
    assert resolved.report_delivery_mode == base.report_delivery_mode
    assert resolved.report_delivery_enabled is base.report_delivery_enabled

    snapshot = capability_snapshot(resolved, None)
    assert snapshot["capabilities"]["report"]["delivery_configured"] is True
    assert snapshot["delivery_mode"] == base.report_delivery_mode
    body = json.dumps(snapshot)
    assert "app-specific-code" not in body and "guardian@example.com" not in body


def test_environment_delivery_credentials_win_over_stored_ones(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "data"
    save_settings(root, {"report_delivery_smtp_host": "stored.example.com"})
    monkeypatch.setenv("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST", "env.example.com")
    resolved = resolve_config(AppConfig(data_root=root, report_delivery_smtp_host="env.example.com"),
                              settings=load_settings(root), detection=None)
    assert resolved.report_delivery_smtp_host == "env.example.com"
