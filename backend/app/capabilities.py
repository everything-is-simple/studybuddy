"""Effective capability resolution: environment, stored settings, detection.

Precedence, highest first:
1. explicit environment variables (operator/launcher intent),
2. settings persisted through the UI under `<data_root>/config/settings.json`,
3. local component auto-detection.

This is what closes the "out-of-box lockdown" defect: an installed and
structurally valid local component becomes usable without hand-copied
environment variables, while an explicit setting always wins.

Outbound delivery is intentionally excluded. It stays runtime-only, default-off
and per-use authorized.
"""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from . import capability_detect as detect
from .capability_detect import (STATUS_AVAILABLE, STATUS_DISABLED, STATUS_NOT_CONFIGURED,
                                STATUS_NOT_INSTALLED, DetectionResult)
from .config import AppConfig
from .local_settings import load_settings

_SOURCE_ENVIRONMENT = "environment"
_SOURCE_SETTINGS = "settings"
_SOURCE_DETECTED = "detected"
_SOURCE_UNSET = "unset"

STATUS_DEGRADED = "degraded"

CAPABILITY_KEYS = ("import_parse", "ocr", "asr", "index", "qa", "generation", "report")


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _stored_path(settings: dict[str, object], key: str) -> Path | None:
    value = settings.get(key)
    return Path(str(value)) if value else None


def resolve_config(base: AppConfig, *, settings: dict[str, object] | None = None,
                   detection: DetectionResult | None = None) -> AppConfig:
    """Layer stored settings and detection onto an environment-derived config."""
    stored = settings if settings is not None else load_settings(base.data_root)

    ocr_provider = base.ocr_provider_id
    ocr_model = base.ocr_model_id
    ocr_root = base.ocr_model_root
    ocr_source = _SOURCE_ENVIRONMENT if _env_present("STUDYBUDDY_OCR_PROVIDER") else _SOURCE_UNSET
    if ocr_source != _SOURCE_ENVIRONMENT and stored.get("ocr_provider_id"):
        ocr_provider = str(stored["ocr_provider_id"])
        ocr_model = str(stored.get("ocr_model_id") or ocr_model)
        ocr_root = _stored_path(stored, "ocr_model_root") or ocr_root
        ocr_source = _SOURCE_SETTINGS
    if not _env_present("STUDYBUDDY_OCR_MODEL_ROOT") and stored.get("ocr_model_root"):
        ocr_root = _stored_path(stored, "ocr_model_root") or ocr_root

    asr_provider = base.asr_provider_id
    asr_model = base.asr_model_id
    asr_runtime = base.asr_runtime_path
    asr_model_path = base.asr_model_path
    asr_source = _SOURCE_ENVIRONMENT if _env_present("STUDYBUDDY_ASR_PROVIDER") else _SOURCE_UNSET
    if asr_source != _SOURCE_ENVIRONMENT and stored.get("asr_provider_id"):
        asr_provider = str(stored["asr_provider_id"])
        asr_model = str(stored.get("asr_model_id") or asr_model)
        asr_source = _SOURCE_SETTINGS
    if not _env_present("STUDYBUDDY_ASR_RUNTIME") and stored.get("asr_runtime_path"):
        asr_runtime = _stored_path(stored, "asr_runtime_path") or asr_runtime
    if not _env_present("STUDYBUDDY_ASR_MODEL_PATH") and stored.get("asr_model_path"):
        asr_model_path = _stored_path(stored, "asr_model_path") or asr_model_path

    ocr_enabled = base.ocr_enabled
    if not _env_present("STUDYBUDDY_OCR_ENABLED") and "ocr_enabled" in stored:
        ocr_enabled = bool(stored["ocr_enabled"])

    if detection is None and base.auto_detect_enabled:
        detection = detect.detect_all(ocr_model_root=ocr_root, asr_runtime=asr_runtime,
                                      asr_model=asr_model_path, preferred_base=base.data_root)
    elif detection is not None and base.auto_detect_enabled:
        detection = _probe_configured_paths(detection, ocr_root, asr_runtime, asr_model_path,
                                           preferred_base=base.data_root)

    if detection is not None:
        if ocr_source == _SOURCE_UNSET and detection.paddle_ocr.available:
            ocr_provider = "paddleocr"
            ocr_model = detection.paddle_ocr.identity or ocr_model
            ocr_source = _SOURCE_DETECTED
            if not _env_present("STUDYBUDDY_OCR_ENABLED") and "ocr_enabled" not in stored:
                # Out-of-box enablement: a detected, structurally valid local
                # component turns the capability on without hand-copied env vars.
                ocr_enabled = True
        if ocr_root is None and detection.paddle_ocr.available:
            ocr_root = detection.paddle_ocr.path
        if asr_source == _SOURCE_UNSET and detection.whisper_asr.available:
            asr_provider = "whisper-cpp"
            asr_model = detection.whisper_asr.identity or asr_model
            asr_source = _SOURCE_DETECTED
        if detection.whisper_asr.available:
            if asr_runtime is None:
                asr_runtime = detection.whisper_asr.path
            if asr_model_path is None:
                asr_model_path = detection.whisper_asr.secondary_path

    ai_provider = base.ai_provider_id
    ai_model = base.ai_model_id
    ai_base_url = base.ai_base_url
    ai_api_key = base.ai_api_key
    if not base.demo_mode:
        if not _env_present("STUDYBUDDY_AI_PROVIDER") and stored.get("ai_provider_id"):
            ai_provider = str(stored["ai_provider_id"])
        if not _env_present("STUDYBUDDY_AI_MODEL") and stored.get("ai_model_id"):
            ai_model = str(stored["ai_model_id"])
        if not _env_present("STUDYBUDDY_AI_BASE_URL") and stored.get("ai_base_url"):
            ai_base_url = str(stored["ai_base_url"])
        if not _env_present("STUDYBUDDY_AI_API_KEY") and stored.get("ai_api_key"):
            ai_api_key = str(stored["ai_api_key"])

    embedding_provider = base.embedding_provider_id
    embedding_model = base.embedding_model_id
    embedding_base_url = base.embedding_base_url
    embedding_api_key = base.embedding_api_key
    if not _env_present("STUDYBUDDY_EMBEDDING_PROVIDER") and stored.get("embedding_provider_id"):
        embedding_provider = str(stored["embedding_provider_id"])
    if not _env_present("STUDYBUDDY_EMBEDDING_MODEL") and stored.get("embedding_model_id"):
        embedding_model = str(stored["embedding_model_id"])
    if not _env_present("STUDYBUDDY_EMBEDDING_BASE_URL") and stored.get("embedding_base_url"):
        embedding_base_url = str(stored["embedding_base_url"])
    if not _env_present("STUDYBUDDY_EMBEDDING_API_KEY") and stored.get("embedding_api_key"):
        embedding_api_key = str(stored["embedding_api_key"])

    ocr_enabled_final = ocr_enabled

    delivery_smtp_host = base.report_delivery_smtp_host
    delivery_smtp_port = base.report_delivery_smtp_port
    delivery_smtp_secure = base.report_delivery_smtp_secure
    delivery_smtp_username = base.report_delivery_smtp_username
    delivery_smtp_password = base.report_delivery_smtp_password_runtime
    delivery_smtp_targets = base.report_delivery_smtp_targets
    delivery_feishu_webhook = base.report_delivery_feishu_webhook
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_HOST") and stored.get("report_delivery_smtp_host"):
        delivery_smtp_host = str(stored["report_delivery_smtp_host"])
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_PORT") and stored.get("report_delivery_smtp_port"):
        delivery_smtp_port = int(stored["report_delivery_smtp_port"])
    if (not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_SECURE")
            and "report_delivery_smtp_secure" in stored):
        delivery_smtp_secure = bool(stored["report_delivery_smtp_secure"])
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_USERNAME") and stored.get("report_delivery_smtp_username"):
        delivery_smtp_username = str(stored["report_delivery_smtp_username"])
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_PASSWORD") and stored.get("report_delivery_smtp_password"):
        delivery_smtp_password = str(stored["report_delivery_smtp_password"])
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_SMTP_TARGETS") and stored.get("report_delivery_smtp_targets"):
        delivery_smtp_targets = _parse_delivery_targets(str(stored["report_delivery_smtp_targets"]))
    if not _env_present("STUDYBUDDY_REPORT_DELIVERY_FEISHU_WEBHOOK") and stored.get("report_delivery_feishu_webhook"):
        delivery_feishu_webhook = str(stored["report_delivery_feishu_webhook"])

    return replace(
        base,
        ai_provider_id=ai_provider, ai_model_id=ai_model, ai_base_url=ai_base_url,
        ai_api_key=ai_api_key,
        embedding_provider_id=embedding_provider, embedding_model_id=embedding_model,
        embedding_base_url=embedding_base_url, embedding_api_key=embedding_api_key,
        ocr_provider_id=ocr_provider, ocr_model_id=ocr_model, ocr_model_root=ocr_root,
        ocr_enabled=ocr_enabled_final, ocr_source=ocr_source,
        asr_provider_id=asr_provider, asr_model_id=asr_model,
        asr_runtime_path=asr_runtime, asr_model_path=asr_model_path, asr_source=asr_source,
        report_delivery_smtp_host=delivery_smtp_host,
        report_delivery_smtp_port=delivery_smtp_port,
        report_delivery_smtp_secure=delivery_smtp_secure,
        report_delivery_smtp_username=delivery_smtp_username,
        report_delivery_smtp_password_runtime=delivery_smtp_password,
        report_delivery_smtp_targets=delivery_smtp_targets,
        report_delivery_feishu_webhook=delivery_feishu_webhook,
    )


def _probe_configured_paths(detection: DetectionResult, ocr_root: Path | None,
                            asr_runtime: Path | None, asr_model: Path | None,
                            *, preferred_base: Path | None) -> DetectionResult:
    """Validate explicitly configured component paths against those paths.

    Startup detection scans conventional locations once. A path supplied by the
    operator or through the UI must be probed on its own terms, otherwise a
    mistyped model directory keeps reporting a usable capability while every real
    call fails: the provider validates the directory itself and refuses to build.
    Paths that detection already found are not probed again.
    """
    updated = detection
    if ocr_root is not None and detection.paddle_ocr.path != ocr_root:
        updated = replace(updated, paddle_ocr=detect.detect_paddle_ocr(ocr_root))
    if asr_runtime is not None and detection.whisper_asr.path != asr_runtime:
        updated = replace(updated, whisper_asr=detect.detect_whisper_asr(
            asr_runtime, asr_model, preferred_base=preferred_base))
    return updated


def _parse_delivery_targets(raw: str) -> tuple[tuple[str, str], ...]:
    """Parse a stored `label=target,label=target` string. Bad entries are dropped."""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item or item.count("=") != 1:
            continue
        label, target = (part.strip() for part in item.split("=", 1))
        if not label or not target or label in seen:
            continue
        seen.add(label)
        pairs.append((label, target))
    return tuple(pairs)


def _state(status: str, *, reason: str | None = None, provider_id: str | None = None,
           model_id: str | None = None, source: str | None = None,
           detail: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"status": status, "reason": reason,
                                  "provider_id": provider_id, "model_id": model_id}
    if source is not None:
        payload["source"] = source
    if detail is not None:
        payload.update(detail)
    return payload


def _ocr_state(config: AppConfig, detection: DetectionResult | None) -> dict[str, object]:
    """OCR capability.

    Status order matters: a missing component must report `not_installed` with its
    probe reason, never `disabled`. `disabled` is reserved for a capability that
    could run on this host but was explicitly turned off, so the dashboard never
    hides a missing dependency behind a switch.
    """
    probe = detection.paddle_ocr if detection else None
    if probe is not None and probe.status == STATUS_NOT_INSTALLED:
        return _state(STATUS_NOT_INSTALLED, reason=probe.reason, source=config.ocr_source)
    if probe is not None and not probe.available and config.ocr_model_root is not None:
        # A configured model root that does not validate is a configuration
        # error, not a working capability: the provider refuses to construct.
        return _state(probe.status, reason=probe.reason, source=config.ocr_source)
    usable = bool(config.ocr_provider_id and config.ocr_model_root) or bool(probe and probe.available)
    if not config.ocr_enabled:
        if not usable:
            reason = probe.reason if probe is not None else "ocr_model_root_not_found"
            return _state(STATUS_NOT_CONFIGURED, reason=reason, source=config.ocr_source)
        return _state(STATUS_DISABLED, reason="ocr_disabled_by_configuration",
                      provider_id=config.ocr_provider_id, model_id=config.ocr_model_id,
                      source=config.ocr_source)
    if config.ocr_provider_id and config.ocr_model_root:
        return _state(STATUS_AVAILABLE, provider_id=config.ocr_provider_id,
                      model_id=config.ocr_model_id, source=config.ocr_source)
    reason = probe.reason if probe is not None else "ocr_model_root_not_found"
    return _state(STATUS_NOT_CONFIGURED, reason=reason, source=config.ocr_source)


def _asr_state(config: AppConfig, detection: DetectionResult | None) -> dict[str, object]:
    probe = detection.whisper_asr if detection else None
    if (probe is not None and not probe.available and not config.demo_mode
            and (config.asr_runtime_path is not None or config.asr_model_path is not None)):
        # Same rule as OCR: a configured runtime or model that does not validate
        # must report its probe reason instead of a usable capability.
        return _state(probe.status, reason=probe.reason, source=config.asr_source)
    if config.asr_provider_id and config.asr_runtime_path and config.asr_model_path:
        return _state(STATUS_AVAILABLE, provider_id=config.asr_provider_id,
                      model_id=config.asr_model_id, source=config.asr_source)
    if config.demo_mode:
        return _state(STATUS_AVAILABLE, provider_id="fake", model_id="fake-capture-v1",
                      source="demo")
    reason = probe.reason if probe is not None else "asr_runtime_not_found"
    status = probe.status if probe is not None else STATUS_NOT_CONFIGURED
    if status == STATUS_AVAILABLE:
        status = STATUS_NOT_CONFIGURED
    return _state(status, reason=reason, source=config.asr_source)


def _provider_state(provider_id: str | None, model_id: str | None, api_key: str | None,
                    base_url: str | None) -> dict[str, object]:
    if provider_id is None:
        return _state(STATUS_NOT_CONFIGURED, reason="provider_not_configured")
    if provider_id == "fake":
        return _state(STATUS_AVAILABLE, provider_id=provider_id, model_id=model_id,
                      source="demo")
    if not api_key or not base_url:
        return _state(STATUS_NOT_CONFIGURED, reason="provider_credentials_missing",
                      provider_id=provider_id, model_id=model_id)
    return _state(STATUS_AVAILABLE, provider_id=provider_id, model_id=model_id)


def _index_state(config: AppConfig, embedding: dict[str, object]) -> dict[str, object]:
    """Index capability.

    Chunking and the lexical FTS index need no provider, so retrieval with
    citations works out of the box. Vector and hybrid retrieval fall back to
    deterministic demo embeddings until a real embedding provider is configured;
    that is a degradation and is labeled as one instead of being hidden.
    """
    if embedding["status"] == STATUS_AVAILABLE:
        return embedding
    return _state(STATUS_DEGRADED, reason="embedding_provider_not_configured",
                  provider_id="local", model_id="lexical_fts_v1")


def capability_snapshot(config: AppConfig, detection: DetectionResult | None = None) -> dict[str, object]:
    """Seven capability lights for the dashboard. No paths, no secrets."""
    if detection is not None and config.auto_detect_enabled:
        detection = _probe_configured_paths(detection, config.ocr_model_root,
                                            config.asr_runtime_path, config.asr_model_path,
                                            preferred_base=config.data_root)
    llm = _provider_state(config.ai_provider_id, config.ai_model_id,
                          config.ai_api_key, config.ai_base_url)
    embedding = _provider_state(config.embedding_provider_id, config.embedding_model_id,
                                config.embedding_api_key, config.embedding_base_url)
    if config.embedding_provider_id is None and config.ai_provider_id == "fake":
        embedding = _state(STATUS_AVAILABLE, provider_id="fake", model_id="fake-embedding-v1",
                           source="demo")
    report = _state(STATUS_AVAILABLE, provider_id="local", model_id="deterministic-projection",
                    detail={"delivery_configured": bool(
                        config.report_delivery_smtp_host and config.report_delivery_smtp_username
                        and config.report_delivery_smtp_password_runtime
                        and config.report_delivery_smtp_targets)})
    capabilities = {
        "import_parse": _state(STATUS_AVAILABLE, provider_id="local",
                               model_id="txt+md+pdf+docx+pptx"),
        "ocr": _ocr_state(config, detection),
        "asr": _asr_state(config, detection),
        "index": _index_state(config, embedding),
        "qa": llm,
        "generation": llm,
        "report": report,
    }
    fallback = detection.rapid_ocr if detection else None
    return {
        "capabilities": capabilities,
        "auto_detect_enabled": config.auto_detect_enabled,
        "delivery_mode": config.report_delivery_mode,
        "ocr_fallback_installed": bool(fallback and fallback.available),
        "ready_count": sum(1 for item in capabilities.values() if item["status"] == STATUS_AVAILABLE),
        "degraded_count": sum(1 for item in capabilities.values() if item["status"] == STATUS_DEGRADED),
        "total_count": len(capabilities),
    }
